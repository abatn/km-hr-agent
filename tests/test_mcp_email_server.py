"""Mailtrap-Umstellung: SMTP_FROM für Header und Envelope (30.10.2026).

Belegt (ohne echten Versand, smtplib ist gemockt):
  * msg["From"] und sendmail-Absender kommen aus SMTP_FROM.
  * Fallback auf SMTP_USERNAME, wenn SMTP_FROM leer ist.
  * Verbindung auf Port 587 mit STARTTLS, Login mit SMTP_USERNAME.
  * Port 465 wird abgewiesen, ohne Verbindungsaufbau.
  * Rückgaben und Fehlertexte enthalten keine Empfängeradresse.

Spec: knowledge/system/configuration-secrets.md §(j).
"""
from __future__ import annotations

import importlib.util
import smtplib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADRESSE = "kandidat-test@example.invalid"


def _lade_modul(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "mcp-email-server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeSMTP:
    """Ersetzt smtplib.SMTP. Zeichnet Aufrufe auf, optional mit Fehler beim Senden."""

    verbindungen: list = []
    fehler_beim_senden: Exception | None = None

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.gestartet = False
        self.login_daten = None
        self.absender = None
        self.empfaenger = None
        self.nachricht = None
        FakeSMTP.verbindungen.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.gestartet = True

    def login(self, user, pw):
        self.login_daten = (user, pw)

    def sendmail(self, absender, empfaenger, nachricht):
        if FakeSMTP.fehler_beim_senden is not None:
            raise FakeSMTP.fehler_beim_senden
        self.absender, self.empfaenger, self.nachricht = absender, empfaenger, nachricht


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.verbindungen = []
    FakeSMTP.fehler_beim_senden = None
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


@pytest.fixture
def mod(monkeypatch):
    monkeypatch.setenv("SMTP_USERNAME", "api")
    monkeypatch.setenv("SMTP_PASSWORD", "test-token")
    monkeypatch.setenv("SMTP_FROM", "no-reply@hanibal-ai.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_SERVER", "live.smtp.mailtrap.io")
    return _lade_modul("mcp_email_server_from")


def test_header_und_envelope_nutzen_smtp_from(smtp, mod):
    res = mod.send_email(ADRESSE, "Betreff", "Text")
    assert res.startswith("OK|")
    conn = smtp.verbindungen[0]
    assert conn.absender == "no-reply@hanibal-ai.com"
    assert "<no-reply@hanibal-ai.com>" in conn.nachricht
    assert "From: KM-HR-Agent <no-reply@hanibal-ai.com>" in conn.nachricht
    assert conn.empfaenger == [ADRESSE]


def test_login_und_starttls_auf_587(smtp, mod):
    mod.send_email(ADRESSE, "Betreff", "Text")
    conn = smtp.verbindungen[0]
    assert (conn.host, conn.port) == ("live.smtp.mailtrap.io", 587)
    assert conn.gestartet is True
    assert conn.login_daten == ("api", "test-token")


def test_fallback_auf_smtp_username_wenn_smtp_from_leer(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_FROM", "")
    monkeypatch.setenv("SMTP_USERNAME", "api")
    monkeypatch.setenv("SMTP_PASSWORD", "test-token")
    monkeypatch.setenv("SMTP_PORT", "587")
    mod = _lade_modul("mcp_email_server_fallback")
    mod.send_email(ADRESSE, "Betreff", "Text")
    conn = smtp.verbindungen[0]
    assert conn.absender == "api"
    assert "<api>" in conn.nachricht


def test_port_465_wird_abgewiesen_ohne_verbindung(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_FROM", "no-reply@hanibal-ai.com")
    monkeypatch.setenv("SMTP_USERNAME", "api")
    monkeypatch.setenv("SMTP_PASSWORD", "test-token")
    monkeypatch.setenv("SMTP_PORT", "465")
    mod = _lade_modul("mcp_email_server_465")
    res = mod.send_email(ADRESSE, "Betreff", "Text")
    assert res.startswith("FEHLER")
    assert "465" in res
    assert smtp.verbindungen == []


def test_erfolgsmeldung_enthaelt_keine_adresse(smtp, mod):
    res = mod.send_email(ADRESSE, "Betreff", "Text")
    assert ADRESSE not in res
    assert "@" not in res


def test_fehlertext_mit_adresse_wird_maskiert(smtp, mod):
    smtp.fehler_beim_senden = smtplib.SMTPRecipientsRefused({ADRESSE: (550, b"no such user")})
    res = mod.send_email(ADRESSE, "Betreff", "Text")
    assert res.startswith("FEHLER")
    assert ADRESSE not in res
    assert "<EMAIL>" in res
