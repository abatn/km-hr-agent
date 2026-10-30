"""Willkommensmail-Registrierung (Plan v2, 30.10.2026).

Deckt die Schnittstellen aus `webui/db.py` und `scripts/agent-runner.py` ab:

  FEHLER   send_welcome/send_confirmation/send_rejection werfen bei
           "FEHLER:"-Text eine RuntimeError (mcp_call IMMER gemockt).
  RETRY    process_task('send_welcome') → finish_task(ok=False), nie "done".
  IDEMPOTENZ  done/pending/running blockieren (auch mit created_at gestern);
           failed erlaubt Neuanlage; gleiche id + andere Rolle → 2 Tasks;
           zwei parallele Aufrufe → genau ein Task.
  CONSENT  finalize_registration: record_consents wirft →
           RegistrationConsentError, Konto + consents kompensiert, kein Task.
           complete_registration: derselbe Fall → REGISTRATION_ERROR (kein
           raise); erfolgreicher Consent → REGISTRATION_OK + genau ein Task.
  NACHLAUF finalize_registration überlebt queue_welcome- und
           insert_notification-Fehler (Konto ist committet, kein raise).
  KONTO    geloeschtes Konto → skipped/kein_konto, mcp_call=0.
  FLAG     KMHR_WELCOME_MAIL=0 → kein Task; =1 → genau ein Task.
  PII      Payload und Ergebnis enthalten kein "@" (Adresse nur aus der DB);
           sie steht ausschliesslich im mcp_call-Argument "to".
           finish_task maskiert auch error_text ("a@b.de" → "<EMAIL>").
  DRY-RUN  "DRY-RUN" → {"status": "dry_run"} (kein Fehler).
  LOG      mcp_call schreibt ein "FEHLER"-Ergebnis als ok=False nach
           logs/mcp-calls.log (echter Fake-MCP-Server, echte Datei).
  URL      build_welcome_mail nutzt KMHR_PUBLIC_BASE_URL für /login,
           /employer und /datenschutz.
  I18N     build_welcome_mail de/en/fr/ar verschieden; Fremdadressen-Hinweis
           in allen vier Sprachen; Arbeitgebertext ohne Werbe-/Garantieworte;
           leerer Name → neutrale Anrede tr("Guten Tag,") in allen Sprachen.

Isolation: tests/conftest.py spiegelt tests/fixtures/seed.db; alle Writes
laufen gegen den Spiegel (fail-closed über `_db()`). Test-Rows tragen IDs
>= 900000 und werden in setUp/tearDown entfernt.
"""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("agent_runner", BASE / "scripts" / "agent-runner.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

from webui import db as webui_db  # noqa: E402  (nach dem Runner-Import: sys.path gesetzt)

LIVE_DB = (BASE / "data" / "feedback.db").resolve()
TEST_ID_MIN = 900000
_ids = iter(range(900100, 901000))

FREMDADRESSEN_HINWEISE = {
    "de": "Falls Sie kein Konto bei uns angelegt haben, ignorieren Sie diese Nachricht.",
    "en": "If you did not create an account with us, please ignore this message.",
    "fr": "Si vous n'avez pas créé de compte chez nous, veuillez ignorer ce message.",
    "ar": "إذا لم تنشئ حساباً لدينا، يرجى تجاهل هذه الرسالة.",
}

# Minimaler MCP-Server (stdio-JSON-RPC) für den echten Log-Schreibtest:
# antwortet auf id=1 mit initialize und auf id=2 mit einem "FEHLER"-Text.
FAKE_MCP_SERVER = '''\
import json
import sys


def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\\n")
    sys.stdout.flush()


for _line in sys.stdin:
    _line = _line.strip()
    if not _line:
        continue
    try:
        _req = json.loads(_line)
    except json.JSONDecodeError:
        continue
    if _req.get("id") == 1:
        _send({"jsonrpc": "2.0", "id": 1,
               "result": {"protocolVersion": "2024-11-05", "capabilities": {},
                          "serverInfo": {"name": "fake-mcp", "version": "1.0"}}})
    elif _req.get("id") == 2:
        _send({"jsonrpc": "2.0", "id": 2,
               "result": {"content": [{"type": "text", "text": "FEHLER: test"}],
                          "isError": False}})
        break
'''


def _db() -> sqlite3.Connection:
    """Verbindung zum DB-Spiegel; verweigert Writes auf der Live-DB (fail-closed)."""
    conn = sqlite3.connect(str(webui_db.AGENT_TASKS_DB))
    landed = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    if landed == LIVE_DB:
        conn.close()
        raise AssertionError(
            f"Zugriff landet auf der LIVE-DB ({landed}) — Isolation "
            "(tests/conftest.py) nicht aktiv?"
        )
    return conn


def _delete_test_tasks() -> None:
    """Entfernt alle send_welcome-Test-Rows (ID >= TEST_ID_MIN) aus dem Spiegel."""
    conn = _db()
    try:
        conn.execute(
            """DELETE FROM agent_tasks
               WHERE task_type = 'send_welcome'
                 AND CAST(json_extract(payload, '$.id') AS INTEGER) >= ?""",
            (TEST_ID_MIN,),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_task(role: str, sid: int, status: str, yesterday: bool = False) -> int:
    """Legt eine send_welcome-Row direkt an (created_at optional gestern)."""
    payload = json.dumps({"role": role, "id": int(sid), "language": "de"},
                         ensure_ascii=False, sort_keys=True)
    created = "datetime('now', '-1 day')" if yesterday else "CURRENT_TIMESTAMP"
    conn = _db()
    try:
        cur = conn.execute(
            f"INSERT INTO agent_tasks (task_type, payload, status, created_at) "
            f"VALUES ('send_welcome', ?, ?, {created})",
            (payload, status),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _delete_test_accounts() -> None:
    """Entfernt Test-Konten (ID >= TEST_ID_MIN), ihre consents und Notifications."""
    conn = _db()
    try:
        conn.execute(
            "DELETE FROM consents WHERE subject_id >= ? "
            "AND subject_type IN ('candidate', 'employer')",
            (TEST_ID_MIN,),
        )
        conn.execute("DELETE FROM candidates WHERE id >= ?", (TEST_ID_MIN,))
        conn.execute("DELETE FROM employers WHERE id >= ?", (TEST_ID_MIN,))
        conn.execute("DELETE FROM notifications WHERE user_id >= ?", (TEST_ID_MIN,))
        conn.commit()
    finally:
        conn.close()


def _insert_candidate(sid: int) -> str:
    """Legt ein Test-Konto mit eindeutiger ID/E-Mail im Spiegel an."""
    email = f"welcome-test-{sid}@example.invalid"
    conn = _db()
    try:
        conn.execute(
            "INSERT INTO candidates (id, email, password_hash, name, status) "
            "VALUES (?, ?, 'x', 'Welcome Test', 'registriert')",
            (sid, email),
        )
        conn.commit()
    finally:
        conn.close()
    return email


def _candidate_row(sid: int):
    conn = _db()
    try:
        return conn.execute(
            "SELECT id, email FROM candidates WHERE id = ?", (sid,)).fetchone()
    finally:
        conn.close()


def _consent_rows(subject_id: int) -> list:
    conn = _db()
    try:
        return conn.execute(
            "SELECT purpose FROM consents WHERE subject_type = 'candidate' "
            "AND subject_id = ? ORDER BY purpose", (int(subject_id),)).fetchall()
    finally:
        conn.close()


def _task_rows(role: str, sid: int) -> list:
    conn = _db()
    try:
        return conn.execute(
            """SELECT id, status, payload FROM agent_tasks
               WHERE task_type = 'send_welcome'
                 AND json_extract(payload, '$.role') = ?
                 AND json_extract(payload, '$.id') = ?""",
            (role, int(sid)),
        ).fetchall()
    finally:
        conn.close()


class TestWelcomeMail(unittest.TestCase):

    def setUp(self):
        _delete_test_tasks()
        _delete_test_accounts()
        self._env = patch.dict(os.environ, {"KMHR_WELCOME_MAIL": "1"})
        self._env.start()

    def tearDown(self):
        _delete_test_tasks()
        _delete_test_accounts()
        self._env.stop()

    # ─── FEHLER-Text → RuntimeError ─────────────────────────────────────

    def test_send_welcome_fehler_wirft_runtimeerror(self):
        with patch.object(mod, "mcp_call",
                          return_value="FEHLER: SMTP-Auth fehlgeschlagen") as m:
            with self.assertRaises(RuntimeError) as ctx:
                mod.send_welcome({"role": "candidate", "id": 10, "language": "de"})
        self.assertIn("SMTP-Auth", str(ctx.exception))
        m.assert_called_once()
        self.assertEqual(m.call_args[0][1], "send_email")

    def test_send_welcome_dry_run_meldet_dry_run(self):
        """DRY-RUN ist kein Fehler, sondern ein eigener Status."""
        with patch.object(mod, "mcp_call", return_value="DRY-RUN") as m:
            res = mod.send_welcome({"role": "candidate", "id": 10, "language": "de"})
        self.assertEqual(res, {"status": "dry_run"})
        m.assert_called_once()
        self.assertEqual(m.call_args[0][1], "send_email")

    def test_send_confirmation_fehler_wirft_runtimeerror(self):
        with patch.object(mod, "mcp_call",
                          return_value="FEHLER: SMTP-Auth fehlgeschlagen") as m:
            with self.assertRaises(RuntimeError) as ctx:
                mod.send_confirmation({"candidate_id": 10, "language": "de"})
        self.assertIn("SMTP-Auth", str(ctx.exception))
        m.assert_called_once()
        self.assertEqual(m.call_args[0][1], "send_email")

    def test_send_rejection_fehler_wirft_runtimeerror(self):
        # Seed: App #17 = abgelehnt, Kandidat #10. Status im finally restaurieren.
        conn = _db()
        try:
            pre = conn.execute(
                "SELECT status FROM applications WHERE id = 17").fetchone()[0]
            conn.execute("UPDATE applications SET status = 'abgelehnt' WHERE id = 17")
            conn.commit()
            try:
                payload = {"application_id": 17, "candidate_id": 10,
                           "trigger": "hr_klick_portal", "language": "de"}
                with patch.object(mod, "mcp_call",
                                  return_value="FEHLER: SMTP-Auth fehlgeschlagen") as m:
                    with self.assertRaises(RuntimeError) as ctx:
                        mod.send_rejection(dict(payload))
                self.assertIn("SMTP-Auth", str(ctx.exception))
                m.assert_called_once()
                self.assertEqual(m.call_args[0][1], "send_email")
            finally:
                conn.execute("UPDATE applications SET status = ? WHERE id = 17", (pre,))
                conn.commit()
        finally:
            conn.close()

    # ─── Retry: process_task meldet ok=False, nie "done" ───────────────

    def test_process_task_send_welcome_fehler_finish_task_false(self):
        conn = MagicMock()
        finishes, logs = [], []

        def _finish(*args, **kwargs):
            finishes.append((args, kwargs))
            return "pending"

        payload = {"role": "candidate", "id": 10, "language": "de"}
        with patch.object(mod, "claim_task", return_value=True), \
             patch.object(mod, "finish_task", side_effect=_finish), \
             patch.object(mod, "log", side_effect=lambda m: logs.append(m)), \
             patch.object(mod, "mcp_call",
                          return_value="FEHLER: SMTP-Auth fehlgeschlagen") as m:
            mod.process_task(conn, 999998, "send_welcome",
                             json.dumps(payload), attempts=0)

        m.assert_called_once()
        self.assertEqual(len(finishes), 1, finishes)
        args, kwargs = finishes[0]
        self.assertFalse(args[2], "finish_task darf nicht mit ok=True (done) laufen")
        self.assertIn("FEHLER", kwargs.get("error") or "")
        self.assertFalse(any(a[2] for a, _ in finishes), finishes)
        self.assertTrue(any("FEHLER" in x for x in logs), logs)

    # ─── Idempotenz ────────────────────────────────────────────────────

    def test_idempotenz_done_pending_running_blockieren_auch_gestern(self):
        for status in ("done", "pending", "running"):
            sid = next(_ids)
            _insert_task("candidate", sid, status, yesterday=True)
            self.assertIsNone(
                webui_db.queue_welcome("candidate", sid),
                f"Status '{status}' (created_at gestern) muss blockieren",
            )
            self.assertEqual(len(_task_rows("candidate", sid)), 1, status)

    def test_idempotenz_failed_erlaubt_neuanlage(self):
        sid = next(_ids)
        _insert_task("candidate", sid, "failed", yesterday=True)
        tid = webui_db.queue_welcome("candidate", sid)
        self.assertIsInstance(tid, int)
        self.assertEqual(len(_task_rows("candidate", sid)), 2)

    def test_idempotenz_gleiche_id_andere_rolle_zwei_tasks(self):
        sid = next(_ids)
        _insert_task("candidate", sid, "done")
        tid = webui_db.queue_welcome("employer", sid)
        self.assertIsInstance(tid, int)
        self.assertEqual(len(_task_rows("candidate", sid)), 1)
        self.assertEqual(len(_task_rows("employer", sid)), 1)

    def test_idempotenz_parallele_aufrufe_genau_ein_task(self):
        sid = next(_ids)
        barrier = threading.Barrier(2)
        results, errors = [], []

        def worker():
            try:
                barrier.wait(timeout=10)
                results.append(webui_db.queue_welcome("candidate", sid))
            except Exception as e:  # Thread-Fehler sichtbar machen
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        self.assertFalse(errors, errors)
        self.assertEqual(len(results), 2, results)
        self.assertEqual(sum(1 for r in results if isinstance(r, int)), 1, results)
        self.assertEqual(sum(1 for r in results if r is None), 1, results)
        self.assertEqual(len(_task_rows("candidate", sid)), 1)

    # ─── finalize_registration: Consent zuerst ─────────────────────────

    def test_finalize_registration_consent_fehler_kein_task(self):
        """Consent wirft → RegistrationConsentError, Konto + consents weg, kein Task."""
        sid = next(_ids)
        _insert_candidate(sid)
        written = []

        def record_then_boom():
            written.append(
                webui_db.record_consent("candidate", sid, "terms", language="de"))
            raise ValueError("consent kaputt")

        with self.assertRaises(webui_db.RegistrationConsentError) as ctx:
            webui_db.finalize_registration("candidate", sid, "de", record_then_boom)

        self.assertIn("consent kaputt", str(ctx.exception))
        self.assertEqual(len(written), 1, "Consent-Zeile muss vor dem Fehler existieren")
        self.assertIsNone(_candidate_row(sid), "Konto muss kompensiert sein")
        self.assertEqual(_consent_rows(sid), [], "consents müssen gelöscht sein")
        self.assertEqual(len(_task_rows("candidate", sid)), 0)

    def test_complete_registration_consent_fehler_error_und_kompensation(self):
        """complete_registration wirft nie: Consent-Fehler → REGISTRATION_ERROR + Löschung."""
        sid = next(_ids)
        _insert_candidate(sid)
        written = []

        def record_then_boom():
            written.append(
                webui_db.record_consent("candidate", sid, "privacy", language="de"))
            raise RuntimeError("consent kaputt")

        outcome = webui_db.complete_registration("candidate", sid, "de", record_then_boom)

        self.assertEqual(outcome, webui_db.REGISTRATION_ERROR)
        self.assertEqual(len(written), 1, "Consent-Zeile muss vor dem Fehler existieren")
        self.assertIsNone(_candidate_row(sid), "Konto muss kompensiert sein")
        self.assertEqual(_consent_rows(sid), [], "consents müssen gelöscht sein")
        self.assertEqual(len(_task_rows("candidate", sid)), 0)

    def test_complete_registration_consent_ok_konto_und_genau_ein_task(self):
        """Erfolgreicher Consent (Flag 1) → REGISTRATION_OK, Konto bleibt, ein Task."""
        sid = next(_ids)
        _insert_candidate(sid)
        called = []

        def record_ok():
            webui_db.record_consent("candidate", sid, "terms", language="de")
            called.append(1)

        outcome = webui_db.complete_registration("candidate", sid, "de", record_ok)

        self.assertEqual(outcome, webui_db.REGISTRATION_OK)
        self.assertEqual(called, [1], "Consent-Callable muss genau einmal laufen")
        self.assertIsNotNone(_candidate_row(sid), "Konto muss bestehen bleiben")
        self.assertEqual(_consent_rows(sid), [("terms",)])
        rows = _task_rows("candidate", sid)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(json.loads(rows[0][2])["id"], sid)

    # ─── finalize_registration: Nachlauf-Fehler nie weiterreichen ──────

    def test_finalize_registration_queue_fehler_kein_raise_und_none(self):
        """Konto ist committet: queue_welcome-Fehler → None, kein raise."""
        sid = next(_ids)

        def boom(*_args, **_kwargs):
            raise RuntimeError("queue kaputt")

        with patch.object(webui_db, "queue_welcome", side_effect=boom), \
             patch.object(webui_db, "insert_notification") as notif:
            tid = webui_db.finalize_registration("candidate", sid, "de", lambda: None)
        self.assertIsNone(tid)
        notif.assert_called_once()
        self.assertEqual(len(_task_rows("candidate", sid)), 0)

    def test_finalize_registration_notification_fehler_task_bleibt(self):
        """insert_notification wirft → Registrierung lebt weiter, Task existiert."""
        sid = next(_ids)

        def boom(*_args, **_kwargs):
            raise RuntimeError("notifications-Tabelle kaputt")

        with patch.object(webui_db, "insert_notification", side_effect=boom):
            tid = webui_db.finalize_registration("candidate", sid, "de", lambda: None)
        self.assertIsInstance(tid, int)
        self.assertEqual(len(_task_rows("candidate", sid)), 1)

    # ─── Gelöschtes Konto ──────────────────────────────────────────────

    def test_send_welcome_konto_geloescht_uebersprungen(self):
        with patch.object(mod, "mcp_call") as m:
            res = mod.send_welcome({"role": "candidate", "id": 99999999})
        self.assertEqual(res, {"status": "skipped", "grund": "kein_konto"})
        m.assert_not_called()

    def test_send_welcome_arbeitgeber_konto_unbekannt_uebersprungen(self):
        with patch.object(mod, "mcp_call") as m:
            res = mod.send_welcome({"role": "employer", "id": 99999999})
        self.assertEqual(res, {"status": "skipped", "grund": "kein_konto"})
        m.assert_not_called()

    # ─── Feature-Flag ──────────────────────────────────────────────────

    def test_flag_aus_kein_task(self):
        sid = next(_ids)
        with patch.dict(os.environ, {"KMHR_WELCOME_MAIL": "0"}):
            self.assertIsNone(webui_db.queue_welcome("candidate", sid))
        self.assertEqual(len(_task_rows("candidate", sid)), 0)

    def test_flag_an_genau_ein_task(self):
        sid = next(_ids)
        with patch.dict(os.environ, {"KMHR_WELCOME_MAIL": "1"}):
            tid = webui_db.queue_welcome("candidate", sid)
            self.assertIsInstance(tid, int)
            self.assertIsNone(webui_db.queue_welcome("candidate", sid))
        rows = _task_rows("candidate", sid)
        self.assertEqual(len(rows), 1)
        payload = json.loads(rows[0][2])
        self.assertEqual(payload["language"], "de")
        self.assertNotIn("@", rows[0][2])

    # ─── Keine Adresse im Payload/Ergebnis ─────────────────────────────

    def test_send_welcome_ohne_email_im_payload_und_ergebnis(self):
        """Adresse nur im mcp_call-Argument; Payload/Ergebnis bleiben PII-frei."""
        conn = _db()
        try:
            email = conn.execute(
                "SELECT email FROM candidates WHERE id = 10").fetchone()[0]
        finally:
            conn.close()
        self.assertTrue(email, "Seed-Kandidat #10 braucht eine E-Mail")
        payload = {"role": "candidate", "id": 10, "language": "de"}
        with patch.object(mod, "mcp_call", return_value="OK|Gesendet") as m:
            res = mod.send_welcome(dict(payload))
        m.assert_called_once()
        self.assertEqual(m.call_args[0][1], "send_email")
        # Empfänger kommt aus dem DB-Lookup und steht im Tool-Argument.
        self.assertEqual(m.call_args[0][2]["to"], email)
        self.assertNotIn("@", json.dumps(res))
        self.assertNotIn(email, json.dumps(res))

    # ─── finish_task maskiert E-Mail in error_text ──────────────────────

    def test_finish_task_maskiert_email_im_error_text(self):
        with tempfile.TemporaryDirectory(prefix="kmhr-finish-") as tmp:
            path = Path(tmp) / "tasks.db"
            conn = sqlite3.connect(str(path))
            try:
                conn.execute("""CREATE TABLE agent_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending', payload TEXT NOT NULL, result_path TEXT,
                    result_json TEXT, error_text TEXT, attempts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, started_at TIMESTAMP,
                    finished_at TIMESTAMP)""")
                conn.execute(
                    "INSERT INTO agent_tasks (task_type, payload, attempts) "
                    "VALUES ('send_welcome', '{}', ?)", (mod.MAX_ATTEMPTS,))
                conn.commit()
                status = mod.finish_task(conn, 1, False,
                                         error="Kontakt a@b.de fehlt")
                self.assertEqual(status, "failed")
                error_text = conn.execute(
                    "SELECT error_text FROM agent_tasks WHERE id = 1").fetchone()[0]
                self.assertIn("Kontakt", error_text)
                self.assertNotIn("@", error_text)
                self.assertIn("<EMAIL>", error_text)
            finally:
                conn.close()

    # ─── MCP-Log: FEHLER-Ergebnis nie als "ok" ─────────────────────────

    def test_mcp_call_loggt_fehler_ergebnis_als_nicht_ok(self):
        """Echter Subprozess + echte Logdatei: "FEHLER: test" → ok=False."""
        with tempfile.TemporaryDirectory(prefix="kmhr-mcplog-") as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            server = root / "fake-mcp-server.py"
            server.write_text(FAKE_MCP_SERVER, encoding="utf-8")
            with patch.object(mod, "PROJECT_ROOT", root), \
                 patch.object(mod, "VENV_PY", Path(sys.executable)), \
                 patch.object(mod, "DRY_RUN", False), \
                 patch.object(mod, "MCP_TIMEOUT", 20):
                out = mod.mcp_call(server, "send_email",
                                   {"to": "niemand@example.invalid",
                                    "subject": "Test"})
            self.assertEqual(out, "FEHLER: test")
            log_datei = root / "logs" / "mcp-calls.log"
            self.assertTrue(log_datei.is_file(), "MCP-Log wurde nicht geschrieben")
            zeilen = [z for z in
                      log_datei.read_text(encoding="utf-8").splitlines() if z.strip()]
            self.assertEqual(len(zeilen), 1, zeilen)
            zeile = zeilen[0]
            self.assertIn("fake-mcp-server.py::send_email", zeile)
            self.assertIn("| FEHLER |", zeile)
            self.assertNotIn("| ok |", zeile)
            self.assertNotIn("niemand@example.invalid", zeile)

    # ─── i18n ──────────────────────────────────────────────────────────

    def test_build_welcome_mail_vier_sprachen_unterschiedlich(self):
        bodies = {}
        for lang in ("de", "en", "fr", "ar"):
            _subject, body = mod.build_welcome_mail("candidate", lang, name="Alex")
            bodies[lang] = body
            # Feste Erwartung je Sprache: ein DE-Fallback (tr() == msgid) wird rot.
            self.assertIn(FREMDADRESSEN_HINWEISE[lang], body,
                          f"Fremdadressen-Hinweis fehlt/falsch ({lang})")
        self.assertEqual(len(set(bodies.values())), 4,
                         "de/en/fr/ar müssen unterschiedliche Bodies liefern")

    def test_build_welcome_mail_arbeitgeber_ohne_werbeversprechen(self):
        verboten = ("kostenlos", "gratuit", "free", "garantie", "guaranteed")
        for lang in ("de", "en", "fr", "ar"):
            _subject, body = mod.build_welcome_mail(
                "employer", lang, name="Alex", firma="Beispiel GmbH")
            low = body.lower()
            for wort in verboten:
                self.assertNotIn(wort, low, f"{lang}: '{wort}' im Arbeitgebertext")

    def test_build_welcome_mail_ohne_namen_nutzt_neutrale_anrede(self):
        """Leerer Name → vorhandene Anrede tr("Guten Tag,") statt "Guten Tag ,"."""
        for lang in ("de", "en", "fr", "ar"):
            for leer in ("", "   "):
                _subject, body = mod.build_welcome_mail("candidate", lang, name=leer)
                anrede = mod.tr("Guten Tag,", lang)
                self.assertTrue(
                    body.startswith(anrede),
                    f"{lang} ({leer!r}): Body beginnt nicht mit {anrede!r}: "
                    f"{body[:50]!r}",
                )

    def test_build_welcome_mail_nutzt_kmhr_public_base_url(self):
        with patch.dict(os.environ,
                        {"KMHR_PUBLIC_BASE_URL": "https://example.test"}):
            for lang in ("de", "en", "fr", "ar"):
                _subject, body = mod.build_welcome_mail("candidate", lang, name="Alex")
                self.assertIn("https://example.test/login", body, lang)
                self.assertIn("https://example.test/datenschutz", body, lang)
                _subject, body = mod.build_welcome_mail(
                    "employer", lang, name="Alex", firma="Beispiel GmbH")
                self.assertIn("https://example.test/employer", body, lang)
                self.assertIn("https://example.test/datenschutz", body, lang)
        # Trailing Slash wird entfernt (kein doppelter Slash im Link).
        with patch.dict(os.environ,
                        {"KMHR_PUBLIC_BASE_URL": "https://example.test/"}):
            _subject, body = mod.build_welcome_mail("candidate", "de", name="Alex")
        self.assertIn("https://example.test/login", body)
        self.assertNotIn("https://example.test//login", body)

    # ─── zentrale Redaktion (result_json / MCP-Log) ─────────────────────

    def test_redact_result_entfernt_email_und_to(self):
        roh = {"status": "sent", "to": "test@example.invalid",
               "mail": "OK|Gesendet an test@example.invalid"}
        sauber = mod._redact_result(roh)
        self.assertNotIn("to", sauber)
        self.assertNotIn("@", json.dumps(sauber))

    def test_mcp_log_whitelist_ohne_to(self):
        self.assertNotIn("to", mod._MCP_LOG_ALLOWED_KEYS)

    def test_mcp_log_live_schreibt_weder_to_noch_email(self):
        """Echter _mcp_log_live-Lauf: Whitelist + Fehlertext-Maskierung."""
        with tempfile.TemporaryDirectory(prefix="kmhr-mcplog-") as tmp:
            root = Path(tmp)
            with patch.object(mod, "PROJECT_ROOT", root):
                mod._mcp_log_live(
                    "mcp-email-server.py", "send_email",
                    {"to": "a@b.de", "subject": "s"}, False, fehler="a@b.de")
            log_datei = root / "logs" / "mcp-calls.log"
            self.assertTrue(log_datei.is_file(), "MCP-Log wurde nicht geschrieben")
            txt = log_datei.read_text(encoding="utf-8")
        self.assertNotIn("@", txt)
        self.assertNotIn('"to"', txt)
        self.assertIn('"subject": "s"', txt)
        self.assertIn("| FEHLER |", txt)

    def test_mcp_call_dry_run_redigiert_args(self):
        """DRY-RUN loggt die Tool-Argumente maskiert (kein to, kein "@")."""
        logs = []
        with patch.object(mod, "DRY_RUN", True), \
             patch.object(mod, "log", side_effect=lambda m: logs.append(m)):
            out = mod.mcp_call(mod.EMAIL_SERVER, "send_email",
                               {"to": "a@b.de", "subject": "s"})
        self.assertEqual(out, "DRY-RUN")
        self.assertEqual(len(logs), 1, logs)
        self.assertNotIn("@", logs[0])
        self.assertNotIn('"to"', logs[0])
        self.assertIn('"subject": "s"', logs[0])

    # ─── Maskierung VOR dem Kürzen auf 200 Zeichen ─────────────────────

    def test_send_welcome_maskiert_vor_kuerzung(self):
        out_ok = "OK" + "x" * 190 + " a@b.de"
        with patch.object(mod, "mcp_call", return_value=out_ok):
            res = mod.send_welcome({"role": "candidate", "id": 10, "language": "de"})
        self.assertEqual(res, {"status": "sent"})
        self.assertNotIn("@", json.dumps(res))
        # Grenzfall: das Kürzen auf 200 Zeichen darf die Adresse nicht
        # zerschneiden, bevor sie maskiert wurde.
        out_fehler = "FEHLER: " + "x" * 185 + " a@b.de"
        with patch.object(mod, "mcp_call", return_value=out_fehler):
            with self.assertRaises(RuntimeError) as ctx:
                mod.send_welcome({"role": "candidate", "id": 10, "language": "de"})
        self.assertNotIn("@", str(ctx.exception))
        # Adresse endet exakt hinter der 200er-Grenze (Punkt bei Index 200):
        # Kürzen VOR dem Maskieren hinterließe "a@b" und würde rot.
        out_grenze = "FEHLER: " + "x" * 188 + " a@b.de"
        self.assertGreater(len(out_grenze), 200)
        with patch.object(mod, "mcp_call", return_value=out_grenze):
            with self.assertRaises(RuntimeError) as ctx:
                mod.send_welcome({"role": "candidate", "id": 10, "language": "de"})
        self.assertNotIn("@", str(ctx.exception))

    def test_send_confirmation_und_rejection_maskieren_vor_kuerzung(self):
        # 194 x: nach dem Kürzen bliebe "a@b" (ohne Punkt) stehen → nur
        # Maskieren VOR dem Kürzen liefert ein "@"-freies Ergebnis.
        out = "OK" + "x" * 194 + " a@b.de"
        with patch.object(mod, "mcp_call", return_value=out):
            res = mod.send_confirmation({"candidate_id": 10, "language": "de"})
        self.assertNotIn("@", json.dumps(res))
        # Kürzen VOR dem Maskieren würde "a@b" hinterlassen (kein Punkt mehr).
        self.assertNotIn("a@b", res["mail"])

        conn = _db()
        try:
            pre = conn.execute(
                "SELECT status FROM applications WHERE id = 17").fetchone()[0]
            conn.execute("UPDATE applications SET status = 'abgelehnt' WHERE id = 17")
            conn.commit()
            try:
                with patch.object(mod, "mcp_call", return_value=out):
                    res = mod.send_rejection(
                        {"application_id": 17, "candidate_id": 10,
                         "trigger": "hr_klick_portal", "language": "de"})
                self.assertNotIn("@", json.dumps(res))
                self.assertNotIn("a@b", res["mail"])
            finally:
                conn.execute("UPDATE applications SET status = ? WHERE id = 17", (pre,))
                conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
