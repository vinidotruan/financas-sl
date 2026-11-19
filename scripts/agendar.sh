#!/bin/bash
# Agenda "slf diario" todo dia às 06:10 no launchd do macOS.
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
UV="$(command -v uv)"
PLIST="$HOME/Library/LaunchAgents/br.financas-sl.diario.plist"
mkdir -p "$PROJ/data/logs" "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>br.financas-sl.diario</string>
  <key>ProgramArguments</key><array>
    <string>$UV</string><string>run</string><string>--project</string><string>$PROJ</string>
    <string>slf</string><string>diario</string>
  </array>
  <key>WorkingDirectory</key><string>$PROJ</string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>10</integer></dict>
  <key>StandardOutPath</key><string>$PROJ/data/logs/diario.log</string>
  <key>StandardErrorPath</key><string>$PROJ/data/logs/diario.log</string>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Agendado: todo dia às 06:10. Log em $PROJ/data/logs/diario.log"
echo "Pra rodar agora: launchctl kickstart gui/$(id -u)/br.financas-sl.diario"
echo "Pra remover: launchctl bootout gui/$(id -u) $PLIST && rm $PLIST"
