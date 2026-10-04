"""Onboarding-Mail: send_onboarding_mail-Variante-A-Guard (23.09.2026).

NEGATIV: kein trigger  → RuntimeError, mcp_call=0
NEGATIV: Status != eingestellt → RuntimeError, mcp_call=0
POSITIV: Status=eingestellt + trigger → mcp_call genau 1x (GEMOCKT, nie echte Mail)
LOG:    process_task(task_type='onboarding_release') → finish_task(ok=False) + Log-Zeile
        „FEHLER … Variante A verletzt", mcp_call=0
        (Mail-Aufruf hängt am Produktions-Task onboarding_release, employer.py:680;
        es gibt KEINEN eigenen task_type "send_onboarding_mail")

Guard-Reihenfolge: trigger-Check ZUERST, dann Status-Check.

DB-Fakten (read-only, Stand 23.09.2026):
  application #24 status=eingestellt candidate_id=24→16 job_id=6 (POSITIV)
  candidate #16 email=e2e-beweis-phase1@example.com name='E2E Beweis Phase1'
  job #6 'E2E-Beweis: Teststelle Phase1 (m/w/d)'
  application #23 status=eingegangen candidate_id=13 (NEGATIV-Status)
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("agent_runner", BASE / "scripts" / "agent-runner.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

POS_PAYLOAD = {"application_id": 24, "candidate_id": 16, "job_id": 6, "trigger": "hr_klick_portal"}
BAD_STATUS_PAYLOAD = {"application_id": 23, "candidate_id": 13, "job_id": 1, "trigger": "hr_klick_portal"}
NO_TRIGGER_PAYLOAD = {"application_id": 24, "candidate_id": 16, "job_id": 6}  # ohne trigger


class TestSendOnboardingGuard(unittest.TestCase):

    def test_negativ_kein_trigger_blockiert_ohne_mail(self):
        with patch.object(mod, "mcp_call") as m:
            with self.assertRaises(RuntimeError) as ctx:
                mod.send_onboarding_mail(dict(NO_TRIGGER_PAYLOAD))
        self.assertIn("nur nach HR-Klick", str(ctx.exception))
        m.assert_not_called()
        print(f"GUARD BLOCKED (kein trigger) — {ctx.exception} — mcp_call=0")

    def test_negativ_status_nicht_eingestellt_blockiert_ohne_mail(self):
        # BAD_STATUS hat trigger → Status-Check wird erreicht (Reihenfolge: trigger zuerst)
        with patch.object(mod, "mcp_call") as m:
            with self.assertRaises(RuntimeError) as ctx:
                mod.send_onboarding_mail(dict(BAD_STATUS_PAYLOAD))
        self.assertIn("nur bei Status 'eingestellt'", str(ctx.exception))
        m.assert_not_called()
        print(f"GUARD BLOCKED (status) — {ctx.exception} — mcp_call=0")

    def test_positiv_eingestellt_mit_trigger_mail_gemockt(self):
        with patch.object(mod, "mcp_call", return_value="OK|Gesendet an test@example.invalid") as m:
            res = mod.send_onboarding_mail(dict(POS_PAYLOAD))
        m.assert_called_once()
        self.assertEqual(m.call_args[0][1], "send_email")
        self.assertIn("mail", res)
        self.assertTrue(res["to"])
        print(f"GUARD PASSED — mcp_call=1 (GEMOCKT, keine echte Mail) — to={res['to']}")

    def test_negativ_process_task_log_zeile_und_failed(self):
        conn = MagicMock()
        logs, finishes = [], []

        def _finish(*args, **kwargs):
            finishes.append((args, kwargs))

        with patch.object(mod, "claim_task", return_value=True), \
             patch.object(mod, "finish_task", side_effect=_finish), \
             patch.object(mod, "log", side_effect=lambda m: logs.append(m)), \
             patch.object(mod, "ERGEBNISSE", Path(tempfile.mkdtemp(prefix="kmhr-onb-"))), \
             patch.object(mod, "mcp_call") as m:
            mod.process_task(conn, 999999, "onboarding_release",
                             json.dumps(NO_TRIGGER_PAYLOAD), attempts=0)

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
