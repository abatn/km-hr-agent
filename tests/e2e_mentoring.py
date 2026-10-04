"""F Mentoring E2E: HR-Klick-Vergabe + Candidate-Anzeige (User-GO 24.09.2026).

Spec: knowledge/lifecycle/mentoring.md §§2A/3C/4, Plan entscheidungen.md
(USER-GO-Eintrag). Tests NUR über echte Auslöser (Portal-Klicks), keine
Hand-Queue-Payloads.

Ablauf:
1. Harness-Precheck (Server) + DB-Baseline (mentoring-Zeilen, cand16 eingestellt)
2. Employer-Login (Test-Arbeitgeber) -> /employer/onboarding
3. Card "E2E Beweis Phase1" (status eingestellt): Input "Mentor (Name):" fuellen
   -> Button "Mentor zuweisen" -> Toast + DB-Zeile status='aktiv'
4. Candidate-Login (#16, Test-Login) -> /candidate/onboarding
5. Expansion sichtbar -> "Ihr Ansprechpartner (Mentor): ..." sichtbar
6. Zurueck Employer: "Patenschaft beenden" -> DB status='beendet', Candidate
   zeigt keine Mentor-Zeile mehr
7. Final-Cleanup: Testzeilen aus mentoring entfernen (nur diese Runde)

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_mentoring.py
"""
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import check_server, pre_max_tasks, db_residue_report  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
CAND_ID = 16
MENTOR_NAME = "Sabine E2E Mentorin"

# Test-Logins (Projekt-Testbestand, gleiche Quelle wie e2e_apply_dialog)
EMP_EMAIL = "hr@techvision.de"
EMP_PASSWORD = "sicher123"
# cand16-Reset 24.09.2026 (User-GO): cand16-E2E-Passwort war nirgends notiert.
CAND_EMAIL = "e2e-beweis-phase1@example.com"
CAND_PASSWORD = "E2EMentoring2026!"
# Expansion-Text auf Candidate-Onboarding: "🎉 {job} – {firma}" (candidate.py:967)
CAND_EXPANSION = "E2E-Beweis: Teststelle Phase1"


def db_state() -> dict:
    conn = sqlite3.connect(str(DB))
    try:
        rows = conn.execute(
            "SELECT id, mentor_name, status FROM mentoring WHERE candidate_id=?",
            (CAND_ID,),
        ).fetchall()
        app = conn.execute(
            "SELECT status FROM applications WHERE candidate_id=? AND status='eingestellt'",
            (CAND_ID,),
        ).fetchone()
        cand = conn.execute(
            "SELECT email FROM candidates WHERE id=?", (CAND_ID,)
        ).fetchone()
        return {"mentor_rows": rows, "app_status": app[0] if app else None,
                "cand_email": cand[0] if cand else None}
    finally:
        conn.close()


def _panel(page, button_pattern: str):
    return page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile(button_pattern, re.I))
    ).first


