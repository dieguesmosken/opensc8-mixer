# OpenSC8 Mixer - gera a config nativa do PipeWire a partir do config.json
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import subprocess

from . import config as C

PW_CONF_DIR = os.path.join(os.path.expanduser("~"), ".config", "pipewire", "pipewire.conf.d")
PW_CONF_PATH = os.path.join(PW_CONF_DIR, "90-opensc8-mixer.conf")


def _q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _null_sink(name, desc, positions="FL FR"):
    return """    {
      factory = adapter
      args = {
        factory.name = support.null-audio-sink
        node.name = %s
        node.description = %s
        media.class = Audio/Sink
        audio.position = [ %s ]
        monitor.channel-volumes = true
        object.linger = true
        priority.session = 500
        opensc8.managed = true
      }
    }""" % (_q(name), _q(desc), positions)


def _loopback(desc, cap_name, cap_target, play_name, play_target, play_desc,
              cap_is_sink_monitor=True, cap_positions="FL FR", play_positions="FL FR"):
    cap_extra = "stream.capture.sink = true" if cap_is_sink_monitor else ""
    return """    {
      name = libpipewire-module-loopback
      args = {
        node.description = %s
        capture.props = {
          node.name = %s
          target.object = %s
          %s
          audio.position = [ %s ]
          node.dont-fallback = true
          node.dont-reconnect = false
          node.latency = "256/48000"
          opensc8.managed = true
        }
        playback.props = {
          node.name = %s
          node.description = %s
          media.name = %s
          target.object = %s
          audio.position = [ %s ]
          node.dont-fallback = true
          node.dont-reconnect = false
          node.latency = "256/48000"
          opensc8.managed = true
        }
      }
    }""" % (_q(desc), _q(cap_name), _q(cap_target), cap_extra, cap_positions,
            _q(play_name), _q(play_desc), _q(play_desc), _q(play_target), play_positions)


def generate(cfg):
    objs, mods = [], []
    # barramentos fixos (a SC8 pode sumir/voltar sem derrubar os loopbacks)
    objs.append(_null_sink(C.BUS_FOR[C.SC8_CHAT], "OpenSC8 Saída Chat"))
    objs.append(_null_sink(C.BUS_FOR[C.SC8_GAME], "OpenSC8 Saída Game"))
    objs.append(_null_sink(C.MIC_BUS, "OpenSC8 Entrada Mic", positions="MONO"))
    for ch in cfg["channels"]:
        cid, name = ch["id"], ch["name"]
        objs.append(_null_sink(C.sink_name(cid), "OpenSC8 " + name))
        mods.append(_loopback(
            "OpenSC8 %s → Fone" % name,
            C.fone_name(cid) + "_in", C.sink_name(cid),
            C.fone_name(cid), C.BUS_FOR.get(ch.get("output", C.SC8_GAME), C.BUS_FOR[C.SC8_GAME]),
            "OpenSC8 %s → Fone" % name))
        mods.append(_loopback(
            "OpenSC8 %s → Live" % name,
            C.live_name(cid) + "_in", C.sink_name(cid),
            C.live_name(cid), C.STREAM_MIX, "OpenSC8 %s → Live" % name))
    # Mic da SC8 -> mix da live
    mods.append(_loopback(
        "OpenSC8 Mic → Live", C.MIC_LIVE + "_in", C.MIC_BUS,
        C.MIC_LIVE, C.STREAM_MIX, "OpenSC8 Mic → Live",
        cap_is_sink_monitor=True, cap_positions="MONO", play_positions="MONO"))
    # Mix da live: sink interno (os loopbacks de live e do mic tocam aqui)
    objs.append(_null_sink(C.STREAM_MIX, "OpenSC8 Mix da Live"))
    # "SC8 Stream": fonte virtual (null sink com classe Audio/Source/Virtual).
    # Os loopbacks de live e do mic escrevem nas portas de entrada dela; o OBS grava dela.
    objs.append("""    {
      factory = adapter
      args = {
        factory.name = support.null-audio-sink
        node.name = %s
        node.description = "SC8 Stream"
        media.class = Audio/Source/Virtual
        audio.position = [ FL FR ]
        object.linger = true
        priority.session = 100
        opensc8.managed = true
      }
    }""" % _q(C.STREAM_SOURCE))

    return ("# OpenSC8 Mixer - GERADO AUTOMATICAMENTE pelo app; não edite à mão.\n"
            "# Para desfazer: apague este arquivo e reinicie o PipeWire (ou rode rollback.sh).\n"
            "context.objects = [\n%s\n]\n\ncontext.modules = [\n%s\n]\n"
            % ("\n".join(objs), "\n".join(mods)))


def write(cfg):
    os.makedirs(PW_CONF_DIR, exist_ok=True)
    text = generate(cfg)
    try:
        with open(PW_CONF_PATH, encoding="utf-8") as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    tmp = PW_CONF_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, PW_CONF_PATH)
    return True


def restart_pipewire():
    subprocess.run(["systemctl", "--user", "restart",
                    "pipewire", "pipewire-pulse", "wireplumber"], check=False)
