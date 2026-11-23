#!/usr/bin/env bash
# OpenSC8 Mixer - rollback: desfaz tudo e volta o áudio ao estado salvo pelo install.sh
# (perfil da SC8, sink/fonte padrão, volumes ALSA, estado do WirePlumber).
# Não usa sudo.
# SPDX-License-Identifier: GPL-3.0-or-later
set -u
BACKUP="${XDG_STATE_HOME:-$HOME/.local/state}/opensc8-mixer/backup"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}"
sc8_card() {  # nome do card PipeWire da SC8, pelo vendor/product ID (3142:0c88)
  pactl --format=json list cards 2>/dev/null | python3 -c 'import json,sys
print(next((c["name"] for c in json.load(sys.stdin) if c["properties"].get("device.vendor.id")=="0x3142" and c["properties"].get("device.product.id")=="0x0c88"),""))'
}

echo "[1/6] Parando o roteador"
systemctl --user disable --now opensc8-router.service 2>/dev/null || true
pkill -f '^python3 -m opensc8_mixer' 2>/dev/null || true

echo "[2/6] Removendo configs do PipeWire/WirePlumber geradas pelo OpenSC8"
rm -f "$CFG/pipewire/pipewire.conf.d/90-opensc8-mixer.conf"
rm -f "$CFG/wireplumber/wireplumber.conf.d/90-opensc8-mixer.conf"

echo "[3/6] Restaurando o estado do WirePlumber"
WPSTATE="${XDG_STATE_HOME:-$HOME/.local/state}/wireplumber"
if [ -d "$BACKUP/wireplumber-state-before" ]; then
  rm -rf "$WPSTATE"
  cp -a "$BACKUP/wireplumber-state-before" "$WPSTATE"
else
  echo "    (sem backup do WirePlumber; mantendo o atual)"
fi

echo "[4/6] Reiniciando PipeWire/WirePlumber"
systemctl --user restart pipewire pipewire-pulse wireplumber
sleep 3

echo "[5/6] Restaurando perfil da SC8 e dispositivos padrão"
CARD="$(sc8_card)"
if [ -n "$CARD" ]; then
  PROFILE="$(cat "$BACKUP/sc8-profile.txt" 2>/dev/null || echo 'output:analog-stereo+input:mono-fallback')"
  pactl set-card-profile "$CARD" "$PROFILE" || true
  sleep 1
fi
[ -f "$BACKUP/default-sink.txt" ] && pactl set-default-sink "$(cat "$BACKUP/default-sink.txt")" || true
[ -f "$BACKUP/default-source.txt" ] && pactl set-default-source "$(cat "$BACKUP/default-source.txt")" || true

echo "[6/6] Restaurando volumes ALSA da SC8"
if [ -f "$BACKUP/alsactl-chat-before.state" ]; then
  IDX="$(grep -l '^3142:0c88$' /proc/asound/card*/usbid 2>/dev/null | head -1 | sed 's|.*/card\([0-9]*\)/usbid|\1|')"
  if [ -n "$IDX" ]; then
    alsactl -f "$BACKUP/alsactl-chat-before.state" restore "$IDX" 2>/dev/null || echo "    (alsactl falhou; volumes ALSA não restaurados)"
  fi
fi

echo "Pronto. Áudio voltou ao estado anterior ao OpenSC8 Mixer."
echo "(O app continua instalado; para removê-lo rode uninstall.sh.)"
