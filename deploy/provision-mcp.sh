#!/usr/bin/env bash
# Idempotentes Provisioning der MCP-Laufzeit auf einem Server (Contabo).
#
# Hintergrund (31.10.2026): Die 14 MCP-Server aus `opencode.json` brauchen
# Node/npx (playwright, filesystem, mcp-remote), uv/uvx (fetch), fastmcp im
# System-Python (Connectoren rufen `python3` auf) und einen Pfad-Symlink, weil
# `opencode.json` absolute Pfade des Entwicklerrechners enthaelt.
#
# Das Skript aendert NICHTS an versionierten Dateien. Es ist idempotent:
# vorhandene Komponenten werden erkannt und uebersprungen.
#
# Aufruf:  bash deploy/provision-mcp.sh
#          REPO_ROOT=/opt/km-hr-agent bash deploy/provision-mcp.sh
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/km-hr-agent}"
SYMLINK_DIR="/home/batnini/mimo-agents"
SYMLINK="${SYMLINK_DIR}/km-hr-agent"
FASTMCP_VERSION="4.0.11"
MCP_VERSION="2.3.0"

log() { echo "[provision-mcp] $*"; }

# ── 1) Python-Pip sicherstellen ────────────────────────────────────────
if ! python3 -m pip --version >/dev/null 2>&1; then
    log "pip fehlt -> installiere python3-pip"
    apt-get update -qq
    apt-get install -y -qq python3-pip >/dev/null
fi

# ── 2) Node + npx ──────────────────────────────────────────────────────
if command -v node >/dev/null 2>&1 && command -v npx >/dev/null 2>&1; then
    log "node vorhanden: $(node -v), npm $(npm -v)"
else
    log "node/npx fehlt -> installiere Node 22 (NodeSource)"
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null
    apt-get install -y -qq nodejs >/dev/null
    log "node installiert: $(node -v), npm $(npm -v)"
fi

# ── 3) uv + uvx ────────────────────────────────────────────────────────
if command -v uv >/dev/null 2>&1 && command -v uvx >/dev/null 2>&1; then
    log "uv vorhanden: $(uv --version)"
else
    log "uv/uvx fehlt -> installiere"
    python3 -m pip install --break-system-packages -q uv
    log "uv installiert: $(uv --version)"
fi

# ── 4) Python-Pakete fuer die Connectoren ──────────────────────────────
if python3 -c "import fastmcp, mcp, requests" >/dev/null 2>&1; then
    log "fastmcp/mcp/requests vorhanden"
else
    log "fastmcp/mcp/requests fehlen -> installiere"
    # Ubuntu 24.04: typing_extensions ist Debian-verwaltet und laesst sich
    # nicht deinstallieren -> --ignore-installed.
    python3 -m pip install --break-system-packages --ignore-installed typing_extensions -q \
        "fastmcp==${FASTMCP_VERSION}" "mcp==${MCP_VERSION}" requests
    python3 -c "import fastmcp; print('[provision-mcp] fastmcp', fastmcp.__version__)"
fi

# ── 5) Pfad-Symlink fuer die absoluten opencode.json-Pfade ─────────────
mkdir -p "${SYMLINK_DIR}"
if [ -e "${SYMLINK}" ] || [ -L "${SYMLINK}" ]; then
    log "Symlink vorhanden: ${SYMLINK} -> $(readlink -f "${SYMLINK}")"
else
    ln -s "${REPO_ROOT}" "${SYMLINK}"
    log "Symlink angelegt: ${SYMLINK} -> ${REPO_ROOT}"
fi

# ── 6) .venv-pdf (liegt im Repo, wird von `git clean -fd` entfernt) ────
if [ ! -e "${REPO_ROOT}/.venv-pdf" ]; then
    ln -s .venv-streamlit "${REPO_ROOT}/.venv-pdf"
    log ".venv-pdf -> .venv-streamlit verknuepft"
else
    log ".venv-pdf vorhanden"
fi

log "fertig"
