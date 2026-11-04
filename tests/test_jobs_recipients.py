"""Empfängerliste: Quellen-Mapping, Priorisierung, Mock-Ausschluss."""
from __future__ import annotations

import importlib.util
import pytest
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec_agent = importlib.util.spec_from_file_location("jobs_agent", SCRIPTS / "jobs_agent.py")
_agent = importlib.util.module_from_spec(_spec_agent)
sys.modules["jobs_agent"] = _agent
_spec_agent.loader.exec_module(_agent)

_spec = importlib.util.spec_from_file_location("jobs_recipients", SCRIPTS / "jobs_recipients.py")
rec = importlib.util.module_from_spec(_spec)
sys.modules["jobs_recipients"] = rec
_spec.loader.exec_module(rec)


def test_quellen_mapping():
    assert rec._quelle(Path("x/2026-10-31-eures-fr/index.md")) == "EURES"
    assert rec._quelle(Path("x/2026-10-31-lhr/index.md")) == "LHR"
    assert rec._quelle(Path("x/2026-10-31-jdp/index.md")) == "Journal des Palaces"
    assert rec._quelle(Path("x/2026-10-31-ch/index.md")) == "Job-Room"
    assert rec._quelle(Path("x/2026-10-31/index.md")) == "Bundesagentur"


def test_sammle_liefert_priorisierte_zeilen():
    rows = rec.sammle()
    if not rows:
        pytest.skip("keine Belege im Checkout (gitignored)")
    assert len(rows) >= 20
    for r in rows:
        assert r["prioritaet"] in (1, 2)
        if r["prioritaet"] == 1:
            assert "@" in r["email"]
        else:
            assert r["email"] == ""


def test_keine_mock_eintraege():
    rows = rec.sammle()
    assert not any(r["arbeitgeber"].upper().startswith("MOCK") for r in rows)
    assert not any("mock" in r["email"].lower() for r in rows if r["email"])


def test_dedupe_pro_arbeitgeber_und_mail():
    rows = rec.sammle()
    keys = [(r["arbeitgeber"].lower(), r["email"]) for r in rows]
    assert len(keys) == len(set(keys))


def test_csv_hat_kopfzeile(tmp_path, monkeypatch):
    ziel = tmp_path / "emp.csv"
    monkeypatch.setattr(rec, "CSV", ziel)
    rec.schreibe_csv(rec.sammle())
    kopf = ziel.read_text(encoding="utf-8").splitlines()[0]
    assert kopf.startswith("prioritaet,arbeitgeber,stelle")


# ── Outbox-Lebensdauer + Kontaktsperre ─────────────────────────────────

ZEILE = {
    "prioritaet": 1, "arbeitgeber": "Permacon GmbH", "stelle": "Pflegefachkraft (m/w/d)",
    "ort": "Berlin", "land": "DE", "branche": "Krankenpflege",
    "email": "gerrit.maronde@permacon.de", "quelle": "Bundesagentur",
    "kontaktweg": "E-Mail",
    "url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1003940671-S",
}


def _outbox(tmp_path, monkeypatch):
    out = tmp_path / "final"
    out.mkdir()
    monkeypatch.setattr(rec, "OUTBOX", out)
    monkeypatch.setattr(rec, "SPERRE", tmp_path / "ansprache.jsonl")
    return out


def test_backup_verschiebt_entwuerfe_und_laesst_logs(tmp_path, monkeypatch):
    out = _outbox(tmp_path, monkeypatch)
    (out / "de-alt.eml").write_text("To: a@b.de\nSubject: alt\n\nAbmelden\n", encoding="utf-8")
    (out / "versand-080501.md").write_text("# Versand\n", encoding="utf-8")

    ziel = rec.backup_outbox()

    assert ziel is not None and ziel.is_dir()
    assert list(ziel.glob("*.eml"))
    assert not list(out.glob("*.eml"))
    assert (out / "versand-080501.md").exists()


def test_backup_ohne_entwuerfe_legt_keinen_ordner_an(tmp_path, monkeypatch):
    _outbox(tmp_path, monkeypatch)
    assert rec.backup_outbox() is None
    assert not list(tmp_path.glob("backup-*"))


def test_rotation_loescht_nur_alte_backups(tmp_path, monkeypatch):
    import os
    _outbox(tmp_path, monkeypatch)
    alt = tmp_path / "backup-20261001-060000"
    neu = tmp_path / "backup-20261104-060000"
    for d in (alt, neu):
        d.mkdir()
        (d / "x.eml").write_text("To: a@b.de\n\nAbmelden\n", encoding="utf-8")
    os.utime(alt, (0, 0))

    entfernt = rec.rotate_backups(max_age=rec.BACKUP_MAX_AGE)

    assert entfernt == [alt.name]
    assert not alt.exists()
    assert neu.exists()


def test_vollauf_leert_outbox_und_schreibt_header(tmp_path, monkeypatch):
    out = _outbox(tmp_path, monkeypatch)
    (out / "de-uralt.eml").write_text("To: x@y.de\nSubject: alt\n\nAbmelden\n", encoding="utf-8")

    n = rec.schreibe_entwuerfe([dict(ZEILE)], prepare=False)

    assert n == 1
    assert not (out / "de-uralt.eml").exists()
    texte = [p.read_text(encoding="utf-8") for p in out.glob("*.eml")]
    assert len(texte) == 1
    assert "X-KMHR-Firma: Permacon GmbH" in texte[0]
    assert "X-KMHR-Keys: id:10001-1003940671-S" in texte[0]


def test_prepare_laesst_backup_und_outbox_unangetastet(tmp_path, monkeypatch):
    out = _outbox(tmp_path, monkeypatch)
    (out / "de-uralt.eml").write_text("To: x@y.de\nSubject: alt\n\nAbmelden\n", encoding="utf-8")

    n = rec.schreibe_entwuerfe([dict(ZEILE)], prepare=True)

    assert n == 1
    assert (out / "de-uralt.eml").exists()
    assert not list(tmp_path.glob("backup-*"))
    assert len(list(out.glob("*.eml"))) == 2


def test_gesperrte_firma_anzeige_erzeugt_keinen_entwurf(tmp_path, monkeypatch):
    import json
    out = _outbox(tmp_path, monkeypatch)
    keys = rec.jk.anzeige_keys(ZEILE["url"], ZEILE["arbeitgeber"], ZEILE["stelle"])
    rec.SPERRE.write_text(
        json.dumps({"firma": ZEILE["arbeitgeber"], "keys": keys}) + "\n", encoding="utf-8")

    n = rec.schreibe_entwuerfe([dict(ZEILE)], prepare=False)

    assert n == 0
    assert not list(out.glob("*.eml"))


def test_neue_anzeige_derselben_firma_ist_nicht_gesperrt(tmp_path, monkeypatch):
    import json
    out = _outbox(tmp_path, monkeypatch)
    alte = rec.jk.anzeige_keys(
        "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-9999999999-S",
        "Permacon GmbH", "Alte Stelle")
    rec.SPERRE.write_text(
        json.dumps({"firma": "Permacon GmbH", "keys": alte}) + "\n", encoding="utf-8")

    n = rec.schreibe_entwuerfe([dict(ZEILE)], prepare=False)

    assert n == 1
    assert len(list(out.glob("*.eml"))) == 1
