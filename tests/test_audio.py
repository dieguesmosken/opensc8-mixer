#!/usr/bin/env python3
# OpenSC8 Mixer - teste de roteamento com tons BAIXOS (-30 dBFS) e curtos.
# Para cada canal: toca um tom no sink "OpenSC8 <canal>" e mede com pw-record
# (a) a fonte "SC8 Stream" (live) e (b) o monitor da saída física (fone).
# Depois zera o slider de live e confere que só o caminho da live caiu, e vice-versa.
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
TONE_DB = -30.0
DUR = 1.6


def make_tone(path, freq=440.0):
    amp = 10 ** (TONE_DB / 20)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        frames = bytearray()
        n = int(RATE * DUR)
        for i in range(n):
            fade = min(1.0, i / 2400, (n - i) / 2400)
            v = int(32767 * amp * fade * math.sin(2 * math.pi * freq * i / RATE))
            frames += struct.pack("<hh", v, v)
        w.writeframes(bytes(frames))


def rms_db(path):
    with open(path, "rb") as f:
        data = f.read()
    n = len(data) // 4
    if n == 0:
        return -200.0
    vals = struct.unpack("<%df" % n, data[: n * 4])
    # descarta o começo/fim (abertura dos streams)
    vals = vals[len(vals) // 4: -len(vals) // 4] or vals
    s = sum(v * v for v in vals) / len(vals)
    return 10 * math.log10(s) if s > 0 else -200.0


def record(target, out, monitor=False):
    args = ["pw-record", "--target", target, "--rate", str(RATE), "--channels", "2",
            "--format", "f32"]
    if monitor:
        args += ["-P", "stream.capture.sink=true"]
    args += ["-P", "node.name=opensc8_test_rec", "-"]
    f = open(out, "wb")
    return subprocess.Popen(args, stdout=f, stderr=subprocess.DEVNULL), f


def measure(sink, tone):
    with tempfile.TemporaryDirectory() as d:
        live_raw, fone_raw = os.path.join(d, "live.raw"), os.path.join(d, "fone.raw")
        ch_out = pw_out_for(sink)
        p1, f1 = record(C.STREAM_SOURCE, live_raw)
        p2, f2 = record(ch_out, fone_raw, monitor=True)
        time.sleep(0.5)
        subprocess.run(["pw-play", "--target", sink, "-P", "node.name=opensc8_test_tone",
                        "-P", "application.name=opensc8-teste", tone],
                       stderr=subprocess.DEVNULL)
        time.sleep(0.3)
        for p, f in ((p1, f1), (p2, f2)):
            p.terminate()
            p.wait()
            f.close()
        return rms_db(live_raw), rms_db(fone_raw)


_cfg = C.load()


def pw_out_for(sink):
    for ch in _cfg["channels"]:
        if C.sink_name(ch["id"]) == sink:
            return ch.get("output", C.SC8_GAME)
    return C.SC8_GAME


def node_id(name):
    ns = pw.nodes()
    return ns[name][0] if name in ns else None


def main():
    results = []
    with tempfile.TemporaryDirectory() as d:
        tone = os.path.join(d, "tone.wav")
        make_tone(tone)
        print("Tom: 440 Hz, %.0f dBFS, %.1f s" % (TONE_DB, DUR))
        mic = node_id(C.MIC_LIVE)
        if mic is not None:
            pw.set_mute(mic, True)  # o ruído de fundo do mic mascararia a medição da live
        for ch in _cfg["channels"]:
            cid = ch["id"]
            sink = C.sink_name(cid)
            fid, lid = node_id(C.fone_name(cid)), node_id(C.live_name(cid))
            # outros canais não devem interferir: mede com volumes do config
            live, fone = measure(sink, tone)
            pw.set_volume(lid, 0.0)
            live0, fone0 = measure(sink, tone)
            pw.set_volume(lid, ch["live"])
            pw.set_volume(fid, 0.0)
            live1, fone1 = measure(sink, tone)
            pw.set_volume(fid, ch["fone"])
            ok = (live > -45 and fone > -45 and live0 < live - 30 and abs(fone0 - fone) < 3
                  and fone1 < fone - 30 and abs(live1 - live) < 3)
            results.append(ok)
            print("%-10s saída=%-8s | normal: live %6.1f dB fone %6.1f dB | live=0: live %6.1f fone %6.1f"
                  " | fone=0: live %6.1f fone %6.1f | %s"
                  % (ch["name"], ch.get("output"), live, fone, live0, fone0, live1, fone1,
                     "OK" if ok else "FALHOU"))
    if mic is not None:
        pw.set_mute(mic, _cfg["mic_live_mute"])
    print("Resultado:", "%d/%d canais OK" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
