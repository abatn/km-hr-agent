"""E2E A2 (30.09.2026): Bewerben-Dialog bei MEHREREN Stellen (Late-Binding-Regression).

Befund: In webui/pages/candidate.py::_tab_stellen war `_open_apply_dialog` eine Closure über
die Schleifenvariablen j_id/j_titel/e_firma -> jeder "Bewerben"-Button öffnete den Dialog der
LETZTEN Stelle der Liste und bewarb auf deren job_id. Fix: Default-Argumente.

NUR gegen die Isolations-Instanz (der Test löscht in der Spiegel-DB Bewerbungen von cand 1):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8091 --only e2e_apply_dialog_multi

Ablauf (>= 2 Stellen, NICHT die letzte der Liste, damit Late Binding auffällt):
 0 Guard: DB-Pfad != Live-DB, sonst Abbruch (exit 2). Bewerbungen von cand 1 auf allen Jobs
   ausser der niedrigsten Job-ID (= letzte Karte, id DESC) werden in der Spiegel-DB entfernt.
 1 Für jede Ziel-Stelle: Karte -> "Bewerben" -> Dialogtitel "Bewerbung: <Titel>" + Firma
   müssen zur angeklickten Karte passen (nicht zur letzten).
 2 "Jetzt bewerben" -> DB: genau EINE neue Bewerbung, job_id == Ziel-Stelle.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import BASE, DB, check_server, seed_email

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = (ROOT / "data" / "feedback.db").resolve()
CAND_ID = 1
EMAIL = seed_email("batniniabdelkader@yahoo.com")
PASSWORD = "Abdel15121978!"


def login(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    panel = page.locator(".q-tab-panel:visible").first
    panel.get_by_label("E-Mail").fill(EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(PASSWORD)
    panel.get_by_role("button").first.click()
    page.wait_for_url("**/candidate**", timeout=15000)


def prepare() -> list:
    """Räumt in der SPIEGEL-DB Bewerbungen von cand 1 frei; liefert Ziel-Jobs [(id, titel, firma)]."""
    conn = sqlite3.connect(str(DB))
    try:
        jobs = conn.execute(
            "SELECT j.id, j.titel, e.firma FROM jobs j JOIN employers e ON e.id=j.employer_id "
            "WHERE j.status='aktiv' ORDER BY j.id DESC").fetchall()
        if len(jobs) < 3:
            return []
        letzte = jobs[-1][0]  # niedrigste ID = letzte Karte (ORDER BY id DESC, ohne Score)
        ziele = [j for j in jobs if j[0] != letzte][:2]
        for jid, _, _ in ziele:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM applications WHERE candidate_id=? AND job_id=?", (CAND_ID, jid))]
            for aid in ids:
                conn.execute("DELETE FROM application_status_history WHERE application_id=?", (aid,))
                conn.execute("DELETE FROM applications WHERE id=?", (aid,))
        conn.commit()
        return ziele
    finally:
        conn.close()


def apps_for(job_id: int) -> list:
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute(
            "SELECT id FROM applications WHERE candidate_id=? AND job_id=?",
            (CAND_ID, job_id)).fetchall()
    finally:
        conn.close()


def main() -> int:
    if Path(DB).resolve() == LIVE_DB:
        print("ABBRUCH: DB-Pfad ist die Live-DB — nur via tests/e2e_isolation.py ausführen")
        return 2
    check_server()
    ziele = prepare()
    if not ziele:
        print("SKIP: weniger als 3 aktive Stellen in der Spiegel-DB")
        return 0
    print(f"Ziel-Stellen: {ziele}")
    fehler = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)
        try:
            login(page)
            for jid, titel, firma in ziele:
                page.goto(f"{BASE}/candidate/stellen", wait_until="load", timeout=90000)
                card = page.locator(".q-card").filter(has_text=re.compile(rf"#{jid} ")).first
                card.wait_for(timeout=30000)
                card.get_by_role("button", name="Bewerben").click()
                dlg = page.locator(".q-dialog")
                dlg.wait_for(timeout=10000)
                text = dlg.inner_text()
                erwartet = f"Bewerbung: {titel}"
                if erwartet in text and firma in text:
                    print(f"job {jid}: Dialogtitel OK ({erwartet!r}, Firma {firma!r})")
                else:
                    fehler.append(f"job {jid}: Dialog zeigt {text[:120]!r}, erwartet {erwartet!r}")
                vorher = apps_for(jid)
                page.get_by_role("button", name="Jetzt bewerben").click()
                page.get_by_text("Bewerbung gesendet!").wait_for(timeout=8000)
                page.wait_for_timeout(1500)
                nachher = apps_for(jid)
                print(f"job {jid}: Bewerbungen vorher={len(vorher)} nachher={len(nachher)}")
                if len(vorher) != 0 or len(nachher) != 1:
                    fehler.append(f"job {jid}: Bewerbung nicht auf dieser job_id "
                                  f"(vorher={len(vorher)}, nachher={len(nachher)})")
        except Exception as ex:  # noqa: BLE001
            fehler.append(f"Exception: {ex!r}")
        finally:
            browser.close()
    if fehler:
        print("FAIL:")
        for f in fehler:
            print("  -", f)
        return 1
    print("PASS: Dialogtitel + Bewerbung passen bei mehreren Stellen zur angeklickten Karte")
    return 0


if __name__ == "__main__":
    sys.exit(main())
