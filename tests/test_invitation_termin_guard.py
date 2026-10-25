"""Terminprüfung Datum+Uhrzeit in create_invitation (22.10.2026, Auftrag:
„Die Uhrzeit gegen die aktuelle Zeit prüfen; liegt der Termin in der
Vergangenheit, nichts versenden, Grund loggen“).

Vorfall (Bewerbung #42, 22.10.2026): Der create_invitation-Task wartete 63 min
in der Queue; die Einladung für den Termin 11:00 ging um 11:16 raus. Der Runner
prüfte nur das DATUM, nicht die Uhrzeit, und verschickte den bereits begonnenen
Termin ohne Warnung.

Isolation: Temp-DB (candidates/jobs/applications), mcp_call +
mcp_connector_call gemockt (KEIN MCP-Server, KEIN Netz), ERGEBNISSE auf
tmp_path, Zeit über eine fixe Uhr im Runner-Modul (keine Flakes um Mitternacht).
"""
import importlib.util
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "agent-runner.py"


def _load_runner():
    """Runner per importlib laden (Muster tests/test_compliance_writer.py)."""
    spec = importlib.util.spec_from_file_location("agent_runner_termin_unit", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tmp_db(tmp_path) -> Path:
    p = tmp_path / "termin-guard.db"
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE candidates (id INTEGER PRIMARY KEY, email TEXT, name TEXT)")
    conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, titel TEXT)")
    conn.execute("CREATE TABLE applications (id INTEGER PRIMARY KEY, candidate_id INTEGER, job_id INTEGER)")
    conn.execute("INSERT INTO candidates VALUES (13,'kandidat@example.org','taoufik')")
    conn.execute("INSERT INTO jobs VALUES (13,'Électricien / Technicien en mécatronique')")
    conn.execute("INSERT INTO applications VALUES (42,13,13)")
    conn.commit()
    conn.close()
    return p


class _Aufrufe:
    """mcp_call-Double: protokolliert jeden Aufruf, liefert Tool-typische Werte."""

    def __init__(self):
        self.calls: list = []

    def __call__(self, server, tool, params=None):
        self.calls.append((server, tool, params or {}))
        if tool == "generate_screening_questions":
            return "Frage 1\nFrage 2"
        if tool == "generate_ics_file":
            return "BEGIN:VCALENDAR\nEND:VCALENDAR"
        if tool == "send_pre_screen_invitation":
            return "OK|Gesendet an kandidat@example.org"
        return ""

    def tools(self):
        return [t for _s, t, _p in self.calls]


def _setup(mod, tmp_path, monkeypatch, jetzt: datetime):
    """Temp-DB + isolierte Ergebnis-Ablage + fixe Uhr im Runner-Modul."""
    monkeypatch.setattr(mod, "DB_PATH", _tmp_db(tmp_path))
    erg = tmp_path / "erg"
    erg.mkdir()
    monkeypatch.setattr(mod, "ERGEBNISSE", erg)

    class _Uhr:
        @staticmethod
        def now():
            return jetzt

        strptime = staticmethod(datetime.strptime)

    monkeypatch.setattr(mod, "datetime", _Uhr)
    aufrufe = _Aufrufe()
    monkeypatch.setattr(mod, "mcp_call", aufrufe)
    monkeypatch.setattr(mod, "mcp_connector_call", lambda *a, **k: {})
    return aufrufe


def _payload(datum: str | None, uhrzeit: str | None, dauer: int = 15) -> dict:
    p = {"application_id": 42, "candidate_id": 13, "job_id": 13,
         "trigger": "hr_klick_portal", "language": "de"}
    if datum is not None:
        p["termin_datum"] = datum
    if uhrzeit is not None:
        p["termin_uhrzeit"] = uhrzeit
    if datum is not None or uhrzeit is not None:
        p["termin_dauer_min"] = dauer
    return p


# ─── 1) Termin heute, Uhrzeit bereits begonnen (Vorfall-Form) ──────────────

def test_vergangene_uhrzeit_heute_wird_nicht_versendet(tmp_path, monkeypatch, capsys):
    """Vorfall #42: Auftrag um 11:16, Termin 11:00 — nichts versenden."""
    mod = _load_runner()
    aufrufe = _setup(mod, tmp_path, monkeypatch, datetime(2026, 10, 22, 11, 16))

    with pytest.raises(RuntimeError, match="Vergangenheit"):
        mod.create_invitation(_payload("2026-10-22", "11:00", 15))

    out = capsys.readouterr().out
    assert "liegt in der Vergangenheit" in out, f"Grund fehlt im Log: {out!r}"
    assert "NICHT versendet" in out
    assert aufrufe.tools() == [], f"trotzdem versendet: {aufrufe.tools()}"


