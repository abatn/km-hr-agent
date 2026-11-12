"""Basis-URL für Mail-Links — fail-closed (12.11.2026).

Vorfall: Ein Passwort-Reset ging mit `http://127.0.0.1:8080/login?reset=…`
raus. Ursache: Eine Dev-Instanz hatte `KMHR_PUBLIC_BASE_URL` auf Loopback
stehen; der Runner übernahm den Wert ungeprüft.

Deckt ab:
  * `scripts/mail_links.py`: Pflicht-Variable, Schema, Zugangsdaten,
    Query/Fragment, Loopback/private Hosts, https-Pflicht im Betrieb,
    `KMHR_DEV=1` als einzige Ausnahme für lokale Entwicklung.
  * `scripts/agent-runner.py`: `send_password_reset` prüft VOR der
    Token-Erzeugung (kein mcp_call, kein DB-Schreibvorgang) und
    `build_welcome_mail` nutzt dieselbe Prüfung.

Spec: knowledge/system/configuration-secrets.md §(g)/(h),
knowledge/system/agent-automation.md (Mail-Links).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Dieselbe Modulinstanz wie im Runner (sys.modules-Cache): die Exception-Klasse
# muss identisch sein, sonst schlägt `pytest.raises` fehl.
import mail_links as ml  # noqa: E402

_spec_runner = importlib.util.spec_from_file_location(
    "agent_runner_mail_links", ROOT / "scripts" / "agent-runner.py")
runner = importlib.util.module_from_spec(_spec_runner)
_spec_runner.loader.exec_module(runner)

ENV = "KMHR_PUBLIC_BASE_URL"


# ─── public_base_url() ───────────────────────────────────────────────────

def test_ohne_variable_fail_closed():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ml.MailLinkConfigError) as exc:
            ml.public_base_url()
    assert ENV in str(exc.value)
    assert "https://jobs.hanibal-ai.com" in str(exc.value)


@pytest.mark.parametrize("wert", ["", "   "])
def test_leere_variable_fail_closed(wert):
    with patch.dict(os.environ, {ENV: wert}, clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            ml.public_base_url()


@pytest.mark.parametrize("wert", [
    "jobs.hanibal-ai.com",          # kein Schema
    "ftp://jobs.hanibal-ai.com",    # falsches Schema
    "https://",                     # kein Host
])
def test_ungueltige_url(wert):
    with patch.dict(os.environ, {ENV: wert}, clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            ml.public_base_url()


def test_zugangsdaten_und_query_abgelehnt():
    with patch.dict(os.environ,
                    {ENV: "https://user:pw@jobs.hanibal-ai.com"}, clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            ml.public_base_url()
    with patch.dict(os.environ,
                    {ENV: "https://jobs.hanibal-ai.com/?x=1"}, clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            ml.public_base_url()


@pytest.mark.parametrize("host", [
    "localhost", "127.0.0.1", "127.0.1.1", "0.0.0.0", "::1", "[::1]",
    "10.1.2.3", "172.16.0.9", "192.168.1.20", "169.254.1.1", "fe80::1",
])
def test_lokale_hosts_im_betrieb_abgelehnt(host):
    with patch.dict(os.environ, {ENV: f"http://{host}:8080"}, clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            ml.public_base_url()


def test_http_im_betrieb_abgelehnt():
    with patch.dict(os.environ, {ENV: "http://jobs.hanibal-ai.com"},
                    clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            ml.public_base_url()


def test_https_oeffentlich_ok_und_trailing_slash_entfernt():
    with patch.dict(os.environ, {ENV: "https://jobs.hanibal-ai.com/"},
                    clear=True):
        assert ml.public_base_url() == "https://jobs.hanibal-ai.com"


def test_dev_modus_erlaubt_loopback_und_http():
    with patch.dict(os.environ,
                    {ENV: "http://127.0.0.1:8080", "KMHR_DEV": "1"},
                    clear=True):
        assert ml.public_base_url() == "http://127.0.0.1:8080"


def test_dev_modus_verlangt_fuer_oeffentliche_hosts_https():
    with patch.dict(os.environ,
                    {ENV: "http://jobs.hanibal-ai.com", "KMHR_DEV": "1"},
                    clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            ml.public_base_url()


@pytest.mark.parametrize("wert", ["1", "true", "yes", "TRUE"])
def test_dev_modus_werte(wert):
    assert ml.dev_mode({"KMHR_DEV": wert}) is True


@pytest.mark.parametrize("wert", ["", "0", "false", "nein"])
def test_dev_modus_aus(wert):
    assert ml.dev_mode({"KMHR_DEV": wert}) is False


# ─── Runner-Integration ─────────────────────────────────────────────────

def test_reset_prueft_vor_token_und_ohne_mcp_call(monkeypatch):
    """Fehlende Basis-URL → Abbruch VOR Token/DB; kein Mailversand."""
    aufrufe = []
    monkeypatch.setattr(runner, "mcp_call",
                        lambda *a, **k: aufrufe.append((a, k)) or "OK")
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            runner.send_password_reset({"role": "candidate", "id": 1})
    assert aufrufe == [], "Ohne gültige Basis-URL darf keine Mail rausgehen"


def test_reset_loopback_im_betrieb_abgelehnt(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(runner, "mcp_call",
                        lambda *a, **k: aufrufe.append((a, k)) or "OK")
    with patch.dict(os.environ,
                    {ENV: "http://127.0.0.1:8080"}, clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            runner.send_password_reset({"role": "candidate", "id": 1})
    assert aufrufe == []


def test_reset_dev_modus_kommt_an_der_pruefung_vorbei(monkeypatch):
    """KMHR_DEV=1 + Loopback: Prüfung passiert, unbekanntes Konto → no_account."""
    monkeypatch.setattr(runner, "mcp_call", lambda *a, **k: "OK")
    monkeypatch.setattr(runner, "log", lambda *a, **k: None)
    with patch.dict(os.environ,
                    {ENV: "http://127.0.0.1:8080", "KMHR_DEV": "1"},
                    clear=True):
        ergebnis = runner.send_password_reset(
            {"role": "candidate", "id": 999999999})
    assert ergebnis["status"] == "no_account"


def test_welcome_mail_prueft_die_basis_ebenfalls():
    with patch.dict(os.environ,
                    {ENV: "http://127.0.0.1:8080"}, clear=True):
        with pytest.raises(ml.MailLinkConfigError):
            runner.build_welcome_mail("candidate", "de", name="Alex")


def test_welcome_mail_dev_modus_nutzt_loopback_link():
    with patch.dict(os.environ,
                    {ENV: "http://127.0.0.1:8080", "KMHR_DEV": "1"},
                    clear=True):
        _subject, body = runner.build_welcome_mail("candidate", "de", name="Alex")
    assert "http://127.0.0.1:8080/login" in body


def test_welcome_link_nutzt_oeffentliche_produktions_basis():
    """Der versendete Link enthaelt die oeffentliche Domain, nie Loopback."""
    with patch.dict(os.environ, {ENV: "https://jobs.hanibal-ai.com"},
                    clear=True):
        _subject, body = runner.build_welcome_mail("candidate", "de", name="Alex")
    assert "https://jobs.hanibal-ai.com/login" in body
    assert "127.0.0.1" not in body
    assert "localhost" not in body
