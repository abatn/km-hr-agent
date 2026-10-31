#!/usr/bin/env bash
# Ein-Befehl-Lauf der gesamten Job-Akquise.
#
#   ./run_all.sh              # Standard: Suche + Belege + Kontakte + Entwürfe + Skills
#   ./run_all.sh --quick      # kleiner Lauf (wenige Stellen) für Tests
#   JOBS_ENRICH=1 ./run_all.sh  # zusätzlich Impressum-/Kontakt-Recherche
#
# Es wird NIE eine E-Mail versendet. Der Versand ist ein separater, bewusster
# Schritt (`scripts/jobs_mail.py --send --yes`), damit UWG §7 gewahrt bleibt.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv-streamlit/bin/python3"
DATUM="$(date +%Y-%m-%d)"
LOG="$ROOT/logs/jobs-agent-$DATUM.log"
mkdir -p "$ROOT/logs" "$ROOT/jobs/belege" "$ROOT/jobs/outbox"

# .env-runner laden (FT-Credentials, NVIDIA etc.) — nur KEY=VALUE, keine Ausgabe
if [ -f "$ROOT/.env-runner" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$ROOT/.env-runner"
    set +a
fi

QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

if [ "$QUICK" = "1" ]; then
    DE=2; CH=1; EU=2; LHR=1; JDP=1
else
    DE="${JOBS_DE:-12}"; CH="${JOBS_CH:-8}"; EU="${JOBS_EURES:-12}"
    LHR="${JOBS_LHR:-6}"; JDP="${JOBS_JDP:-4}"
fi

log() { echo "[$(date +%H:%M:%S)] $*"; }
run() { log "START $*"; "$@"; log "OK    $*"; }
# Adapter duerfen "nichts gefunden" (rc=2) melden, ohne den Gesamtlauf zu stoppen.
run_tolerant() {
    log "START $*"
    set +e
    "$@"
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ]; then
        log "OK    $* (rc=$rc)"
    else
        log "FEHLER $* (rc=$rc)"
        exit "$rc"
    fi
}

{
    log "Job-Akquise-Lauf $DATUM (quick=$QUICK)"
    log "Python: $($PY --version 2>&1)"

    run_tolerant "$PY" scripts/jobs_api.py   --max-jobs "$DE"  --min-jobs 1
    run_tolerant "$PY" scripts/jobs_ch.py    --max-jobs "$CH"  --min-jobs 1
    run_tolerant "$PY" scripts/jobs_eures.py --max-jobs "$EU"  --min-jobs 1 --per-quota 2
    run_tolerant "$PY" scripts/jobs_lhr.py   --max-jobs "$LHR" --min-jobs 1 --min-score 30
    run_tolerant "$PY" scripts/jobs_jdp.py   --max-jobs "$JDP" --min-jobs 1 --min-score 30

    # Empfängerliste + Entwürfe (Phase 1: aus Belegen)
    run "$PY" scripts/jobs_recipients.py

    # Kontakt-Recherche (optional, Netzlast): Impressum/Kontaktseiten
    if [ "${JOBS_ENRICH:-0}" = "1" ]; then
        run "$PY" scripts/jobs_enrich.py
    else
        log "SKIP  jobs_enrich.py (JOBS_ENRICH=1 aktiviert die Recherche)"
    fi
    # Entwürfe/Formularnachrichten aus der (ggf. angereicherten) Liste neu bauen
    run "$PY" scripts/jobs_recipients.py --prepare-only

    # Skill-Lattice: Induktion, Transfer, Form-Designer
    run "$PY" scripts/jobs_induce.py induce
    run "$PY" scripts/jobs_induce.py transfer
    run "$PY" scripts/jobs_induce.py forms

    BELEGE=$(find "$ROOT/jobs/belege" -name 'index.md' | wc -l)
    ENTWUERFE=$(find "$ROOT/jobs/outbox/final" -name '*.eml' 2>/dev/null | wc -l)
    EMPF=$(($(wc -l < "$ROOT/jobs/empfaenger_final.csv" 2>/dev/null || echo 1) - 1))
    log "FERTIG. Beleg-Tabellen: $BELEGE, Entwuerfe: $ENTWUERFE, Empfaenger: $EMPF"
} 2>&1 | tee -a "$LOG"

# Log-Rotation: nur die letzten 14 Tageslogs behalten
find "$ROOT/logs" -maxdepth 1 -name 'jobs-agent-*.log' -mtime +14 -delete 2>/dev/null || true
log "Log: $LOG"
