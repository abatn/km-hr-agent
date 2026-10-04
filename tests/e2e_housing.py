"""D Housing E2E: HR-Klick 'Einstellen' -> Freigabe-Report mit Wohnungs-Abschnitt
-> Candidate-Onboarding zeigt Abschnitt (Code-Go 24.09.2026).

Spec: knowledge/portal/housing-search.md §§2/5, Plan entscheidungen.md
(USER-GO-Eintrag Code-Go). Tests NUR ueber echte Ausloeser (Portal-Klicks),
keine Hand-Queue-Payloads.

Ablauf:
1. Harness-Precheck (Server) + DB-Baseline (cand1: keine eingestellte Bewerbung)
2. Statischer MD-Check: Checklistenpunkt in 4 Templates
3. Employer-Login -> /employer/match -> Kandidat batnini -> 'Einstellen'
   -> Dialog-Bestaetigung 'Einstellen' (employer.py:757/685).
   Do-Hire wirkt seit P0-3 auf die Bewerbung der angeklickten Aktionszeile
   (application_id) -> hired_app_id dynamisch aus DB.
4. Runner-Task onboarding_release abwarten -> report-{hired_app_id} enthaelt
   '## 🏠 Wohnungssuche (Checkliste + freie Quellen)'
5. Candidate-Login (#1) -> /candidate/onboarding -> Expansion oeffnen ->
   Wohnungs-Abschnitt sichtbar
6. Employer /employer/onboarding -> Karte cand1 sichtbar (HR-Lesicht Spec §2.5,
   kein Report-Render dort)

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_housing.py
"""
import re
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import check_server, pre_max_tasks, db_residue_report  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
CAND_ID = 1
HOUSING_HEADER = "## 🏠 Wohnungssuche (Checkliste + freie Quellen)"

# Test-Logins (Projekt-Testbestand, gleiche Quelle wie e2e_mentoring.py)
EMP_EMAIL = "hr@techvision.de"
EMP_PASSWORD = "sicher123"
CAND_EMAIL = "batniniabdelkader@yahoo.com"
CAND_PASSWORD = "Abdel15121978!"

TEMPLATES = [
    ROOT / "knowledge" / "templates" / "onboarding-templates" / "onboarding-de.md",
    ROOT / "knowledge" / "templates" / "onboarding-templates" / "onboarding-fr.md",
    ROOT / "knowledge" / "templates" / "onboarding-templates" / "onboarding-ch.md",
    ROOT / "knowledge" / "onboarding-default.md",
]


def db_state() -> dict:
    conn = sqlite3.connect(str(DB))
    try:
        hired = conn.execute(
            "SELECT id FROM applications WHERE candidate_id=? AND status='eingestellt'",
            (CAND_ID,),
        ).fetchall()
        active = conn.execute(
            "SELECT id, status FROM applications WHERE candidate_id=? "
            "AND status IN ('eingegangen','angesehen','eingeladen')",
            (CAND_ID,),
        ).fetchall()
        cand = conn.execute(
            "SELECT email FROM candidates WHERE id=?", (CAND_ID,)
        ).fetchone()
        return {"hired": hired, "active": active,
                "cand_email": cand[0] if cand else None}
    finally:
        conn.close()


def report_path(app_id: int) -> Path:
    return ROOT / "ergebnisse" / f"onboarding-freigabe-bewerbung-{app_id}.md"


def check_templates() -> list:
    failures = []
    for path in TEMPLATES:
        if not path.exists():
            failures.append(f"Template fehlt: {path.name}")
            continue
        text = path.read_text(encoding="utf-8")
        if "Wohnungssuche" not in text and "Recherche de logement" not in text:
            failures.append(f"Template ohne Wohnungs-Punkt: {path.name}")
        else:
            print(f"OK template: {path.name}")
    return failures


def _panel(page, button_pattern: str):
    return page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile(button_pattern, re.I))
    ).first


