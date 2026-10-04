#!/bin/bash
set -u
cd /home/batnini/mimo-agents/km-hr-agent
LOG=/tmp/opencode/recruiter-20260928
pkill -f "[w]ebui.main" 2>/dev/null; sleep 2
setsid .venv-streamlit/bin/python -m webui.main > "$LOG/server.log" 2>&1 &
for i in $(seq 1 40); do
  c=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8080/login || true)
  [ "$c" = "200" ] && break; sleep 3
done
echo "bereit"
.venv-streamlit/bin/python /tmp/opencode/recruiter-20260928/debug_row3.py > /tmp/opencode/recruiter-20260928/dbg3.log 2>&1 | tail -8
pkill -f "[w]ebui.main" 2>/dev/null
