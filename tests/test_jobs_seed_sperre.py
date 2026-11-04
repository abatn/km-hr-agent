"""Sperr-Migration aus Versand-Logs: Parsing, Titel-Formate, Dedupe, Schreiben."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec_agent = importlib.util.spec_from_file_location("jobs_agent", SCRIPTS / "jobs_agent.py")
_agent = importlib.util.module_from_spec(_spec_agent)
sys.modules["jobs_agent"] = _agent
_spec_agent.loader.exec_module(_agent)

_spec = importlib.util.spec_from_file_location("jobs_seed_sperre", SCRIPTS / "jobs_seed_sperre.py")
seed = importlib.util.module_from_spec(_spec)
sys.modules["jobs_seed_sperre"] = seed
_spec.loader.exec_module(seed)


def _log(tmp_path: Path, text: str, name: str = "versand-080501.md") -> Path:
    p = tmp_path / "outbox" / "2026-11-03" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _eml(tmp_path: Path, name: str, to: str, firma: str, betreff: str) -> Path:
    p = tmp_path / "outbox" / "final" / f"{name}.eml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"To: {to}\nSubject: {betreff}\n\nGuten Tag {firma},\n\nAbmelden\n", encoding="utf-8")
    return p


def test_titel_aus_betreff_alle_formate():
    assert seed.titel_aus_betreff("Kostenlose Listung: Pflegefachkraft (m/w/d) auf Jobs.hanibal-ai.com") == "Pflegefachkraft (m/w/d)"
    assert seed.titel_aus_betreff("Ihre Stellenanzeige „Elektriker (m/w/d)“ – kostenlose, unverbindliche Listung") == "Elektriker (m/w/d)"
    assert seed.titel_aus_betreff("Votre offre « Cuisinier H/F » – publication gratuite et sans engagement") == "Cuisinier H/F"
    assert seed.titel_aus_betreff("Publication gratuite : Cuisinier H/F sur Jobs.hanibal-ai.com") == "Cuisinier H/F"
    assert seed.titel_aus_betreff("Your job posting “Cook (m/f/d)” – free, no-obligation listing") == "Cook (m/f/d)"
    assert seed.titel_aus_betreff("Free listing: Cook (m/f/d) on Jobs.hanibal-ai.com") == "Cook (m/f/d)"
    assert seed.titel_aus_betreff("Unbekanntes Format") == ""


def test_logs_dedupe_und_neuestes_datum(tmp_path):
    _log(tmp_path, "# Versand 2026-11-03 08:05\n\nModus: SEND\n\n"
         "- OK: hr@example.org — Kostenlose Listung: A auf X — OK\n", "versand-080501.md")
    _log(tmp_path, "# Versand 2026-11-04 08:05\n\nModus: SEND\n\n"
         "- OK: hr@example.org — Kostenlose Listung: A auf X — OK\n"
         "- FEHLER: kaputt@example.org — X — Fehler\n", "versand-080502.md")
    logs = seed.parse_logs(tmp_path / "outbox")
    assert list(logs) == ["hr@example.org"]
    assert logs["hr@example.org"]["datum"] == "2026-11-04"
    assert "kaputt@example.org" not in logs


def test_csv_und_eml_aufloesung(tmp_path):
    _log(tmp_path, "# Versand 2026-11-04 08:05\n\n"
         "- OK: csv@example.org — Ihre Stellenanzeige „Pflegefachkraft“ – x — OK\n"
         "- OK: eml@example.org — Kostenlose Listung: Alter Job auf X — OK\n")
    csv_p = tmp_path / "emp.csv"
    csv_p.write_text(
        "prioritaet,arbeitgeber,stelle,ort,land,branche,email,quelle,kontaktweg,url\n"
        "1,Permacon GmbH,Pflegefachkraft (m/w/d),Berlin,DE,Krankenpflege,csv@example.org,"
        "Bundesagentur,E-Mail,https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1-S\n",
        encoding="utf-8")
    _eml(tmp_path, "de-alt", "eml@example.org", "Alte Firma GmbH",
         "Kostenlose Listung: Alter Job auf Jobs.hanibal-ai.com")

    logs = seed.parse_logs(tmp_path / "outbox")
    saetze, offen = seed.baue_datensaetze(
        logs, seed.parse_csv(csv_p), seed.parse_eml(tmp_path / "outbox" / "final"))

    assert not offen
    csv_satz = next(s for s in saetze if s["email"] == "csv@example.org")
    assert csv_satz["herkunft"] == "csv"
    assert any(k.startswith("id:10001-1-S") for k in csv_satz["keys"])
    eml_satz = next(s for s in saetze if s["email"] == "eml@example.org")
    assert eml_satz["herkunft"] == "eml"
    assert eml_satz["firma"] == "Alte Firma GmbH"
    assert eml_satz["keys"] == [k for k in eml_satz["keys"] if k.startswith("hash:")]


def test_unaufgeloest_und_schreiben_mit_backup(tmp_path):
    _log(tmp_path, "# Versand 2026-11-04 08:05\n\n- OK: weg@example.org — Kostenlose Listung: X auf Y — OK\n")
    logs = seed.parse_logs(tmp_path / "outbox")
    saetze, offen = seed.baue_datensaetze(logs, {}, {})
    assert saetze == [] and offen == ["weg@example.org"]

    ziel = tmp_path / "ansprache.jsonl"
    ziel.write_text(json.dumps({"email": "alt@example.org", "keys": ["hash:x"]}) + "\n", encoding="utf-8")
    satz = {"datum": "2026-11-04", "firma": "F", "firma_key": "f", "keys": ["hash:a"],
            "email": "neu@example.org", "betreff": "B", "herkunft": "csv"}
    backup = seed.schreibe([satz], ziel, force=True)

    assert backup is not None and backup.exists()
    zeilen = [json.loads(z) for z in ziel.read_text(encoding="utf-8").splitlines()]
    assert {z["email"] for z in zeilen} == {"alt@example.org", "neu@example.org"}


def test_schreiben_ohne_ziel_kein_backup(tmp_path):
    ziel = tmp_path / "neu.jsonl"
    satz = {"datum": "2026-11-04", "firma": "F", "firma_key": "f", "keys": ["hash:a"],
            "email": "a@example.org", "betreff": "B", "herkunft": "csv"}
    assert seed.schreibe([satz], ziel, force=False) is None
    assert len(ziel.read_text(encoding="utf-8").splitlines()) == 1
