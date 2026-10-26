"""
KM-HR-Agent - NiceGUI Web-App (Phase 1: Design-System + Pages)
================================================================
Migration von Streamlit zu NiceGUI.

Start:  .venv-streamlit/bin/python3 -m webui.main   (http://localhost:8080)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from nicegui import app, ui

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from webui import db, logic  # noqa: E402
# Theme-Import entfaellt (02.10.2026): inject_css/css-Tokens nutzen die Pages
# direkt (webui/pages/landing.py, webui/pages/login.py) — hier unbenutzt (pyflakes).

# P1-10 (30.09.2026, sicherheitsrelevant, Nutzer-GO): STORAGE_SECRET stand im
# Klartext im Quellcode. Er wird jetzt aus der Umgebung gelesen.
#   KMHR_STORAGE_SECRET   Geheimnis fuer NiceGUI-Session-/Storage-Signierung.
#                         Ohne die Variable startet die App mit dem unten
#                         dokumentierten Default und WARNT — dieser Default ist
#                         fuer Entwicklung ok und fuer den Betrieb NICHT.
# Design-Entscheidung (kein Gesetz/Standard): Name der Variablen, Default-Wert
# und Verhalten bei fehlender Konfiguration.
STORAGE_SECRET_DEFAULT = "km-hr-agent-phase0-secret"
STORAGE_SECRET = os.environ.get("KMHR_STORAGE_SECRET", "").strip() or STORAGE_SECRET_DEFAULT
USING_DEFAULT_SECRET = STORAGE_SECRET == STORAGE_SECRET_DEFAULT

if USING_DEFAULT_SECRET:
    print(
        "[webui] WARNUNG: KMHR_STORAGE_SECRET ist nicht gesetzt — es wird der "
        "Entwicklungs-Default verwendet. Fuer den Betrieb zwingend setzen:\n"
        "         export KMHR_STORAGE_SECRET='<zufaelliges Geheimnis>'",
        file=sys.stderr,
    )

# ─── R3-4 Fail-closed Secrets (30.09.2026, Nutzer-GO „A: Fail-closed,
# KMHR_DEV=1-Override") ────────────────────────────────────────────────
# Gate LIEGT VOR app_bootstrap() (DB-Zugriff) und vor ui.run(): ohne beide
# Pflicht-Variablen wird die App nicht gestartet (SystemExit(1)).
# KMHR_DEV=1 erlaubt den Entwicklungslauf ohne Secrets — dann greift weiterhin
# die Default-Warnung oben (die der Abbruchfall wegen SystemExit nie erreicht).
# Quelle: Nutzer-GO R3-4 (30.09.2026). Env-Name KMHR_DEV und die Override-Werte
# "1/true/yes" sind eine Design-Entscheidung (kein Gesetz/Standard).
# Spec: knowledge/system/configuration-secrets.md (Abschnitt KMHR_DEV).
KMHR_DEV = os.environ.get("KMHR_DEV", "").strip().lower() in ("1", "true", "yes")
# Session-Cookies hinter HTTPS (Cloudflare/Caddy) nur über TLS senden.
# Lokal (HTTP) bleibt das Flag aus, sonst wäre der Login dort cookie-los.
COOKIE_SECURE = os.environ.get("KMHR_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes")
_SESSION_MIDDLEWARE_KWARGS = {"https_only": True} if COOKIE_SECURE else None
_missing = [k for k in ("KMHR_STORAGE_SECRET", "KMHR_ADMIN_SEED_PASSWORD")
            if not os.environ.get(k, "").strip()]
if _missing and not KMHR_DEV:
    print(
        "[webui] ABBRUCH: fehlende Umgebungsvariable(n): " + ", ".join(_missing)
        + "\n         Fail-closed Start (R3-4): ohne KMHR_STORAGE_SECRET und"
        "\n         KMHR_ADMIN_SEED_PASSWORD startet die App nicht."
        + "\n         Entwicklung:  export KMHR_DEV=1   (Default + Warnung, kein Betrieb)"
        + "\n         Betrieb:      export KMHR_STORAGE_SECRET=... "
        "\n         und           export KMHR_ADMIN_SEED_PASSWORD=..."
        + "\n         Details: knowledge/system/configuration-secrets.md",
        file=sys.stderr,
    )
    raise SystemExit(1)

# ─── Boot-Sequenz ────────────────────────────────────────────────────
logic.app_bootstrap()
db.init_notifications_table()
db.init_mentoring_table()  # Phase D P10, User-GO 24.09.2026 (Spec §3C)
db.init_compliance_protokoll_table()  # N-K, 01.10.2026 (Writer + Berichte, application_id)
db.init_password_resets_table()  # Passwort-Reset, 18.10.2026 (Spec configuration-secrets.md §(g))
db.init_candidates_migrations()  # FR-Filter Hiring-Board, 18.10.2026 (Spec employer-board.md)
db.init_consents_table()  # Consent-Nachweise, 26.10.2026 (DSGVO Art. 6/7/9, § 26 BDSG)


# ─── Session Helper ──────────────────────────────────────────────────

def _session() -> dict:
    return app.storage.user


def require_role(page_role: str):
    s = _session()
    role = logic.current_role(s)
    if role == page_role or (role == "admin" and page_role in ("candidate", "employer")):
        return s
    ui.navigate.to("/login")
    return None


def logout_and_go():
    logic.logout_user(_session())
    logic.logout_employer(_session())
    logic.logout_admin(_session())
    ui.navigate.to("/login")


# ─── Register Pages ──────────────────────────────────────────────────
from webui.pages.login import create as create_login
from webui.pages.landing import create as create_landing
from webui.pages.candidate import create as create_candidate
from webui.pages.employer import create as create_employer
from webui.pages.admin import create as create_admin
from webui.pages.not_found import create as create_404
from webui.pages.legal import create as create_legal

create_login()
create_candidate()
create_employer()
create_admin()
create_404()
create_legal()


# ─── Index (Landingpage, Nutzerentscheidung A 02.10.2026) ───────────
# Frueher: `/` leitete nur auf /login um. Jetzt zeigt `/` GAESTEN die
# Landingpage (webui/pages/landing.py, Three.js-Animation, offline);
# eingeloggte Nutzer werden dort wie bisher auf /admin|/employer|/candidate
# umgeleitet (Verhalten unveraendert). Quelle: Nutzer-GO 02.10.2026.

create_landing()


# ─── Catch-all: unknown routes → 404 ────────────────────────────────

@app.exception_handler(404)
async def _handle_404(request, exc):
    from starlette.responses import RedirectResponse
    return RedirectResponse("/404")


# ─── ASGI-Guard: Socket.IO-Client-Abbruch → 400 statt 500 (10.10.2026) ─
# Spec: knowledge/system/asgi-guard.md (engineio-KeyError 'REQUEST_METHOD').
from webui.asgi_guard import SocketioAbortGuard  # noqa: E402

app.add_middleware(SocketioAbortGuard)


# ─── Run ──────────────────────────────────────────────────────────────
# Port per Env KMHR_PORT übersteuerbar (E2E-Isolation 27.09.2026);
# ohne Env weiterhin 8080. DB-Seite: webui/db.py (KMHR_DB_PATH).
# Host per KMHR_HOST: Default 127.0.0.1 (loopback). Öffentlich nur über den
# Reverse-Proxy (Caddy/Cloudflare); 0.0.0.0 muss bewusst gesetzt werden.
ui.run(title="KM-HR-Agent", host=os.environ.get("KMHR_HOST", "127.0.0.1"),
       port=int(os.environ.get("KMHR_PORT", "8080")),
       storage_secret=STORAGE_SECRET,
       session_middleware_kwargs=_SESSION_MIDDLEWARE_KWARGS,
       reload=False, show=False)
