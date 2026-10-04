"""B2-2 (c)2 E2E: Score-Filter passiver Matches im Feedback-Picker (view-only).

Ablauf:
1. Employer-Login -> /employer/feedback (default-Stelle = Job 1 des Testemployers)
2. Candidate-Select-Optionen gegen ein DB-Replik der Regel pruefen
   (Paritaet app.py:3911-3914 / employer.py::refresh_cands nach B2-2 (c)2):
   (a) passiver Nicht-Treffer fehlt im Select,
   (b) alle aktiven Bewerber sind IMMER drin (ungefiltert),
   (d) Reihenfolge = Bewerber ASC, danach passive (DESC) — unveraendert.
3. Stelle wechseln (Job 6) -> Regel fuer diese Stelle erneut pruefen.
4. (c) DB-Zaehlwerk vor/nach identisch (nur Lesen) + F3-Residue = 0.

Roter Beweis: vor dem (c)2-Fix failt (a) fuer Job 1 (passiver Kandidat 10
wird aktuell ohne Score-Pruefung angeboten), danach gruen.

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_feedback_filter.py
"""
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webui import logic  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
EMP_EMAIL = "hr@techvision.de"
EMP_PW = "sicher123"
JOB_TITEL_6 = "E2E-Beweis: Teststelle Phase1 (m/w/d)"


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
            "applications": conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
            "history": conn.execute(
                "SELECT COUNT(*) FROM application_status_history"
            ).fetchone()[0],
            "feedback": conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0],
            "max_task": conn.execute("SELECT COALESCE(MAX(id),0) FROM agent_tasks").fetchone()[0],
            "cand_status": conn.execute(
                "SELECT GROUP_CONCAT(id || ':' || status, '|') FROM (SELECT id, status FROM candidates ORDER BY id)"
            ).fetchone()[0],
        }
    finally:
        conn.close()


def expected_labels(job_id: int) -> list:
    """Replik refresh_cands() nach B2-2 (c)2: Bewerber ungefiltert ASC,
    passive Matches mit Score-Filter (>=1 Must-Have UND Exp >= 50%)."""
    conn = sqlite3.connect(str(DB))
    try:
        job = conn.execute(
            """SELECT j.hard_skills, j.soft_skills, j.berufserfahrung_jahre,
                      j.deutsch_level, j.englisch_level, j.standort, j.stellentyp,
                      e.branche
               FROM jobs j JOIN employers e ON e.id = j.employer_id
               WHERE j.id = ?""",
            (job_id,),
        ).fetchone()
        j_hard, j_soft, j_exp, j_de, j_en, j_st, j_typ, j_br = job
        applicants = conn.execute(
            """SELECT c.id, c.name FROM candidates c
               JOIN applications a ON a.candidate_id = c.id
               WHERE a.job_id = ?
                 AND a.status IN ('eingegangen', 'angesehen', 'eingeladen')
               ORDER BY a.erstellungsdatum ASC""",
            (job_id,),
        ).fetchall()
        passive = conn.execute(
            """SELECT c.id, c.name, c.hard_skills, c.soft_skills,
                      c.berufserfahrung_jahre, c.abschluss, c.deutsch, c.englisch,
                      c.standort, c.lebenslauf_text
               FROM candidates c
               WHERE c.status IN ('lebenslauf_hochgeladen', 'zugeordnet', 'aktiv')
                 AND c.id NOT IN (
                     SELECT candidate_id FROM applications
                     WHERE job_id = ?
                       AND status IN ('eingegangen', 'angesehen', 'eingeladen'))
               ORDER BY c.id DESC LIMIT 20""",
            (job_id,),
        ).fetchall()
        labels = [f"📩 {n or f'Kandidat #{i}'}" for i, n in applicants]
        for p in passive:
            cid, name = p[0], p[1]
            k = {"hard_skills": p[2], "soft_skills": p[3],
                 "berufserfahrung_jahre": p[4], "abschluss": p[5],
                 "deutsch": p[6], "englisch": p[7], "standort": p[8],
                 "lebenslauf_text": p[9] or ""}
            jd = {"hard_skills": j_hard, "soft_skills": j_soft,
                  "berufserfahrung_jahre": j_exp, "deutsch_level": j_de,
                  "englisch_level": j_en, "standort": j_st, "stellentyp": j_typ,
                  "branche": j_br}
            try:
                res = logic.berechne_match_score(k, jd)
            except Exception:
                res = {"matches": False}
            if not res.get("matches"):
                print(f"  drop #{cid}: kein Must-Have-Match")
                continue
            if j_exp and (p[4] or 0) < j_exp * 0.5:
                print(f"  drop #{cid}: Erfahrung {p[4]} < 50% von {j_exp}")
                continue
            labels.append(name or f"Kandidat #{cid}")
        return labels
    finally:
        conn.close()


def read_cand_options(page) -> list:
    sel = page.locator('input[aria-label="Kandidat"]')
    if sel.count() < 1:
        return []
    el = sel.first
    el.click()
    page.wait_for_timeout(500)
    opts = [t.strip() for t in page.get_by_role("option").all_inner_texts()]
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return opts


