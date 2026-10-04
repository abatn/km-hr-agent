"""Isolierte, ASGI-instrumentierte Instanz der KM-HR-Web-UI.

Zweck (Diagnose 01.10.2026): Jeder ASGI-Vorgang wird mit Client-IP/Port,
Pfad, Methode und ERSTEM Receive-Event protokolliert, um die Absender der
abgebrochenen `/_nicegui_ws/socket.io/`-Anfragen (KeyError
'REQUEST_METHOD') zu identifizieren – mit Rohdaten statt Vermutung.

Isolation (Vorbild tests/e2e_isolation.py, 27.09.2026):
  * KMHR_PORT        eigener Port (Default 8123, nie 8080)
  * KMHR_DB_PATH     Spiegel-DB (Pflicht – kein Zugriff auf data/feedback.db)
  * KMHR_RUNNER_AUTOSTART=0   kein zweiter Agent-Runner
  * KMHR_DEV=1       R3-4-Fail-closed-Gate (Entwicklungs-Override)
  * NICEGUI_STORAGE_PATH      Session-Dateien liegen im Trace-Ordner,
                              nicht in .nicegui/ des Live-Betriebs

Aufruf (aus dem Repo-Root):
  KMHR_DB_PATH=/tmp/opencode/asgi-trace-<ts>/mirror.db \
  KMHR_TRACE_DIR=/tmp/opencode/asgi-trace-<ts> \
  .venv-streamlit/bin/python3 scripts/asgi_trace_run.py

Wichtig: KEINE Aenderung an Produktionscode – die Middleware wird per
Patches auf `nicegui.ui.run` VOR dem uvicorn-Start eingehängt
(`nicegui.app.add_middleware`), solange der Starlette-Middleware-Stack
noch nicht gebaut ist.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TRACE_DIR = Path(os.environ.get("KMHR_TRACE_DIR")
                 or "/tmp/opencode/asgi-trace")
TRACE_DIR.mkdir(parents=True, exist_ok=True)

# ── Isolation-Defaults (nur setzen, wenn nicht ohnehin vorgegeben) ─────
os.environ.setdefault("KMHR_PORT", "8123")
os.environ.setdefault("KMHR_RUNNER_AUTOSTART", "0")
os.environ.setdefault("KMHR_DEV", "1")
os.environ.setdefault("NICEGUI_STORAGE_PATH", str(TRACE_DIR / ".nicegui"))

db_path = os.environ.get("KMHR_DB_PATH", "").strip()
if not db_path:
    sys.exit("[asgi-trace] ABBRUCH: KMHR_DB_PATH fehlt – isolierte Instanz "
             "braucht eine Spiegel-DB (nie data/feedback.db).")
if Path(db_path).resolve() == (ROOT / "data" / "feedback.db").resolve():
    sys.exit("[asgi-trace] ABBRUCH: KMHR_DB_PATH zeigt auf die Live-DB.")

from scripts.asgi_trace import TraceMiddleware, TraceWriter  # noqa: E402

writer = TraceWriter(TRACE_DIR / "trace.jsonl", TRACE_DIR / "trace.log")

from nicegui import app as nice_app  # noqa: E402
from nicegui import ui as nice_ui  # noqa: E402

_orig_run = nice_ui.run


def _traced_run(*args, **kwargs):
    # Add-Middleware ist nur erlaubt, solange der Stack noch nicht gebaut
    # ist (starlette/applications.py:105) – hier also VOR uvicorn-Start.
    nice_app.add_middleware(TraceMiddleware, writer=writer)
    print(f"[asgi-trace] Middleware aktiv | JSONL={writer.jsonl}")
    sys.stdout.flush()
    return _orig_run(*args, **kwargs)


nice_ui.run = _traced_run

print(f"[asgi-trace] isolierte Instanz: port={os.environ['KMHR_PORT']} "
      f"db={db_path}")
print(f"[asgi-trace] trace.log={TRACE_DIR / 'trace.log'} "
      f"storage={os.environ['NICEGUI_STORAGE_PATH']}")
sys.stdout.flush()

import webui.main  # noqa: E402,F401  (registriert Pages + startet ui.run)
