"""Versand: .eml-Parsing, Abmelde-Pflicht, Dedupe, MCP-Fehlerpfad."""
from __future__ import annotations

import argparse
import importlib.util
import json
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


# --- Sperrliste (ansprache.jsonl) -------------------------------------------

KEYS = "id:10001-1003940671-S hash:a1b2c3d4e5f6a7b8"


def _eml_keys(tmp_path: Path, name: str = "k", to: str = "hr@example.org") -> Path:
    p = tmp_path / f"{name}.eml"
    p.write_text(
        "To: " + to + "\n"
        "Subject: Testbetreff\n"
        "X-KMHR-Firma: Permacon GmbH\n"
        f"X-KMHR-Keys: {KEYS}\n"
        "\n" + BODY,
        encoding="utf-8",
    )
    return p


def test_parse_eml_liest_firma_und_keys(tmp_path):
    d = mail.parse_eml(_eml_keys(tmp_path))
    assert d["firma"] == "Permacon GmbH"
    assert d["keys"] == ["id:10001-1003940671-S", "hash:a1b2c3d4e5f6a7b8"]


def test_parse_eml_ohne_zusatz_header_leer(tmp_path):
    d = mail.parse_eml(_eml(tmp_path, "ohne", "hr@example.org"))
    assert d["firma"] == ""
    assert d["keys"] == []


def test_merke_ansprache_schreibt_eine_json_zeile(tmp_path):
    ziel = tmp_path / "ansprache.jsonl"
    m = {"to": "hr@example.org", "subject": "Testbetreff",
         "firma": "Permacon GmbH", "keys": KEYS.split()}
    assert mail.merke_ansprache(m, ziel) is True
    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 1
    satz = json.loads(zeilen[0])
    assert satz["datum"]
    assert satz["firma"] == "Permacon GmbH"
    assert satz["keys"] == KEYS.split()
    assert satz["email"] == "hr@example.org"
    assert satz["betreff"] == "Testbetreff"
    assert "firma_key" in satz


def test_merke_ansprache_ohne_firma_oder_keys_schreibt_nichts(tmp_path):
    ziel = tmp_path / "ansprache.jsonl"
    assert mail.merke_ansprache({"to": "a@b.de", "firma": "", "keys": ["k"]}, ziel) is False
    assert mail.merke_ansprache({"to": "a@b.de", "firma": "Firma", "keys": []}, ziel) is False
    assert not ziel.exists()


def _args(outbox: Path, to: str = "") -> argparse.Namespace:
    return argparse.Namespace(outbox=str(outbox), send=True, yes=True, to=to,
                              allow_real=True, limit=5, force=True)


def test_run_merkt_nur_bei_erfolg(tmp_path, monkeypatch):
    d = tmp_path / "outbox"
    d.mkdir()
    _eml_keys(d)
    ziel = tmp_path / "ansprache.jsonl"
    monkeypatch.setattr(mail, "ANSPRACHE", ziel)

    monkeypatch.setattr(mail, "mcp_send", lambda *a, **k: (True, "OK"))
    assert mail.run(_args(d)) == 0
    assert ziel.exists()
    assert len(ziel.read_text(encoding="utf-8").splitlines()) == 1

    ziel.unlink()
    monkeypatch.setattr(mail, "mcp_send", lambda *a, **k: (False, "x"))
    assert mail.run(_args(d)) == 1
    assert not ziel.exists() or not ziel.read_text(encoding="utf-8").strip()


def test_run_testversand_merkt_nichts(tmp_path, monkeypatch):
    d = tmp_path / "outbox"
    d.mkdir()
    _eml_keys(d)
    ziel = tmp_path / "ansprache.jsonl"
    monkeypatch.setattr(mail, "ANSPRACHE", ziel)
    monkeypatch.setattr(mail, "mcp_send", lambda *a, **k: (True, "OK"))
    assert mail.run(_args(d, to="test@example.org")) == 0
    assert not ziel.exists()
