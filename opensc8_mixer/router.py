# OpenSC8 Mixer - roteador (serviço de usuário)
# Move programas novos para o canal certo, mantém o sink padrão em "OpenSC8 Sistema"
# e reaplica volumes quando a SC8 é reconectada.
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import queue
import re
import subprocess
import sys
import threading
import time

from . import config as C
from . import pw

PHYSICAL = {C.SC8_CHAT, C.SC8_GAME}


def log(*a):
    print("[opensc8-router]", *a, flush=True)


class Router:
    def __init__(self):
        self.cfg = C.load()
        self.mtime = self._mtime()
        self.seen = set()
        self.pw_started = time.time()

    def _mtime(self):
        try:
            return os.path.getmtime(C.CONFIG_PATH)
        except OSError:
            return 0

    def reload_if_changed(self):
        m = self._mtime()
        if m != self.mtime:
            self.mtime = m
            self.cfg = C.load()
            log("config recarregada")

    def route(self, objs=None, only_new=True):
        objs = objs if objs is not None else pw.dump()
        streams = pw.app_streams(objs)
        alive = {(s["id"], s["props"].get("object.serial")) for s in streams}
        self.seen &= alive
        pending = False
        for s in streams:
            key = (s["id"], s["props"].get("object.serial"))
            if only_new and key in self.seen:
                continue
            if s["target"] is None:
                # ainda sem link; tenta de novo daqui a pouco
                pending = True
                continue
            self.seen.add(key)
            ch = C.channel_for_app(self.cfg, s["props"])
            if ch:
                want = C.sink_name(ch)
            elif s["target"] in PHYSICAL:
                want = C.sink_name(self.cfg.get("default_channel", "sistema"))
            else:
                continue
            if s["target"] != want:
                ok = pw.move_stream(s["id"], want)
                if not ok:
                    self.seen.discard(key)
                    pending = True
                log("%s (%s) -> %s %s" % (s["label"], s["props"].get("application.process.binary", "?"),
                                          want, "ok" if ok else "FALHOU"))
        return pending

    def setup(self):
        objs = pw.dump()
        ns = pw.nodes(objs)
        if C.SC8_GAME in ns:
            pw.ensure_game_pcm(int(self.cfg.get("sc8_game_pcm", 4096)))
        default = C.sink_name(self.cfg.get("default_channel", "sistema"))
        if default in ns and pw.default_sink() != default:
            pw.set_default_sink(default)
            log("sink padrão ->", default)
        # fonte padrão: se a atual sumiu (ex.: nome antigo da SC8), usa o "SC8 Mic"
        cur_src = pw.default_source()
        if C.SC8_MIC in ns and cur_src not in ns:
            pw.set_default_source(C.SC8_MIC)
            log("fonte padrão ->", C.SC8_MIC)
        # os links fixos ficam a cargo do watchdog() (roda a cada ~2 s)
        pw.apply_volumes(self.cfg, objs)

    def watchdog(self):
        """Mantém os links fixos e detecta saída da SC8 travada."""
        made = pw.ensure_stream_links()
        if made:
            log("%d link(s) fixos (re)criados" % len(made))
            hw = any(x.startswith(("sc8_chat:", "sc8_game:", "sc8_mic:")) for l in made for x in l)
            if (hw and time.time() - self.pw_started > 20
                    and time.time() - getattr(self, "last_auto_restart", 0) > 120):
                # A SC8 foi reconectada com o PipeWire já rodando. Nesse caso o grafo
                # do mic/live às vezes fica parado; reiniciar o PipeWire resolve
                # (1–2 s sem áudio, só na reconexão).
                log("SC8 reconectada; reiniciando o PipeWire para religar tudo")
                self.pw_started = self.last_auto_restart = time.time()
                subprocess.run(["systemctl", "--user", "restart", "pipewire", "pipewire-pulse",
                                "wireplumber"], check=False)
                return
            pw.ensure_game_pcm(int(self.cfg.get("sc8_game_pcm", 4096)))
        stuck = pw.stuck_playback_pcms()
        if not stuck:
            self.stuck_count = 0
            return
        self.stuck_count = getattr(self, "stuck_count", 0) + 1
        if self.stuck_count < 3:  # ~6 s seguidos travado
            return
        self.stuck_count = 0
        self.recoveries = getattr(self, "recoveries", 0) + 1
        if self.recoveries <= 2:
            log("saída travada (%s); reabrindo a SC8" % ",".join(stuck))
            pw.reopen_sc8()
        else:
            if time.time() - getattr(self, "last_auto_restart", 0) < 120:
                return  # já reiniciou há pouco; evita laço
            self.last_auto_restart = self.pw_started = time.time()
            log("saída continua travada; reiniciando o PipeWire")
            subprocess.run(["systemctl", "--user", "restart", "pipewire", "pipewire-pulse",
                            "wireplumber"], check=False)
            self.recoveries = 0

    def run(self):
        self.setup()
        self.route(only_new=False)
        q = queue.Queue()

        def reader():
            while True:
                try:
                    p = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE,
                                         text=True, bufsize=1)
                    q.put("'new' on server (reconectado)")
                    for line in p.stdout:
                        q.put(line.strip())
                except OSError as e:
                    log("pactl subscribe falhou:", e)
                time.sleep(2)  # pipewire-pulse reiniciou; reconecta

        threading.Thread(target=reader, daemon=True).start()
        last_setup = 0
        while True:
            try:
                ev = q.get(timeout=2)
            except queue.Empty:
                self.reload_if_changed()
                self.watchdog()
                continue
            events = [ev]
            time.sleep(0.25)  # agrupa rajadas de eventos
            while not q.empty():
                events.append(q.get_nowait())
            self.reload_if_changed()
            joined = " ".join(events)
            if "(reconectado)" in joined:
                self.pw_started = time.time()
            if (re.search(r"'(new|remove)' on (sink|source|card) #", joined)
                    or "'new' on server" in joined):
                if time.time() - last_setup > 1:
                    time.sleep(0.5)
                    self.setup()
                    last_setup = time.time()
            if "sink-input" in joined:
                for _ in range(10):
                    if not self.route():
                        break
                    time.sleep(0.3)


def main():
    if "--once" in sys.argv:
        r = Router()
        r.setup()
        r.route(only_new=False)
        return
    Router().run()


if __name__ == "__main__":
    main()
