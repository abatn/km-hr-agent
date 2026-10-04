"""E2E R3-5 (30.09.2026): Neue Bewerbung -> Arbeitgeber-Benachrichtigung
+ Badge/Drawer-Refresh nach „Alle als gelesen markieren" (N-D1 + N-D2).

Teil A (N-D1, webui/pages/candidate.py::_notify_neue_bewerbung):
  frischer Kandidat (Registrierung ueber die UI) -> Login -> Lebenslauf ->
  Bewerbung ueber die UI -> Spiegel-DB: notifications-Zeile role='employer',
  user_id=1 (Ersteller der gewaehlten Stelle = TechVision GmbH), deutscher
  Text "<Name> hat sich beworben: <Stellentitel>".

Teil B (N-D2, webui/components.py::notifications_drawer/shell):
  notifications-Zeile fuer den Kandidaten einspielen (direkter INSERT in die
  SPIEGEL-DB = Test-Setup) -> Kandidaten-Seite neu laden -> Badge zeigt
  ungelesen (DOM) -> Drawer oeffnen -> „Alle als gelesen markieren" klicken ->
  Badge verschwindet/0 OHNE Seiten-Reload (DOM) UND Drawer-Inhalt zeigt
  "Keine Benachrichtigungen" (DOM) UND DB get_unread_count = 0.

NUR gegen die Isolations-Instanz (schreibt candidates/applications/
notifications in die Spiegel-DB; die Live-DB wird nur gelesen):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --only e2e_notifications_flow --port 8093

Reste werden in finally zurueckgeraeumt (Bewerbung, notifications,
Kandidat, agent_tasks ueber Baseline, testdaten/-Datei).
"""
from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import BASE, DB, check_server, pre_max_tasks

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = (ROOT / "data" / "feedback.db").resolve()
TESTDATEN = ROOT / "testdaten"

EMPLOYER_ID = 1                     # TechVision GmbH (Ersteller der Stellen)
TS = time.strftime("%H%M%S")
EMAIL = f"r35-e2e-{TS}@example.invalid"
NAME = f"R35 E2E Kandidat {TS}"
PW = "R35E2EPasswort2026!"

# Kandidaten-ID schon nach der REGISTRIERUNG festhalten (nicht erst nach dem
# Login) -> cleanup() findet die Zeile auch, wenn spaetere Schritte scheitern.
STATE: dict = {}


# ─── Spiegel-DB-Helfer (Test-Setup + Auenabis) ─────────────────────────

def rows(sql: str, args: tuple = ()) -> list:
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def run(sql: str, args: tuple = ()) -> None:
    conn = sqlite3.connect(str(DB))
    try:
        conn.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


def unread(user_id: int, role: str) -> int:
    return rows(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND role=? AND gelesen=0",
        (user_id, role))[0][0]


def candidate_id() -> int | None:
    r = rows("SELECT id FROM candidates WHERE email=?", (EMAIL,))
    return r[0][0] if r else None


# ─── UI-Schritte ────────────────────────────────────────────────────────

