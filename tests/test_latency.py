#!/usr/bin/env python3
# OpenSC8 Mixer - latência extra dos caminhos virtuais (aproximada).
# Grava ao mesmo tempo o monitor do canal (entrada) e (a) o monitor da saída física
# (caminho do fone) e (b) a fonte "SC8 Stream" (caminho da live); compara o início
# de um bip curto e baixo (-30 dBFS). Não mede a latência do hardware USB.
# SPDX-License-Identifier: GPL-3.0-or-later
import math
import os
import struct
import subprocess
import sys
import tempfile
import time
import wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from opensc8_mixer import config as C, pw  # noqa: E402

RATE = 48000


def beep(path):
    amp = 10 ** (-30 / 20)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        fr = bytearray()
        for i in range(int(RATE * 0.6)):
            v = int(32767 * amp * math.sin(2 * math.pi * 1000 * i / RATE)) if i > RATE * 0.2 else 0
            fr += struct.pack("<hh", v, v)
        w.writeframes(bytes(fr))


def onsets(path, thr=10 ** (-45 / 20)):
    w = wave.open(path)
    d = w.readframes(w.getnframes())
    v = struct.unpack("<%dh" % (len(d) // 2), d)
    res = []
    for c in (0, 1):
        res.append(next((i // 2 for i in range(c, len(v), 2) if abs(v[i]) / 32768 > thr), None))
    return res


def measure(src_port, dst_port, sink):
    """Um único gravador estéreo: L = entrada do canal, R = saída do caminho."""
    with tempfile.TemporaryDirectory() as d:
        b, f = os.path.join(d, "b.wav"), os.path.join(d, "r.wav")
        beep(b)
        rec = subprocess.Popen(["pw-record", "-P", "{ node.autoconnect = false node.name = opensc8_lat_rec }",
                                "--channels", "2", "--rate", str(RATE), f],
                               stderr=subprocess.DEVNULL)
        time.sleep(0.6)
        subprocess.run(["pw-link", src_port, "opensc8_lat_rec:input_FL"], stderr=subprocess.DEVNULL)
        subprocess.run(["pw-link", dst_port, "opensc8_lat_rec:input_FR"], stderr=subprocess.DEVNULL)
        time.sleep(0.4)
        subprocess.run(["pw-play", "--target", sink, b], stderr=subprocess.DEVNULL)
        time.sleep(0.4)
        rec.terminate()
        rec.wait()
        a, z = onsets(f)
    if a is None or z is None:
        return None
    return (z - a) * 1000.0 / RATE


def main(channel="game"):
    sink = C.sink_name(channel)
    out = next((c.get("output", C.SC8_GAME) for c in C.load()["channels"] if c["id"] == channel),
               C.SC8_GAME)
    ns = pw.nodes()
    mic = ns.get(C.MIC_LIVE, [None])[0]
    if mic:
        pw.set_mute(mic, True)
    try:
        fone = measure(sink + ":monitor_FL", out + ":monitor_AUX0", sink)
        live = measure(sink + ":monitor_FL", C.STREAM_SOURCE + ":capture_FL", sink)
    finally:
        if mic:
            pw.set_mute(mic, C.load()["mic_live_mute"])
    fmt = lambda x: "falhou" if x is None else "%.1f ms" % x  # noqa: E731
    print("Canal %s: latência extra até o fone (antes do USB) = %s; até o SC8 Stream = %s"
          % (channel, fmt(fone), fmt(live)))
    print("(Fora isso, o hardware USB da SC8 soma a latência normal do PipeWire/ALSA.)")
    return fone, live


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "game")
