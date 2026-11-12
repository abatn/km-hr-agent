"""Unit-Tests fuer `webui/registration_guard.py` (Maßnahmen 5a + 6, 12.11.2026).

Deckt die drei Ebenen ab, die ohne UI pruefbar sind:

* E-Mail-Validator: Format, Laengen (RFC 5321), Ein-Buchstaben-TLD,
  Reserve-TLDs/-Domaenen, IDN und Plus-Adressen.
* Flags: `KMHR_REGISTRATION_STRICT_EMAIL` / `KMHR_REGISTRATION_HONEYPOT`
  (Default 1, Flag 0 = Altverhalten inkl. log-only).
* Honeypot/Timing-Entscheidung `registration_blocked` inklusive Schwelle
  `MIN_FILL_SECONDS = 3.0`.

Die UI-Verdrahtung (Felder, unsichtbares Feld, Handler-Reihenfolge) prueft
`tests/test_registration_ui.py`; Spec: `knowledge/system/registration-hardening.md`.
"""
from __future__ import annotations

import pytest

from webui import registration_guard as guard

GUELTIG = [
    "anna@beispiel.de",
    "a.b+tag@sub.beispiel.de",
    "jürgen@beispiel.de",          # Umlaut im Lokalteil (SMTPUTF8)
    "anna@bücher.de",              # IDN-Domain
    "ANNA@Beispiel.DE",            # Gross-/Kleinschreibung
    " anna@beispiel.de ",          # Leerraum wird normalisiert
]

UNGENUELTIG = [
    ("anna", "format"),
    ("anna@", "format"),
    ("@beispiel.de", "format"),
    ("anna@beispiel..de", "format"),
    ("anna@localhost", "format"),
    ("anna@127.0.0.1", "format"),
    ("anna@beispiel.c", "tld"),                # Ein-Buchstaben-TLD
    ("a" * 65 + "@beispiel.de", "local_len"),  # RFC-Grenze Lokalteil
    ("a" * 64 + "@" + "b" * 187 + ".de", "total_len"),
    ("anna@example.invalid", "reserved_tld"),
    ("anna@firma.test", "reserved_tld"),
    ("anna@firma.localhost", "reserved_tld"),
    ("anna@firma.example", "reserved_tld"),
    ("anna@example.com", "reserved_domain"),
    ("anna@example.net", "reserved_domain"),
    ("anna@example.org", "reserved_domain"),
]


# ─── E-Mail-Pruefung ───────────────────────────────────────────────────

def test_normalize_email():
    assert guard.normalize_email("  Anna@Beispiel.DE ") == "anna@beispiel.de"
    assert guard.normalize_email(None) == ""
    assert guard.normalize_email("") == ""


@pytest.mark.parametrize("adresse", GUELTIG)
def test_gueltige_adressen_werden_akzeptiert(adresse):
    ok, grund = guard.check_registration_email(adresse)
    assert ok, f"{adresse!r} abgelehnt: {grund}"
    assert grund == "ok"


@pytest.mark.parametrize("adresse,erwartet", UNGENUELTIG)
def test_ungueltige_adressen_werden_abgelehnt(adresse, erwartet):
    ok, grund = guard.check_registration_email(adresse)
    assert not ok, f"{adresse!r} wurde akzeptiert"
    assert grund == erwartet, f"{adresse!r}: {grund} statt {erwartet}"


def test_email_validator_laesst_reserve_tld_durch_eigene_regel_noetig():
    """Belegt die Luecke, wegen der die Sperrliste existiert (Messung 12.11.2026):
    `email-validator` akzeptiert `anna@bücher.example` und TLDs mit einem Zeichen."""
    from email_validator import validate_email

    assert validate_email("anna@bücher.example", check_deliverability=False)
    assert validate_email("anna@beispiel.c", check_deliverability=False)
    # Genau diese beiden Faelle faengt der Guard.
    assert guard.check_registration_email("anna@bücher.example") == (False, "reserved_tld")
    assert guard.check_registration_email("anna@beispiel.c") == (False, "tld")


# ─── Flags ──────────────────────────────────────────────────────────────

def test_flags_default_an(monkeypatch):
    monkeypatch.delenv(guard.STRICT_EMAIL_FLAG, raising=False)
    monkeypatch.delenv(guard.HONEYPOT_FLAG, raising=False)
    assert guard.strict_email_enabled() is True
    assert guard.honeypot_enabled() is True


@pytest.mark.parametrize("wert", ["0", "false", "no", "off", " OFF "])
def test_flags_abschaltbar(monkeypatch, wert):
    monkeypatch.setenv(guard.STRICT_EMAIL_FLAG, wert)
    monkeypatch.setenv(guard.HONEYPOT_FLAG, wert)
    assert guard.strict_email_enabled() is False
    assert guard.honeypot_enabled() is False


