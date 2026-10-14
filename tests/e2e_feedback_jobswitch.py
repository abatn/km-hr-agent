"""N-F1 E2E: Feedback-Save nach Stellenwechsel am AKTUELL gewählten Kandidaten.

Roter Beweis: refresh_cands() zerstoert den alten Kandidaten-Select
(cand_container.clear(), Codemark refresh_cands, employer.py, Messung 13.10.2026)
und der Stellen-Handler wirkt den Rueckgabewert weg -> save_feedback liest die tote
Referenz (Kandidat der VORHERIGEN Stelle X) statt den im neuen Picker gewählten Y.

Ablauf:
1. Fixture (AGENTS.md Klasse a, 13.10.2026): fehlende Bewerber auf Job 1/6 werden
   im Spiegel selbst angelegt und am Ende entfernt (statt SKIP).
2. Employer-Login -> /employer/feedback (default Stelle Job 1, X = 1. Bewerber)
3. Stellenwechsel -> Job 6 (PICK_JOB, alter Select wird dabei zerstoert)
4. IM neuen Picker Kandidat Y waehlen ( != Default, != X ), Anmerkung = Marker
5. "Feedback speichern" (💾)
6. DB: Marker-Zeile -> match_id == employer-job-6-cand-{Y}-{heute}
   (vor dem Fix: cand-{X} -> FAIL)

Seiteneffekte ausgeschlossen: VOR dem Save existieren beide denkbaren
match_ids als Testzeilen -> der Save nimmt IMMER den UPDATE-Pfad
(is_new=False -> kein adjust_weights, kein export_report-Task).
Cleanup entfernt die eigenen Testzeilen wieder (Ausgangs-DB-Zaehlwerk).

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_feedback_jobswitch.py
"""
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
from e2e_feedback_filter import JOB_TITEL_6, login_employer, pick_job

EMP_EMAIL = seed_email("hr@techvision.de")
JOB_1_ID = 1
JOB_6_ID = 6
ACTIVE = "('eingegangen','angesehen','eingeladen')"


def scalar(sql, args=()):
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


def applicants(job_id: int) -> list:
    """1. Bewerber-Teil des refresh_cands-Repliks (ASC)."""
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute(
            f"""SELECT c.id, c.name FROM candidates c
               JOIN applications a ON a.candidate_id = c.id
               WHERE a.job_id = ?
                 AND a.status IN {ACTIVE}
               ORDER BY a.erstellungsdatum ASC""",
            (job_id,),
        ).fetchall()
    finally:
        conn.close()


def seed_applicants(need: dict[int, int]) -> list[int]:
    """Legt fehlende aktive Bewerber je Stelle im Spiegel an (AGENTS.md Klasse a,
    13.10.2026) und gibt die angelegten application-IDs zurueck (Cleanup Pflicht).
    Kandidaten werden pro Stelle neu gewaehlt und nicht wiederverwendet, damit
    X (Job 1) != Y (Job 6) konstruierbar bleibt."""
    created: list[int] = []
    conn = sqlite3.connect(str(DB))
    try:
        used: set[int] = set()
        for job_id, min_count in need.items():
            have = [r[0] for r in conn.execute(
                f"SELECT candidate_id FROM applications WHERE job_id=? AND status IN {ACTIVE}",
                (job_id,)).fetchall()]
            used.update(have)
            missing = max(0, min_count - len(have))
            if not missing:
                continue
            sql = ("SELECT c.id FROM candidates c WHERE COALESCE(c.name,'') != '' "
                   "AND NOT EXISTS (SELECT 1 FROM applications a "
                   "                WHERE a.candidate_id=c.id AND a.job_id=?)")
            args: list = [job_id]
            if used:
                sql += " AND c.id NOT IN (%s)" % ",".join("?" * len(used))
                args.extend(sorted(used))
            sql += " ORDER BY c.id LIMIT ?"
            args.append(missing)
            for (cid,) in conn.execute(sql, args).fetchall():
                cur = conn.execute(
                    "INSERT INTO applications (candidate_id, job_id, status) "
                    "VALUES (?, ?, 'eingegangen')", (cid, job_id))
                created.append(cur.lastrowid)
                used.add(cid)
                print(f"OK Fixture: Bewerbung #{cur.lastrowid} cand{cid} -> "
                      f"job{job_id} ('eingegangen')")
        conn.commit()
    finally:
        conn.close()
    return created


