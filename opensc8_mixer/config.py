# OpenSC8 Mixer - configuração
# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
import os
import re
import unicodedata

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "opensc8-mixer")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# Nós físicos da SC8 (nomes definidos pela regra do WirePlumber da Fase 0)
SC8_CHAT = "sc8_chat"
SC8_GAME = "sc8_game"
SC8_MIC = "sc8_mic"
SC8_USB_ID = "3142:0c88"          # a SC8 é identificada pelo product ID 0c88
SC8_ALSA_CARD = "Chat"            # nome ALSA padrão (só usado se o USB ID não for achado)
SC8_GAME_PCM_NUMID = 9            # 'PCM Playback Volume',index=1 (saída Game)
STREAM_MIX = "opensc8_stream_mix" # sink interno do mix da live (monitor -> SC8 Stream)
STREAM_SOURCE = "sc8_stream"      # fonte virtual "SC8 Stream" (para o OBS)
MIC_LIVE = "opensc8_mic_live"     # loopback mic -> mix da live
MIC_BUS = "opensc8_mic_bus"       # sink interno que recebe o mic da SC8
# Barramentos de saída: sempre existem, mesmo com a SC8 desconectada.
# O roteador liga o monitor deles às saídas físicas quando a SC8 aparece.
BUS_FOR = {SC8_CHAT: "opensc8_bus_chat", SC8_GAME: "opensc8_bus_game"}

MAX_EXTRA_CHANNELS = 3

DEFAULT_CHANNELS = [
    {"id": "game", "name": "Game", "output": SC8_GAME},
    {"id": "navegador", "name": "Navegador", "output": SC8_GAME},
    {"id": "chat", "name": "Chat", "output": SC8_CHAT},
    {"id": "musica", "name": "Música", "output": SC8_GAME},
    {"id": "sistema", "name": "Sistema", "output": SC8_GAME},
    {"id": "efeitos", "name": "Efeitos", "output": SC8_GAME},  # soundboard
]
BUILTIN_IDS = [c["id"] for c in DEFAULT_CHANNELS]

DEFAULT_RULES = [
    # a ordem importa: a primeira regra que casar vence
    {"match": "steam", "channel": "game"},
    {"match": "gamescope", "channel": "game"},
    {"match": "wine", "channel": "game"},
    {"match": "proton", "channel": "game"},
    {"match": ".exe", "channel": "game"},
    {"match": "discord", "channel": "chat"},
    {"match": "vesktop", "channel": "chat"},
    {"match": "webcord", "channel": "chat"},
    {"match": "spotify", "channel": "musica"},
    {"match": "firefox", "channel": "navegador"},
    {"match": "chrome", "channel": "navegador"},
    {"match": "chromium", "channel": "navegador"},
    {"match": "brave", "channel": "navegador"},
]

DEFAULT_CONFIG = {
    "version": 1,
    "channels": [dict(c, fone=1.0, live=1.0, mute=False) for c in DEFAULT_CHANNELS],
    "rules": DEFAULT_RULES,
    "default_channel": "sistema",
    "master": 1.0,
    "master_mute": False,
    "live_master": 1.0,
    "mic_live": 1.0,
    "mic_live_mute": False,
    "sc8_game_pcm": 4096,
    # soundboard: [{"name": "Aplausos", "file": "/caminho/a.ogg", "volume": 0.8, "hotkey": "F1"}]
    "soundboard": [],
}


def sink_name(channel_id):
    return "opensc8_" + channel_id


def fone_name(channel_id):
    return "opensc8_%s_fone" % channel_id


def live_name(channel_id):
    return "opensc8_%s_live" % channel_id


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s or "canal"


def load():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        save(cfg)
        return cfg
    # completa chaves que faltarem (configs antigas)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, copy.deepcopy(v))
    have = {c["id"] for c in cfg["channels"]}
    for d in DEFAULT_CHANNELS:  # canais embutidos novos (ex.: Efeitos) em configs antigas
        if d["id"] not in have:
            cfg["channels"].append(dict(d, fone=1.0, live=1.0, mute=False))
    for ch in cfg["channels"]:
        ch.setdefault("fone", 1.0)
        ch.setdefault("live", 1.0)
        ch.setdefault("mute", False)
        ch.setdefault("output", SC8_GAME)
    return cfg


def save(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)


def channel_for_app(cfg, props):
    """Retorna o id do canal para um stream, a partir das regras."""
    ids = {c["id"] for c in cfg["channels"]}
    hay = " ".join(
        str(props.get(k, "")) for k in
        ("application.process.binary", "application.name", "application.id")
    ).lower()
    for r in cfg["rules"]:
        m = r.get("match", "").lower()
        if m and m in hay and r.get("channel") in ids:
            return r["channel"]
    return None


def app_key(props):
    """Chave estável para 'lembrar' um programa."""
    return (props.get("application.process.binary")
            or props.get("application.name") or "").lower()


def remember(cfg, props, channel_id):
    key = app_key(props)
    if not key:
        return
    cfg["rules"] = [r for r in cfg["rules"] if r.get("match", "").lower() != key]
    cfg["rules"].insert(0, {"match": key, "channel": channel_id})
