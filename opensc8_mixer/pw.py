# OpenSC8 Mixer - acesso ao PipeWire (via pw-dump / wpctl / pactl / amixer)
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess

from . import config as C


def _run(args, timeout=5):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def dump():
    r = _run(["pw-dump"], timeout=8)
    if not r or r.returncode != 0:
        return []
    try:
        return json.loads(r.stdout)
    except ValueError:
        return []


def nodes(objs=None):
    """{node.name: (id, props, info)} de todos os nós."""
    out = {}
    for o in objs if objs is not None else dump():
        if o.get("type") != "PipeWire:Interface:Node":
            continue
        info = o.get("info") or {}
        props = info.get("props") or {}
        name = props.get("node.name")
        if name:
            out[name] = (o["id"], props, info)
    return out


def node_volume(info):
    """(volume linear 0..1.5, mute) a partir de params.Props."""
    for p in (info.get("params") or {}).get("Props", []):
        if "channelVolumes" in p:
            vols = p["channelVolumes"] or [1.0]
            v = max(vols)
            # wpctl trabalha em escala cúbica
            return round(v ** (1 / 3), 3), bool(p.get("mute", False))
    return 1.0, False


def set_volume(node_id, vol):
    vol = max(0.0, min(1.5, float(vol)))
    _run(["wpctl", "set-volume", str(node_id), "%.3f" % vol])


def set_mute(node_id, mute):
    _run(["wpctl", "set-mute", str(node_id), "1" if mute else "0"])


def app_streams(objs=None):
    """Streams de programas (sink-inputs) que não são do próprio OpenSC8."""
    objs = objs if objs is not None else dump()
    by_id = {o["id"]: o for o in objs}
    ns = nodes(objs)
    id_to_name = {v[0]: k for k, v in ns.items()}
    # destino atual de cada stream, via links
    target = {}
    for o in objs:
        if o.get("type") != "PipeWire:Interface:Link":
            continue
        info = o.get("info") or {}
        target[info.get("output-node-id")] = info.get("input-node-id")
    out = []
    for name, (nid, props, info) in ns.items():
        if props.get("media.class") != "Stream/Output/Audio":
            continue
        if name.startswith("opensc8_") or props.get("opensc8.managed"):
            continue
        out.append({
            "id": nid,
            "name": name,
            "props": props,
            "label": props.get("application.name") or props.get("application.process.binary")
                     or props.get("media.name") or name,
            "media": props.get("media.name", ""),
            "target": id_to_name.get(target.get(nid)),
        })
    return out


def move_stream(stream_id, sink_node_name, tries=3):
    """Move um stream para um sink (por nome) via pactl. Tenta algumas vezes:
    logo que o stream nasce ele pode ainda não aparecer como sink-input."""
    import time
    for i in range(tries):
        if _move_once(stream_id, sink_node_name):
            return True
        time.sleep(0.2)
    return False


def _move_once(stream_id, sink_node_name):
    r = _run(["pactl", "--format=json", "list", "sink-inputs"])
    if not r or r.returncode != 0:
        return False
    try:
        items = json.loads(r.stdout)
    except ValueError:
        return False
    for it in items:
        if str(it.get("properties", {}).get("object.id")) == str(stream_id):
            r2 = _run(["pactl", "move-sink-input", str(it["index"]), sink_node_name])
            return bool(r2 and r2.returncode == 0)
    return False


def set_default_sink(name):
    _run(["pactl", "set-default-sink", name])


def default_sink():
    r = _run(["pactl", "get-default-sink"])
    return r.stdout.strip() if r and r.returncode == 0 else ""


def set_default_source(name):
    _run(["pactl", "set-default-source", name])


def default_source():
    r = _run(["pactl", "get-default-source"])
    return r.stdout.strip() if r and r.returncode == 0 else ""


def sc8_card_name():
    """Nome do card PipeWire da SC8 (vendor 0x3142, product 0x0c88)."""
    r = _run(["pactl", "--format=json", "list", "cards"])
    try:
        for c in json.loads(r.stdout if r else "[]"):
            p = c.get("properties", {})
            if p.get("device.vendor.id") == "0x3142" and p.get("device.product.id") == "0x0c88":
                return c["name"]
    except ValueError:
        pass
    return None


def _alsa_card():
    idx = sc8_card_index()
    return str(idx) if idx is not None else C.SC8_ALSA_CARD