@pytest.mark.parametrize("wert", ["1", "true", "yes", "on"])
def test_flags_einschaltbar(monkeypatch, wert):
    monkeypatch.setenv(guard.STRICT_EMAIL_FLAG, wert)
    monkeypatch.setenv(guard.HONEYPOT_FLAG, wert)
    assert guard.strict_email_enabled() is True
    assert guard.honeypot_enabled() is True


def test_strict_email_flag_0_ist_log_only(monkeypatch, capsys):
    """Flag 0 = Altverhalten: ablehnen unterbleibt, der Grund wird geloggt (ohne Adresse)."""
    monkeypatch.setenv(guard.STRICT_EMAIL_FLAG, "0")
    assert guard.registration_email_blocked("anna@example.com") is False
    log = capsys.readouterr().out
    assert "log-only" in log
    assert "reserved_domain" in log
    assert "anna@example.com" not in log, "Adresse darf nicht im Log stehen"


def test_strict_email_flag_1_lehnt_ab(monkeypatch):
    monkeypatch.setenv(guard.STRICT_EMAIL_FLAG, "1")
    assert guard.registration_email_blocked("anna@example.com") is True
    assert guard.registration_email_blocked("anna@beispiel.de") is False


# ─── Client-Validierung (5 Felder, zwei Verhalten) ─────────────────────

@pytest.mark.parametrize("wert", ["kandidat1@example.invalid", "anna@beispiel.de", "a@b.c"])
def test_login_felder_bleiben_tolerant(wert):
    """Seed-/E2E-Konten tragen `@example.invalid` — Login darf sie nie blockieren."""
    assert guard.email_field_valid(wert) is True


@pytest.mark.parametrize("wert", ["anna", "anna.de", "", None])
def test_login_felder_wie_vorher(wert):
    assert guard.email_field_valid(wert) is False


def test_login_felder_altregel_bleibt_bewusst_grob():
    """Altverhalten (`"@" in v and "." in v`) wird NICHT verschaerft: nur bei
    der Registrierung gilt die strikte Regel; der Login bleibt tolerant."""
    assert guard.email_field_valid("@beispiel.de") is True


def test_registrierungsfeld_leer_gilt_als_gueltig(monkeypatch):
    monkeypatch.delenv(guard.STRICT_EMAIL_FLAG, raising=False)
    assert guard.registration_email_field_valid("") is True
    assert guard.registration_email_field_valid(None) is True


def test_registrierungsfeld_strikt(monkeypatch):
    monkeypatch.delenv(guard.STRICT_EMAIL_FLAG, raising=False)
    assert guard.registration_email_field_valid("anna@beispiel.de") is True
    assert guard.registration_email_field_valid("anna@example.com") is False
    assert guard.registration_email_field_valid("kandidat1@example.invalid") is False


def test_registrierungsfeld_flag_0_wie_vorher(monkeypatch):
    monkeypatch.setenv(guard.STRICT_EMAIL_FLAG, "0")
    assert guard.registration_email_field_valid("anna@example.com") is True
    assert guard.registration_email_field_valid("anna") is False  # Altregel


# ─── Honeypot + Timing ─────────────────────────────────────────────────

@pytest.mark.parametrize("wert", ["", None, "   "])
def test_honeypot_leer(wert):
    assert guard.honeypot_triggered(wert) is False


@pytest.mark.parametrize("wert", ["http://spam.example", "x", " 1 "])
def test_honeypot_gefuellt(wert):
    assert guard.honeypot_triggered(wert) is True


def test_schwelle_ist_drei_sekunden():
    assert guard.MIN_FILL_SECONDS == 3.0


def test_timing_grenze():
    assert guard.too_fast(0.0) is True
    assert guard.too_fast(2.99) is True
    assert guard.too_fast(3.0) is False
    assert guard.too_fast(10.0) is False
    assert guard.too_fast(2.99, min_seconds=0.0) is False


def test_registration_blocked_honeypot(monkeypatch):
    monkeypatch.delenv(guard.HONEYPOT_FLAG, raising=False)
    assert guard.registration_blocked("http://spam.example", 10.0) is True
    assert guard.registration_blocked("", 10.0) is False


def test_registration_blocked_zu_schnell(monkeypatch):
    monkeypatch.delenv(guard.HONEYPOT_FLAG, raising=False)
    assert guard.registration_blocked("", 0.5) is True
    assert guard.registration_blocked("", 3.5) is False


def test_registration_blocked_flag_0_verhaelt_wie_vorher(monkeypatch):
    """Negativfall: Flag 0 schaltet BEIDE Schichten ab (Honeypot und Timing)."""
    monkeypatch.setenv(guard.HONEYPOT_FLAG, "0")
    assert guard.registration_blocked("http://spam.example", 0.0) is False


def test_blockierte_registrierung_loggt_ohne_eingabe(monkeypatch, capsys):
    monkeypatch.delenv(guard.HONEYPOT_FLAG, raising=False)
    guard.registration_blocked("geheim", 10.0)
    log = capsys.readouterr().out
    assert "Honeypot" in log
    assert "geheim" not in log, "Honeypot-Inhalt darf nicht im Log stehen"
