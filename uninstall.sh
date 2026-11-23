#!/usr/bin/env bash
# OpenSC8 Mixer - desinstalação (sem sudo). Volta o áudio e remove os arquivos do app.
# Mantém ~/.config/opensc8-mixer/config.json, a não ser que você passe --purge.
# SPDX-License-Identifier: GPL-3.0-or-later
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}"

# 1) volta o áudio ao estado anterior
if [ -x "$HERE/rollback.sh" ]; then
  "$HERE/rollback.sh"
elif [ -x "$DATA/opensc8-mixer/rollback.sh" ]; then
  "$DATA/opensc8-mixer/rollback.sh"
fi

# 2) remove serviço, atalho e app
rm -f "$CFG/systemd/user/opensc8-router.service"
systemctl --user daemon-reload 2>/dev/null || true
rm -f "$DATA/applications/io.github.opensc8.Mixer.desktop"
rm -f "$HOME/.local/bin/opensc8-mixer"
rm -rf "$DATA/opensc8-mixer"

if [ "${1:-}" = "--purge" ]; then
  rm -rf "$CFG/opensc8-mixer" "$STATE/opensc8-mixer"
  echo "Config e backup removidos."
else
  echo "Config mantida em $CFG/opensc8-mixer (use --purge para apagar)."
fi
echo "OpenSC8 Mixer removido."
