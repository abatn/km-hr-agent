"""E2E Hiring-Board Aktionen (MVP Arbeitgeber-UI, 19.10.2026).

Prueft am ISOLATIONS-Spiegel (nie :8080):
1) Kartenklick im Aktiv-Tab oeffnet den Detail-Drawer (rechts verankertes
   Dialog, `position=right`, Codemark `_board_drawer`/`_open_board_drawer`).
2) Bei Status `eingeladen` zeigt der Drawer **Einstellen** und
   **Visum-Info/Schritte**; **Onboarding** erst nach `eingestellt`.
3) Einstellen schreibt 1:1 die do_hire-Sequenz: UPDATE + History
   (`changed_by 'arbeitgeber'`) + `onboarding_release`-Task
   (`trigger=hr_klick_portal`) + Kandidaten-Notification.
3b) Nach dem Einstellen bleibt **Visum-Info/Schritte** verfügbar
   (`VISA_INFO_STATUS`, 19.10.2026) und loest `visa_confirmation` aus.
4) Onboarding-Aktion ist reine Navigation auf /employer/onboarding
   (kein zweiter Trigger).
5) Restore + residue=0.

Datengetrieben: Arbeitgeber/Bewerbung werden aus dem Spiegel gewaehlt
(Seed- und Live-Modus), Login-E-Mail aus `employers.email`.
"""
import re
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import BASE, DB, SEED_MODE, check_server, db_residue_report, pre_max_tasks  # noqa: E402
from webui.pages.employer import anzeige_name  # noqa: E402

EMP_PW = "sicher123"
# Seed-Modus: Arbeitgeber wird datengetrieben aus der ersten `eingeladen`-Zeile
# gewaehlt (Fixture = 1, CI-Seed = 4; beide mit E2E-Passwort `sicher123`).
# Live-Modus: nur Employer 1 (dort ist `sicher123` verifiziert; Employer 4 hat
# live ein echtes, unbekanntes Passwort).
EMPLOYER_ID = 4 if SEED_MODE else 1
LIVE_DB = (ROOT / "data" / "feedback.db").resolve()


def _ro():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def _pick_case():
    """(employer_id, app_id, candidate_id, name, email) einer eingeladenen Bewerbung.

    Bewerbungen mit bereits vorhandenem `visa_confirmation`-Task werden
    ausgeschlossen: dort rendert `visa_info_section` den „versendet"-Hinweis
    statt des Buttons (Fix 19.10.2026, deterministisch fuer Seed + Live).
    """
    NO_VISA = (
        " AND NOT EXISTS (SELECT 1 FROM agent_tasks t WHERE t.task_type = 'visa_confirmation'"
        " AND t.status IN ('pending','running','done')"
        " AND json_extract(t.payload,'$.application_id') = a.id)"
    )
    conn = _ro()
    try:
        if SEED_MODE:
            # Seed-Modus: Arbeitgeber datengetrieben (Fixture: 1, CI-Seed: 4);
            # beide tragen das bekannte E2E-Passwort `sicher123`.
            row = conn.execute(
                "SELECT j.employer_id, a.id, a.candidate_id, c.name "
                "FROM applications a JOIN jobs j ON j.id = a.job_id "
                "JOIN candidates c ON c.id = a.candidate_id "
                "WHERE a.status = 'eingeladen'" + NO_VISA +
                " ORDER BY a.id LIMIT 1").fetchone()
        else:
            # Live-Modus: nur Employer 1 (dort ist `sicher123` verifiziert;
            # Employer 4 hat live ein echtes, unbekanntes Passwort).
            row = conn.execute(
                "SELECT j.employer_id, a.id, a.candidate_id, c.name "
                "FROM applications a JOIN jobs j ON j.id = a.job_id "
                "JOIN candidates c ON c.id = a.candidate_id "
                "WHERE a.status = 'eingeladen' AND j.employer_id = ?" + NO_VISA +
                " ORDER BY a.id LIMIT 1", (EMPLOYER_ID,)).fetchone()
        if not row:
            return None
        email = conn.execute("SELECT email FROM employers WHERE id = ?",
                             (row[0],)).fetchone()[0]
        return (*row, email)
    finally:
        conn.close()


def login_employer(page, email: str):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(700)
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I))
    ).first
    panel.get_by_label("E-Mail").fill(email)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def _status(app_id: int) -> str:
    conn = _ro()
    try:
        return conn.execute("SELECT status FROM applications WHERE id = ?",
                            (app_id,)).fetchone()[0]
    finally:
        conn.close()


