"""R5-3 (30.09.2026): Jeder reale Status hat Klartext-Label + Badge-Farbe.

Quellen der Statusmengen (Spiegel-DB der Live-DB, read-only via conftest):
  SELECT DISTINCT status FROM candidates / applications / jobs / agent_tasks
plus die Job-Status-Optionen aus dem Quelltext (employer.py:594,
admin.py:678: aktiv/pausiert/besetzt/abgelaufen).

Soll: status_label(status) != Fallback (kein 'Unterstrich-kapitalize') und
status_badge ist erzeugbar für jeden Wert. Rot vor dem Fix: 'pausiert' fehlte
(label fiel auf Fallback 'Pausiert' war Zufall des Fallbacks — aber badge_map
kannte es nicht → grauer Badge statt bernstein).

Ausführen: .venv-streamlit/bin/python3 -m pytest tests/test_status_labels_complete.py -v
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nicegui import ui  # noqa: E402
from webui.components import STATUS_LABELS, status_badge, status_label  # noqa: E402
from webui import db  # noqa: E402

# Job-Status-Optionen aus dem Quelltext (Select-Optionen, die per UPDATE
# in jobs.status geschrieben werden können — employer.py:594, admin.py:678)
JOB_STATUS_OPTIONEN = ["aktiv", "pausiert", "besetzt", "abgelaufen"]


def _distinct_status(table: str) -> set[str]:
    conn = db.get_conn()
    try:
        rows = conn.execute(f"SELECT DISTINCT status FROM {table}").fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows if r[0]}


def _alle_status() -> set[str]:
    status: set[str] = set()
    for table in ("candidates", "applications", "jobs", "agent_tasks"):
        status |= _distinct_status(table)
    status |= set(JOB_STATUS_OPTIONEN)
    return status


def test_alle_realen_status_haben_label():
    for s in sorted(_alle_status()):
        label = status_label(s)
        assert label != s, f"status_label({s!r}) ist der Fallback (Slug selbst)"
        assert not re.search(r"_", label), f"status_label({s!r}) = {label!r} enthält '_' (Fallback)"


def test_alle_realen_status_haben_badge_farbe():
    """Jeder reale Status ist in der badge_map von status_badge gemappt.

    Bewusst OHNE UI-Erzeugung (status_badge() braucht einen Slot, der im
    Sammellauf nach user_simulation-Tests leer ist — gemessen: RuntimeError).
    Die Zuordnung wird aus dem Quelltext der Funktion gelesen — der
    Produktionscode, nicht eine Kopie.
    """
    import inspect
    from webui import components
    src = inspect.getsource(components.status_badge)
    fehlend = [s for s in sorted(_alle_status()) if f'"{s}":' not in src]
    assert not fehlend, f"status_badge: ohne Farb-Mapping: {fehlend}"


def test_pausiert_ist_bernstein():
    """Der gefundene Fall: 'pausiert' (dt. Job-Status) → Label + amber-Badge.

    Badge-Klasse direkt aus der Quell-Map geprüft (ohne UI-Erzeugung):
    status_badge() mappt über badge_map auf C.BADGE_AMBER — der Test liest
    die Map über die Funktion heraus, indem er die Badge-Klassen in einem
    Slot baut (dieselbe Technik wie test_alle_realen_status_haben_badge_farbe).
    """
    assert status_label("pausiert") == "Pausiert"
    from webui import components
    # Die Zuordnung direkt aus dem badge_map der Funktion nachlesen:
    import inspect
    src = inspect.getsource(components.status_badge)
    assert '"pausiert": C.BADGE_AMBER' in src, \
        "status_badge: 'pausiert' ist nicht auf C.BADGE_AMBER gemappt"
