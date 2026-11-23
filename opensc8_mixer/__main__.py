# OpenSC8 Mixer - ponto de entrada
#   python3 -m opensc8_mixer              abre a janela
#   python3 -m opensc8_mixer --router     roda o roteador (serviço)
#   python3 -m opensc8_mixer --play N     toca o pad N (número ou nome) da soundboard
#   python3 -m opensc8_mixer --apply      regenera a config do PipeWire e reaplica volumes
# SPDX-License-Identifier: GPL-3.0-or-later
import sys


def main():
    args = sys.argv[1:]
    if args[:1] == ["--router"]:
        from . import router
        sys.argv = [sys.argv[0]] + args[1:]
        return router.main()
    if args[:1] == ["--play"] and len(args) > 1:
        from . import config, soundboard
        ok, err = soundboard.play_blocking(config.load(), " ".join(args[1:]))
        if not ok:
            print("Erro:", err, file=sys.stderr)
            return 1
        return 0
    if args[:1] == ["--apply"]:
        import time
        from . import config, pw, pwconf
        cfg = config.load()
        if pwconf.write(cfg):
            print("Config do PipeWire atualizada; reiniciando o PipeWire…")
            pwconf.restart_pipewire()
            time.sleep(3)
        pw.ensure_stream_links()
        pw.apply_volumes(cfg)
        return 0
    from . import app
    return app.main()


if __name__ == "__main__":
    sys.exit(main())
