"""Zustellfehler (Bounce) per IMAP-DSN, 30.10.2026.

Spec: `knowledge/system/agent-automation.md` §3.2.

Belegt:
  * `scripts/mail_bounce.py::parse_dsn` erkennt nur harte Fehler (Action failed,
    Status 5.x.x) aus synthetischen DSN-Nachrichten.
  * Poller ist ohne `KMHR_BOUNCE_POLL_ENABLED=1` ein No-op (kein IMAP-Zugriff).
  * Doppelte Verarbeitung derselben DSN erzeugt keine zweite Zeile.
  * Ablage (agent_tasks) und Rückgabe enthalten keine E-Mail-Adresse.
  * Gebouncte Adresse sperrt den weiteren Welcome-Versand des Kontos.

Isolation: `tests/conftest.py` leitet die DB in einen /tmp-Spiegel um.
Der IMAP-Zugriff ist vollständig durch eine Fake-Klasse ersetzt.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from webui import db

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mail_bounce  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "agent_runner_bounce", ROOT / "scripts" / "agent-runner.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

BOUNCE_MAIL = "bounce-test-cand@example.invalid"


def _dsn(recipient: str, status: str = "5.1.1", action: str = "failed",
         message_id: str = "<dsn-test-1@example.invalid>") -> bytes:
    return (
        "From: MAILER-DAEMON@example.invalid\n"
        f"Message-ID: {message_id}\n"
        "Subject: Delivery Status Notification (Failure)\n"
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/report; report-type=delivery-status; boundary="BND"\n'
        "\n"
        "--BND\n"
        "Content-Type: text/plain\n"
        "\n"
        "Undeliverable.\n"
        "\n"
        "--BND\n"
        "Content-Type: message/delivery-status\n"
        "\n"
        "Reporting-MTA: dns; example.invalid\n"
        "\n"
        f"Final-Recipient: rfc822; {recipient}\n"
        f"Action: {action}\n"
        f"Status: {status}\n"
        "Diagnostic-Code: smtp; 550 user unknown\n"
        "\n"
        "--BND--\n"
    ).encode("utf-8")


class FakeIMAP:
    """Minimaler IMAP4-Ersatz: liefert feste Nachrichten, zählt Login/Verbindungen."""

    instances = 0

    def __init__(self, host, port, messages):
        FakeIMAP.instances += 1
        self.messages = messages

    def login(self, user, password):
        return ("OK", [b"logged in"])

    def select(self, mailbox, readonly=False):
        return ("OK", [b"1"])

    def search(self, charset, *criteria):
        return ("OK", [" ".join(str(i + 1) for i in range(len(self.messages))).encode()])

    def fetch(self, num, what):
        raw = self.messages[int(num) - 1]
        return ("OK", [(b"1 (BODY[] {%d}" % len(raw), raw), b")"])

    def logout(self):
        return ("BYE", [b""])


def _factory(messages):
    return lambda host, port: FakeIMAP(host, port, messages)


def _env(enabled: bool = True) -> dict:
    env = {"KMHR_IMAP_HOST": "imap.example.invalid", "KMHR_IMAP_USER": "u",
           "KMHR_IMAP_PASSWORD": "geheim"}
    if enabled:
        env["KMHR_BOUNCE_POLL_ENABLED"] = "1"
    return env


def _insert_candidate() -> int:
    conn = db.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO candidates (email, name, password_hash, status) "
            "VALUES (?, 'Bounce Test', 'x', 'registriert')", (BOUNCE_MAIL,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _cleanup() -> None:
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM agent_tasks WHERE task_type = 'mail_bounce' "
                     "AND json_extract(payload, '$.role') = 'candidate' "
                     "AND json_extract(payload, '$.id') IN "
                     "(SELECT id FROM candidates WHERE email = ?)", (BOUNCE_MAIL,))
        conn.execute("DELETE FROM candidates WHERE email = ?", (BOUNCE_MAIL,))
        conn.commit()
    finally:
        conn.close()


def _bounce_rows(cid: int) -> list[tuple]:
    conn = db.get_conn()
    try:
        return conn.execute(
            "SELECT payload, result_json FROM agent_tasks WHERE task_type = 'mail_bounce' "
            "AND json_extract(payload, '$.id') = ?", (cid,)).fetchall()
    finally:
        conn.close()


# ─── Parser ──────────────────────────────────────────────────────────────

def test_parse_dsn_erkennt_harten_fehler():
    treffer = mail_bounce.parse_dsn(_dsn(BOUNCE_MAIL))
    assert len(treffer) == 1
    assert treffer[0]["address"] == BOUNCE_MAIL
    assert treffer[0]["status"] == "5.1.1"


def test_parse_dsn_ignoriert_weichen_fehler():
    assert mail_bounce.parse_dsn(_dsn(BOUNCE_MAIL, status="4.2.2")) == []


def test_parse_dsn_ignoriert_nicht_fehlgeschlagen():
    assert mail_bounce.parse_dsn(_dsn(BOUNCE_MAIL, action="delayed")) == []


def test_parse_dsn_ignoriert_gewoehnliche_mail():
    raw = b"From: a@example.invalid\nSubject: Hallo\n\nText\n"
    assert mail_bounce.parse_dsn(raw) == []


# ─── Poller ──────────────────────────────────────────────────────────────

def test_poll_ohne_flag_ist_noop(monkeypatch):
    FakeIMAP.instances = 0

    def boom(host, port):
        raise AssertionError("IMAP darf ohne Flag nicht angesprochen werden")

    res = mail_bounce.poll_bounces(env=_env(enabled=False), imap_factory=boom)
    assert res == {"status": "disabled"}
    assert FakeIMAP.instances == 0


def test_poll_erfasst_einmal_und_dedupliziert():
    _cleanup()
    try:
        cid = _insert_candidate()
        messages = [_dsn(BOUNCE_MAIL)]
        res1 = mail_bounce.poll_bounces(env=_env(), imap_factory=_factory(messages))
        assert res1["erfasst"] == 1 and res1["duplikat"] == 0
        res2 = mail_bounce.poll_bounces(env=_env(), imap_factory=_factory(messages))
        assert res2["erfasst"] == 0 and res2["duplikat"] == 1
        assert len(_bounce_rows(cid)) == 1
    finally:
        _cleanup()


def test_poll_speichert_keine_adresse():
    _cleanup()
    try:
        cid = _insert_candidate()
        res = mail_bounce.poll_bounces(env=_env(), imap_factory=_factory([_dsn(BOUNCE_MAIL)]))
        assert BOUNCE_MAIL not in repr(res)
        rows = _bounce_rows(cid)
        assert rows, "Zeile fehlt"
        for payload, result_json in rows:
            assert "@" not in payload
            assert result_json is None or "@" not in result_json
            data = json.loads(payload)
            assert set(data) == {"role", "id", "dsn", "status"}
            assert data["role"] == "candidate"
    finally:
        _cleanup()


def test_poll_unbekannte_adresse_erzeugt_keine_zeile():
    _cleanup()
    try:
        res = mail_bounce.poll_bounces(
            env=_env(),
            imap_factory=_factory([_dsn("niemand@example.invalid")]))
        assert res["unbekannt"] == 1 and res["erfasst"] == 0
        assert "niemand@example.invalid" not in repr(res)
    finally:
        _cleanup()


# ─── Welcome-Sperre ──────────────────────────────────────────────────────

def test_gebouncte_adresse_blockiert_welcome(monkeypatch, tmp_path):
    _cleanup()
    try:
        cid = _insert_candidate()
        mail_bounce.poll_bounces(env=_env(), imap_factory=_factory([_dsn(BOUNCE_MAIL)]))
        captured = {}

        def fake_mcp_call(server, tool, args):
            captured["called"] = True
            return "OK (gemockt)"

        monkeypatch.setattr(mod, "mcp_call", fake_mcp_call)
        monkeypatch.setattr(mod, "LOG_FILE", tmp_path / "agent-runner.log")
        res = mod.send_welcome({"role": "candidate", "id": cid, "language": "de"})
        assert res == {"status": "skipped", "grund": "zustellfehler"}
        assert "called" not in captured
    finally:
        _cleanup()


def test_welcome_ohne_bounce_wird_gesendet(monkeypatch, tmp_path):
    _cleanup()
    try:
        cid = _insert_candidate()
        monkeypatch.setattr(mod, "mcp_call", lambda s, t, a: "OK (gemockt)")
        monkeypatch.setattr(mod, "LOG_FILE", tmp_path / "agent-runner.log")
        res = mod.send_welcome({"role": "candidate", "id": cid, "language": "de"})
        assert res == {"status": "sent"}
    finally:
        _cleanup()