def ensure_game_pcm(value):
    """Garante o volume de hardware da saída Game da SC8 (ALSA numid=9)."""
    card = _alsa_card()
    r = _run(["amixer", "-c", card, "cget", "numid=%d" % C.SC8_GAME_PCM_NUMID])
    if not r or r.returncode != 0:
        return False
    if (": values=%d,%d" % (value, value)) in r.stdout:
        return True
    r = _run(["amixer", "-c", card, "-q", "cset",
              "numid=%d" % C.SC8_GAME_PCM_NUMID, "%d,%d" % (value, value)])
    return bool(r and r.returncode == 0)


def _wanted_links():
    """Links fixos que o OpenSC8 mantém (o WirePlumber não cria estes sozinho)."""
    links = []
    for ch in ("FL", "FR"):
        # mix da live -> fonte virtual "SC8 Stream"
        links.append(("%s:monitor_%s" % (C.STREAM_MIX, ch), "%s:input_%s" % (C.STREAM_SOURCE, ch)))
    for hw, bus in C.BUS_FOR.items():
        # barramento -> saída física (pro-audio usa portas AUX0/AUX1)
        links.append(("%s:monitor_FL" % bus, "%s:playback_AUX0" % hw))
        links.append(("%s:monitor_FR" % bus, "%s:playback_AUX1" % hw))
    links.append(("%s:capture_AUX0" % C.SC8_MIC, "%s:playback_MONO" % C.MIC_BUS))
    return links


def ensure_stream_links():
    """Cria os links fixos que faltarem. Links com --linger sobrevivem ao processo;
    o roteador recria quando a SC8 é reconectada ou o PipeWire reinicia."""
    r = _run(["pw-link", "-l"])
    existing = r.stdout if r and r.returncode == 0 else ""
    r = _run(["pw-link", "-io"])
    ports = set((r.stdout if r else "").split())
    made = []
    for src, dst in _wanted_links():
        if src not in ports or dst not in ports:
            continue  # SC8 desconectada, por exemplo
        if ("%s\n  |<- %s" % (dst, src)) in existing or ("%s\n  |-> %s" % (src, dst)) in existing:
            continue
        r2 = _run(["pw-link", "-L", src, dst])
        if r2 and r2.returncode == 0:
            made.append((src, dst))
    return made


def apply_volumes(cfg, objs=None):
    """Aplica todos os volumes/mutes do config nos nós."""
    ns = nodes(objs)

    def setv(name, vol, mute=None):
        if name in ns:
            set_volume(ns[name][0], vol)
            if mute is not None:
                set_mute(ns[name][0], mute)

    for ch in cfg["channels"]:
        cid = ch["id"]
        setv(C.fone_name(cid), ch["fone"])
        setv(C.live_name(cid), ch["live"])
        setv(C.sink_name(cid), 1.0, ch["mute"])
    for bus in C.BUS_FOR.values():
        setv(bus, cfg["master"], cfg["master_mute"])
    for hw in C.BUS_FOR:  # saídas físicas ficam em 100%; o MASTER age nos barramentos
        setv(hw, 1.0, False)
    setv(C.STREAM_SOURCE, cfg["live_master"])
    setv(C.MIC_LIVE, cfg["mic_live"], cfg["mic_live_mute"])


def sc8_card_index():
    """Índice ALSA da SC8, identificada pelo USB ID 3142:0c88."""
    import glob
    for path in sorted(glob.glob("/proc/asound/card*/usbid")):
        try:
            with open(path) as f:
                if f.read().strip() == C.SC8_USB_ID:
                    return int(path.split("/card")[1].split("/")[0])
        except (OSError, ValueError):
            continue
    return None


def stuck_playback_pcms():
    """PCMs de playback da SC8 abertos mas parados (PREPARED com hw_ptr 0).
    Às vezes, ao abrir as duas saídas ao mesmo tempo, uma delas não inicia."""
    idx = sc8_card_index()
    if idx is None:
        return []
    out = []
    for pcm in ("pcm0p", "pcm1p"):
        try:
            with open("/proc/asound/card%d/%s/sub0/status" % (idx, pcm)) as f:
                st = f.read()
        except OSError:
            continue
        if "state: PREPARED" in st and "hw_ptr      : 0" in st:
            out.append(pcm)
    return out


def reopen_sc8():
    """Reabre o dispositivo: perfil off -> pro-audio."""
    card = sc8_card_name()
    if not card:
        return False
    import time
    _run(["pactl", "set-card-profile", card, "off"])
    time.sleep(1)
    _run(["pactl", "set-card-profile", card, "pro-audio"])
    return True
