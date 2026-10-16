"""E2E Einladungen-Flow (S7/S5, Iteration „Einladungen", 16.10.2026).

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
4. UX-Korrektur 16.10.2026 (C1-Muster, employer-board.md §3): Der Karten-
   Button "Einladen" oeffnet NUR den Bestaetigungs-Dialog `_ein_dialog`
   (Marker `_ein_open_confirm`); ERST der Dialog-Bestaetigen-Klick fuehrt
   `_ein_send_invite` aus. Die Termin-Widgets `ui.date` (mask="YYYY-MM-DD")
   + `ui.time` + Dauer-`ui.select` liegen JETZT IM Dialog — es gibt KEIN
   date_input/time_input mehr auf dieser Seite. Defaults (morgen 10:00/30)
   bleiben unangetastet und fliessen in den create_invitation-Payload
   (Assertions unten = Defaults-Nachweis).
5. Behauptungen:
   - angesehene Karte A: 'Einladen'-Knopf + Kontext-Link "Match-Seite
     öffnen", aber KEIN Datum-/Zeit-Widget auf der Karte;
   - eingegangene Karte B: NUR 'Als angesehen markieren', KEIN Einladen
     (ALLOWED_TRANSITIONS: eingegangen -> {angesehen, abgelehnt});
   - genau 1 Datum- und 1 Zeit-Widget auf der ganzen Seite — beide IM
     offenen Dialog (LOCATOR-FALLE s.u.).
6. Klicks (Zielpfad ab Status 'angesehen', employer-board.md §6):
   (1) Sidebar "Einladungen" -> (2) Karte "Einladen" -> (3) Dialog
   "Einladen" -> DB-Status 'eingeladen'.
   LOCATOR-FALLE: nach Klick 2 existieren MEHRERE Buttons mit dem Text
   "Einladen" (Sidebar-Item "Einladungen", Karte A, Dialog) — der
   Bestaetigen-Klick ist deshalb AUF `.q-dialog` gescoped
   (Dialog-Muster wie e2e_housing.py / e2e_c7_downloads.py).
7. NEGATIVTEST Abbrechen (zweite Bewerbung B, isolierter Spiegel): Karte B
   "Einladen" -> Dialog oeffnen -> "Abbrechen" -> DB-Status B bleibt
   'angesehen', History-/Task-Zaehler unveraendert.
8. KLICKMESSUNG fuer employer-board.md §6: die GEMESSENE Zahl ausgeben
   (Soll 3 — Wahrheit, nicht Wunsch). Klicks ausserhalb des Zielpfads
   (Fixtures/Abbrechen) werden separat gezaehlt und mit ausgewiesen.
9. residue=0 (F3) am Ende; die Live-sha256-Gleichheit liefert der
   Isolations-Lauf (tests/e2e_isolation.py, summary.txt).

Login-/Restore-Muster: e2e_match_actions.py, e2e_invitation_termin.py.
"""
import json
import re
import sqlite3
import sys
import time
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


def status_von(app_id: int) -> str | None:
    """Status einer Bewerbung in der ISOLATIONS-DB (nie Live-DB)."""
    conn = _conn()
    try:
        row = conn.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def warte_status(app_id: int, soll: str, timeout: float = 10.0) -> str | None:
    """Pollt den Spiegel-DB-Status bis == soll oder Timeout — dann letzter Wert."""
    deadline = time.time() + timeout
    st = status_von(app_id)
    while st != soll and time.time() < deadline:
        time.sleep(0.3)
        st = status_von(app_id)
    return st


