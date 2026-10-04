#!/usr/bin/env python3
"""E2E P1-2 (29.09.2026): CV-Gate-Sackgasse hat jetzt einen klickbaren Upload-Weg.

Read-only-Nachweis gegen die Live-App:
1. Login als Kandidat #16 (Status 'registriert' → außerhalb der CV-Whitelist).
2. Pre-Screen-Tab öffnen → Warn-Label + NEU: Button „→ Zum Lebenslauf-Upload".
3. Klick → Landung im Upload-Tab (Sackgasse behoben).
4. DB-Baseline vor == nach (read-only, keine Writes).

Spec: knowledge/portal/cv-pflicht.md §(h) · Plan: ergebnisse/ui-mvp-plan-v2.md §6 P1-2
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from e2e_harness import BASE, DB, check_server  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CAND_EMAIL = "e2e-beweis-phase1@example.com"
CAND_PASSWORD = "E2EMentoring2026!"  # Klartext nur hier (Hausregel)

failures: list[str] = []


def main() -> int:
    check_server()

    # DB-Baseline (read-only)
    conn = sqlite3.connect(str(DB))
    before_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    before_tasks = conn.execute("SELECT COALESCE(MAX(id),0) FROM agent_tasks").fetchone()[0]
    conn.close()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        try:
            # 1. Login (Default-Tab = Candidate Login)
            page.goto(f"{BASE}/login", wait_until="load")
            page.wait_for_timeout(2500)
            panel = page.locator(".q-tab-panel:visible").first
            panel.get_by_label("E-Mail").fill(CAND_EMAIL)
            panel.get_by_label("Passwort", exact=True).fill(CAND_PASSWORD)
            panel.get_by_role("button").first.click()
            page.wait_for_url("**/candidate**", timeout=15000)
            print("OK login cand16")

            # 2. Pre-Screen-Tab öffnen
            page.goto(f"{BASE}/candidate/prescreen", wait_until="load")
            page.wait_for_timeout(3000)
            body = page.inner_text("body")

            warn_ok = "CV-Pflicht" in body
            btn = page.get_by_role("button", name="Zum Lebenslauf-Upload")
            btn_ok = btn.count() >= 1
            print(f"OK warn_label={warn_ok} upload_button={btn_ok}")
            if not warn_ok:
                failures.append("Warn-Label fehlt")
            if not btn_ok:
                failures.append("klickbarer Upload-Weg fehlt (Sackgasse bestand weiterhin)")

            # 3. Klick → Upload-Tab (Header lautet "Lebenslauf hochladen", candidate.py:33)
            if btn_ok:
                btn.first.click()
                page.wait_for_timeout(3000)
                body2 = page.inner_text("body")
                land_ok = "Lebenslauf hochladen" in body2
                print(f"OK landing upload={land_ok} url={page.url}")
                if not land_ok:
                    failures.append("Klick landet nicht im Upload")
            else:
                failures.append("Kein Klick möglich (Button fehlt)")
        finally:
            ctx.close()
            browser.close()

    # 4. DB unverändert (read-only-Lauf)
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
    print("E2E P1-2 PASS: Warn-Label + klickbarer Upload-Weg + Klick landet im Upload, DB unveraendert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
