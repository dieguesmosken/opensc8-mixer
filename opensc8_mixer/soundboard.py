# OpenSC8 Mixer - soundboard: toca arquivos no canal virtual "Efeitos"
# (que vai para o fone e para a live, como qualquer outro canal).
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import shutil
import subprocess
import threading
from urllib.parse import quote

from . import config as C

EFEITOS = "efeitos"
_procs = []
_lock = threading.Lock()


def _target():
    return C.sink_name(EFEITOS)


def _start(pad):
    path = os.path.expanduser(pad.get("file", ""))
    if not os.path.isfile(path):
        return None, "arquivo não encontrado: %s" % path
    vol = max(0.0, min(1.5, float(pad.get("volume", 1.0))))
    # -P recebe um objeto SPA-JSON; valores com espaço precisam de aspas
    props = ["-P", "{ application.name = %s media.name = %s opensc8.managed = true }" % (
        json.dumps("OpenSC8 Soundboard"),
        json.dumps(pad.get("name") or os.path.basename(path), ensure_ascii=False))]
    # pw-play (libsndfile: wav, flac, ogg, mp3 a partir do libsndfile 1.1)
    if shutil.which("pw-play"):
        p = subprocess.Popen(["pw-play", "--target", _target(), "--volume", "%.3f" % vol]
                             + props + [path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            p.wait(timeout=0.4)
        except subprocess.TimeoutExpired:
            return p, None  # está tocando
        if p.returncode == 0:
            return None, None  # arquivo curtíssimo, já terminou
    # alternativa: GStreamer (formatos que o libsndfile não abre)
    if shutil.which("gst-launch-1.0"):
        uri = "file://" + quote(os.path.abspath(path))
        p = subprocess.Popen(["gst-launch-1.0", "-q", "playbin", "uri=%s" % uri,
                              "volume=%.3f" % vol,
                              "audio-sink=pulsesink device=%s client-name=\"OpenSC8 Soundboard\""
                              % _target()],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return p, None
    return None, "nenhum player disponível (pw-play/gst-launch-1.0)"


def play(pad):
    """Toca um pad. Retorna (ok, mensagem_de_erro)."""
    p, err = _start(pad)
    if p:
        with _lock:
            _procs[:] = [x for x in _procs if x.poll() is None] + [p]
    return err is None, err


def stop_all():
    with _lock:
        for p in _procs:
            if p.poll() is None:
                p.terminate()
        _procs.clear()


def find_pad(cfg, key):
    """Acha um pad por número (1..N) ou nome."""
    pads = cfg.get("soundboard", [])
    if str(key).isdigit():
        i = int(key) - 1
        return pads[i] if 0 <= i < len(pads) else None
    for pad in pads:
        if pad.get("name", "").lower() == str(key).lower():
            return pad
    return None


def play_blocking(cfg, key):
    pad = find_pad(cfg, key)
    if not pad:
        return False, "pad não encontrado: %s" % key
    p, err = _start(pad)
    if p:
        p.wait()
    return err is None, err
