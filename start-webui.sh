#!/usr/bin/env bash
# KM-HR-Agent – NiceGUI Web-UI Starter
# Start:  ./start-webui.sh          → http://localhost:8080
# Stop:   pkill -f "python3 -m webui.main"   (oder das systemd-Unit)
#
# R6-2.2 (30.09.2026, Nutzer-GO "Ja: .env statt KMHR_DEV-Default"):
#   * KMHR_DEV wird NICHT mehr automatisch gesetzt (frueher: KMHR_DEV=1 als
#     Default → die Live-App lief mit bekanntem Session-Secret).
#   * Secrets kommen aus einer .env-Datei (Vorlage: .env.example). Pfad per
#     KMHR_ENV_FILE uebersteuerbar (Tests). .env ist in .gitignore (".env*").
#   * Fehlen KMHR_STORAGE_SECRET / KMHR_ADMIN_SEED_PASSWORD und ist KMHR_DEV
#     nicht ausdruecklich gesetzt, verweigert der Starter den Start (rc=1);
#     webui/main.py bricht zusaetzlich selbst ab (R3-4, fail-closed).
#   * Entwicklung ohne Secrets: bewusst `KMHR_DEV=1 ./start-webui.sh`.
#   * Host: Default 127.0.0.1 (loopback). Für LAN bewusst KMHR_HOST=0.0.0.0 setzen;
#     öffentlich nur über den Reverse-Proxy (Caddy/Cloudflare).
# Spec: knowledge/system/configuration-secrets.md (Abschnitt (f)).
cd "$(dirname "$0")" || exit 1
source .venv-streamlit/bin/activate

ENV_FILE="${KMHR_ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

_dev="$(printf '%s' "${KMHR_DEV:-}" | tr '[:upper:]' '[:lower:]')"
case "$_dev" in 1|true|yes) _dev=1 ;; *) _dev= ;; esac

if [ -z "$_dev" ]; then
  _missing=""
  [ -z "${KMHR_STORAGE_SECRET:-}" ] && _missing="$_missing KMHR_STORAGE_SECRET"
  [ -z "${KMHR_ADMIN_SEED_PASSWORD:-}" ] && _missing="$_missing KMHR_ADMIN_SEED_PASSWORD"
  if [ -n "$_missing" ]; then
    echo "[start-webui] ABBRUCH: fehlende Variable(n):$_missing" >&2
    echo "  Lege '$ENV_FILE' an (Vorlage: .env.example, chmod 600) oder starte" >&2
    echo "  bewusst mit Entwicklungs-Override:  KMHR_DEV=1 ./start-webui.sh" >&2
    echo "  Details: knowledge/system/configuration-secrets.md" >&2
    exit 1
  fi
fi
# PID-Datei (data/webui.pid): nur der Live-Start pflegt sie — isolierte
# Test-/E2E-Instanzen setzen KMHR_DB_PATH und schreiben NICHT (kein Clobbern
# der Live-PID). Die PID wird beim Start geschrieben; ein Waechter entfernt sie,
# sobald der App-Prozess endet (exec erhaelt die PID → MAIN == App-PID) — auch
# nach SIGKILL. Stop: pkill -f "python3 -m webui.main".
if [ -z "${KMHR_DB_PATH:-}" ]; then
  mkdir -p data
  MAIN=$$
  echo "$MAIN" > data/webui.pid
  ( while kill -0 "$MAIN" 2>/dev/null; do sleep 1; done; rm -f data/webui.pid ) &
fi
exec python3 -m webui.main
