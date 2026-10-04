"""P1-9 (30.09.2026): Compliance-Seite zeigt nicht mehr den global letzten Eintrag.

BEFUND: `_page_compliance` las `... ORDER BY id DESC LIMIT 1` aus
`compliance_protokoll` — ohne jeden Bezug zum angemeldeten Arbeitgeber. Ein
Eintrag einer fremden Bewerbung konnte so als eigenes Compliance-Ergebnis
erscheinen.

BEFUND 2: `compliance_protokoll` hat keinen Fremdschluessel und wird im Projekt
nirgends geschrieben (grep ueber alle .py: 0 Writer). Die vorhandenen Zeilen
tragen Legacy-Freitext, z. B. 'anna-schuster-devops-2026'.

FIX: `_compliance_rows(conn, employer_id)` zurechnet nur Eintraege im Schema
`employer-job-<job_id>-cand-<cand_id>-<datum>` und prueft die job_id gegen die
eigenen Stellen. Legacy-Zeilen werden als nicht zurechenbar gezaehlt und NICHT
angezeigt.
"""
import sqlite3
from pathlib import Path

import pytest

from webui.pages.employer import _compliance_rows

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = ROOT / "data" / "feedback.db"


@pytest.fixture
def db():
    """In-Memory-Nachbau des relevanten Teilschemas (Live-DB bleibt unberuehrt)."""
    c = sqlite3.connect(":memory:")
    c.executescript(
        """
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, employer_id INTEGER, titel TEXT);
        CREATE TABLE compliance_protokoll (
            id INTEGER PRIMARY KEY, match_id TEXT, land TEXT, pruefpunkt TEXT,
            status TEXT, details TEXT, datum TEXT);
        INSERT INTO jobs (id, employer_id, titel) VALUES
            (10, 1, 'Stelle A'),   -- Arbeitgeber 1
            (11, 1, 'Stelle B'),   -- Arbeitgeber 1
            (20, 2, 'Stelle C');   -- Arbeitgeber 2
        """
    )
    return c


def _add(c, mid, status="COMPLIANT"):
    c.execute("INSERT INTO compliance_protokoll (match_id, land, pruefpunkt, status, "
              "details, datum) VALUES (?, 'DE', 'Aufenthalt', ?, 'd', '2026-09-10')",
              (mid, status))
    c.commit()


# ─── Arbeitgeber-Isolation: das eigentliche Problem ────────────────────────

def test_fremder_eintrag_wird_nicht_angezeigt(db):
    """Arbeitgeber 1 sieht nicht den Eintrag von Arbeitgeber 2."""
    _add(db, "employer-job-20-cand-99-2026-09-10")
    zugeordnet, nicht_zurechenbar = _compliance_rows(db, 1)
    assert zugeordnet == []
    assert nicht_zurechenbar == 0, "match_id IST zurechenbar (job 20 -> AG 2), also kein Legacy"


def test_je_arbeitgeber_nur_seine_eigenen(db):
    _add(db, "employer-job-10-cand-5-2026-09-10")
    _add(db, "employer-job-20-cand-6-2026-09-10")
    ag1, _ = _compliance_rows(db, 1)
    ag2, _ = _compliance_rows(db, 2)
    assert [r["cand_id"] for r in ag1] == [5]
    assert [r["cand_id"] for r in ag2] == [6]


def test_job_id_zu_fremder_stelle_verschafft_keinen_zutritt(db):
    """match_id zeigt auf eine Stelle, die einem ANDEREN Arbeitgeber gehoert."""
    _add(db, "employer-job-20-cand-7-2026-09-10")
    assert _compliance_rows(db, 1)[0] == []
    assert len(_compliance_rows(db, 2)[0]) == 1


# ─── Legacy-Zeilen: ehrlich leer statt fremde Daten ────────────────────────

@pytest.mark.parametrize("mid", [
    "anna-schuster-devops-2026",
    "employer-job-10-cand-5",                    # ohne Datum
    "employer-job-10-cand-5-2026-9-10",          # falsches Datumsformat
    "job-10-cand-5-2026-09-10",                  # falsches Praefix
    "employer-job-abc-cand-5-2026-09-10",        # nicht-numerische job_id
    "",
])
def test_legacy_match_id_wird_nicht_gezeigt(db, mid):
    _add(db, mid)
    zugeordnet, nicht_zurechenbar = _compliance_rows(db, 1)
    assert zugeordnet == [], f"{mid!r} wurde faelschlich zugeordnet"
    assert nicht_zurechenbar == 1


def test_gemischte_lage_wird_richtig_aufgeteilt(db):
    _add(db, "employer-job-10-cand-5-2026-09-10")   # zuordenbar, AG 1
    _add(db, "employer-job-20-cand-6-2026-09-10")   # zuordenbar, AG 2
    _add(db, "anna-schuster-devops-2026")            # Legacy
    zugeordnet, nicht_zurechenbar = _compliance_rows(db, 1)
    assert [r["cand_id"] for r in zugeordnet] == [5]
    assert nicht_zurechenbar == 1


def test_reihenfolge_neueste_zuerst(db):
    for i, cid in enumerate([1, 2, 3]):
        _add(db, f"employer-job-10-cand-{cid}-2026-09-1{i}")
    zugeordnet, _ = _compliance_rows(db, 1)
    assert [r["cand_id"] for r in zugeordnet] == [3, 2, 1], "ORDER BY id DESC"


def test_leere_tabelle(db):
    assert _compliance_rows(db, 1) == ([], 0)


# ─── Ist-Zustand der Live-DB (read-only, nur zur Einordnung) ───────────────

def test_live_db_alle_zeilen_legacy():
    c = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    try:
        zugeordnet, nicht_zurechenbar = _compliance_rows(c, 1)
    finally:
        c.close()
    assert nicht_zurechenbar > 0, "Live-DB hat Legacy-Zeilen ohne Arbeitgeber-Bezug"
    assert zugeordnet == [], "in der Live-DB ist aktuell nichts zurechenbar"
