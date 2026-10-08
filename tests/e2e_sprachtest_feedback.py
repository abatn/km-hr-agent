"""P3 E2E C4: Sprachtest-Tab-Display (Prozent/LIMIT/Caption) + Cat-Map 'Schwach'.

Ablauf:
1. DB-Vorher sichern: heutige feedback-rows, gewichtung_historie MAX(id),
   export_report-Tasks (Restore-Scope)
2. Teil A (view-only): Candidate-Login → /candidate/sprachtest
   - Caption 'Session-gebunden' sichtbar (Streamlit app.py:2925)
   - GENAU 5 Ergebnis-Karten (LIMIT 5, app.py:2945; DB hat 11)
   - 'Score: 0%' statt Rohwert 0.0 (app.py:2950)
3. Teil B (write): Employer-Login → /employer/feedback → Score=30,
   Eingeladen=Ja (vermeidet Weight-Adjust: Ja+30<80) → speichern
   - DB: neue Row match_id employer-job-*-cand-*-heute, kategorie='Schwach'
     (Connector Weak → Map app.py:3943; vorher fälschlich 'Nicht passend')
4. Restore: heutige feedback-Rows + export_report-Tasks + gewichtung id>pre
5. Final-Check

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_sprachtest_feedback.py
Hinweis: agent-runner waehrend Test gestoppt (keine Echtest-Ausfuehrung).
"""
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
TODAY = date.today().isoformat()
CAND_EMAIL = seed_email("batniniabdelkader@yahoo.com")
CAND_PW = "Abdel15121978!"
EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"


def read_state() -> dict:
    conn = sqlite3.connect(DB)
    fb_today = conn.execute(
        "SELECT id, match_id, kategorie FROM feedback WHERE match_id LIKE ?",
        (f"%-{TODAY}",),
    ).fetchall()
    gew_max = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM gewichtung_historie"
    ).fetchone()[0]
    tasks = conn.execute(
        "SELECT id, payload FROM agent_tasks WHERE task_type='export_report' "
        "AND payload LIKE ?",
        (f"%{TODAY}%",),
    ).fetchall()
    conn.close()
    return {"fb_today": fb_today, "gew_max": gew_max, "tasks": tasks}


def restore(pre: dict) -> None:
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM feedback WHERE match_id LIKE ?", (f"%-{TODAY}",))
    conn.execute(
        "DELETE FROM agent_tasks WHERE task_type='export_report' AND payload LIKE ?",
        (f"%{TODAY}%",),
    )
    conn.execute(
        "DELETE FROM gewichtung_historie WHERE id > ?", (pre["gew_max"],)
    )
    conn.commit()
    conn.close()


def _panel(page, button_pattern: str):
    return page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile(button_pattern, re.I))
    ).first