def login_employer(page):
    """Tab-Login Muster (e2e_vorgemerkt.py:70-79) – Candidate-Tab ist Default."""
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(700)
    panel = _panel(page, "Arbeitgeber-Login")
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PASSWORD)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def login_candidate(page):
    """Default-Tab = Candidate Login (e2e_sprachtest_feedback.py:77-86)."""
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    panel = page.locator(".q-tab-panel:visible").first
    panel.get_by_label("E-Mail").fill(CAND_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(CAND_PASSWORD)
    panel.get_by_role("button").first.click()
    page.wait_for_url("**/candidate**", timeout=15000)


def cleanup_mentoring():
    conn = sqlite3.connect(str(DB))
    conn.execute("DELETE FROM mentoring WHERE candidate_id=?", (CAND_ID,))
    conn.commit()
    conn.close()


def main() -> int:
    check_server()
    pre = pre_max_tasks()
    failures = []
    before = db_state()
    print(f"Baseline: {before}")
    if before["app_status"] != "eingestellt":
        print(f"FAIL: cand{CAND_ID} hat keine eingestellte Bewerbung")
        return 1
    # E-Mail-Verifikation: DB-Wert muss dem Test-Login entsprechen
    if before["cand_email"] != CAND_EMAIL:
        print(f"FAIL: cand{CAND_ID} E-Mail {before['cand_email']!r} != {CAND_EMAIL!r}")
        return 1
    cleanup_mentoring()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            # ── 1) Employer: Mentor zuweisen (HR-Klick §2A) ──
            # Eigener Context (Session-Trennung Employer/Candidate, Muster
            # e2e_sprachtest_feedback.py:112/135 – gleicher Page = Rollen-Konflikt)
            ctx_emp = browser.new_context()
            page_emp = ctx_emp.new_page()
            page_emp.set_default_timeout(60000)
            login_employer(page_emp)
            page_emp.goto(f"{BASE}/employer/onboarding", wait_until="load", timeout=90000)
            page_emp.wait_for_timeout(2500)

            mentor_input = page_emp.get_by_label("Mentor (Name):").first
            mentor_input.fill(MENTOR_NAME)
            page_emp.get_by_role("button", name="Mentor zuweisen").first.click()
            page_emp.wait_for_timeout(2500)

            after_assign = db_state()
            active = [r for r in after_assign["mentor_rows"] if r[2] == "aktiv"]
            if not active or active[0][1] != MENTOR_NAME:
                failures.append(f"DB aktiv nach Klick: {after_assign['mentor_rows']}")
            else:
                print(f"OK assign: {active[0]}")

            # UI zeigt aktiven Mentor + End-Button
            page_emp.wait_for_timeout(1000)
            if not page_emp.get_by_text(f"Aktiver Mentor: {MENTOR_NAME}").first.is_visible():
                failures.append("Employer-UI zeigt 'Aktiver Mentor' nicht")
            else:
                print("OK employer UI active mentor visible")

            # ── 2) Candidate: Anzeige im Onboarding-Tab (eigener Context) ──
            ctx_cand = browser.new_context()
            page_cand = ctx_cand.new_page()
            page_cand.set_default_timeout(60000)
            login_candidate(page_cand)
            page_cand.goto(f"{BASE}/candidate/onboarding", wait_until="load", timeout=90000)
            page_cand.wait_for_timeout(3500)
            print("cand URL:", page_cand.url)

            # Expansion oeffnen (q-expansion-item Header)
            exp_items = page_cand.locator(".q-expansion-item")
            if exp_items.count() > 0:
                try:
                    exp_items.first.locator(".q-item").first.click()
                    page_cand.wait_for_timeout(1500)
                except Exception as e:
                    print(f"expansion click note: {e}")

            mentor_line = page_cand.get_by_text(f"Ihr Ansprechpartner (Mentor): {MENTOR_NAME}")
            try:
                mentor_line.first.wait_for(state="visible", timeout=8000)
                print("OK candidate sees mentor line")
            except Exception:
                failures.append("Candidate-Onboarding zeigt Mentor-Zeile nicht")
            ctx_cand.close()

            # ── 3) Employer: Patenschaft beenden (§4 HR-Klick) ──
            page_emp.goto(f"{BASE}/employer/onboarding", wait_until="load", timeout=90000)
            page_emp.wait_for_timeout(2500)
            page_emp.get_by_role("button", name="Patenschaft beenden").first.click()
            page_emp.wait_for_timeout(2500)

            after_end = db_state()
            still_active = [r for r in after_end["mentor_rows"] if r[2] == "aktiv"]
            ended = [r for r in after_end["mentor_rows"] if r[2] == "beendet"]
            if still_active:
                failures.append(f"noch aktiv nach End-Klick: {still_active}")
            elif not ended:
                failures.append(f"keine beendete Zeile: {after_end['mentor_rows']}")
            else:
                print(f"OK end: {ended}")

            # Candidate sieht keine Mentor-Zeile mehr
            ctx_cand2 = browser.new_context()
            page_cand2 = ctx_cand2.new_page()
            page_cand2.set_default_timeout(60000)
            login_candidate(page_cand2)
            page_cand2.goto(f"{BASE}/candidate/onboarding", wait_until="load", timeout=90000)
            page_cand2.wait_for_timeout(3500)
            exp_items = page_cand2.locator(".q-expansion-item")
            if exp_items.count() > 0:
                try:
                    exp_items.first.locator(".q-item").first.click()
                    page_cand2.wait_for_timeout(1500)
                except Exception:
                    pass
            try:
                page_cand2.get_by_text(
                    f"Ihr Ansprechpartner (Mentor): {MENTOR_NAME}"
                ).first.wait_for(state="visible", timeout=3000)
                failures.append("Mentor-Zeile noch sichtbar nach Ende")
            except Exception:
                print("OK candidate no mentor line after end")
            ctx_cand2.close()
            ctx_emp.close()

        except Exception as e:
            failures.append(f"Exception: {e}")
        finally:
            cleanup_mentoring()
            browser.close()

    db_residue_report(pre)
    if failures:
        print("E2E MENTORING FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("E2E MENTORING PASS (assign -> candidate view -> end -> hidden)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
