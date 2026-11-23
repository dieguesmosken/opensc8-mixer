#!/usr/bin/env bash
# OpenSC8 Mixer - instalação por usuário (sem sudo)
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}"
BACKUP="$STATE/opensc8-mixer/backup"
BIN="$HOME/.local/bin"
APPDIR="$DATA/opensc8-mixer"

sc8_card() {  # nome do card PipeWire da SC8, pelo vendor/product ID (3142:0c88)
  pactl --format=json list cards 2>/dev/null | python3 -c 'import json,sys
print(next((c["name"] for c in json.load(sys.stdin) if c["properties"].get("device.vendor.id")=="0x3142" and c["properties"].get("device.product.id")=="0x0c88"),""))'
}
need() { command -v "$1" >/dev/null || { echo "Faltando: $1"; exit 1; }; }
for c in python3 pw-dump pw-link pw-play pw-record wpctl pactl amixer systemctl; do need "$c"; done
python3 -c 'import gi; gi.require_version("Gtk","3.0")' 2>/dev/null \
  || { echo "Faltando PyGObject com GTK 3 (pacote python3-gi + gir1.2-gtk-3.0)."; exit 1; }

if [ -z "$(sc8_card)" ]; then
  echo "Aviso: não encontrei a fifine SC8 conectada. Vou instalar assim mesmo."
fi

# 1) backup do estado atual (só na primeira instalação)
if [ ! -f "$BACKUP/default-sink.txt" ]; then
  echo "Salvando o estado atual do áudio em $BACKUP"
  mkdir -p "$BACKUP"
  pactl get-default-sink > "$BACKUP/default-sink.txt" || true
  pactl get-default-source > "$BACKUP/default-source.txt" || true
  CARD="$(sc8_card)"
  if [ -n "$CARD" ]; then
    pactl --format=json list cards | python3 -c "import json,sys;[print(c['active_profile']) for c in json.load(sys.stdin) if c['name']=='$CARD']" > "$BACKUP/sc8-profile.txt"
  fi
  IDX="$(grep -l '^3142:0c88$' /proc/asound/card*/usbid 2>/dev/null | head -1 | sed 's|.*/card\([0-9]*\)/usbid|\1|')"
  [ -n "$IDX" ] && echo "$IDX" > "$BACKUP/sc8-alsa-card.txt"
  [ -n "$IDX" ] && alsactl -f "$BACKUP/alsactl-chat-before.state" store "$IDX" 2>/dev/null || true
  [ -d "$STATE/wireplumber" ] && cp -a "$STATE/wireplumber" "$BACKUP/wireplumber-state-before"
else
  echo "Backup já existe em $BACKUP (mantido)."
fi

# 2) arquivos do app
echo "Instalando o app em $APPDIR"
mkdir -p "$APPDIR" "$BIN"
rm -rf "$APPDIR/opensc8_mixer"
cp -r "$SRC/opensc8_mixer" "$APPDIR/"
cp "$SRC/rollback.sh" "$SRC/uninstall.sh" "$APPDIR/"
cat > "$BIN/opensc8-mixer" <<EOF
#!/bin/sh
cd "$APPDIR" && exec python3 -m opensc8_mixer "\$@"
EOF
chmod +x "$BIN/opensc8-mixer" "$APPDIR/rollback.sh" "$APPDIR/uninstall.sh"

# 3) Fase 0: perfil pro-audio + nomes "SC8 Chat/Game/Mic" (WirePlumber)
mkdir -p "$CFG/wireplumber/wireplumber.conf.d"
cp "$SRC/data/wireplumber/90-opensc8-mixer.conf" "$CFG/wireplumber/wireplumber.conf.d/90-opensc8-mixer.conf"

# 4) atalho no menu e serviço do roteador
mkdir -p "$DATA/applications" "$CFG/systemd/user"
sed "s|@BIN@|$BIN|g" "$SRC/data/io.github.opensc8.Mixer.desktop" > "$DATA/applications/io.github.opensc8.Mixer.desktop"
sed "s|@BIN@|$BIN|g" "$SRC/data/systemd/opensc8-router.service" > "$CFG/systemd/user/opensc8-router.service"

# 5) gera a config do PipeWire, reinicia o áudio e liga o roteador
systemctl --user restart wireplumber
sleep 2
CARD="$(sc8_card)"
[ -n "$CARD" ] && pactl set-card-profile "$CARD" pro-audio || true
"$BIN/opensc8-mixer" --apply
systemctl --user daemon-reload
systemctl --user enable opensc8-router.service
systemctl --user restart opensc8-router.service

echo
echo "OpenSC8 Mixer instalado."
echo "  Abrir:        opensc8-mixer   (ou pelo menu: OpenSC8 Mixer)"
echo "  OBS:          adicione 'Captura de entrada de áudio' -> 'SC8 Stream'"
echo "  Desfazer:     $APPDIR/rollback.sh  (volta o áudio)  |  $APPDIR/uninstall.sh (remove tudo)"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "  Obs.: $BIN não está no PATH; use $BIN/opensc8-mixer";; esac
