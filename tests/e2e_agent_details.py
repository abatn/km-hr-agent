"""P3 E2E (view-only): C5 Agent-Details — Ergebnis-Parser + Badge-Zeilen.

Paritaet zu Streamlit 🔍 Agent-Details (app.py:1969-2026) + Spec
ergebnisse/agent-details-doku.md. Keine DB-Schreiboperation → kein Restore.

Ablauf:
1. Employer-Login → /employer/agent_details
2. Default-Kandidat (erster Name = "E2E Beweis Phase1", id16, hat KEINE
   Ergebnis-Dateien) → 9x "Kein Bericht vorhanden" (Pfad ⚪)
3. Kandidat "E2E Kette" (id17) wählen → alle 9 Berichte, Badge-Farben:
   - check_visa  → 🔴 (Visum-Status: ERFORDERLICH)
   - check_gdpr  → 🟢 (DSGVO-Status: KONFORM)
   - verify_docs → 🟡 (Gesamtstatus: UNBEKANNT)
4. check_visa-Expander öffnen → Volltext "Visum-Status: ERFORDERLICH"
5. Sichtbarkeit der Task-Queue (DB) prüfen

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_agent_details.py
"""
import re
import sys

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
EMP_EMAIL = "hr@techvision.de"
EMP_PW = "sicher123"

TASK_LABELS = [
    "Profil extrahieren", "Kandidat matchen", "Compliance pruefen",
    "Culture Fit pruefen", "Dokumente verifizieren", "Visum pruefen",
    "DSGVO pruefen", "Match erklaeren", "Kandidat benachrichtigen",
]


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


def select_field(page, label, value):
    el = page.get_by_label(label, exact=True)
    el.click()
    page.wait_for_timeout(250)
    opt = page.get_by_role("option", name=str(value), exact=True)
    if opt.count() == 0:
        opt = page.get_by_text(str(value), exact=True).last
    opt.first.click()
    page.wait_for_timeout(400)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    fails = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            login_employer(page)
            page.goto(f"{BASE}/employer/agent_details", wait_until="load", timeout=20000)
            page.wait_for_timeout(1200)

            # ── 2. Default (id16, keine Dateien) → 9x ⚪ ──
            n_empty = page.get_by_text("Kein Bericht vorhanden").count()
            if n_empty != 9:
                fails.append(f"default: {n_empty}x 'Kein Bericht vorhanden' (erwartet 9)")
            if page.get_by_text("Status-Übersicht:").count() < 1:
                fails.append("default: 'Status-Übersicht:' fehlt")

            # ── 3. Kandidat 17 wählen ──
            select_field(page, "Kandidat", "E2E Kette")
            page.wait_for_timeout(600)

            n_empty2 = page.get_by_text("Kein Bericht vorhanden").count()
            if n_empty2 != 0:
                fails.append(f"cand17: {n_empty2}x 'Kein Bericht vorhanden' (erwartet 0)")

            for lbl in TASK_LABELS:
                if page.get_by_text(f"{lbl} (", exact=False).count() < 1:
                    fails.append(f"cand17: Expander '{lbl} (' fehlt")

            # Badge-Farben via Expander-Label (gleicher Parser wie Badge-Zeile)
            visa = page.get_by_text(re.compile(r"🔴 🛂 Visum pruefen \("))
            gdpr = page.get_by_text(re.compile(r"🟢 🔒 DSGVO pruefen \("))
            vdoc = page.get_by_text(re.compile(r"🟡 📄 Dokumente verifizieren \("))
            if visa.count() < 1:
                fails.append("cand17: Check-Visa-Expander nicht 🔴")
            if gdpr.count() < 1:
                fails.append("cand17: Check-GDPR-Expander nicht 🟢")
            if vdoc.count() < 1:
                fails.append("cand17: Verify-Documents-Expander nicht 🟡")

            # ── 4. Visa-Expander öffnen → Parser-Volltext ──
            visa.first.click()
            page.wait_for_timeout(400)
            if page.get_by_text("Visum-Status: ERFORDERLICH").count() < 1:
                fails.append("visa-expander: 'Visum-Status: ERFORDERLICH' nicht sichtbar")

            # ── 5. Task-Queue ──
            if page.get_by_text("Task-Queue (Datenbank)").count() < 1:
                fails.append("queue: 'Task-Queue (Datenbank)' fehlt")

        except Exception as e:  # noqa: BLE001
            fails.append(f"EXC: {type(e).__name__}: {e}")
        finally:
            browser.close()

    residue = db_residue_report(pre_tasks)
    if residue:
        fails.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if fails:
        print("FAIL:")
        for f in fails:
            print(f" - {f}")
        return 1
    print("PASS: C5 Agent-Details — 9x-Looper + kandidat-{id}-Parser + "
          "🔴/🟢/🟡 + Visa-Volltext + Queue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