def remove_applicants(ids: list[int]) -> None:
    if not ids:
        return
    conn = sqlite3.connect(str(DB))
    try:
        for aid in ids:
            conn.execute(
                "DELETE FROM application_status_history WHERE application_id=?",
                (aid,))
            conn.execute("DELETE FROM applications WHERE id=?", (aid,))
        conn.commit()
    finally:
        conn.close()
    print(f"OK Fixture entfernt: Bewerbungen {ids}")


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    pre_gew = scalar("SELECT COALESCE(MAX(id),0) FROM gewichtung_historie")
    fb_before = scalar("SELECT COUNT(*) FROM feedback")  # echter Ausgangszustand
    failures: list[str] = []

    # Fixture (AGENTS.md Klasse a, 13.10.2026): Vorbedingung selbst herstellen
    # statt SKIP — finally rollt zurueck, auch bei Fehlerpfaden.
    fixture_apps = seed_applicants({JOB_1_ID: 1, JOB_6_ID: 2})
    try:
        jobs1 = applicants(JOB_1_ID)
        jobs6 = applicants(JOB_6_ID)
        if not jobs1 or not jobs6:
            print(f"FAIL: Bewerber fehlen (job1={len(jobs1)}, job6={len(jobs6)})")
            return 1
        x_id, x_name = jobs1[0]  # Default der Job-1-Seite
        default6 = jobs6[0][0]
        y_pick = [c for c in jobs6 if c[0] != x_id and c[0] != default6] or [
            c for c in jobs6 if c[0] != x_id
        ]
        if not y_pick:
            print("FAIL: kein Kandidat Y != X fuer Job 6 vorhanden")
            return 1
        y_id, y_name = y_pick[0]
        y_label = y_name or f"Kandidat #{y_id}"

        today = datetime.now().strftime("%Y-%m-%d")
        mid_stale = f"employer-job-{JOB_6_ID}-cand-{x_id}-{today}"  # Ziel VOR Fix
        mid_y = f"employer-job-{JOB_6_ID}-cand-{y_id}-{today}"  # Ziel NACH Fix
        marker = f"N-F1-JOBSWITCH {today} {int(time.time())}"

        # Testzeilen VORAB anlegen -> Save greift immer UPDATE (keine Nebenwirkungen)
        created = []
        conn = sqlite3.connect(str(DB))
        for mid, nm in ((mid_stale, x_name or f"Kandidat #{x_id}"),
                        (mid_y, y_label)):
            if not conn.execute(
                    "SELECT 1 FROM feedback WHERE match_id = ?", (mid,)).fetchone():
                conn.execute(
                    """INSERT INTO feedback
                       (match_id, kandidat_name, stellenprofil, score, kategorie,
                        eingeladen, anmerkungen)
                       VALUES (?, ?, ?, 85, 'Gut', 'Ja', '')""",
                    (mid, nm, JOB_TITEL_6))
                created.append(mid)
        conn.commit()
        conn.close()
        print(f"Vorbereitung: X=#{x_id} ({x_name})  Y=#{y_id} ({y_label})  "
              f"Default(Job6)=#{default6}  Testzeilen angelegt: {created}")
        # Snapshot NACH dem Anlegen der Testzeilen (sonst zaehlt +2 als INSERT-Schaden)
        pre_fb = scalar("SELECT COUNT(*) FROM feedback")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context()
                page = ctx.new_page()
                login_employer(page)
                page.goto(f"{BASE}/employer/feedback", wait_until="load", timeout=60000)
                page.wait_for_timeout(3500)

                cand_sel = page.locator('input[aria-label="Kandidat"]')
                if cand_sel.count() != 1:
                    failures.append(f"Kandidat-Inputs: {cand_sel.count()} != 1")
                else:
                    before = cand_sel.first.input_value()
                    print(f"Default-Anzeige (Job 1 = X): {before!r}")

                    # Stellenwechsel -> alter Select wird zerstoert
                    pick_job(page, JOB_TITEL_6, failures)

                    # Neuen Picker Y explizit waehlen (Default ist #{default6})
                    cand_sel = page.locator('input[aria-label="Kandidat"]')
                    if cand_sel.count() != 1:
                        failures.append(
                            f"nach Wechsel: Kandidat-Inputs {cand_sel.count()} != 1")
                    else:
                        cand_sel.first.click()
                        page.wait_for_timeout(600)
                        opt = page.get_by_role("option", name=y_label, exact=False)
                        if opt.count() < 1:
                            failures.append(f"Option {y_label!r} fehlt im Job-6-Picker")
                        else:
                            opt.first.click()
                            got = ""
                            for _ in range(24):
                                page.wait_for_timeout(250)
                                got = cand_sel.first.input_value()
                                if y_label in got:
                                    break
                            page.wait_for_timeout(400)
                            print(f"Picker zeigt nach Wahl: {got!r}")
                            if y_label not in got:
                                failures.append(
                                    f"Picker zeigt nicht Y: {got!r} != {y_label!r}")

                            # Anmerkung = Marker, dann speichern
                            ta = page.get_by_label("Anmerkungen", exact=True)
                            if ta.count() != 1:
                                failures.append(
                                    f"Anmerkungen-Inputs: {ta.count()} != 1")
                            else:
                                ta.first.fill(marker)
                                page.get_by_role(
                                    "button", name="💾 Feedback speichern", exact=True
                                ).click()
                                # Marker-Zeile pollen (Roundtrip)
                                row = None
                                for _ in range(24):
                                    page.wait_for_timeout(250)
                                    conn = sqlite3.connect(str(DB))
                                    row = conn.execute(
                                        "SELECT match_id, kandidat_name FROM feedback "
                                        "WHERE anmerkungen = ?", (marker,)).fetchone()
                                    conn.close()
                                    if row:
                                        break
                                if not row:
                                    failures.append(
                                        "keine Feedback-Zeile mit Marker nach Save")
                                else:
                                    print(f"GESPEICHERT: match_id={row[0]!r} "
                                          f"kandidat_name={row[1]!r}")
                                    if row[0] != mid_y:
                                        failures.append(
                                            f"falsches match_id: {row[0]!r} != {mid_y!r} "
                                            f"(erwartet Kandidat Y #{y_id})")
                ctx.close()
            finally:
                browser.close()

        # Nebenwirkungs-Kontrolle (UPDATE-Pfad erwartet: nichts neu)
        post_gew = scalar("SELECT COALESCE(MAX(id),0) FROM gewichtung_historie")
        post_fb = scalar("SELECT COUNT(*) FROM feedback")
        print(f"gewichtung_historie max: {pre_gew} -> {post_gew} | "
              f"feedback COUNT: {pre_fb} -> {post_fb}")
        if post_gew != pre_gew:
            failures.append(
                f"adjust_weights ausgeloest: gewichtung max {pre_gew} -> {post_gew}")
        if post_fb != pre_fb:
            failures.append(f"feedback-Zeilen geaendert (INSERT?): {pre_fb} -> {post_fb}")

        # Cleanup eigener Testzeilen (Restaurierung Ausgangszustand)
        conn = sqlite3.connect(str(DB))
        for mid in created:
            conn.execute("DELETE FROM feedback WHERE match_id = ?", (mid,))
        if not created:
            conn.execute("UPDATE feedback SET anmerkungen = '' WHERE anmerkungen = ?",
                         (marker,))
        conn.commit()
        post_cleanup = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        conn.close()
        print(f"Cleanup: created={created}, feedback COUNT danach={post_cleanup} "
              f"(Soll {fb_before})")
        if post_cleanup != fb_before:
            failures.append(f"Cleanup unvollstaendig: {fb_before} -> {post_cleanup}")

        residue = db_residue_report(pre_tasks)
        if residue:
            failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")

        if failures:
            print("FAIL:")
            for f in failures:
                print(" -", f)
            return 1
        print("PASS: N-F1 — Feedback nach Stellenwechsel landet beim im NEUEN "
              "Picker gewählten Kandidaten (match_id = cand-Y), keine Nebenwirkungen")
        return 0
    finally:
        remove_applicants(fixture_apps)


if __name__ == "__main__":
    sys.exit(main())
