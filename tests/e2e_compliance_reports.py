"""R3-3 E2E: Compliance-Seite liest die echten check_compliance-Berichte.

Ablauf (read-only fuer die DB, kein Task, kein Restore noetig):
1. Employer-Login (hr@techvision.de) -> /employer/compliance
2. Assert Primarquelle: mindestens EIN echter Bericht sichtbar
   (Status-Token "COMPLIANT" UND das juengste echte Datum 2026-09-29)
3. Assert Zurechnung: Klarname/Stellen-Titel eines eigenen Berichts sichtbar
4. Assert Archiv-Block: "Archiv: compliance_protokoll (Legacy)" existiert

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_isolation.py --only e2e_compliance_reports --port 8092
"""
import re
import sys

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"

ARCHIV_LABEL = "Archiv: compliance_protokoll (Legacy)"
PRIMAER_LABEL = "Aktuelle Berichte: check_compliance (Primärquelle)"
JUESTES_DATUM = "2026-09-29"  # neueste der 17 echten Berichte (read-only Vorab-Befund)
ERWARTET_STATUS = ["COMPLIANT", "NICHT_COMPLIANT"]


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="load", timeout=20000)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I))
    ).first
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    fails = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            login_employer(page)
            page.goto(f"{BASE}/employer/compliance", wait_until="load", timeout=20000)
            page.wait_for_timeout(1500)
            body = page.locator("body").inner_text()

            if PRIMAER_LABEL not in body:
                fails.append("Primarquelle-Label fehlt (Block 1 nicht gerendert)")
            if ARCHIV_LABEL not in body:
                fails.append(f"Archiv-Block fehlt: {ARCHIV_LABEL!r}")

            n_status = sum(1 for s in ERWARTET_STATUS if s in body)
            if n_status == 0:
                fails.append("kein echter Bericht sichtbar (weder COMPLIANT noch "
                             "NICHT_COMPLIANT im Body)")
            if JUESTES_DATUM not in body:
                fails.append(f"echtes Datum {JUESTES_DATUM} nicht sichtbar "
                             "(juengster Bericht fehlt)")
            # Zurechnung: Job-Titel + Kandidaten-Name aus der DB sichtbar
            if "Senior Cloud/DevOps Engineer" not in body:
                fails.append("Stellen-Titel 'Senior Cloud/DevOps Engineer' nicht sichtbar")
            if "batnini abdelkader" not in body and "Kandidat #1" not in body:
                fails.append("weder Klarname noch Fallback 'Kandidat #1' sichtbar")
            # Begrueindung aufklappbar vorhanden
            if page.get_by_text("Begründung", exact=False).count() == 0:
                fails.append("Expander 'Begründung' fehlt")

            print("Body-Auszug:", re.sub(r"\s+", " ", body)[:700])
        finally:
            browser.close()

    residue = db_residue_report(pre_tasks)
    if residue:
        fails.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")

    if fails:
        print("FAIL:")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS: R3-3 Compliance-Seite — echte check_compliance-Berichte sichtbar "
          "(Status + Datum + Zurechnung) UND Archiv-Block compliance_protokoll da")
    return 0


if __name__ == "__main__":
    sys.exit(main())
