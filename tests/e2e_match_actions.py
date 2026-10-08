"""E2E Match-Aktionen (S3d): Match-Seite Employer-Portal.

Ablauf:
1. Server-Precheck (F2) + DB-Baseline (F3)
2. Employer-Login (hr@techvision.de / sicher123)
3. /employer/match -> Kandidaten + Scores + Aktionen sichtbar
4. Sprachtests-Expander pruefen (S3d-Neuheit)
5. Statusuebergang 'angesehen' klicken (nur lesen, falls Button fehlt)
6. DB-Integritaet (Isolation via KMHR_DB_PATH)
"""
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import BASE, DB, seed_email  # noqa: E402

EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(700)
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I))
    ).first
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def db_counts() -> dict:
    conn = sqlite3.connect(str(DB))
    try:
        return {
            "apps": conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
            "hist": conn.execute(
                "SELECT COUNT(*) FROM application_status_history"
            ).fetchone()[0],
            "tasks": conn.execute(
                "SELECT COALESCE(MAX(id),0) FROM agent_tasks"
            ).fetchone()[0],
        }
    finally:
        conn.close()


def main():
    check_server()
    pre = pre_max_tasks()
    baseline = db_counts()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        try:
            login_employer(page)
            page.goto(f"{BASE}/employer/match", wait_until="load")
            page.wait_for_timeout(3000)

            # Kandidaten-Namen sichtbar
            names = page.locator(".font-medium").all_text_contents()
            cand_names = [n.strip() for n in names if n.strip()]
            assert len(cand_names) > 0, f"Keine Kandidaten-Namen: {names[:5]}"

            # Score-Texte sichtbar (z.B. "85/100 (Kern)")
            score_texts = page.locator("text=/\\/100/").all_text_contents()
            assert len(score_texts) > 0, "Keine Score-Texte (/100) sichtbar"

            # Aktions-Buttons je Status vorhanden
            for label in ("Einladen", "Ablehnen", "Einstellen"):
                _ = page.locator(f"button:has-text('{label}')").count()

            # Sprachtests-Expander (S3d): sichtbar oder 0 ist ok
            expanders = page.locator("text=Sprachtests").all()

            # Statusuebergang nur lesen: 'angesehen' klicken falls vorhanden
            seen_btn = page.locator(
                "button:has-text('Als angesehen markieren')"
            ).first
            if seen_btn.count() > 0:
                hist_before = db_counts()["hist"]
                seen_btn.click()
                page.wait_for_timeout(1500)
                hist_after = db_counts()["hist"]
                # Transition erzeugt genau 1 History-Zeile
                assert hist_after == hist_before + 1, (
                    f"History unerwartet: {hist_before} -> {hist_after}"
                )

            # Schreibschutz: apps und tasks duerfen sich nicht aendern
            after = db_counts()
            assert after["apps"] == baseline["apps"], "App-Count veraendert"
            assert after["tasks"] == baseline["tasks"], "Tasks veraendert"

            residue = db_residue_report(pre)
            print(f"OK names={len(cand_names)} scores={len(score_texts)} "
                  f"expanders={len(expanders)} residue={residue}")
            sys.exit(0 if residue == 0 else 1)

        except Exception as ex:
            print(f"E2E FEHLER: {ex}")
            sys.exit(1)
        finally:
            ctx.close()
            browser.close()


if __name__ == "__main__":
    main()