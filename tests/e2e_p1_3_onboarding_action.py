#!/usr/bin/env python3
"""E2E P1-3 (29.09.2026): Onboarding-Leerzustand hat klickbaren Weg.

Read-only-Nachweis gegen die Live-App:
1. Login als Kandidat #1 (0 'eingestellt'-Bewerbungen → Empty-Zweig; Passwort
   aus tests/e2e_housing.py, gleicher Test-Login).
2. Onboarding-Tab: Empty-State + NEU Button „→ Stellen ansehen".
3. Klick → Stellen-Tab sichtbar (Sackgasse behoben).
4. DB-Baseline vor == nach (read-only).

Hinweis: S2a/S2b (Leertexte components.py) sind im Live-Datenstand nicht
erreichbar (Selbstpräsentationen + Profile existieren) → statisch verifiziert
(py_compile + Codepfad), ehrlich im Protokoll vermerkt.
Spec: skills/pre-screen/SKILL.md (Sackgassen-Regel P1-3) · Plan: ui-mvp-plan-v2 §6 P1-3
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from e2e_harness import BASE, DB, check_server  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CAND_EMAIL = "batniniabdelkader@yahoo.com"
CAND_PASSWORD = "Abdel15121978!"  # Test-Login aus tests/e2e_housing.py

failures: list[str] = []


def main() -> int:
    check_server()

    conn = sqlite3.connect(str(DB))
    before_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    before_tasks = conn.execute("SELECT COALESCE(MAX(id),0) FROM agent_tasks").fetchone()[0]
    conn.close()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        try:
            page.goto(f"{BASE}/login", wait_until="load")
            page.wait_for_timeout(2500)
            panel = page.locator(".q-tab-panel:visible").first
            panel.get_by_label("E-Mail").fill(CAND_EMAIL)
            panel.get_by_label("Passwort", exact=True).fill(CAND_PASSWORD)
            panel.get_by_role("button").first.click()
            page.wait_for_url("**/candidate**", timeout=15000)
            print("OK login cand1 (0 eingestellt-Apps → Empty-Zweig)")

            page.goto(f"{BASE}/candidate/onboarding", wait_until="load")
            page.wait_for_timeout(3000)
            body = page.inner_text("body")
            empty_ok = "Noch kein Onboarding aktiv" in body
            btn = page.get_by_role("button", name="Stellen ansehen")
            btn_ok = btn.count() >= 1
            print(f"OK empty_state={empty_ok} action_button={btn_ok}")
            if not empty_ok:
                failures.append("Empty-State fehlt (Datenstand anders als erwartet?)")
            if not btn_ok:
                failures.append("klickbarer Weg fehlt (Sackgasse bestand weiterhin)")

            if btn_ok:
                btn.first.click()
                page.wait_for_timeout(3000)
                body2 = page.inner_text("body")
                land_ok = "Stellenangebote" in body2
                print(f"OK landing stellen={land_ok}")
                if not land_ok:
                    failures.append("Klick landet nicht im Stellen-Tab")
            else:
                failures.append("Kein Klick möglich (Button fehlt)")
        finally:
            ctx.close()
            browser.close()

    conn = sqlite3.connect(str(DB))
    after_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    after_tasks = conn.execute("SELECT COALESCE(MAX(id),0) FROM agent_tasks").fetchone()[0]
    conn.close()
    db_ok = (before_apps == after_apps) and (before_tasks == after_tasks)
    print(f"DB-CHECK: apps {before_apps}=={after_apps}, max_task {before_tasks}=={after_tasks}, unveraendert={db_ok}")
    if not db_ok:
        failures.append("DB wurde veraendert (read-only verletzt)")

    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("E2E P1-3 PASS: Onboarding-Empty-State mit klickbarem Weg, Klick landet im Stellen-Tab, DB unveraendert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