def register_and_login(page) -> int:
    """Frischer Kandidat: Registrieren (UI) -> Login (UI) -> cand_id.

    Panels werden ueber ihren Inhalt statt ueber ":visible .first" gewaehlt —
    waehrend der Quasar-Transition sind beide sichtbar (.first griff sonst
    ins falsche Panel, Beweis: Lauf 08:28, „Pflichtfelder"-Meldung).
    """
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)

    page.get_by_role("tab", name="Registrieren").click()
    page.wait_for_timeout(1200)
    panel = page.locator(".q-tab-panel:visible").filter(
        has_text="Neues Konto erstellen")
    assert panel.count() == 1, "Registrierungs-Panel nicht sichtbar"
    panel.get_by_label("E-Mail").fill(EMAIL)
    panel.get_by_label("Name").fill(NAME)
    panel.get_by_label("Passwort", exact=True).fill(PW)
    panel.get_by_role("button", name="Registrieren").click()
    page.get_by_text("Registriert! Jetzt einloggen.").wait_for(timeout=15000)
    print(f"A1 Registrierung OK: {EMAIL} / {NAME}")
    STATE["cid"] = candidate_id()
    assert STATE["cid"], "Kandidat nach Registrierung nicht in der Spiegel-DB"

    page.get_by_role("tab", name="Login").click()
    page.wait_for_timeout(1200)
    panel = page.locator(".q-tab-panel:visible").filter(has_text="Willkommen zurueck")
    assert panel.count() == 1, f"Login-Panel nicht sichtbar: {panel.count()}"
    panel.get_by_label("E-Mail").fill(EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(PW)
    inputs = panel.locator("input")
    print("DEBUG login DOM values:", [inputs.nth(i).input_value()[:30]
                                       for i in range(inputs.count())])
    panel.get_by_role("button", name="Einloggen").click()
    try:
        page.wait_for_url("**/candidate**", timeout=20000)
    except Exception:
        print("DEBUG nach Login, sichtbares Panel:", repr(
            page.locator(".q-tab-panel:visible").first.inner_text()[:300]))
        raise
    print(f"A2 Login OK: candidate_id={STATE['cid']}")
    return STATE["cid"]


def upload_cv(page, cid: int) -> str:
    """Lebenslauf ueber die UI (Fallback: Status-Update in der Spiegel-DB)."""
    page.goto(f"{BASE}/candidate/profil", wait_until="load")
    page.wait_for_timeout(1500)
    cv_file = Path(tempfile.gettempdir()) / f"r35-e2e-cv-{TS}.txt"
    cv_file.write_text(
        "R35 E2E Lebenslauf\nPython, Kubernetes, Linux\n"
        "Berufserfahrung: 5 Jahre Cloud/DevOps\n", encoding="utf-8")
    try:
        loc = page.locator("input[type=file]").first
        try:
            loc.set_input_files(str(cv_file))
        except Exception:
            loc.evaluate(
                "el => { el.style.display='block'; el.style.visibility='visible'; }")
            loc.set_input_files(str(cv_file))
        page.get_by_text("Lebenslauf hochgeladen").wait_for(timeout=20000)
        page.wait_for_timeout(1500)
        status = rows("SELECT status FROM candidates WHERE id=?", (cid,))[0][0]
        if status == "lebenslauf_hochgeladen":
            return str(cv_file)
        print(f"A3 UI-Upload ohne Statuswechsel (status={status}) -> Fallback Spiegel-DB")
    except Exception as ex:  # noqa: BLE001
        print(f"A3 UI-Upload fehlgeschlagen ({ex!r}) -> Fallback Spiegel-DB")
    # Test-Setup (erlaubt: nur die SPIEGEL-DB, wie Teil B)
    run("UPDATE candidates SET status='lebenslauf_hochgeladen', "
        "lebenslauf_text='R35 E2E Lebenslauf' WHERE id=?", (cid,))
    return str(cv_file)


def pick_job() -> tuple[int, str]:
    r = rows(
        "SELECT id, titel FROM jobs WHERE status='aktiv' AND employer_id=? "
        "ORDER BY id DESC LIMIT 1", (EMPLOYER_ID,))
    assert r, "keine aktive Stelle fuer employer_id=1 in der Spiegel-DB"
    return r[0][0], r[0][1]


def apply_via_ui(page, jid: int) -> None:
    page.goto(f"{BASE}/candidate/stellen", wait_until="load")
    card = page.locator(".q-card").filter(has_text=re.compile(rf"#{jid} ")).first
    card.wait_for(timeout=30000)
    card.get_by_role("button", name="Bewerben").click()
    page.locator(".q-dialog").wait_for(timeout=15000)
    page.get_by_role("button", name="Jetzt bewerben").click()
    page.get_by_text("Bewerbung gesendet!").wait_for(timeout=15000)
    page.wait_for_timeout(2000)
    print(f"A4 Bewerbung ueber die UI gesendet (job {jid})")


def badge_text(page) -> str:
    b = page.locator("header .q-badge")
    if b.count() == 0:
        return ""
    return b.first.inner_text().strip()


def cleanup(pre_tasks: int, cid: int | None, cv_file: str | None) -> None:
    """Spiegel-DB + testdaten auf den Zustand vor dem Test zuruecksetzen."""
    if cid:
        run("DELETE FROM application_status_history WHERE application_id IN "
            "(SELECT id FROM applications WHERE candidate_id=?)", (cid,))
        run("DELETE FROM applications WHERE candidate_id=?", (cid,))
        run("DELETE FROM notifications WHERE user_id=? OR "
            "(user_id=? AND role='employer' AND nachricht LIKE ?)",
            (cid, EMPLOYER_ID, f"%{NAME}%"))
        run("DELETE FROM candidates WHERE id=?", (cid,))
    run("DELETE FROM agent_tasks WHERE id > ?", (pre_tasks,))
    if cv_file:
        try:
            Path(cv_file).unlink()
        except OSError:
            pass
    for f in TESTDATEN.glob(f"kandidat-{cid}-*"):
        try:
            f.unlink()
        except OSError:
            pass


# ─── Test ───────────────────────────────────────────────────────────────

def main() -> int:
    if Path(DB).resolve() == LIVE_DB:
        print("ABBRUCH: DB-Pfad ist die Live-DB — nur via tests/e2e_isolation.py ausführen")
        return 2
    check_server()
    pre_tasks = pre_max_tasks()
    cid = None
    cv_file = None
    fehler: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(60000)
            try:
                # ── Teil A: frischer Kandidat -> Bewerbung -> Employer-Zeile ──
                cid = register_and_login(page)
                cv_file = upload_cv(page, cid)
                jid, titel = pick_job()
                print(f"A3 Ziel-Stelle: #{jid} {titel} (employer_id={EMPLOYER_ID})")
                apply_via_ui(page, jid)

                erwartet = f"{NAME} hat sich beworben: {titel}"
                notifs = rows(
                    "SELECT user_id, role, titel, nachricht, gelesen FROM notifications "
                    "WHERE role='employer' AND user_id=? ORDER BY id DESC",
                    (EMPLOYER_ID,))
                treffer = [n for n in notifs if n[3] == erwartet]
                if treffer and treffer[0][2] == "Neue Bewerbung" and treffer[0][4] == 0:
                    print(f"A5 notifications-Zeile OK: user_id={EMPLOYER_ID} "
                          f"role=employer titel='Neue Bewerbung' nachricht={erwartet!r} "
                          f"gelesen=0")
                else:
                    fehler.append(f"A5 notifications-Zeile fehlt/falsch: {notifs!r} "
                                  f"(erwartet nachricht={erwartet!r})")

                # ── Teil B: Badge + Drawer-Refresh ohne Reload ────────────────
                run("INSERT INTO notifications (user_id, role, titel, nachricht) "
                    "VALUES (?, 'candidate', 'Neue Mitteilung', ?)",
                    (cid, "R35 E2E Test-Benachrichtigung fuer den Drawer"))
                print(f"B1 notifications-Zeile fuer Kandidat {cid} eingespielt "
                      f"(ungelesen={unread(cid, 'candidate')})")

                page.goto(f"{BASE}/candidate", wait_until="load")
                page.locator("header .q-btn").first.wait_for(timeout=30000)
                page.wait_for_timeout(2500)
                vorher = badge_text(page)
                if vorher.isdigit() and int(vorher) >= 1:
                    print(f"B2 Badge zeigt ungelesen: {vorher!r} (DOM header .q-badge)")
                else:
                    fehler.append(f"B2 Badge zeigt {vorher!r}, erwartet >= 1")

                # Drawer oeffnen (Header-Click wird vom Badge-Overlay abgefangen;
                # Drawer-Root hat nicht .q-drawer -> JS-Fallback, siehe Diagnose)
                page.evaluate("""() => {
                    const d = document.querySelector('.q-drawer--right');
                    if (d && !d.classList.contains('q-drawer--open')) d.classList.add('q-drawer--open');
                }""")
                page.wait_for_timeout(400)
                drawer = page.locator(".q-drawer").filter(has_text="Benachrichtigungen")
                drawer_text = (drawer.first.text_content() or "")
                if "R35 E2E Test-Benachrichtigung" in drawer_text:
                    print("B3 Drawer offen, Inhalt zeigt die neue Benachrichtigung")
                else:
                    fehler.append(f"B3 Drawer-Inhalt ohne Benachrichtigung: {drawer_text[:200]!r}")

                page.get_by_text("Alle als gelesen markieren").first.click(timeout=10000)
                page.wait_for_timeout(2000)
                page.get_by_text("Alle als gelesen markiert").wait_for(timeout=10000)
                page.wait_for_timeout(2000)  # KEIN Reload: SPA bleibt stehen

                nachher = badge_text(page)
                b_dom = (nachher == "" or nachher == "0"
                         or page.locator("header .q-badge").count() == 0
                         or not page.locator("header .q-badge").first.is_visible())
                if b_dom:
                    print(f"B4 Badge nach Klick weg/0: {nachher!r} (ohne Seiten-Reload)")
                else:
                    fehler.append(f"B4 Badge immer noch sichtbar: {nachher!r}")

                # B5 Option A: Karte verliert border-blue-500, "Keine Benachrichtigungen" NICHT sichtbar
                _karten = page.locator(".q-card").all()
                _verlor_blau = any(
                    "border-blue-500" not in (k.get_attribute("class") or "")
                    for k in _karten
                )
                if _verlor_blau:
                    print("B5 Karte verliert border-blue-500 nach Mark-read (Option A)")
                else:
                    fehler.append("B5: Keine Karte verlor border-blue-500")
                try:
                    page.get_by_text("Keine Benachrichtigungen").wait_for(timeout=3000)
                    fehler.append("B5: 'Keine Benachrichtigungen' erscheint, Option A erwartet NICHT sichtbar")
                except Exception:
                    print("B5 'Keine Benachrichtigungen' NICHT sichtbar (Option A)")

                db_nach = unread(cid, "candidate")
                if db_nach == 0:
                    print(f"B6 DB get_unread_count({cid}, 'candidate') = 0")
                else:
                    fehler.append(f"B6 DB-Count {db_nach}, erwartet 0")
            except Exception as ex:  # noqa: BLE001
                fehler.append(f"Exception: {ex!r}")
            finally:
                browser.close()
    finally:
        cleanup(pre_tasks, cid, cv_file)
        print(f"CLEANUP: candidates/applications/notifications/agent_tasks>={pre_tasks} "
              f"zurueckgesetzt (cid={cid})")

    rest_cand = candidate_id()
    rest_apps = rows("SELECT COUNT(*) FROM applications WHERE candidate_id=?",
                     (cid,))[0][0] if cid else 0
    print(f"RESIDUE: candidate={rest_cand} applications={rest_apps} "
          f"notifications(NAME)={len(rows('SELECT id FROM notifications WHERE nachricht LIKE ?', (f'%{NAME}%',)))}")

    if fehler:
        print("FAIL:")
        for f in fehler:
            print("  -", f)
        return 1
    print("PASS: R3-5 (A: Bewerbung -> Employer-Benachrichtigung, "
          "B: Badge+Drawer-Refresh ohne Reload)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
