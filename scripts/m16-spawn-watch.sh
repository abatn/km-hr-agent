#!/usr/bin/env bash
# M-16 Spawn-Watcher (Mess-Helfer, READ-ONLY): protokolliert NEUE Connector-
# Subprozesse waehrend des Messfensters. Beim Start vorhandene Prozesse
# (persistente opencode-MCP-Server) gelten als bekannt und werden nicht
# mitgezaehlt. Log: ergebnisse/m16-spawn-watch.log (eine Zeile je neuem PID).
# Aufruf:  setsid bash scripts/m16-spawn-watch.sh &
# Stopp:   pkill -f "[m]16-spawn-watch.sh"
cd "$(dirname "$0")/.."
LOG="ergebnisse/m16-spawn-watch.log"
: > "$LOG"
declare -A SEEN
for p in $(pgrep -f "[c]onnectors/" 2>/dev/null); do
    SEEN[$p]=1
done
echo "# watcher-start $(date -Iseconds) pre-existing: ${!SEEN[@]}" >> "$LOG"
while true; do
    for p in $(pgrep -f "[c]onnectors/" 2>/dev/null); do
        if [ -z "${SEEN[$p]:-}" ]; then
            SEEN[$p]=1
            echo "$(date +%s.%N) NEW_PID=$p $(ps -o args= -p "$p" 2>/dev/null)" >> "$LOG"
        fi
    done
    sleep 0.25
done