def test_termin_minutoechnisch_grenze_wird_nicht_versendet(tmp_path, monkeypatch):
    """Termin = Jetzt-Minus-Eine-Minute -> abgebrochen (Grenze: nur < , nicht <=)."""
    mod = _load_runner()
    aufrufe = _setup(mod, tmp_path, monkeypatch, datetime(2026, 10, 22, 11, 16))

    with pytest.raises(RuntimeError, match="Vergangenheit"):
        mod.create_invitation(_payload("2026-10-22", "11:15", 15))

    assert aufrufe.tools() == []


# ─── 2) Vergangenes Datum (frueher: Fallback morgen + senden) ──────────────

def test_vergangenes_datum_wird_nicht_versendet(tmp_path, monkeypatch, capsys):
    """Verhaltensaenderung 22.10.2026: gestern + gueltige Uhrzeit ist KEIN
    Ersatztermin mehr, sondern Abbruch (vorher: Fallback morgen 10:00)."""
    mod = _load_runner()
    aufrufe = _setup(mod, tmp_path, monkeypatch, datetime(2026, 10, 22, 11, 16))

    with pytest.raises(RuntimeError, match="Vergangenheit"):
        mod.create_invitation(_payload("2026-10-21", "10:00", 15))

    out = capsys.readouterr().out
    assert "liegt in der Vergangenheit" in out
    assert aufrufe.tools() == [], f"trotzdem versendet: {aufrufe.tools()}"


# ─── 3) Regressionsfall: zukuenftiger Termin geht normal raus ──────────────

def test_zukuenftiger_termin_wird_versendet(tmp_path, monkeypatch):
    mod = _load_runner()
    aufrufe = _setup(mod, tmp_path, monkeypatch, datetime(2026, 10, 22, 11, 16))

    res = mod.create_invitation(_payload("2026-10-23", "10:30", 15))

    assert "send_pre_screen_invitation" in aufrufe.tools()
    assert aufrufe.tools().count("generate_ics_file") == 2, "Kandidaten- + HR-ICS erwartet"
    assert "2026-10-23 10:30" in res["termin"], res["termin"]
    assert res["mail"].startswith("OK|")
    # Termin im Mail-Parameter identisch zum HR-Termin
    mail_params = [p for _s, t, p in aufrufe.calls if t == "send_pre_screen_invitation"]
    assert mail_params[0]["date"] == "2026-10-23"
    assert mail_params[0]["time"] == "10:30"


def test_termin_gerade_jetzt_ist_noch_gueltig(tmp_path, monkeypatch):
    """Grenze: Termin = Jetzt -> nicht in der Vergangenheit (nur < bricht ab)."""
    mod = _load_runner()
    aufrufe = _setup(mod, tmp_path, monkeypatch, datetime(2026, 10, 22, 11, 16))

    res = mod.create_invitation(_payload("2026-10-22", "11:16", 15))

    assert "send_pre_screen_invitation" in aufrufe.tools()
    assert "2026-10-22 11:16" in res["termin"]


# ─── 4) Legacy-Pfade bleiben unveraendert ──────────────────────────────────

def test_ungueltiges_datum_faellt_auf_morgen_zurueck(tmp_path, monkeypatch):
    """Ungueltige HR-Eingabe -> Fallback morgen 10:00, Versand laeuft (Altverhalten)."""
    mod = _load_runner()
    aufrufe = _setup(mod, tmp_path, monkeypatch, datetime(2026, 10, 22, 11, 16))

    res = mod.create_invitation(_payload("Quatsch", "10:00", 15))

    assert "2026-10-23 10:00" in res["termin"], res["termin"]
    assert "send_pre_screen_invitation" in aufrufe.tools()


def test_ohne_hr_termin_sendet_mit_fallback(tmp_path, monkeypatch):
    """Alt-Task ohne termin_* (Variante A aus frueherer Phase): sendet wie bisher."""
    mod = _load_runner()
    aufrufe = _setup(mod, tmp_path, monkeypatch, datetime(2026, 10, 22, 11, 16))

    res = mod.create_invitation(_payload(None, None))

    assert "2026-10-23 10:00" in res["termin"], res["termin"]
    assert "send_pre_screen_invitation" in aufrufe.tools()


# ─── 5) Quelltext-Guard: die Pruefung darf nicht wieder verschwinden ───────

def test_quelltext_enthaelt_terminpruefung():
    src = RUNNER.read_text(encoding="utf-8")
    assert "if _hr_datum_ok:" in src
    assert "_termin_dt < datetime.now()" in src
    assert "Einladung nicht versendet (neuen Termin setzen)" in src
