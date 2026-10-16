"""E2E Einladungen-Flow (S7, Iteration „Einladungen", 16.10.2026).

Seite /employer/einladen (Codemark `_page_einladen` in webui/pages/employer.py):
1. Server-Precheck (F2) + Spiegel-Guard: Fixture-Schreibzugriffe NUR gegen
   den Isolations-Spiegel ("e2e-iso-" im DB-Pfad) — nie gegen die Live-DB.
2. Fixture: zwei Bewerbungen von Employer 1 auf 'angesehen' (A) und
   'eingegangen' (B) gesetzt; ORIGINAL-Statusse gemerkt, RESTORE am Ende
   (Status + History-Zeilen + Task + Notifications), damit der gemeinsame
   Spiegel die Folgeskripte nicht stoert (db_residue_report muss 0 sein).
3. Navigation OHNE hartes goto auf die Seite (Hang-Falle,
   knowledge/system/i18n-runner-chain.md §5): Login -> Dashboard -> Sidebar-
   Klick "Einladungen".
4. Behauptungen:
   - angesehene Karte: Datum/Uhrzeit/Dauer-Widgets (Defaults morgen 10:00/30)
     + 'Einladen'-Knopf;
   - eingegangene Karte: NUR 'Als angesehen markieren', KEIN Einladen
     (ALLOWED_TRANSITIONS: eingegangen -> {angesehen, abgelehnt});
   - genau 1 Datum-Feld (Widget nur bei einladbarer Status-Karte).
5. Klicks: B 'Als angesehen markieren' -> DB ansehen + History +1.
   A 'Einladen' (Klick Nr. 2 ab Dashboard, Defaults unangetastet) -> DB
   eingeladen, History +1, create_invitation-Task mit termin-* Defaults,
   Kandidaten-Notification; Karte wandert nach unten in 'Eingeladene (n)'.
6. 📹-Artefakt-Karte datengekoppelt: zaehlt nur, wenn der Spiegel bereits
   DONE create_invitation-Tasks mit result_json fuer eingeladene Bewerbungen
   hat (Runner laeuft im Isolationslauf NICHT: KMHR_RUNNER_AUTOSTART=0) —
   informativ, kein hartes Assert.
7. KLICKMESSUNG fuer employer-board.md §6: Sidebar(1) + Einladen(2) = 2.

Login-/Restore-Muster: e2e_match_actions.py, e2e_invitation_termin.py.
"""
import json
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import BASE, DB, seed_email  # noqa: E402

EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"


def _conn():
    return sqlite3.connect(str(DB))


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


