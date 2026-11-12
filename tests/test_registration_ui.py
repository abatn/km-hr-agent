"""UI-Tests: Honeypot + Mindest-Fuellzeit + E-Mail-Guard der Registrierung.

Gerendert wird die ECHTE Seite `/login` aus `webui/pages/login.py`; die Route
registriert `tests/nicegui_main.py` per `login_page.create()` (Regel R5-1:
Render-Routen gehoeren in die main_file, nicht ins Testmodul).

Abgedeckt:

* Das Lockfeld ist off-screen, aus dem Tab-Fluss (`tabindex=-1`) und aus dem
  Screenreader-Baum (`aria-hidden=true`) — in beiden Registrierungspanels.
* Gefuelltes Lockfeld -> **generische** Meldung (kein Hinweis auf den Grund),
  kein Datensatz in der (Spiegel-)DB.
* Zu schnelles Absenden -> dieselbe generische Meldung, kein Datensatz.
* Serverseitiger E-Mail-Guard greift unabhaengig von der Client-Validierung
  (Reserve-Domaene `example.com`).
* Negativfall Flag 0: `KMHR_REGISTRATION_HONEYPOT=0` = Verhalten wie vorher —
  Honeypot und Timing blockieren nicht, die Registrierung laeuft durch.

Spec: `knowledge/system/registration-hardening.md`.
"""
from __future__ import annotations

import pytest

from webui import db
from webui import registration_guard as guard

GENERIC = "Registrierung derzeit nicht möglich. Bitte versuchen Sie es später erneut."
EMAIL_ERROR = "Bitte eine gueltige E-Mail eingeben."
CONSENT_ERROR = "Bitte akzeptieren Sie AGB und Datenschutzerklärung, um sich zu registrieren."
OK_TEXT = "Registriert! Jetzt einloggen."


# ─── Helfer ────────────────────────────────────────────────────────────

async def _open_login(user) -> None:
    await user.open("/login")
    await user.should_see("Neues Konto erstellen")


def _fill_candidate(user, email: str) -> None:
    user.find(marker="reg-email").type(email)
    user.find(marker="reg-name").type("UI Test")
    user.find(marker="reg-pw").type("Testpasswort2026")


def _ohne_timing(monkeypatch) -> None:
    """Timing-Schwelle auf 0: die UI-Tests laufen in Millisekunden.

    Die 3-Sekunden-Schwelle selbst ist in `tests/test_registration_guard.py`
    geprueft; hier geht es um die Verdrahtung.
    """
    monkeypatch.setattr(guard, "MIN_FILL_SECONDS", 0.0)


def _db_has_email(email: str) -> bool:
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE lower(email) = lower(?)", (email,)
        ).fetchone()
        return int(row[0]) > 0
    finally:
        conn.close()


def _cleanup(email: str) -> None:
    """Spiegel-DB sauber halten (Tests duerfen keine Kandidaten hinterlassen)."""
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM candidates WHERE lower(email) = lower(?)", (email,)
        ).fetchone()
        if not row:
            return
        cid = int(row[0])
        conn.execute("DELETE FROM notifications WHERE role = 'candidate' AND user_id = ?", (cid,))
        conn.execute("DELETE FROM consents WHERE subject_type = 'candidate' AND subject_id = ?", (cid,))
        conn.execute("DELETE FROM candidates WHERE id = ?", (cid,))
        conn.commit()
    finally:
        conn.close()


# ─── Lockfeld ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("marker", ["hp-register-candidate", "hp-register-employer"])
async def test_honeypot_ist_unsichtbar_und_ausserhalb_des_tabflusses(user, marker):
    await _open_login(user)
    with user.scope(marker=marker) as hp:
        assert hp.props.get("aria-hidden") == "true", "Lockfeld muss vor Screenreadern verborgen sein"
        assert hp.props.get("tabindex") == "-1", "Lockfeld darf nicht per Tab erreichbar sein"
        assert hp.props.get("autocomplete") == "off"
        assert hp._style.get("position") == "absolute"
        assert hp._style.get("left") == "-10000px", "Lockfeld muss off-screen stehen"


