#!/bin/bash
# Nachweis-Lauf: Server starten, E2E + Messung ausfuehren, Server beenden.
# Alles in EINEM Prozess — der Tool-Runner beendet Hintergrundprozesse
# nach jedem Aufruf, deshalb Start und Pruefung hier zusammen.
set -u
cd /home/batnini/mimo-agents/km-hr-agent
LOG=/tmp/opencode/recruiter-20260928
mkdir -p "$LOG"

pkill -f "[w]ebui.main" 2>/dev/null
sleep 2
setsid .venv-streamlit/bin/python -m webui.main > "$LOG/server.log" 2>&1 &
SRV=$!

ready=0
for i in $(seq 1 40); do
  c=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8080/login || true)
  if [ "$c" = "200" ]; then ready=1; break; fi
  sleep 3
done
if [ "$ready" != "1" ]; then
  echo "SERVER NICHT STARTBAR"; tail -20 "$LOG/server.log"; exit 1
fi
echo "Server bereit (PID $SRV)"

echo "=== E2E-Kette (beide Rollen) ==="
.venv-streamlit/bin/python tests/e2e_ui_p0_p1.py 2>&1 | tail -45
E2E_RC=${PIPESTATUS[0]}

echo "=== Messung NACHHER ==="
.venv-streamlit/bin/python tests/ui_measure.py nachher ergebnisse/reports/screenshots/nachher 2>&1 | head -20

echo "=== Stabilitaet nach dem Lauf ==="
curl -s -o /dev/null -w "login=%{http_code}\n" --max-time 5 http://localhost:8080/login || true

pkill -f "[w]ebui.main" 2>/dev/null
echo "E2E-Exitcode: $E2E_RC"
