"""Versand: .eml-Parsing, Abmelde-Pflicht, Dedupe, MCP-Fehlerpfad."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("jobs_mail", SCRIPTS / "jobs_mail.py")
mail = importlib.util.module_from_spec(_spec)
sys.modules["jobs_mail"] = mail
_spec.loader.exec_module(mail)

BODY = "Guten Tag,\n\nAngebot.\n\nFalls Sie keine Nachrichten wuenschen, antworten Sie mit Abmelden.\n"


def _eml(tmp_path: Path, name: str, to: str, body: str = BODY) -> Path:
    p = tmp_path / f"{name}.eml"
    p.write_text(f"To: {to}\nSubject: Testbetreff\n\n{body}", encoding="utf-8")
    return p


def test_parse_eml_liest_kopf_und_body(tmp_path):
    d = mail.parse_eml(_eml(tmp_path, "a", "hr@example.org"))
    assert d["to"] == "hr@example.org"
    assert d["subject"] == "Testbetreff"
    assert "Angebot" in d["body"]


def test_abmelde_option_deutsch_englisch_franzoesisch(tmp_path):
    for wort in ("Abmelden", "Unsubscribe", "Désabonner"):
        p = _eml(tmp_path, f"m{wort[:3]}", "hr@example.org", f"Text.\n\n{wort}\n")
        ok, fehler = mail.pruefen([mail.parse_eml(p)])
        assert ok and not fehler, wort


def test_mail_ohne_abmelde_option_wird_verworfen(tmp_path):
    p = _eml(tmp_path, "ohne", "hr@example.org", "Nur ein Angebot ohne Abmeldung.")
    ok, fehler = mail.pruefen([mail.parse_eml(p)])
    assert not ok
    assert any("Abmelde-Option fehlt" in f for f in fehler)


def test_ungueltige_adresse_wird_verworfen(tmp_path):
    p = _eml(tmp_path, "leer", "")
    ok, fehler = mail.pruefen([mail.parse_eml(p)])
    assert not ok
    assert any("Empfängeradresse" in f for f in fehler)


def test_dedupe_pro_empfaenger(tmp_path):
    a = _eml(tmp_path, "a", "HR@Example.org")
    b = _eml(tmp_path, "b", "hr@example.org")
    ok, fehler = mail.pruefen([mail.parse_eml(a), mail.parse_eml(b)])
    assert len(ok) == 1 and not fehler


def test_abmelde_regex_ist_case_insensitiv():
    assert mail.ABMELDE.search("bitte ABMELDEN")
    assert mail.ABMELDE.search("Unsubscribe me")