def pick_job(page, titel: str, failures: list) -> None:
    job_sel = page.locator('input[aria-label="Stelle"]')
    if job_sel.count() != 1:
        failures.append(f"Stelle-Inputs: {job_sel.count()} != 1")
        return
    # Robustheit (Runde 6): NiceGUI-JS-Timeouts koennen den ersten Klick
    # verschlucken (Log: 'JavaScript did not respond within 1.0 s') -> 2 Versuche.
    # Runde 7 (27.09.2026): 1. Lauf nach App-Start rot (Wert beider Versuche bei
    # 1.5 s noch alt, danach 3 gruene Laeufe + Reproduktions-Probe mit exakt dem
    # Ablauf -> Wert nach 0.5 s korrekt). Ursache: frueher Einzel-Auslesen waehrend
    # der Client/Server-Roundtrip-Phase, nicht Klick-Verlust.
    # Fix nur am Skript: Wert-Polling bis 6 s (24 x 250 ms), Nachlese nach
    # 600 ms (Rollback-Schutz), 3 Versuche, danach 2 s fuer refresh_cands().
    for attempt in (1, 2, 3):
        job_sel.first.click()
        page.wait_for_timeout(600)
        try:
            page.get_by_role("option", name=titel, exact=True).wait_for(timeout=5000)
        except Exception:
            print(f"  Stellen-Option {titel!r} nicht sichtbar (Versuch {attempt})")
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            continue
        page.get_by_role("option", name=titel, exact=True).click()
        got = ""
        for _ in range(24):  # Wert-Polling bis 6 s statt Einzelmessung bei 1.5 s
            page.wait_for_timeout(250)
            got = job_sel.first.input_value()
            if got == titel:
                break
        page.wait_for_timeout(600)
        got = job_sel.first.input_value()  # Nachlese: rueckgaengig gemachte Props?
        print(f"Stelle gewaehlt (Versuch {attempt}): {got!r}")
        if got == titel:
            page.wait_for_timeout(2000)  # serverseitiges refresh_cands() abwarten
            return
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    failures.append(f"Stellen-Wechsel griff nach 3 Versuchen nicht (!= {titel!r})")


def check_case(page, job_id: int, titel: str, failures: list) -> None:
    got = read_cand_options(page)
    exp = expected_labels(job_id)
    print(f"Job {job_id} ({titel}):")
    print(f"  erwartet ({len(exp)}): {exp}")
    print(f"  gerendert ({len(got)}): {got}")
    # (a) Nicht-Treffer fehlen: gerenderte passive Menge == erwartete passive Menge
    exp_passive = [l for l in exp if not l.startswith("📩 ")]
    got_passive = [l for l in got if not l.startswith("📩 ")]
    for l in exp_passive:
        if l not in got_passive:
            failures.append(f"Job {job_id}: erwarteter passiver Match fehlt im Select: {l!r}")
    for l in got_passive:
        if l not in exp_passive:
            failures.append(
                f"Job {job_id} (a): passiver NICHT-Treffer steht im Select (kein Score-Filter): {l!r}")
    # (b) Bewerber immer da + (d) ASC-Reihenfolge
    exp_apps = [l for l in exp if l.startswith("📩 ")]
    got_apps = [l for l in got if l.startswith("📩 ")]
    if got_apps != exp_apps:
        failures.append(f"Job {job_id} (b/d): Bewerber-Teil falsch: {exp_apps} != {got_apps}")
    else:
        print(f"  OK Bewerber ungefiltert + ASC ({len(exp_apps)})")
    if got != exp:
        failures.append(f"Job {job_id}: Gesamt-Reihenfolge/Inhalt weicht vom Replik ab")
    else:
        print(f"  OK Select == Replik ({len(exp)} Optionen)")


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    pre_counts = db_counts()
    failures = []
    print("DB vor:", pre_counts)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context()
            page = ctx.new_page()
            login_employer(page)
            page.goto(f"{BASE}/employer/feedback", wait_until="load", timeout=60000)
            page.wait_for_timeout(3500)
            n_sel = page.locator('input[aria-label="Kandidat"]').count()
            print(f"Kandidat-Selects im DOM: {n_sel}")
            if n_sel < 1:
                failures.append("kein Kandidat-Select auf /employer/feedback")
            else:
                # Default-Stelle = erste Zeile der jobs-Query (Job 1)
                check_case(page, 1, "Senior Cloud/DevOps Engineer (default)", failures)
                # Stelle wechseln -> Regel fuer Job 6
                pick_job(page, JOB_TITEL_6, failures)
                check_case(page, 6, JOB_TITEL_6, failures)
            ctx.close()
        finally:
            browser.close()

    post_counts = db_counts()
    print("DB nach:", post_counts)
    if pre_counts != post_counts:
        failures.append(f"(c) DB geaendert: {pre_counts} != {post_counts}")
    else:
        print("OK: DB-Zaehlwerk unveraendert (nur lesend)")

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")

    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: B2-2 (c)2 — passiver Score-Filter im Feedback-Picker, Bewerber "
          "ungefiltert+ASC, DB unveraendert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
