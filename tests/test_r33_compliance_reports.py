"""R3-3 (Runde 3, Nutzer-GO „A"): Compliance-Seite liest die echten
check_compliance-Berichte aus ergebnisse/.

Zu pruefen (pytest = Schreib-Nachweis ueber den Spiegel aus tests/conftest.py;
diese Datei selbst schreibt NUR nach tmp_path, nie in die Live-DB):
  1. read-only Vorab-Zaehlung: 18 Dateien, Schema (Dateiname/Titel/Status)
  2. Werteverteilung: 16x COMPLIANT, 2x NICHT_COMPLIANT
  3. Attribution: employer 1 -> alle zugeordenbar, employer 999 -> 0
  4. jobs -> employer_id gegen die (Spiegel-)DB
  5. Nicht-zuordenbar-Fall: Stelle #999 existiert nicht (tmp_path-Ordner)
  6. Sortierung: juengste zuerst

Ausfuehren: .venv-streamlit/bin/python3 -m pytest -q tests/test_r33_compliance_reports.py
"""
from __future__ import annotations

import re
from pathlib import Path

from webui import db
from webui.pages.employer import _compliance_berichte, _compliance_status

ROOT = Path(__file__).resolve().parents[1]
ERG = ROOT / "ergebnisse"
GLOB = "check_compliance-kandidat-*.md"
FILE_RE = re.compile(r"^check_compliance-kandidat-(\d+)-(\d{4}-\d{2}-\d{2})\.md$")

# read-only Vorab-Befund (01.10.2026, R6-5 Datenstand-Refresh): 18 Dateien,
# 16 COMPLIANT / 2 NICHT_COMPLIANT — Zuwachs geg. 30.09.: neu
# check_compliance-kandidat-20-2026-09-30.md (Phase-5-Agent-Task live am
# 30.09.2026 14:20, COMPLIANT, Stelle #6 = Arbeitgeber 1, Kandidat 20 mit
# Klarnamen — Quelle: read-only ls+grep ergebnisse/check_compliance-*.md)
ERWARTET_DATEIEN = 18
ERWARTET_COMPLIANT = 16
ERWARTET_NICHT = 2


def _files() -> list:
    return sorted(ERG.glob(GLOB))


def test_dateien_18_vorhanden():
    files = _files()
    assert len(files) == ERWARTET_DATEIEN, f"{len(files)} Dateien statt 18"


def test_schema_der_18_dateien():
    """Jede Datei: Dateiname-Schema, Titelzeile mit Stelle #, Status + Begruendung."""
    compliant = nicht = 0
    for f in _files():
        m = FILE_RE.match(f.name)
        assert m, f"Dateiname bricht Schema: {f.name}"
        text = f.read_text(encoding="utf-8", errors="replace")
        titel = next((z for z in text.splitlines() if z.startswith("# ")), "")
        assert titel.startswith("# Check Compliance"), f"Titel fehlt: {f.name}"
        assert re.search(r"Stelle #\d+", titel), f"keine Stelle # in: {f.name} ({titel!r})"
        status, begr = _compliance_status(text)
        assert status in ("COMPLIANT", "NICHT_COMPLIANT"), f"{f.name}: status={status!r}"
        assert begr, f"{f.name}: keine Begruendung geparsed"
        if status == "COMPLIANT":
            compliant += 1
        else:
            nicht += 1
    assert compliant == ERWARTET_COMPLIANT, compliant
    assert nicht == ERWARTET_NICHT, nicht


def test_parser_sonstige_status_leer():
    """Ohne 'Compliance-Status:'-Zeile -> ("", "") (defensiv, kein Crash)."""
    assert _compliance_status("# Titel\n\nirgendwas\n") == ("", "")


def test_attribution_employer_1_alle_18():
    berichte = _compliance_berichte(1)
    assert len(berichte) == ERWARTET_DATEIEN, len(berichte)
    assert all(b["zugeordenbar"] for b in berichte), \
        [b["datei"] for b in berichte if not b["zugeordenbar"]]
    for b in berichte:
        assert b["kandidat_name"]
        assert b["job_titel"]
        assert b["datum"] and b["status"]


def test_attribution_employer_999_null():
    berichte = _compliance_berichte(999)
    assert len(berichte) == ERWARTET_DATEIEN, len(berichte)
    assert not any(b["zugeordenbar"] for b in berichte), \
        "fremder Arbeitgeber darf keine Berichte zugeordnet bekommen"


def test_jobs_zuordnung_gegen_db():
    """job_id aus den Berichten -> jobs.employer_id (Spiegel-DB, read-only)."""
    berichte = _compliance_berichte(1)
    conn = db.get_conn()
    try:
        jobs = dict(conn.execute("SELECT id, employer_id FROM jobs").fetchall())
    finally:
        conn.close()
    job_ids = {b["job_id"] for b in berichte}
    assert job_ids, "keine job_id geparsed"
    for jid in job_ids:
        assert jobs.get(jid) == 1, f"Stelle {jid}: employer_id={jobs.get(jid)} != 1"


def test_nicht_zuordenbar_fall(tmp_path):
    """Stelle #999 existiert nicht -> Zaehlung ehrlich, Anzeige geblockt."""
    (tmp_path / "check_compliance-kandidat-1-2026-01-01.md").write_text(
        "# Check Compliance – Kandidat #1 / Stelle #999\n\n"
        "Compliance-Status: COMPLIANT\nBegründung: Synthetischer Testfall.\n",
        encoding="utf-8")
    (tmp_path / "check_compliance-kandidat-2-2026-01-02.md").write_text(
        "# Check Compliance – Kandidat #2 / Stelle #1\n\n"
        "Compliance-Status: NICHT_COMPLIANT\nBegründung: Synthetischer Testfall 2.\n",
        encoding="utf-8")
    berichte = _compliance_berichte(1, ordner=tmp_path)
    assert len(berichte) == 2
    zuordenbar = [b for b in berichte if b["zugeordenbar"]]
    offen = [b for b in berichte if not b["zugeordenbar"]]
    assert len(zuordenbar) == 1 and zuordenbar[0]["job_id"] == 1
    assert len(offen) == 1 and offen[0]["job_id"] == 999
    assert offen[0]["job_titel"] == "Stelle #999"
    # juengste zuerst
    assert berichte[0]["datum"] == "2026-01-02"
    assert berichte[0]["status"] == "NICHT_COMPLIANT"


def test_sortierung_juengste_zuerst():
    berichte = _compliance_berichte(1)
    datume = [b["datum"] for b in berichte]
    assert datume == sorted(datume, reverse=True), datume
    assert datume[0] == "2026-09-30", datume[0]
