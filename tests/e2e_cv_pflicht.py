"""B2 E2E: CV-Pflicht vor Bewerbung (GO B2-3).

Spec: knowledge/portal/cv-pflicht.md — Bewerben erst ab Status
'lebenslauf_hochgeladen' / 'profil_geprueft' / 'match_berechnet' / 'eingeladen',
Paritaet app.py:3279 (Streamlit-Wahrheit), Quelltext-Stellen candidate.py
(cv_ok + Warnung + 🔒-Button) und db.py::apply_to_job (harter Guard vor INSERT).

Warum nicht e2e_apply_dialog: dessen feste Voraussetzung cand1×job6 ist seit
24.09.2026 durch App #27 ('eingestellt') belegt — der Test faellt VOR jeder
UI-Interaktion auf der Datenlage aus (vorbestehend, nicht B2-bedingt).

Ablauf:
 A QUELLTEXT  3 Listen (candidate.py cv_ok, db.py Guard, app.py:3279) exakt gleich
 B DB-GUARD   apply_to_job(cand16='registriert') -> ValueError, apps+Tasks unveraendert
 C UI SPERRE  Candidate-Login cand16 -> /candidate/stellen: Warnung + 🔒-Buttons
 D UI FREIGABE temporärer Status 'lebenslauf_hochgeladen' (finally zurueckgesetzt)
              -> reload -> normale 'Bewerben'-Buttons, keine 🔒-Buttons mehr
 Baselines: applications COUNT, agent_tasks MAX, candidates.status(cand16) — alle
 vor/nach identisch (reines Rendern + ein Guard-Aufruf ohne Write).

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_cv_pflicht.py
"""
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webui import db as webui_db  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
CAND_ID = 16
CAND_EMAIL = "e2e-beweis-phase1@example.com"
CAND_PASSWORD = "E2EMentoring2026!"
CAND_NEG_STATUS = "registriert"
CAND_POS_STATUS = "lebenslauf_hochgeladen"
LIST_OK = ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")


def db_state() -> dict:
    conn = sqlite3.connect(str(DB))
    try:
        return {
            "apps": conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
            "max_task": conn.execute("SELECT COALESCE(MAX(id),0) FROM agent_tasks").fetchone()[0],
            "status": conn.execute("SELECT status FROM candidates WHERE id=?",
                                   (CAND_ID,)).fetchone()[0],
        }
    finally:
        conn.close()


def set_status(status: str) -> None:
    conn = sqlite3.connect(str(DB))
    try:
        conn.execute("UPDATE candidates SET status=? WHERE id=?", (status, CAND_ID))
        conn.commit()
    finally:
        conn.close()


def login(page):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.get_by_label("E-Mail").fill(CAND_EMAIL)
    page.get_by_label("Passwort", exact=True).fill(CAND_PASSWORD)
    page.get_by_role("button", name="Einloggen").click()
    page.wait_for_url("**/candidate**", timeout=15000)


def check_a(failures) -> None:
    cand_src = (ROOT / "webui" / "pages" / "candidate.py").read_text(encoding="utf-8")
    db_src = (ROOT / "webui" / "db.py").read_text(encoding="utf-8")
    app_src = (ROOT / "app.py").read_text(encoding="utf-8")

    m_cand = re.search(r"cv_ok = bool\(cand\) and \(cand\[8\] or \"\"\) in \((.*?)\)",
                       cand_src, re.S)
    m_db = re.search(r"_row\[0\] not in \((.*?)\)", db_src, re.S)
    m_app = re.search(r"cv_ok = mein_status in \((.*?)\)", app_src, re.S)
    if not (m_cand and m_db and m_app):
        failures.append(f"A cv_ok-Liste nicht gefunden (candidate={bool(m_cand)}, "
                        f"db={bool(m_db)}, app={bool(m_app)})")
        return
    l_cand = eval("(" + m_cand.group(1) + ")")  # noqa: S307 — Quelltext-Konstante
    l_db = eval("(" + m_db.group(1) + ")")  # noqa: S307
    l_app = eval("(" + m_app.group(1) + ")")  # noqa: S307
    print(f"A Listen: candidate={l_cand} db={l_db} app={l_app}")
    if tuple(l_cand) != LIST_OK or tuple(l_db) != LIST_OK or tuple(l_app) != LIST_OK:
        failures.append(f"A Listen abweichend vom Paritaets-Standard {LIST_OK}")

    for needle, src, desc in [
        ("CV-Pflicht: Bewerben ist erst nach Lebenslauf-Upload", cand_src, "Warnung candidate.py"),
        ("🔒 Lebenslauf nötig", cand_src, "🔒-Button candidate.py"),
        ("if not cv_ok:", cand_src, "Gate candidate.py"),
        ("CV-Pflicht: Status", db_src, "Guard-Text db.py"),
        ("raise ValueError", db_src, "Guard-Raise db.py"),
    ]:
        ok = needle in src
        print(f"A {desc}: {'OK' if ok else 'FEHLT'}")
        if not ok:
            failures.append(f"A {desc} fehlt")