def _wait_status(app_id: int, expected: str, timeout=12.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if _status(app_id) == expected:
            return True
        time.sleep(0.25)
    return False


def _visa_task_da(app_id: int, pre_tasks: int) -> bool:
    """Wurde nach pre_tasks ein visa_confirmation-Task fuer diese Bewerbung angelegt?"""
    conn = sqlite3.connect(DB)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM agent_tasks WHERE id > ? AND task_type = 'visa_confirmation' "
            "AND json_extract(payload,'$.application_id') = ?",
            (pre_tasks, app_id)).fetchone()[0] > 0
    finally:
        conn.close()


def main() -> None:
    # Sicherheitsnetz: dieser Test SCHREIBT (Status/History/Task/Notification).
    # Nur auf einem Isolations-Spiegel, nie auf der Live-DB.
    if Path(DB).resolve() == LIVE_DB:
        print(f"ABBRUCH: DB ist die Live-DB ({DB}) — E2E nur isoliert")
        sys.exit(2)
    check_server()
    case = _pick_case()
    if not case:
        if SEED_MODE:
            print("FAIL: Seed-Modus ohne Bewerbung mit Status 'eingeladen'")
            sys.exit(2)
        print("SKIP: keine Bewerbung mit Status 'eingeladen' (Live-Modus)")
        sys.exit(0)
    employer_id, app_id, cand_id, name, email = case
    label = anzeige_name(name, cand_id, "eingeladen")
    print(f"FALL employer={employer_id} app={app_id} kandidat={cand_id} label={label!r}")

    pre_tasks = pre_max_tasks()
    conn = sqlite3.connect(DB)
    base_hist = conn.execute("SELECT COALESCE(MAX(id),0) FROM application_status_history").fetchone()[0]
    base_notif = conn.execute("SELECT COALESCE(MAX(id),0) FROM notifications").fetchone()[0]
    conn.close()

    ok = False
    created_files: set = set()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            try:
                login_employer(page, email)
                # Navigation ohne hartes goto (Hang-Falle, i18n-runner-chain §5).
                page.get_by_role("button", name=re.compile("Hiring-Board")).first.click()
                page.wait_for_timeout(1200)
                assert "/employer/board" in page.url, page.url
                page.get_by_role("tab", name=re.compile("Aktiv")).click()
                page.wait_for_timeout(500)

                # 1) Kartenklick -> Drawer
                page.get_by_text(label, exact=True).first.click()
                drawer = page.locator(".q-dialog:visible").filter(has_text="Bewerbungsdetails")
                drawer.wait_for(state="visible", timeout=8000)
                assert drawer.get_by_text("Einstellen", exact=True).count() >= 1
                assert drawer.get_by_text("Visum-Info/Schritte", exact=True).count() >= 1
                assert drawer.get_by_text("Onboarding", exact=True).count() == 0, \
                    "Onboarding darf vor dem Einstellen nicht angeboten werden"
                print("DRAWER: offen, Einstellen + Visum-Info/Schritte sichtbar, Onboarding aus")

                # 2) Einstellen + Bestaetigung
                drawer.get_by_text("Einstellen", exact=True).click()
                hire = page.locator(".q-dialog:visible").filter(has_text="Kandidat einstellen")
                hire.wait_for(state="visible", timeout=5000)
                hire.get_by_text("Einstellen", exact=True).click()
                assert _wait_status(app_id, "eingestellt"), \
                    f"Status blieb {_status(app_id)!r}"
                print("HIRE: applications.status = eingestellt")

                # 3) History + Task + Notification
                conn = sqlite3.connect(DB)
                hist = conn.execute(
                    "SELECT status, changed_by FROM application_status_history "
                    "WHERE id > ? AND application_id = ?",
                    (base_hist, app_id)).fetchall()
                tasks = conn.execute(
                    "SELECT payload FROM agent_tasks WHERE id > ? AND task_type = 'onboarding_release' "
                    "AND json_extract(payload,'$.application_id') = ?",
                    (pre_tasks, app_id)).fetchall()
                notifs = conn.execute(
                    "SELECT COUNT(*) FROM notifications WHERE id > ? AND user_id = ? AND role = 'candidate'",
                    (base_notif, cand_id)).fetchone()[0]
                conn.close()
                assert ("eingestellt", "arbeitgeber") in hist, hist
                assert len(tasks) == 1, tasks
                assert '"trigger": "hr_klick_portal"' in tasks[0][0], tasks[0][0]
                assert notifs >= 1, notifs
                print("DB: +1 History(arbeitgeber), +1 onboarding_release(hr_klick_portal), Notification")

                # 4) Nach Reload: Onboarding + Visum-Info (auch bei `eingestellt`)
                page.wait_for_timeout(1500)
                page.get_by_role("button", name=re.compile("Hiring-Board")).first.click()
                page.wait_for_timeout(1200)
                page.get_by_text(label, exact=True).first.click()
                drawer2 = page.locator(".q-dialog:visible").filter(has_text="Bewerbungsdetails")
                drawer2.wait_for(state="visible", timeout=8000)
                onboard = drawer2.get_by_text("Onboarding", exact=True)
                assert onboard.count() >= 1, "Onboarding fehlt nach eingestellt"
                visa = drawer2.get_by_text("Visum-Info/Schritte", exact=True)
                assert visa.count() >= 1, "Visum-Info fehlt nach eingestellt (VISA_INFO_STATUS)"
                print("DRAWER nach HIRE: Onboarding + Visum-Info/Schritte sichtbar")

                # 4b) Visum-Info nach dem Einstellen ausloesen
                visa.click()
                end = time.time() + 12
                while time.time() < end and not _visa_task_da(app_id, pre_tasks):
                    time.sleep(0.25)
                assert _visa_task_da(app_id, pre_tasks), \
                    "kein visa_confirmation-Task nach Klick auf Visum-Info (eingestellt)"
                print("VISA: visa_confirmation ausgeloest trotz Status 'eingestellt'")

                # 4c) Zurueck zum Board: Onboarding = reine Navigation
                page.wait_for_timeout(1500)
                page.get_by_role("button", name=re.compile("Hiring-Board")).first.click()
                page.wait_for_timeout(1200)
                page.get_by_text(label, exact=True).first.click()
                drawer3 = page.locator(".q-dialog:visible").filter(has_text="Bewerbungsdetails")
                drawer3.wait_for(state="visible", timeout=8000)
                drawer3.get_by_text("Onboarding", exact=True).click()
                page.wait_for_url("**/employer/onboarding**", timeout=8000)
                print("ONBOARDING: Navigation /employer/onboarding, kein zweiter Trigger")

                # 4d) Generator: Kandidat kommt aus der DB (Status 'eingestellt'),
                # Checkliste entsteht lokal in ergebnisse/ (kein Mailversand).
                _before = set(ROOT.glob("ergebnisse/onboarding-*.md"))
                _sel = page.locator(".q-select").first
                _sel.click()
                page.wait_for_timeout(700)
                page.get_by_text(label, exact=True).last.click()
                page.wait_for_timeout(500)
                page.get_by_role("button", name=re.compile(r"^Onboarding generieren$")).click()
                page.wait_for_timeout(2000)
                _after = set(ROOT.glob("ergebnisse/onboarding-*.md"))
                _neu = _after - _before
                assert _neu, "keine Onboarding-Checkliste erzeugt (DB-Kandidat fehlt im Generator)"
                created_files.update(_neu)
                print(f"ONBOARDING-CHECKLISTE: {[f.name for f in _neu]} (Quelle: DB-Kandidat)")
                ok = True
            finally:
                browser.close()
    finally:
        # Restore: Status + alle Testzeilen (History/Task/Notification) entfernen.
        conn = sqlite3.connect(DB)
        try:
            conn.execute("UPDATE applications SET status = 'eingeladen' WHERE id = ?", (app_id,))
            conn.execute("DELETE FROM application_status_history WHERE id > ? AND application_id = ?",
                         (base_hist, app_id))
            conn.execute(
                "DELETE FROM agent_tasks WHERE id > ? AND task_type = 'onboarding_release' "
                "AND json_extract(payload,'$.application_id') = ?", (pre_tasks, app_id))
            conn.execute(
                "DELETE FROM agent_tasks WHERE id > ? AND task_type = 'visa_confirmation' "
                "AND json_extract(payload,'$.application_id') = ?", (pre_tasks, app_id))
            conn.execute("DELETE FROM notifications WHERE id > ? AND user_id = ?",
                         (base_notif, cand_id))
            conn.commit()
        finally:
            conn.close()
        # Erzeugte Checklisten-Dateien entfernen (kein Rest im Repo).
        for _f in created_files:
            try:
                _f.unlink()
            except OSError:
                pass

    residue = db_residue_report(pre_tasks)
    print(f"RESTORE: app {app_id} wieder 'eingeladen', History/Task/Notification entfernt")
    sys.exit(0 if (ok and residue == 0) else 1)


if __name__ == "__main__":
    main()