def fixture_apps():
    """Zwei Bewerbungen von Employer 1 mit finalen Statusen (für die wir
    Fixture-Werte setzen dürfen) — deterministisch nach id."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT a.id, a.status, a.candidate_id, j.titel FROM applications a "
            "JOIN jobs j ON j.id = a.job_id "
            "WHERE j.employer_id = 1 AND a.status IN ('eingestellt', 'abgelehnt') "
            "ORDER BY a.id LIMIT 2",
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) >= 2, f"Zwei Fixture-Bewerbungen nötig, Spiegel hat: {rows}"
    return rows  # [(id, status, cand, titel)]


def set_fixture(app_a, app_b):
    conn = _conn()
    try:
        conn.execute("UPDATE applications SET status='angesehen', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?", (app_a,))
        conn.execute("UPDATE applications SET status='eingegangen', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?", (app_b,))
        conn.commit()
    finally:
        conn.close()


def restore_fixture(app_a, st_a, app_b, st_b, hist_base, task_base, notif_base):
    """Spiegel auf den Vor-Zustand: Statusse zurück, Test-Reste löschen."""
    conn = _conn()
    try:
        conn.execute("UPDATE applications SET status=? WHERE id=?", (st_a, app_a))
        conn.execute("UPDATE applications SET status=? WHERE id=?", (st_b, app_b))
        conn.execute("DELETE FROM application_status_history WHERE rowid > ?", (hist_base,))
        conn.execute("DELETE FROM agent_tasks WHERE id > ?", (task_base,))
        conn.execute("DELETE FROM notifications WHERE id > ?", (notif_base,))
        conn.commit()
    finally:
        conn.close()


def main():
    check_server()
    if "e2e-iso-" not in str(DB):
        print(f"ABORT: kein Isolations-Spiegel (DB={DB}) — Fixture-Schreiben verboten")
        sys.exit(1)

    apps = fixture_apps()
    app_a, st_a, cand_a, titel_a = apps[0]
    app_b, st_b, cand_b, titel_b = apps[1]

    conn = _conn()
    try:
        hist_base = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM application_status_history").fetchone()[0]
        notif_base = conn.execute("SELECT COALESCE(MAX(id), 0) FROM notifications").fetchone()[0]
    finally:
        conn.close()
    task_base = pre_max_tasks()
    morgen = str(date.today() + timedelta(days=1))

    set_fixture(app_a, app_b)
    clicks = 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            try:
                login_employer(page)
                # KLICK 1: Sidebar „Einladungen" (kein goto — Hang-Falle §5)
                page.get_by_role("button", name=re.compile("Einladungen", re.I)).first.click()
                clicks += 1
                page.wait_for_timeout(3000)
                assert "/employer/einladen" in page.url, f"Route verfehlt: {page.url}"

                # Seiten-Struktur
                page.locator("text=Einladbar (").first.wait_for(timeout=15000)
                assert page.locator("text=Eingeladene (").count() >= 1, "Unten-Sektion fehlt"

                # eingegangen-Karte: nur „Als ansehen", KEIN Einladen, KEIN Widget
                karte_b = page.locator(f".q-card:has-text('Kandidat #{cand_b}')")
                assert karte_b.count() >= 1, f"Karte B (#{cand_b}) fehlt"
                assert karte_b.first.locator("button:has-text('Als angesehen markieren')").count() == 1, "B ohne Markieren-Knopf"
                assert karte_b.first.locator("button:has-text('Einladen')").count() == 0, "B bietet Einladen (Whitelist-Bruch!)"

                # angesehen-Karte: Widgets + Einladen (genau 1 Datum-Feld auf der Seite)
                assert page.get_by_label("Datum").count() == 1, "Datum-Widget != 1 (nur angesehene Karten)"
                assert page.get_by_label("Uhrzeit").count() == 1
                karte_a = page.locator(f".q-card:has-text('Kandidat #{cand_a}')").first
                assert karte_a.locator("button:has-text('Einladen')").count() == 1, "A ohne Einladen-Knopf"

                # Markieren (B)
                karte_b.first.locator("button:has-text('Als angesehen markieren')").click()
                page.wait_for_timeout(2000)
                conn = _conn()
                try:
                    st = conn.execute("SELECT status FROM applications WHERE id=?", (app_b,)).fetchone()[0]
                    hz = conn.execute("SELECT COUNT(*) FROM application_status_history WHERE rowid > ?", (hist_base,)).fetchone()[0]
                finally:
                    conn.close()
                assert st == "angesehen", f"B nach Markieren: {st}"
                assert hz == 1, f"History-Zeilen nach Markieren (Zahl seit Fixture): {hz}"

                # KLICK 2: „Einladen" auf A-Karte — Defaults (morgen/10:00/30) unangetastet
                karte_a = page.locator(f".q-card:has-text('Kandidat #{cand_a}')").first
                karte_a.locator("button:has-text('Einladen')").click()
                clicks += 1
                page.wait_for_timeout(2500)

                conn = _conn()
                try:
                    st = conn.execute("SELECT status FROM applications WHERE id=?", (app_a,)).fetchone()[0]
                    assert st == "eingeladen", f"A nach Einladen: {st}"
                    hz = conn.execute("SELECT COUNT(*) FROM application_status_history WHERE rowid > ?", (hist_base,)).fetchone()[0]
                    assert hz == 2, f"History-Zeilen erwartet 2, ist {hz}"
                    task = conn.execute(
                        "SELECT task_type, payload FROM agent_tasks WHERE id > ? ORDER BY id", (task_base,)
                    ).fetchall()
                    assert len(task) == 1 and task[0][0] == "create_invitation", f"Task-Fehlzun: {task}"
                    payload = json.loads(task[0][1])
                    assert payload["termin_datum"] == morgen, f"termin_datum: {payload}"
                    assert payload["termin_uhrzeit"] == "10:00", f"termin_uhrzeit: {payload}"
                    assert int(payload["termin_dauer_min"]) == 30, f"dauer: {payload}"
                    assert payload["trigger"] == "hr_klick_portal", f"trigger: {payload}"
                    nn = conn.execute(
                        "SELECT COUNT(*) FROM notifications WHERE id > ? AND role='candidate'", (notif_base,)
                    ).fetchone()[0]
                    assert nn >= 1, "Keine Kandidaten-Notification (R3-5-Pfad?)"
                finally:
                    conn.close()

                # Unten: A ist jetzt in „Eingeladene", oben nur noch B mit Widget
                page.wait_for_timeout(1000)
                assert page.get_by_label("Datum").count() == 1, "Widget-Zahl nach Refresh != 1 (B jetzt einladbar)"
                beh = page.locator("text=Eingeladene (").first.text_content()
                print(f"INFO unten-Sektion: {beh!r}")

                # 📹 datengekoppelt (informativ)
                conn = _conn()
                try:
                    art = conn.execute(
                        "SELECT COUNT(*) FROM agent_tasks WHERE task_type='create_invitation' "
                        "AND status='done' AND result_json IS NOT NULL"
                    ).fetchone()[0]
                finally:
                    conn.close()
                vid = page.locator("text=📹 Einladung").count()
                print(f"INFO artifacts(done)={art}, sichtbare 📹-Karten={vid} (Runner aus, kein Assert)")
            finally:
                ctx.close()
                browser.close()
    finally:
        restore_fixture(app_a, st_a, app_b, st_b, hist_base, task_base, notif_base)

    assert clicks == 2, f"Klickzaehler: {clicks}"
    print(f"KLICKMESSUNG einladen: {clicks} Klicks (Sidebar Einladungen + Button Einladen, Defaults unangetastet) — Ziel employer-board §6 erreicht")
    residue = db_residue_report(task_base)
    print(f"OK einladen-flow appA={app_a} appB={app_b} residue={residue}")
    sys.exit(0 if residue == 0 else 1)


if __name__ == "__main__":
    main()