# ─── Blockade: Honeypot ────────────────────────────────────────────────

async def test_honeypot_gefuellt_blockiert_generisch(user, monkeypatch):
    _ohne_timing(monkeypatch)
    email = "ui-honeypot@beispiel.de"
    await _open_login(user)
    _fill_candidate(user, email)
    user.find(marker="reg-consent").click()
    user.find(marker="hp-register-candidate").type("http://spam.example")
    user.find(marker="reg-submit").click()

    await user.should_see(GENERIC)
    await user.should_not_see(OK_TEXT)
    assert _db_has_email(email) is False, "trotz Honeypot wurde ein Konto angelegt"


async def test_honeypot_arbeitgeber_blockiert_generisch(user, monkeypatch):
    _ohne_timing(monkeypatch)
    await _open_login(user)
    user.find(marker="reg-emp-email").type("ui-honeypot@firma-beispiel.de")
    user.find(marker="reg-emp-firma").type("UI Test GmbH")
    user.find(marker="reg-emp-kontakt").type("UI Test")
    user.find(marker="reg-emp-pw").type("Testpasswort2026")
    user.find(marker="reg-emp-consent").click()
    user.find(marker="hp-register-employer").type("http://spam.example")
    user.find(marker="reg-emp-submit").click()

    await user.should_see(GENERIC)


# ─── Blockade: Mindest-Fuellzeit ───────────────────────────────────────

async def test_zu_schnelle_registrierung_blockiert_generisch(user, monkeypatch):
    """Schwelle hochgesetzt statt Zeit gepatcht: deterministisch, ohne Uhr-Mock."""
    monkeypatch.setattr(guard, "MIN_FILL_SECONDS", 60.0)
    email = "ui-zu-schnell@beispiel.de"
    await _open_login(user)
    _fill_candidate(user, email)
    user.find(marker="reg-consent").click()
    user.find(marker="reg-submit").click()

    await user.should_see(GENERIC)
    assert _db_has_email(email) is False


# ─── E-Mail-Guard (serverseitig) ───────────────────────────────────────

async def test_reserve_domaene_wird_serverseitig_abgelehnt(user, monkeypatch):
    """Die Client-Validierung ist umgehbar — der Handler prueft erneut."""
    _ohne_timing(monkeypatch)
    email = "ui-reserve@example.com"
    await _open_login(user)
    # Value direkt setzen: `type()` wuerde die Client-Validierung nur markieren,
    # der Klick auf "Registrieren" geht trotzdem in den Handler.
    user.find(marker="reg-email").type(email)
    user.find(marker="reg-name").type("UI Test")
    user.find(marker="reg-pw").type("Testpasswort2026")
    user.find(marker="reg-consent").click()
    user.find(marker="reg-submit").click()

    await user.should_see(EMAIL_ERROR)
    assert _db_has_email(email) is False


# ─── Negativfall: Flag 0 = Verhalten wie vorher ────────────────────────

async def test_flag_0_honeypot_und_timing_wirken_nicht(user, monkeypatch):
    monkeypatch.setenv(guard.HONEYPOT_FLAG, "0")
    await _open_login(user)
    _fill_candidate(user, "ui-flag0@beispiel.de")
    user.find(marker="hp-register-candidate").type("http://spam.example")
    user.find(marker="reg-submit").click()  # ohne Consent, ohne Wartezeit

    # Der Consent-Guard ist erreicht: Honeypot + Timing haben nicht geblockt.
    await user.should_see(CONSENT_ERROR)
    await user.should_not_see(GENERIC)


async def test_flag_0_registrierung_laeuft_wie_vorher_durch(user, monkeypatch):
    monkeypatch.setenv(guard.HONEYPOT_FLAG, "0")
    email = "ui-flag0-ok@beispiel.de"
    await _open_login(user)
    try:
        _fill_candidate(user, email)
        user.find(marker="reg-consent").click()
        user.find(marker="reg-submit").click()
        await user.should_see(OK_TEXT)
        assert _db_has_email(email) is True
    finally:
        _cleanup(email)