def login_employer(page):
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
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    panel = page.locator(".q-tab-panel:visible").first
    panel.get_by_label("E-Mail").fill(CAND_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(CAND_PASSWORD)
    panel.get_by_role("button").first.click()
    page.wait_for_url("**/candidate**", timeout=15000)


def wait_for_report(app_id: int, timeout_s: int = 90) -> bool:
    rep = report_path(app_id)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if rep.exists() and HOUSING_HEADER in rep.read_text(
            encoding="utf-8", errors="replace"
        ):
            return True
        time.sleep(2)
    return False


def main() -> int:
    check_server()
    pre = pre_max_tasks()
    failures = []
    before = db_state()
    print(f"Baseline: {before}")
    # Restore-Baseline (Teil-2-Residue-Fix 25.09.2026, Phase-E Runde 6): der
    # Hire-Klick darf keine bleibende Residue hinterlassen (sonst Vorb.-Fail
    # wie App #27 am 24.09. und Bruch fuer e2e_c7_downloads).
    _conn0 = sqlite3.connect(str(DB))
    pre_flip = {r[0]: (r[1], r[2]) for r in _conn0.execute(
        "SELECT id, status, aktualisiert_am FROM applications WHERE candidate_id=?",
        (CAND_ID,))}
    pre_hist_max = _conn0.execute(
        "SELECT COALESCE(MAX(id),0) FROM application_status_history").fetchone()[0]
    _conn0.close()
    print(f"Restore-Baseline: {len(pre_flip)} Apps, hist_max={pre_hist_max}")
    if before["hired"]:
        print(f"FAIL: cand{CAND_ID} hat bereits eingestellte Bewerbung: {before['hired']}")
        return 1
    if not before["active"]:
        print(f"FAIL: cand{CAND_ID} hat keine aktive Bewerbung")
        return 1
    if before["cand_email"] != CAND_EMAIL:
        print(f"FAIL: cand{CAND_ID} E-Mail {before['cand_email']!r} != {CAND_EMAIL!r}")
        return 1
    # Vorlauf-Cleanup: alter Report ohne Wohnungs-Abschnitt (von altem Runner)
    for app_row in before["active"]:
        stale = report_path(app_row[0])
        if stale.exists() and HOUSING_HEADER not in stale.read_text(
            encoding="utf-8", errors="replace"
        ):
            stale.unlink()
            print(f"removed stale report-{app_row[0]} (ohne Wohnungs-Abschnitt)")

    failures.extend(check_templates())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            # ── 1) Employer: Einstellen-Klick (Variante A, echter Trigger) ──
            ctx_emp = browser.new_context()
            page_emp = ctx_emp.new_page()
            page_emp.set_default_timeout(60000)
            login_employer(page_emp)
            page_emp.goto(f"{BASE}/employer/match", wait_until="load", timeout=90000)
            page_emp.wait_for_timeout(3000)

            # Kandidaten-Card 'batnini' (ui.card, kein q-expansion-item)
            # P0-3 (29.09.2026): Aktionen sind zustandsbewusst — 'Einstellen' erscheint nur
            # bei Bewerbungen im Status 'eingeladen' (frueher: immer 3 globale Buttons).
            cand_card = page_emp.locator(".q-card", has_text=re.compile(
                "batnini", re.I)).filter(
                has=page_emp.get_by_role("button", name="Einstellen")
            ).first
            cand_card.scroll_into_view_if_needed()
            page_emp.wait_for_timeout(500)

            hire_btn = cand_card.get_by_role("button", name="Einstellen").first
            hire_btn.scroll_into_view_if_needed()
            hire_btn.click()
            page_emp.wait_for_timeout(1000)

            # Dialog-Bestaetigung (zweiter 'Einstellen'-Button in .q-dialog)
            dialog = page_emp.locator(".q-dialog")
            dialog.get_by_role("button", name="Einstellen").click()
            page_emp.wait_for_timeout(2500)

            mid = db_state()
            if len(mid["hired"]) != 1:
                failures.append(f"DB cand{CAND_ID} nach Klick: hired={mid['hired']}")
                hired_app_id = None
            else:
                hired_app_id = mid["hired"][0][0]
                print(f"OK hire click: app{hired_app_id} status=eingestellt")

            # ── 2) Runner-Report mit Wohnungs-Abschnitt abwarten ──
            if hired_app_id and wait_for_report(hired_app_id):
                print(f"OK report: onboarding-freigabe-bewerbung-{hired_app_id}.md "
                      "enthaelt Wohnungs-Abschnitt")
            elif hired_app_id:
                rep = report_path(hired_app_id)
                failures.append(
                    f"Report-{hired_app_id} ohne {HOUSING_HEADER!r} nach 90s "
                    f"(exists={rep.exists()})"
                )

            # ── 3) Candidate: Wohnungs-Abschnitt im Onboarding-Tab ──
            ctx_cand = browser.new_context()
            page_cand = ctx_cand.new_page()
            page_cand.set_default_timeout(60000)
            login_candidate(page_cand)
            page_cand.goto(f"{BASE}/candidate/onboarding", wait_until="load",
                           timeout=90000)
            page_cand.wait_for_timeout(3500)

            exp_items = page_cand.locator(".q-expansion-item")
            housing_seen = False
            for i in range(exp_items.count()):
                item = exp_items.nth(i)
                try:
                    item.locator(".q-item").first.click()
                    page_cand.wait_for_timeout(800)
                except Exception:
                    pass
                try:
                    if page_cand.get_by_text("Wohnungssuche (Checkliste + freie Quellen)").first.is_visible(timeout=2000):
                        housing_seen = True
                        break
                except Exception:
                    continue
            if housing_seen:
                print("OK candidate sees housing section")
            else:
                failures.append("Candidate-Onboarding zeigt Wohnungs-Abschnitt nicht")
            ctx_cand.close()

            # ── 4) Employer: Onboarding-Karte cand1 = eingestellt (HR-Lesicht) ──
            page_emp.goto(f"{BASE}/employer/onboarding", wait_until="load",
                          timeout=90000)
            page_emp.wait_for_timeout(2500)
            try:
                card = page_emp.locator(".q-card", has_text=re.compile(
                    "batnini", re.I)).first
                if card.is_visible(timeout=5000):
                    print("OK employer onboarding card for cand1 visible")
                else:
                    failures.append("Employer-Onboarding: Karte cand1 nicht sichtbar")
            except Exception as e:
                failures.append(f"Employer-Onboarding Karte: {e}")
            ctx_emp.close()

        except Exception as e:
            failures.append(f"Exception: {e}")
        finally:
            browser.close()
            # Restore (Teil-2 25.09.2026): Hire-Flip rueckgaengig + History-Zeile
            # des UI-Klicks entfernt -> PRE_HIST_COUNT=21 und c7-Vorbedingung stabil.
            _conn9 = sqlite3.connect(str(DB))
            for _aid, (_st, _ts) in pre_flip.items():
                _conn9.execute(
                    "UPDATE applications SET status=?, aktualisiert_am=? WHERE id=?",
                    (_st, _ts, _aid))
            _conn9.execute("DELETE FROM application_status_history WHERE id > ?",
                           (pre_hist_max,))
            _conn9.commit()
            _conn9.close()
            _final = db_state()
            print(f"Final (nach Restore): {_final}")
            if _final["hired"]:
                failures.append(f"Restore hired: {_final['hired']} nicht leer")
            if _final["active"] != before["active"]:
                failures.append(
                    f"Restore active: {_final['active']} != {before['active']}")

    db_residue_report(pre)
    if failures:
        print("E2E HOUSING FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("E2E HOUSING PASS (hire click -> report housing -> candidate view -> hr card)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
