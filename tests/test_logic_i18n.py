"""S5 (12.10.2026): `logic.change_password` liefert deutsche **msgids**, die
Call-Sites (candidate/employer) uebersetzen via `_()` == `tr(msgid, get_language())`.

Beleg fuer Lab-Schritt 4: `knowledge/system/i18n.md` (Konvention: msgid bleibt
deutsch, Uebersetzung erst am Call-Site; keine f-Strings in `_()`, Ruff INT001).

Isolation: eigene Temp-SQLite je Test (kein Zugriff auf die Live-/Spiegel-DB);
keine Netz-/LLM-Abhaengigkeit.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from webui import logic
from webui.i18n_core import tr

_ROOT = Path(__file__).resolve().parents[1]


# ─── DB-Helfer (framework-frei: nur der uebergebene conn wird genutzt) ─────

def _make_db(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "pw.db"))
    conn.execute(
        "CREATE TABLE candidates (id INTEGER PRIMARY KEY, password_hash TEXT)")
    conn.commit()
    return conn


def _seed_user(conn: sqlite3.Connection, user_id: int, password: str) -> None:
    conn.execute(
        "INSERT INTO candidates (id, password_hash) VALUES (?, ?)",
        (user_id, logic.hash_password_argon2id(password)))
    conn.commit()


# ─── change_password: deutsche msgid je Zweig ──────────────────────────────

def test_benutzer_nicht_gefunden(tmp_path):
    conn = _make_db(tmp_path)
    try:
        assert logic.change_password(conn, "candidates", 999, "x", "y") == (
            False, "Benutzer nicht gefunden.")
    finally:
        conn.close()


def test_altes_passwort_falsch(tmp_path):
    conn = _make_db(tmp_path)
    try:
        _seed_user(conn, 1, "Start-PW-123")
        ok, msg = logic.change_password(
            conn, "candidates", 1, "falsch", "Ganz-Neu-987")
        assert ok is False
        assert msg == "Altes Passwort ist nicht korrekt."
    finally:
        conn.close()


def test_neues_passwort_zu_kurz(tmp_path):
    conn = _make_db(tmp_path)
    try:
        _seed_user(conn, 1, "Start-PW-123")
        ok, msg = logic.change_password(
            conn, "candidates", 1, "Start-PW-123", "kurz")
        assert ok is False
        assert msg == (
            "Neues Passwort muss mindestens {0} Zeichen lang sein."
            .format(logic.MIN_PASSWORD_LENGTH))
    finally:
        conn.close()


def test_neues_gleich_altem_passwort(tmp_path):
    conn = _make_db(tmp_path)
    try:
        _seed_user(conn, 1, "Start-PW-123")
        ok, msg = logic.change_password(
            conn, "candidates", 1, "Start-PW-123", "Start-PW-123")
        assert ok is False
        assert msg == "Neues Passwort darf nicht dem alten Passwort entsprechen."
    finally:
        conn.close()


def test_passwort_geaendert(tmp_path):
    conn = _make_db(tmp_path)
    try:
        _seed_user(conn, 1, "Start-PW-123")
        ok, msg = logic.change_password(
            conn, "candidates", 1, "Start-PW-123", "Ganz-Neu-987")
        assert ok is True
        assert msg == "Passwort geändert."
        new_hash = conn.execute(
            "SELECT password_hash FROM candidates WHERE id = 1").fetchone()[0]
        assert logic.verify_password_argon2id("Ganz-Neu-987", new_hash)
    finally:
        conn.close()


# ─── Call-Site-Uebersetzung (dieselbe Pipeline wie `_()` in den Pages) ─────

class _FakeTranslations:
    """Minimaler gettext-Ersatz fuer die neuen msgids (echte .po ungepflegt)."""

    def gettext(self, msgid: str) -> str:
        return {
            "Benutzer nicht gefunden.": "User not found.",
            "Passwort geändert.": "Password changed.",
        }.get(msgid, msgid)


def _callsite_render(msgid: str, lang: str) -> str:
    """Mimik der Call-Site: `_(msg)` == `tr(msg, get_language())`."""
    return tr(msgid, lang)


def test_callsite_uebersetzt_msgid(monkeypatch):
    from webui import i18n_core
    i18n_core._translate.cache_clear()
    monkeypatch.setattr(
        i18n_core, "_translation", lambda lang: _FakeTranslations())
    try:
        assert _callsite_render("Passwort geändert.", "en") == "Password changed."
        assert _callsite_render("Passwort geändert.", "en") != "Passwort geändert."
        assert _callsite_render("Passwort geändert.", "de") == "Passwort geändert."
    finally:
        i18n_core._translate.cache_clear()


def test_callsites_wrap_msg_mit_uebersetzung():
    """S5: beide behandelten Call-Sites wickeln die Meldung in `_(msg)`."""
    snippet = 'ui.notify(_(msg), type="positive" if ok else "negative")'
    for rel in ("webui/pages/candidate.py", "webui/pages/employer.py"):
        src = (_ROOT / rel).read_text(encoding="utf-8")
        assert snippet in src, rel


def test_report_language_defensiv():
    """S4b: `_report_language` liest `language` bzw. rohes `result_json`."""
    from webui.pages import employer as emp
    assert emp._report_language(None) is None
    assert emp._report_language({"text": "x"}) is None
    assert emp._report_language({"language": "de"}) == "de"
    assert emp._report_language({"result_json": '{"language": "en"}'}) == "en"
    assert emp._report_language({"result_json": "kein json"}) is None
    assert emp._report_language({"language": "  "}) is None
