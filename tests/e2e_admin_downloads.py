"""P3 E2E (view-only): C6 Admin-Tool-Ergebnisse + Downloads (Auflage #1/12).

Paritaet: Streamlit st.download_button app.py:1378/1531/1641/1734/1851
(Extract/Match/Compliance/Contact/Culture) — NiceGUI zeigt das Runner-
Artefakt aus ergebnisse/ inkl. Vorschau + Download-Button pro Tool-Seite.

Ablauf:
1. Admin-Login → je 5 Tool-Seiten (/admin/{extract,match_tool,
   compliance_tool,contact,culture_fit})
2. Pro Seite: "Ergebnis:"-Karte + "Herunterladen"-Button sichtbar
3. Artefakt-Dateiname passt zum Task-Glob (extract_page als Stellvertreter)
4. Download ausloesen → Event mit .md-Filename (extract_page)
5. Kein DB-Write → kein Restore

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_admin_downloads.py
"""
import re
import sys

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
ADMIN_EMAIL = seed_email("admin@km-hr-agent.local")
ADMIN_PW = "admin-agent-2026"

PAGES = [
    ("/admin/extract", "extract_profile-", "Extract Profile"),
    ("/admin/match_tool", "match_candidate-", "Match Candidate"),
    ("/admin/compliance_tool", "check_compliance-", "Check Compliance"),
    ("/admin/contact", "notify_user-", "Contact Candidate"),
    ("/admin/culture_fit", "assess_culture_fit-", "Culture Fit"),
]


def login_admin(page):
    page.goto(f"{BASE}/login", wait_until="load", timeout=20000)
    page.get_by_role("tab", name="Admin", exact=True).click()
    page.wait_for_timeout(600)
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Admin-Login", re.I))
    ).first
    panel.get_by_label("Admin-E-Mail").fill(ADMIN_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(ADMIN_PW)
    panel.get_by_role("button", name=re.compile("Admin-Login", re.I)).click()
    page.wait_for_url("**/admin**", timeout=15000)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    fails = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            login_admin(page)

            for path, filename_hint, label in PAGES:
                page.goto(f"{BASE}{path}", wait_until="load", timeout=20000)
                page.wait_for_timeout(900)
                head = page.get_by_text(f"Ergebnis: {label}", exact=False)
                if head.count() < 1:
                    fails.append(f"{path}: 'Ergebnis: {label}' fehlt")
                    continue
                dl = page.get_by_role("button", name="Herunterladen")
                if dl.count() < 1:
                    fails.append(f"{path}: Download-Button fehlt")
                    continue
                # Artefakt-Dateiname muss dem Task-Glob entsprechen
                if page.get_by_text(filename_hint, exact=False).count() < 1:
                    fails.append(f"{path}: Dateiname '{filename_hint}*' nicht sichtbar")
                # Vorschau-Zugang
                if page.get_by_text("Vorschau", exact=False).count() < 1:
                    fails.append(f"{path}: 'Vorschau'-Expander fehlt")

            # Download-Event auf der ersten Seite ausloesen
            page.goto(f"{BASE}/admin/extract", wait_until="load", timeout=20000)
            page.wait_for_timeout(900)
            with page.expect_download(timeout=8000) as dl_info:
                page.get_by_role("button", name="Herunterladen").first.click()
            download = dl_info.value
            suggested = download.suggested_filename
            if not suggested.startswith("extract_profile-") or not suggested.endswith(".md"):
                fails.append(f"download: suggested_filename={suggested!r} (erwartet extract_profile-*.md)")

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
    print("PASS: C6 Admin-Tools — 5x Ergebnis-Karte + Download-Button + "
          "Vorschau + .md-Download-Event")
    return 0


if __name__ == "__main__":
    sys.exit(main())
