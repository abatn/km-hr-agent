"""O1 E2E: Bewerbungs-Dialog mit echtem Submit nach _SHELL_STATE-pro-Client-Fix.

Spec/Plan: entscheidungen.md 24.09.2026 (Analyse: Cross-Client-State in
_SHELL_STATE → navigate_to() traf gelöschten Client → RuntimeError
'The client this element belongs to has been deleted'). Fix O1: Key =
f"{client.id}:{role}" + Staleness-Guard mit Vollnavigation-Fallback.

Ablauf:
1. Harness-Precheck (Server, F2) + DB-Baseline (apps, max-Task)
2. Candidate-Login (#1, bekanntes Test-Login) -> /candidate/stellen
3. Karte "#6 E2E-Beweis" -> "Bewerben" -> Dialog
4. textarea maxlength-Attr prüfen (2000) -> Text füllen -> "Jetzt bewerben"
5. (a) positiver Toast "Bewerbung gesendet!" sichtbar
6. (b) KEIN Toast "Fehler:" / "client this element" (O1-Beweis)
7. (b2) Stellen-Tab gerendert (navigate_to hat Content getauscht)
8. (c) DB: neue Application (candidate 1 × job 6) existiert, apps +1,
   neue agent_tasks (Kette: send_confirmation + Chain — beabsichtigt, kein Residue-Null-Gate)

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_apply_dialog.py
"""
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import check_server, seed_email  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
EMAIL = seed_email("batniniabdelkader@yahoo.com")
PASSWORD = "Abdel15121978!"
CAND_ID = 1
# Teil-2-Residue-Fix 25.09.2026: kein hartes Paar mehr — JOB_ID wird in main()
# dynamisch gesucht (freier Job fuer CAND_ID) bzw. sauber ausgesprungen.
JOB_ID = None  # type: ignore[assignment]
LIST_OK = ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")


def find_runnable() -> tuple:
    """Sucht einen freien Job fuer CAND_ID UND prueft das CV-Gate (B2-3).

    Gibt (job_id|None, grund) zurueck; job_id None = echter Skip.
    """
    conn = sqlite3.connect(str(DB))
    try:
        st = conn.execute("SELECT status FROM candidates WHERE id=?", (CAND_ID,)).fetchone()
        free = [r[0] for r in conn.execute(
            """SELECT j.id FROM jobs j
               WHERE j.status = 'aktiv'
                 AND NOT EXISTS (SELECT 1 FROM applications a
                                 WHERE a.candidate_id = ? AND a.job_id = j.id)
               ORDER BY j.id""",
            (CAND_ID,),
        ).fetchall()]
    finally:
        conn.close()
    status = st[0] if st else None
    if status not in LIST_OK:
        return None, (f"CV-Gate (B2-3/Paritaet app.py:3278): Status {status!r} nicht in "
                      f"{LIST_OK} — Bewerben gesperrt, Test kann nicht greifen")
    if not free:
        return None, (f"kein freier Job fuer cand{CAND_ID}: alle aktiven Jobs haben bereits "
                      f"eine Bewerbung (UNIQUE-Paar) und nur dieses Test-Login existiert")
    return free[0], ""


def db_baseline(job_id: int) -> dict:
    conn = sqlite3.connect(str(DB))
    try:
        return {
            "apps": conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
            "max_task": conn.execute("SELECT COALESCE(MAX(id),0) FROM agent_tasks").fetchone()[0],
            "pair": conn.execute(
                "SELECT id, status FROM applications WHERE candidate_id=? AND job_id=?",
                (CAND_ID, job_id),
            ).fetchone(),
        }
    finally:
        conn.close()