def check_b(before: dict, failures) -> None:
    if before["status"] != CAND_NEG_STATUS:
        failures.append(f"B Vorbedingung: cand{CAND_ID} Status {before['status']!r} "
                        f"!= {CAND_NEG_STATUS!r}")
        return
    job_row = None
    conn = sqlite3.connect(str(DB))
    try:
        job_row = conn.execute("SELECT id FROM jobs WHERE status='aktiv' ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()
    try:
        webui_db.apply_to_job(CAND_ID, job_row[0], "B2-3 E2E: darf nicht geschrieben werden.")
        failures.append(f"B apply_to_job(cand{CAND_ID}) hat NICHTS geworfen")
    except ValueError as ex:
        print(f"B Guard: ValueError erwartet: {ex}")
    except Exception as ex:  # noqa: BLE001
        failures.append(f"B unerwartete Exception: {ex!r}")
    after = db_state()
    print(f"B nachher: apps={after['apps']} max_task={after['max_task']} status={after['status']}")
    if after["apps"] != before["apps"] or after["max_task"] != before["max_task"]:
        failures.append(f"B DB unveraendert verletzt: vor {before} / nach {after}")


def check_c(page, failures) -> None:
    page.goto(f"{BASE}/candidate/stellen", wait_until="load", timeout=90000)
    page.wait_for_timeout(2500)
    body = page.locator("body").inner_text()
    warn = "CV-Pflicht: Bewerben ist erst nach Lebenslauf-Upload" in body
    lock_btns = page.get_by_role("button", name=re.compile("Lebenslauf nötig")).count()
    open_btns = page.get_by_role("button", name="Bewerben", exact=True).count()
    print(f"C Warnung={warn} 🔒-Buttons={lock_btns} Bewerben-Buttons={open_btns}")
    if not warn:
        failures.append("C CV-Pflicht-Warnung fehlt")
    if lock_btns < 1:
        failures.append("C kein 🔒-Button sichtbar")
    if open_btns > 0:
        failures.append(f"C {open_btns} freie 'Bewerben'-Buttons trotz fehlendem CV")


def check_d(page, failures) -> None:
    set_status(CAND_POS_STATUS)
    page.goto(f"{BASE}/candidate/stellen", wait_until="load", timeout=90000)
    page.reload(wait_until="load")
    page.wait_for_timeout(2500)
    body = page.locator("body").inner_text()
    warn = "CV-Pflicht: Bewerben ist erst nach Lebenslauf-Upload" in body
    lock_btns = page.get_by_role("button", name=re.compile("Lebenslauf nötig")).count()
    open_btns = page.get_by_role("button", name="Bewerben", exact=True).count()
    print(f"D Warnung={warn} 🔒-Buttons={lock_btns} Bewerben-Buttons={open_btns}")
    if warn:
        failures.append("D Warnung trotz freigegebenem Status")
    if lock_btns > 0:
        failures.append(f"D {lock_btns} 🔒-Buttons trotz freigegebenem Status")
    if open_btns < 1:
        failures.append("D kein freier 'Bewerben'-Button bei Status 'lebenslauf_hochgeladen'")


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    before = db_state()
    print(f"DB-Baseline vor: {before}")
    failures = []
    check_a(failures)
    check_b(before, failures)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)
        try:
            login(page)
            check_c(page, failures)
            check_d(page, failures)
        except Exception as ex:  # noqa: BLE001
            failures.append(f"Exception: {ex!r}")
        finally:
            set_status(CAND_NEG_STATUS)
            browser.close()

    after = db_state()
    print(f"DB-Baseline nach (Restore): {after}")
    if after["status"] != CAND_NEG_STATUS:
        failures.append(f"Restore verletzt: Status {after['status']!r} != {CAND_NEG_STATUS!r}")
    if after["apps"] != before["apps"]:
        failures.append(f"apps veraendert {before['apps']} -> {after['apps']}")
    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: B2-3 CV-Pflicht — 3 Listen paritaetisch, DB-Guard wirft, "
          "UI gesperrt ohne CV / frei mit CV, DB unveraendert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
