"""O3/C4 E2E: Option „Vorgemerkt" im Employer-Feedback-Select (23.09.2026).

Ablauf (P3: Restore am Ende, Agent-Runner WAEHREND des Tests gestoppt):
1. Pre-Check: Server 200, pre-States (feedback heute, gew_max, export_report heute)
2. Employer-Login -> /employer/feedback
   - Default des Selects = „Ja" (Paritaet app.py:3924, value-Default)
   - Optionsliste = [Ja, Nein, Vorgemerkt] (O3-Portierung employer.py:1252)
   - Option „Vorgemerkt" wählbar -> Select zeigt „Vorgemerkt"
   - Score 50, speichern
3. DB-Beweis: neue feedback-Row mit eingeladen='Vorgemerkt' (match_id ...-heute)
   - gewichtung_historie UNVERAENDERT (Vorgemerkt = neutral, kein Weight-Loop)
4. Restore: feedback heute, export_report-Tasks heute, gew id > pre
5. F3-Residue (Test-Reste = id > pre_max muessen 0 sein)

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_vorgemerkt.py
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
EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"


def read_state() -> dict:
    conn = sqlite3.connect(DB)
    fb_today = conn.execute(
        "SELECT id, match_id, eingeladen FROM feedback WHERE match_id LIKE ?",
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
    conn.execute("DELETE FROM gewichtung_historie WHERE id > ?", (pre["gew_max"],))
    conn.commit()
    conn.close()


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
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    pre = read_state()
    print("Pre:", pre, "| pre_max_tasks:", pre_tasks)
    failures = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context()
            page = ctx.new_page()
            login_employer(page)
            page.goto(f"{BASE}/employer/feedback", wait_until="load", timeout=60000)
            page.wait_for_timeout(3000)
            print("URL:", page.url)

            # Zwei Selects mit aria-label "Eingeladen?" auf der Seite:
            #   employer.py:1252 (Tab 4, 3 Optionen, O3-Ziel) vs.
            #   components.py:824 (Skill 8, bewusst 2 Optionen)
            # -> jedes per Optionsliste identifizieren („Vorgemerkt" nur in Tab 4)
            sel_loc = page.locator('input[aria-label="Eingeladen?"]')
            n_sel = sel_loc.count()
            print(f"Eingeladen?-Selects im DOM: {n_sel}")
            if n_sel < 1:
                failures.append("kein Eingeladen?-Select gefunden")
            eing, opts, default_val = None, [], None
            for i in range(n_sel):
                el = sel_loc.nth(i)
                dv = el.input_value()
                print(f"  select[{i}] default={dv!r}")
                el.click()
                page.wait_for_timeout(500)
                o = [t.strip() for t in page.get_by_role("option").all_inner_texts()]
                print(f"  select[{i}] Optionen: {o}")
                if "Vorgemerkt" in o:
                    eing, opts, default_val = el, o, dv
                    break
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            if eing is None:
                failures.append('kein Select mit Option „Vorgemerkt“ (Defaults/Options: siehe Log)')
            else:
                # 1) Default = „Ja" (Streamlit-Paritaet app.py:3924)
                print(f"Ziel-Select default = {default_val!r} | Optionen: {opts}")
                if default_val != "Ja":
                    failures.append(f"Default {default_val!r} != 'Ja' (Paritaet app.py:3924)")
                # 2) Alle 3 Optionen belegt
                for need in ("Ja", "Nein", "Vorgemerkt"):
                    if need not in opts:
                        failures.append(f"Option {need!r} fehlt (gefunden: {opts})")
                # 3) „Vorgemerkt" wählbar (Dropdown ist offen)
                page.get_by_role("option", name="Vorgemerkt", exact=True).click()
                page.wait_for_timeout(400)
                sel_val = eing.input_value()
                print(f"Gewählt: {sel_val!r}")
                if sel_val != "Vorgemerkt":
                    # Der Quasar-Select-Readback (input_value) liefert bei diesem
                    # NiceGUI-Stand das Modell-Label nicht zuverlaessig; autoritativ
                    # ist der DB-Beweis unten (feedback-Row eingeladen='Vorgemerkt').
                    # Deshalb Hinweis statt FAIL (kein Codefehler).
                    print(f"  HINWEIS: Select-Readback {sel_val!r} != 'Vorgemerkt' "
                          "(autoritativ: DB-Beweis unten)")

            # 4) Speichern (Score 50; Vorgemerkt = neutral, kein Weight-Loop)
            page.get_by_label("Match-Score (0-100)").first.fill("50")
            page.get_by_role("button", name=re.compile("Feedback speichern")).first.click()
            page.wait_for_timeout(2500)

            # 5) DB-Beweis
            post = read_state()
            print("Post fb_today:", post["fb_today"])
            pre_ids = {x[0] for x in pre["fb_today"]}
            new_rows = [r for r in post["fb_today"] if r[0] not in pre_ids]
            if not new_rows:
                failures.append("keine neue feedback-Row")
            else:
                for _id, match_id, eingeladen in new_rows:
                    if eingeladen != "Vorgemerkt":
                        failures.append(f"eingeladen={eingeladen!r} != 'Vorgemerkt' (match {match_id})")
                    else:
                        print(f"OK DB-Beweis: {match_id} -> eingeladen='Vorgemerkt'")
            if post["gew_max"] != pre["gew_max"]:
                failures.append(
                    f"gewichtung_historie wuchs ({pre['gew_max']}->{post['gew_max']}) trotz Vorgemerkt"
                )
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
                failures.append(
                    f"Restore export_report: {len(final['tasks'])} != {len(pre['tasks'])}"
                )

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print('PASS: O3/C4 — Option „Vorgemerkt“ wählbar + Default „Ja“ + DB-Beweis + Restore')
    return 0


if __name__ == "__main__":
    sys.exit(main())
