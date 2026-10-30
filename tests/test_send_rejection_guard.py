"""O2/C1: send_rejection-Variante-A-Guard (23.09.2026).

NEGATIV: kein trigger  → RuntimeError, mcp_call=0
NEGATIV: Status != abgelehnt → RuntimeError, mcp_call=0
POSITIV: Status=abgelehnt + trigger → mcp_call genau 1x (GEMOCKT, nie echte Mail)
LOG:    process_task → finish_task(ok=False) + Log-Zeile „FEHLER … Variante A verletzt", mcp_call=0

Zustands-Setup (27.09.2026, nach Isolation durch tests/conftest.py):
  DER Grund: send_rejection LIEST den Status (scripts/agent-runner.py:451ff,
  ohne jede Schreib-SQL) und verlangt fuer POS #17 "abgelehnt" sowie fuer NEG
  #23 "!= abgelehnt". Bislang wurde der Spiegel-Zustand zum Kopierzeitpunkt
  GEERBT => der Test war abhaengig vom Live-Status von #23 (und #17).
  Jetzt: setUp setzt den erwarteten Anfangszustand SELBST (in der
  Isolations-DB, unter pytest = prozesseigener Spiegel, nie die Live-DB),
  tearDown stellt wieder her. Fail-closed, falls die Isolation fehlt.
  Werte = DB-Fakten der Vorfassung (Stand 23.09.2026):
  application #17 status=abgelehnt candidate_id=10 (Mail vorhanden)
  application #23 status=eingegangen candidate_id=13
  Guard-Logik, Assertions, Baselines und Mail-Inhalt unveraendert.
"""
import importlib.util
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("agent_runner", BASE / "scripts" / "agent-runner.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

# ─── Eigenes Zustands-Setup (Isolation, 27.09.2026) ───────────────────────
LIVE_DB = (BASE / "data" / "feedback.db").resolve()

# Erwarteter Anfangszustand. Quelle der konkreten Werte: DB-Fakten der
# Vorfassung (Stand 23.09.2026, siehe Docstring); der Guard-Vertrag selbst
# fordert nur "17 = abgelehnt" und "23 != abgelehnt" => Design-Entscheidung.
REQUIRED_STATUS = {17: "abgelehnt", 23: "eingegangen"}


def _isolated_conn() -> sqlite3.Connection:
    """Verbindung zur Isolations-DB (unter pytest = prozesseigener Spiegel).

    Fail-closed per FUNKTIONELLEM Nachweis: erst wird read-only sondiert,
    auf welcher Datei der Zugriff landet — landet er auf der Live-DB (also
    ohne aktive Umleitung, z. B. Direktlauf ohne tests/conftest.py), wird das
    Schreib-Setup VERWEIGERT statt in der Live-DB zu schreiben.
    (Erste Fassung pruehte mod.DB_PATH — das war FALSCH: DB_PATH zeigt immer
    auf die Live-Datei, umgeleitet wird in sqlite3.connect selbst. Beweis:
    type(sqlite3.connect) = builtin_function_or_method ohne conftest,
    = function mit conftest; PRAGMA database_list zeigt den Spiegel.)"""
    probe = sqlite3.connect(f"file:{Path(mod.DB_PATH)}?mode=ro", uri=True)
    try:
        landed = Path(probe.execute("PRAGMA database_list").fetchone()[2]).resolve()
    finally:
        probe.close()
    if landed == LIVE_DB:
        raise AssertionError(
            "Schreib-Setup verweigert: Zugriff landet auf der LIVE-DB "
            f"({landed}) — Isolation (tests/conftest.py) nicht aktiv?"
        )
    return sqlite3.connect(str(Path(mod.DB_PATH)))


POS_PAYLOAD = {"application_id": 17, "candidate_id": 10, "job_id": 6, "trigger": "hr_klick_portal"}
BAD_STATUS_PAYLOAD = {"application_id": 23, "candidate_id": 13, "job_id": 1, "trigger": "hr_klick_portal"}
NO_TRIGGER_PAYLOAD = {"application_id": 17, "candidate_id": 10, "job_id": 6}


class TestSendRejectionGuard(unittest.TestCase):

    def setUp(self):
        """Setzt den vom Guard erwarteten Zustand SELBST (statt ihn zu erben)."""
        conn = _isolated_conn()
        try:
            ids = tuple(REQUIRED_STATUS)
            marks = ",".join("?" * len(ids))
            self._pre = dict(conn.execute(
                f"SELECT id, status FROM applications WHERE id IN ({marks})", ids))
            if set(self._pre) != set(REQUIRED_STATUS):
                raise AssertionError(
                    "Testbewerbungen fehlen in der Isolations-DB: "
                    f"{sorted(self._pre)}"
                )
            conn.executemany(
                "UPDATE applications SET status=? WHERE id=?",
                [(s, i) for i, s in REQUIRED_STATUS.items()])
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        """Stellt die vorgefundenen Zustände wieder her (nur die Isolations-DB)."""
        conn = _isolated_conn()
        try:
            conn.executemany(
                "UPDATE applications SET status=? WHERE id=?",
                [(s, i) for i, s in self._pre.items()])
            conn.commit()
        finally:
            conn.close()

    def test_negativ_kein_trigger_blockiert_ohne_mail(self):
        with patch.object(mod, "mcp_call") as m:
            with self.assertRaises(RuntimeError) as ctx:
                mod.send_rejection(dict(NO_TRIGGER_PAYLOAD))
        self.assertIn("nur nach HR-Klick", str(ctx.exception))
        m.assert_not_called()
        print(f"GUARD BLOCKED (kein trigger) — {ctx.exception} — mcp_call=0")

    def test_negativ_status_nicht_abgelehnt_blockiert_ohne_mail(self):
        with patch.object(mod, "mcp_call") as m:
            with self.assertRaises(RuntimeError) as ctx:
                mod.send_rejection(dict(BAD_STATUS_PAYLOAD))
        self.assertIn("nur bei Status 'abgelehnt'", str(ctx.exception))
        m.assert_not_called()
        print(f"GUARD BLOCKED (status) — {ctx.exception} — mcp_call=0")

    def test_positiv_abgelehnt_mit_trigger_mail_gemockt(self):
        conn = _isolated_conn()
        try:
            email = conn.execute(
                "SELECT email FROM candidates WHERE id = ?", (10,)).fetchone()[0]
        finally:
            conn.close()
        self.assertTrue(email, "Seed-Kandidat #10 braucht eine E-Mail")
        with patch.object(mod, "mcp_call", return_value="OK|Gesendet an test@example.invalid") as m:
            res = mod.send_rejection(dict(POS_PAYLOAD))
        m.assert_called_once()
        self.assertEqual(m.call_args[0][1], "send_email")
        # Empfängeradresse steht im Tool-Argument (aus der DB), nicht im Ergebnis.
        self.assertEqual(m.call_args[0][2]["to"], email)
        self.assertIn("mail", res)
        self.assertNotIn("to", res)
        print("GUARD PASSED — mcp_call=1 (GEMOCKT, keine echte Mail) — kein 'to' im Ergebnis")

    def test_negativ_process_task_log_zeile_und_failed(self):
        conn = MagicMock()
        logs, finishes = [], []

        def _finish(*args, **kwargs):
            finishes.append((args, kwargs))

        with patch.object(mod, "claim_task", return_value=True), \
             patch.object(mod, "finish_task", side_effect=_finish), \
             patch.object(mod, "log", side_effect=lambda m: logs.append(m)), \
             patch.object(mod, "mcp_call") as m:
            mod.process_task(conn, 999999, "send_rejection",
                             json.dumps(BAD_STATUS_PAYLOAD), attempts=0)

        m.assert_not_called()
        self.assertEqual(len(finishes), 1, finishes)
        args, kwargs = finishes[0]
        ok = args[2]
        error = kwargs.get("error") or ""
        self.assertFalse(ok)
        self.assertIn("Variante A verletzt", error)
        self.assertTrue(any("FEHLER" in x and "Variante A verletzt" in x for x in logs), logs)
        print(f"LOG-ZEILE sichtbar + task ok=False — {error[:90]} — mcp_call=0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