def dialog_offen(page, timeout: float = 10.0) -> bool:
    """True, sobald ein sichtbarer .q-dialog da ist."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if page.locator(".q-dialog:visible").count() >= 1:
            return True
        page.wait_for_timeout(200)
    return False


def dialog_zu(page, timeout: float = 8.0) -> bool:
    """True, wenn kein sichtbarer .q-dialog mehr da ist (Portal weg/verborgen)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if page.locator(".q-dialog:visible").count() == 0:
            return True
        page.wait_for_timeout(200)
    return False


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
    clicks = 0        # Zielpfad A: Sidebar(1) -> Karte(2) -> Dialog(3)
    other_clicks = 0  # ausserhalb des Zielpfads (Fixtures + Abbrechen-Test)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            try:
                login_employer(page)
                # KLICK 1: Sidebar „Einladungen" (kein goto — Hang-Falle §5)
                print("KLICK 1: Sidebar „Einladungen\"")
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
                assert karte_b.first.locator(".q-date").count() == 0, "B-Karte trägt ein Datum-Widget (gehört in den Dialog)"
                assert karte_b.first.locator(".q-time").count() == 0, "B-Karte trägt ein Zeit-Widget (gehört in den Dialog)"

                # angesehen-Karte: Einladen + Match-Seite-Link, KEINE Widgets
                karte_a = page.locator(f".q-card:has-text('Kandidat #{cand_a}')").first
                assert karte_a.locator("button:has-text('Einladen')").count() == 1, "A ohne Einladen-Knopf"
                assert karte_a.locator("button:has-text('Match-Seite öffnen')").count() == 1, "A ohne Kontext-Link „Match-Seite öffnen\""
                assert karte_a.locator(".q-date").count() == 0, "A-Karte trägt ein Datum-Widget (gehört in den Dialog)"
                assert karte_a.locator(".q-time").count() == 0, "A-Karte trägt ein Zeit-Widget (gehört in den Dialog)"
                # Widget-Wechsel: keine Datum-/Zeit-Außenstelle auf der Seite —
                # was existiert, liegt IM (ggf. noch geschlossenen) Dialog.
                assert page.locator(".q-date").count() == page.locator(".q-dialog .q-date").count(), \
                    "Datum-Widget ausserhalb des Dialogs"
                assert page.locator(".q-time").count() == page.locator(".q-dialog .q-time").count(), \
                    "Zeit-Widget ausserhalb des Dialogs"

                # KLICK 2: „Einladen" auf A-Karte -> oeffnet NUR den Dialog
                print("KLICK 2: Karte A „Einladen\" (öffnet den Dialog)")
                karte_a = page.locator(f".q-card:has-text('Kandidat #{cand_a}')").first
                karte_a.locator("button:has-text('Einladen')").click()
                clicks += 1
                assert dialog_offen(page), "Dialog `_ein_dialog` öffnet nicht"

                # LOCATOR-FALLE: nach Klick 2 existieren MEHRERE „Einladen"-Treffer
                # (Sidebar-Item „Einladungen", Karte A, Dialog) — unscoped click()
                # waere ein Falschziel-/Strict-Mode-Klick. Darum: Scoping auf den Dialog.
                dlg = page.locator(".q-dialog:visible")
                assert dlg.count() == 1, f"sichtbare Dialoge: {dlg.count()}"
                treffer_seite = page.get_by_role("button", name="Einladen").count()
                treffer_dlg = dlg.get_by_role("button", name="Einladen").count()
                treffer_karte = karte_a.locator("button:has-text('Einladen')").count()
                assert treffer_seite >= 2, f"LOCATOR-FALLE nicht reproduzierbar: nur {treffer_seite} Treffer"
                assert treffer_dlg == 1 and treffer_karte == 1, \
                    f"Unscoped/Scoped-Zahl stimmt nicht: Seite={treffer_seite} Karte={treffer_karte} Dialog={treffer_dlg}"
                print(f"LOCATOR-FALLE: {treffer_seite} Buttons mit Text „Einladen\" auf der Seite "
                      f"(davon Karte A: {treffer_karte}, Dialog: {treffer_dlg}, Rest z.B. Sidebar-Item "
                      f"„Einladungen\") -> Klick GESCOPED auf .q-dialog")
                assert dlg.locator("button:has-text('Einladen')").count() == 1, "Dialog ohne Bestätigen-Knopf"
                assert dlg.locator("button:has-text('Abbrechen')").count() == 1, "Dialog ohne Abbrechen-Knopf"
                # Termin-Widgets liegen IM Dialog (ui.date/ui.time, kein *_input)
                assert dlg.locator(".q-date").count() == 1, "Dialog ohne ui.date"
                assert dlg.locator(".q-time").count() == 1, "Dialog ohne ui.time"
                assert dlg.get_by_text("Dauer (Min.)").count() == 1, "Dialog ohne Dauer-Select"
                assert page.locator(".q-date").count() == 1, "Datum-Widgetzahl != 1 (nur im Dialog)"
                assert page.locator(".q-time").count() == 1, "Zeit-Widgetzahl != 1 (nur im Dialog)"

                # KLICK 3: Dialog-Bestaetigen -> _ein_send_invite
                print("KLICK 3: Dialog „Einladen\" (Bestätigen, gescoped)")
                dlg.get_by_role("button", name="Einladen").click()
                clicks += 1
                assert dialog_zu(page), "Dialog bleibt nach Bestätigen offen"
                assert warte_status(app_a, "eingeladen") == "eingeladen", \
                    f"A nach Dialog-Bestätigen: {status_von(app_a)}"

                conn = _conn()
                try:
                    hz = conn.execute("SELECT COUNT(*) FROM application_status_history WHERE rowid > ?", (hist_base,)).fetchone()[0]
                    assert hz == 1, f"History-Zeilen nach Einladung A (nur A): {hz}"
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
                print(f"DB: A#{app_a} status=eingeladen, Dialog-Defaults geflossen "
                      f"(termin {payload['termin_datum']} {payload['termin_uhrzeit']} / "
                      f"{payload['termin_dauer_min']} min)")

                # Danach: B „Als angesehen markieren" (ausserhalb des Zielpfads)
                karte_b = page.locator(f".q-card:has-text('Kandidat #{cand_b}')").first
                karte_b.locator("button:has-text('Als angesehen markieren')").click()
                other_clicks += 1
                page.wait_for_timeout(1500)
                assert warte_status(app_b, "angesehen") == "angesehen", f"B nach Markieren: {status_von(app_b)}"
                conn = _conn()
                try:
                    hz = conn.execute("SELECT COUNT(*) FROM application_status_history WHERE rowid > ?", (hist_base,)).fetchone()[0]
                finally:
                    conn.close()
                assert hz == 2, f"History-Zeilen erwartet 2 (A-Einladung + B-Markieren), ist {hz}"

                # Unten: A ist jetzt in „Eingeladene"; B einladbar — ABER ohne
                # Widget auf der Karte (Widgets wohnen im Dialog).
                page.wait_for_timeout(1000)
                beh = page.locator("text=Eingeladene (").first.text_content()
                print(f"INFO unten-Sektion: {beh!r}")
                karte_b = page.locator(f".q-card:has-text('Kandidat #{cand_b}')").first
                assert karte_b.locator("button:has-text('Einladen')").count() == 1, "B nach Markieren nicht einladbar"
                assert karte_b.locator(".q-date").count() == 0, "Widget-Zahl nach Refresh != 0 (Widget sitzt im Dialog)"
                assert page.locator(".q-date").count() == page.locator(".q-dialog .q-date").count(), \
                    "Datum-Widget ausserhalb des Dialogs (nach Refresh)"

                # ── ABBRECHEN-NEGATIVTEST (zweite Bewerbung B, isolierter Spiegel) ──
                print("ABBRECHEN-TEST: Dialog auf B öffnen und „Abbrechen\" klicken")
                karte_b.locator("button:has-text('Einladen')").click()
                other_clicks += 1
                assert dialog_offen(page), "ABBRECHEN-TEST: Dialog öffnet nicht"
                dlg_b = page.locator(".q-dialog:visible")
                assert dlg_b.count() == 1, f"ABBRECHEN-TEST: sichtbare Dialoge: {dlg_b.count()}"
                dlg_b.get_by_role("button", name="Abbrechen").click()
                other_clicks += 1
                assert dialog_zu(page), "ABBRECHEN-TEST: Dialog bleibt offen"
                page.wait_for_timeout(2000)  # Zeitfenster, in dem ein versehentlicher Schreibpfad landen muesste
                st_b_final = status_von(app_b)
                conn = _conn()
                try:
                    hz_b = conn.execute("SELECT COUNT(*) FROM application_status_history WHERE rowid > ?", (hist_base,)).fetchone()[0]
                    task_b = conn.execute("SELECT COUNT(*) FROM agent_tasks WHERE id > ?", (task_base,)).fetchone()[0]
                finally:
                    conn.close()
                assert st_b_final == "angesehen", f"ABBRECHEN-TEST: Status {st_b_final!r} != 'angesehen'"
                assert hz_b == 2, f"ABBRECHEN-TEST: History-Zeilen {hz_b} != 2 (kein Neuer-Eintrag)"
                assert task_b == 1, f"ABBRECHEN-TEST: create_invitation-Tasks {task_b} != 1 (kein Neuer-Task)"
                print(f"ABBRECHEN-TEST: Status bleibt angesehen ✓ (appB={app_b}, "
                      f"history+{hz_b - 2}, tasks+{task_b - 1})")

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

    assert clicks == 3, f"Klickzaehler Zielpfad: {clicks} (erwartet 3)"
    print(f"KLICKMESSUNG einladen: {clicks} Klicks ab Status angesehen "
          f"(Sidebar(1) → Karte „Einladen“(2) → Dialog „Einladen“(3)) — gemessen 16.10.2026 "
          f"(E2E, Isolationslauf) — employer-board §6")
    print(f"KLICKMESSUNG detalle: ausserhalb des Zielpfads {other_clicks} weitere Klicks "
          f"(B „Als angesehen markieren“ + Abbrechen-Test) — nicht Teil des Zielwerts")
    residue = db_residue_report(task_base)
    print(f"OK einladen-flow appA={app_a} appB={app_b} residue={residue}")
    sys.exit(0 if residue == 0 else 1)


if __name__ == "__main__":
    main()