def login(page):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.get_by_label("E-Mail").fill(EMAIL)
    page.get_by_label("Passwort", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Einloggen").click()
    page.wait_for_url("**/candidate**", timeout=15000)


def main() -> int:
    global JOB_ID
    check_server()
    failures = []
    # Teil-2-Residue-Fix 25.09.2026: freies Paar suchen statt hartes cand1×job6
    job_id, skip_grund = find_runnable()
    if job_id is None:
        print(f"SKIP (echter Skip, exit 0): {skip_grund}")
        print("Backlog: eigene TEST-Stelle/GO, wenn O1-Coverage wieder benoetigt wird.")
        return 0
    JOB_ID = job_id
    before = db_baseline(job_id)
    print(f"DB-Baseline vor: {before} (freies Paar cand{CAND_ID}×job{job_id})")
    if before["pair"]:
        # Zwischen find_runnable() und Baseline kann nichts passieren — Safety only
        print(f"SKIP: Paar cand{CAND_ID}×job{job_id} inzwischen belegt ({before['pair']})")
        return 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)
        try:
            login(page)
            page.goto(f"{BASE}/candidate/stellen", wait_until="load", timeout=90000)

            # Karte mit Job-Nr. finden (Titel-Label enthaelt "#<id> ")
            card = page.locator(".q-card").filter(has_text=f"#{job_id} ").first
            card.wait_for(timeout=30000)
            card.get_by_role("button", name="Bewerben").click()

            # Dialog: maxlength-Attr (24.09. Fix) + Fuellen + Submit
            ta = page.locator(".q-dialog textarea")
            ta.wait_for(timeout=10000)
            ml = ta.get_attribute("maxlength")
            print(f"textarea maxlength-Attribut: {ml}")
            if ml != "2000":
                failures.append(f"maxlength={ml} != 2000")
            ta.fill("O1-E2E: Submit nach _SHELL_STATE-pro-Client-Fix.")
            page.get_by_role("button", name="Jetzt bewerben").click()

            # (a) positiver Toast
            pos = page.get_by_text("Bewerbung gesendet! Der Agent prueft Ihren Lebenslauf.")
            try:
                pos.wait_for(timeout=8000)
                print("(a) positiver Toast: OK")
            except Exception:
                failures.append("(a) positiver Toast nicht sichtbar")

            # (b) kein Fehler-Toast (Client-deleted oder sonstiger)
            page.wait_for_timeout(1500)  # Zeit fuer verspaetete Fehler-Toasts
            neg = page.get_by_text("Fehler:", exact=False)
            n_neg = neg.count()
            print(f"(b) Fehler-Toasts: {n_neg}")
            if n_neg > 0:
                failures.append(f"(b) Fehler-Toast sichtbar: "
                                f"{neg.first.inner_text()[:120]!r}")

            # (b2) Stellen-Tab nach navigate_to-Render
            hdr = page.get_by_text("Stellenangebote")
            hdr_ok = hdr.count() > 0
            print(f"(b2) Stellen-Tab nach Submit: {hdr_ok}")
            if not hdr_ok:
                failures.append("(b2) Stellenangebote-Header fehlt nach navigate_to")

            # (c) DB: Application + Kette
            time.sleep(2)
            after = db_baseline(job_id)
            print(f"DB-Baseline nach: {after}")
            if not after["pair"]:
                failures.append(f"(c) Application cand{CAND_ID}×job{job_id} nicht angelegt")
            elif after["pair"][0] != before["apps"] + 1 and after["apps"] != before["apps"] + 1:
                pass  # apps-Check unten
            if after["apps"] != before["apps"] + 1:
                failures.append(f"(c) apps {before['apps']} -> {after['apps']} != +1")
            new_tasks = after["max_task"] - before["max_task"]
            print(f"(c) neue Tasks: +{new_tasks} (Kette erwartet)")
            if new_tasks < 1:
                failures.append("(c) keine neuen agent_tasks (Kette fehlt)")
        except Exception as ex:  # noqa: BLE001
            failures.append(f"Exception: {ex!r}")
        finally:
            browser.close()

    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: Dialog-Submit ohne Client-deleted-Fehler, Application+Kette angelegt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
