"""Passwort-Reset per E-Mail (18.10.2026).

Spec: `knowledge/system/configuration-secrets.md` §(g).

Belegt:
  * Tabelle `password_resets` idempotent (`webui/db.py::init_password_resets_table`).
  * Token wird NUR als SHA-256-Hash gespeichert; Lookup deterministisch
    (`webui/db.py::hash_reset_token`).
  * `webui/logic.py::apply_password_reset`: gültig -> neu (argon2id), Einmal-
    Verwendung (2. Versuch = invalid), Ablauf (invalid), Policy (too_short,
    same_as_old), Zieltabelle aus der Rolle.
  * Rate-Limit 3/10 Min (`webui/db.py::count_recent_password_resets`).
  * Runner-Task `send_password_reset`: unbekannte E-Mail -> keine Mail
    (generisch), gültige E-Mail -> Mail mit Link, **Token nur im Body**
    (Log-Whitelist schliesst `body` aus; `log()`/Rückgabe enthalten ihn nie).

Isolation: `tests/conftest.py` leitet `data/feedback.db` in einen /tmp-Spiegel
um — die Live-DB wird NIE beschrieben. Eingefuegte Test-Zeilen werden im
`finally` per E-Mail wieder entfernt (keine Residuen fuer Folgetests).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from webui import db, logic

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "agent_runner_pwreset", ROOT / "scripts" / "agent-runner.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

CAND_MAIL = "reset-test-cand@example.invalid"
EMP_MAIL = "reset-test-emp@example.invalid"


def _conn():
    return db.get_conn()


def _cleanup() -> None:
    conn = _conn()
    try:
        conn.execute("DELETE FROM password_resets WHERE email IN (?, ?)",
                     (CAND_MAIL, EMP_MAIL))
        conn.execute("DELETE FROM candidates WHERE email = ?", (CAND_MAIL,))
        conn.execute("DELETE FROM employers WHERE email = ?", (EMP_MAIL,))
        conn.commit()
    finally:
        conn.close()


def _insert_candidate(pw_hash: str) -> int:
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO candidates (email, name, password_hash, status) "
            "VALUES (?, 'Reset Test', ?, 'registriert')", (CAND_MAIL, pw_hash))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _insert_employer(pw_hash: str) -> int:
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO employers (email, password_hash, firma, kontaktperson) "
            "VALUES (?, ?, 'ResetFirma', 'Reset Test')", (EMP_MAIL, pw_hash))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _add_reset(email: str, role: str, token: str, minutes: int) -> None:
    from datetime import datetime, timedelta, timezone
    exp = (datetime.now(timezone.utc).replace(tzinfo=None)
           + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _conn()
    try:
        db.create_password_reset(conn, email, role, db.hash_reset_token(token), exp)
    finally:
        conn.close()


def _pw_hash_of(email: str, table: str) -> str:
    conn = _conn()
    try:
        return conn.execute(
            f"SELECT password_hash FROM {table} WHERE email = ?", (email,)).fetchone()[0]
    finally:
        conn.close()


# ─── DB-Layer ────────────────────────────────────────────────────────────

def test_init_password_resets_table_idempotent_and_constants():
    db.init_password_resets_table()   # 2. Aufruf darf nicht werfen
    conn = _conn()
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(password_resets)")}
    finally:
        conn.close()
    assert {"id", "email", "role", "token_hash", "created_at",
            "expires_at", "used_at"} <= cols
    assert db.RESET_TTL_MINUTES == 60          # Design-Entscheidung §(g)
    assert db.RESET_RATE_LIMIT == 3
    assert db.RESET_RATE_WINDOW_MINUTES == 10


def test_hash_reset_token_deterministic_and_not_plaintext():
    tok = "abc-DEF-123_xyz"
    h = db.hash_reset_token(tok)
    assert h == db.hash_reset_token(tok)
    assert h != tok and len(h) == 64


# ─── apply_password_reset ────────────────────────────────────────────────

def test_reset_ok_single_use():
    _cleanup()
    try:
        _insert_candidate(logic.hash_password_argon2id("altpasswort1"))
        _add_reset(CAND_MAIL, "candidate", "tok-ok-1", 30)
        ok, code = logic.apply_password_reset("tok-ok-1", "neupasswort1")
        assert (ok, code) == (True, "ok")
        assert logic.verify_password_argon2id(
            "neupasswort1", _pw_hash_of(CAND_MAIL, "candidates"))
        # Einmal-Verwendung: derselbe Token ist verbraucht
        ok2, code2 = logic.apply_password_reset("tok-ok-1", "nochmal-egal1")
        assert (ok2, code2) == (False, "invalid")
    finally:
        _cleanup()


def test_reset_expired_is_invalid():
    _cleanup()
    try:
        _insert_candidate(logic.hash_password_argon2id("altpasswort1"))
        _add_reset(CAND_MAIL, "candidate", "tok-exp-1", -5)   # abgelaufen
        ok, code = logic.apply_password_reset("tok-exp-1", "neupasswort1")
        assert (ok, code) == (False, "invalid")
    finally:
        _cleanup()


def test_reset_unknown_token_is_invalid():
    _cleanup()
    try:
        ok, code = logic.apply_password_reset("gibt-es-nicht", "neupasswort1")
        assert (ok, code) == (False, "invalid")
    finally:
        _cleanup()


def test_reset_policy_too_short_and_same_as_old():
    _cleanup()
    try:
        old = "altespasswort1"
        _insert_candidate(logic.hash_password_argon2id(old))
        _add_reset(CAND_MAIL, "candidate", "tok-p1", 30)
        assert logic.apply_password_reset("tok-p1", "kurz") == (False, "too_short")
        # Token noch nicht verbraucht -> weiter nutzbar für den 2. Fall
        assert logic.apply_password_reset("tok-p1", old) == (False, "same_as_old")
    finally:
        _cleanup()


def test_reset_role_employer_targets_employers_table():
    _cleanup()
    try:
        _insert_employer(logic.hash_password_argon2id("empaltpass1"))
        _add_reset(EMP_MAIL, "employer", "tok-emp-1", 30)
        ok, code = logic.apply_password_reset("tok-emp-1", "empneupass1")
        assert (ok, code) == (True, "ok")
        assert logic.verify_password_argon2id(
            "empneupass1", _pw_hash_of(EMP_MAIL, "employers"))
    finally:
        _cleanup()


# ─── Rate-Limit ──────────────────────────────────────────────────────────

def test_count_recent_password_resets_window():
    _cleanup()
    try:
        for i in range(3):
            _add_reset(CAND_MAIL, "candidate", f"tok-rate-{i}", 30)
        conn = _conn()
        try:
            assert db.count_recent_password_resets(conn, CAND_MAIL) == 3
            # Fenster 0 Min -> 0 (nichts juenger als jetzt)
            assert db.count_recent_password_resets(conn, CAND_MAIL, minutes=0) == 0
        finally:
            conn.close()
    finally:
        _cleanup()


# ─── Runner-Task send_password_reset ─────────────────────────────────────

def _run_runner(payload: dict, monkeypatch, tmp_path):
    """Ruft mod.send_password_reset mit gemocktem mcp_call + umgeleitetem Log.
    Gibt (result, captured_args, log_text) zurück."""
    captured = {}

    def fake_mcp_call(server, tool, args):
        captured["tool"] = tool
        captured["args"] = args
        return "OK (gemockt)"

    log_file = tmp_path / "agent-runner.log"
    monkeypatch.setattr(mod, "mcp_call", fake_mcp_call)
    monkeypatch.setattr(mod, "LOG_FILE", log_file)
    result = mod.send_password_reset(payload)
    log_text = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
    return result, captured, log_text


def _payload(email: str, role: str) -> dict:
    """Payload wie ihn die UI nach Treffer queued: role + id, keine Adresse."""
    table = "candidates" if role == "candidate" else "employers"
    conn = _conn()
    try:
        row = conn.execute(f"SELECT id FROM {table} WHERE lower(email) = lower(?)",
                           (email,)).fetchone()
    finally:
        conn.close()
    return {"role": role, "id": row[0] if row else 999999999}


def test_runner_unknown_email_no_mail(monkeypatch, tmp_path):
    _cleanup()
    try:
        result, captured, _ = _run_runner(
            {"role": "candidate", "id": 999999999}, monkeypatch, tmp_path)
        assert result["status"] == "no_account"
        assert captured == {}          # kein Mail-Aufruf
    finally:
        _cleanup()


def test_runner_sends_link_token_only_in_body(monkeypatch, tmp_path):
    _cleanup()
    try:
        _insert_candidate(logic.hash_password_argon2id("altpasswort1"))
        result, captured, log_text = _run_runner(
            _payload(CAND_MAIL, "candidate"), monkeypatch, tmp_path)
        assert result["status"] == "sent"
        assert captured["tool"] == "send_email"
        body = captured["args"]["body"]
        subject = captured["args"]["subject"]
        assert "/login?reset=" in body
        token = body.split("/login?reset=")[1].split()[0].strip()

        # Token NICHT in subject / Rückgabe / Log
        assert token not in subject
        assert token not in str(result)
        assert token not in log_text

        # Nur Hash gespeichert
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT token_hash, role FROM password_resets WHERE email = ?",
                (CAND_MAIL,)).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == db.hash_reset_token(token)
        assert row[0] != token
        assert row[1] == "candidate"

        # Kette: der erzeugte Token funktioniert wirklich
        ok, code = logic.apply_password_reset(token, "ganzneupass1")
        assert (ok, code) == (True, "ok")
    finally:
        _cleanup()


def test_runner_rate_limit_blocks_fourth(monkeypatch, tmp_path):
    _cleanup()
    try:
        _insert_candidate(logic.hash_password_argon2id("altpasswort1"))
        statuses = []
        for _ in range(4):
            r, _, _ = _run_runner(
                _payload(CAND_MAIL, "candidate"), monkeypatch, tmp_path)
            statuses.append(r["status"])
        assert statuses[:3] == ["sent", "sent", "sent"]
        assert statuses[3] == "rate_limited"
    finally:
        _cleanup()


def test_mcp_log_whitelist_excludes_body_and_recipient():
    """Der Live-MCP-Nachweislog schreibt weder Body noch Empfängeradresse (DSGVO)."""
    import tempfile
    from unittest.mock import patch as _patch
    with tempfile.TemporaryDirectory() as d:
        with _patch.object(mod, "PROJECT_ROOT", Path(d)):
            mod._mcp_log_live("mcp-email-server.py", "send_email",
                              {"to": "a@b.de", "subject": "s",
                               "body": "TOKEN-GEHEIM-123"}, True)
            txt = (Path(d) / "logs" / "mcp-calls.log").read_text(encoding="utf-8")
    assert "TOKEN-GEHEIM-123" not in txt
    assert "a@b.de" not in txt
    assert '"subject": "s"' in txt


def test_runner_dispatch_enthaelt_send_password_reset():
    import inspect
    src = inspect.getsource(mod.process_task)
    assert 'task_type == "send_password_reset"' in src


@pytest.mark.parametrize("role,email,table,inserter", [
    ("candidate", CAND_MAIL, "candidates", _insert_candidate),
    ("employer", EMP_MAIL, "employers", _insert_employer),
])
def test_runner_role_picks_target_table(role, email, table, inserter, monkeypatch, tmp_path):
    """Zieltabelle folgt dem Tab-Kontext (role): der erzeugte Token setzt das
    Passwort in der richtigen Tabelle — und nur dort."""
    _cleanup()
    try:
        inserter(logic.hash_password_argon2id("altpasswort1"))
        result, captured, _ = _run_runner(
            _payload(email, role), monkeypatch, tmp_path)
        assert result["status"] == "sent"
        token = captured["args"]["body"].split("/login?reset=")[1].split()[0].strip()
        conn = _conn()
        try:
            stored = conn.execute(
                "SELECT role FROM password_resets WHERE email = ?", (email,)).fetchone()
        finally:
            conn.close()
        assert stored and stored[0] == role
        ok, code = logic.apply_password_reset(token, "zielneupass1")
        assert (ok, code) == (True, "ok")
        assert logic.verify_password_argon2id(
            "zielneupass1", _pw_hash_of(email, table))
    finally:
        _cleanup()


@pytest.mark.parametrize("role,email,inserter", [
    ("candidate", CAND_MAIL, _insert_candidate),
    ("employer", EMP_MAIL, _insert_employer),
])
def test_payload_ohne_adresse_sendet_trotzdem(role, email, inserter, monkeypatch, tmp_path):
    """Payload nur role + id (30.10.2026): kein '@', der Runner lädt die Adresse selbst."""
    _cleanup()
    try:
        inserter(logic.hash_password_argon2id("altpasswort1"))
        payload = _payload(email, role)
        assert "@" not in json.dumps(payload)
        assert set(payload) == {"role", "id"}
        result, captured, log_text = _run_runner(payload, monkeypatch, tmp_path)
        assert result["status"] == "sent"
        assert captured["args"]["to"] == email
        assert email not in log_text
        assert email not in json.dumps(result)
    finally:
        _cleanup()


def test_alt_task_mit_email_im_payload_funktioniert_weiter(monkeypatch, tmp_path):
    """Übergang: vor der Umstellung gequeuete Tasks tragen noch `email`."""
    _cleanup()
    try:
        _insert_candidate(logic.hash_password_argon2id("altpasswort1"))
        result, captured, _ = _run_runner(
            {"email": CAND_MAIL, "role": "candidate"}, monkeypatch, tmp_path)
        assert result["status"] == "sent"
    finally:
        _cleanup()


def test_unbekannte_id_erzeugt_keine_mail_und_keine_adresse_im_log(monkeypatch, tmp_path):
    _cleanup()
    try:
        result, captured, log_text = _run_runner(
            {"role": "employer", "id": 999999999}, monkeypatch, tmp_path)
        assert result["status"] == "no_account"
        assert captured == {}
        assert "@" not in log_text
    finally:
        _cleanup()


def test_login_queued_nur_role_und_id():
    """Quelltext-Vertrag: Die Reset-UI queued bei Treffer role + id, keine Adresse."""
    src = (ROOT / "webui" / "pages" / "login.py").read_text(encoding="utf-8")
    block = src.split('db.queue_agent_task("send_password_reset", {', 1)[1].split("})", 1)[0]
    assert '"id": konto_id' in block
    assert '"role": _reset_ctx["role"]' in block
    assert "email" not in block