def login_candidate(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    panel = _panel(page, "Anmelden|Login")  # Default-Tab = Candidate
    # Default-Panel aktiv; nur fuellen
    panel = page.locator(".q-tab-panel:visible").first
    panel.get_by_label("E-Mail").fill(CAND_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(CAND_PW)
    panel.get_by_role("button").first.click()
    page.wait_for_url("**/candidate**", timeout=15000)


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(700)
    panel = _panel(page, "Arbeitgeber-Login")
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    pre = read_state()
    print("Pre:", pre)
    failures = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            # ── Teil A: Sprachtest-Display (view-only) ──
            ctx = browser.new_context()
            page = ctx.new_page()
            login_candidate(page)
            page.goto(f"{BASE}/candidate/sprachtest", wait_until="load", timeout=60000)
            page.wait_for_timeout(3000)
            body = page.locator("body").inner_text()
            print("A URL:", page.url)

            if "Session-gebunden" not in body:
                failures.append("A: Caption 'Session-gebunden' fehlt")
            n_score = body.count("Score:")
            print(f"A Score:-Vorkommen={n_score} (erwartet 5, LIMIT)")
            if n_score != 5:
                failures.append(f"A: {n_score} Score-Karten != 5 (LIMIT 5)")
            if "Score: 0%" not in body:
                failures.append("A: 'Score: 0%' fehlt (Prozent-Format)")
            if "0.0" in body and re.search(r"Score:\s*0\.0", body):
                failures.append("A: Rohwert '0.0' noch sichtbar")
            if "Französisch C1" not in body:
                failures.append("A: neuestes Test 'Französisch C1' nicht oben/ichtbar")
            ctx.close()

            # ── Teil B: Cat-Map 'Schwach' (write + restore) ──
            ctx = browser.new_context()
            page = ctx.new_page()
            login_employer(page)
            page.goto(f"{BASE}/employer/feedback", wait_until="load", timeout=60000)
            page.wait_for_timeout(3000)
            print("B URL:", page.url)

            # Runde 7 (27.09.2026): /employer/feedback rendert ZWEI Formulare
            # mit identischen Labels - Phase-4-Karte "Neues Feedback"
            # (employer.py:1406-1600) vs. Skill-8-Karte (components.py:855-1003).
            # Vorher strict-Mode-Fehler "2 elements" (c61/c84) bei get_by_label.
            # Scope = die nicegui-card, die das Stelle-Select traegt (gemessen:
            # gesamt 2 Karten/2 Score/2 Eingeladen/2 Buttons -> in der Karte je 1).
            cards = page.locator(
                ".nicegui-card", has=page.locator('input[aria-label="Stelle"]'))
            if cards.count() != 1:
                failures.append(
                    f"B: Phase-4-Karte mit Stelle-Select: {cards.count()} != 1")
            form = cards.first
            score = form.get_by_label("Match-Score (0-100)")
            if score.count() != 1:
                failures.append(f"B: Match-Score-Input in Karte: {score.count()} != 1")
            score.first.fill("30")
            # Eingeladen = Ja (verhindert Weight-Adjust bei low score)
            eing = form.get_by_label("Eingeladen?")
            if eing.count() != 1:
                failures.append(f"B: Eingeladen-Select in Karte: {eing.count()} != 1")
            eing.first.click()
            page.wait_for_timeout(300)
            page.get_by_role("option", name="Ja", exact=True).first.click()
            page.wait_for_timeout(200)
            btn = form.get_by_role("button", name=re.compile("Feedback speichern"))
            if btn.count() != 1:
                failures.append(f"B: Speichern-Button in Karte: {btn.count()} != 1")
            btn.first.click()
            page.wait_for_timeout(2000)

            post = read_state()
            print("Post fb_today:", post["fb_today"])
            new_rows = [r for r in post["fb_today"] if r[0] not in {x[0] for x in pre["fb_today"]}]
            if not new_rows:
                failures.append("B: keine neue feedback-Row")
            else:
                for _id, match_id, kategorie in new_rows:
                    if kategorie != "Schwach":
                        failures.append(f"B: kategorie={kategorie!r} != 'Schwach' (match {match_id})")
                    else:
                        print(f"OK B: {match_id} -> kategorie='Schwach'")
            # Kein Weight-Adjust erwartet (Ja + 30 < 80)
            if post["gew_max"] != pre["gew_max"]:
                failures.append(f"B: gewichtung_historie wuchs ({pre['gew_max']}→{post['gew_max']}) trotz Eingeladen=Ja")
            ctx.close()
        finally:
            browser.close()
            restore(pre)
            final = read_state()
            print("Final:", final)
            if final["fb_today"] != pre["fb_today"]:
                failures.append(f"Restore feedback: {final['fb_today']} != {pre['fb_today']}")
            if final["gew_max"] != pre["gew_max"]:
                failures.append(f"Restore gewichtung: {final['gew_max']} != {pre['gew_max']}")
            if final["tasks"] != pre["tasks"]:
                failures.append(f"Restore export_report: {len(final['tasks'])} != {len(pre['tasks'])}")

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: C4 — Sprachtest (Caption/LIMIT 5/Prozent) + Cat-Map 'Schwach' + Restore")
    return 0


if __name__ == "__main__":
    sys.exit(main())
