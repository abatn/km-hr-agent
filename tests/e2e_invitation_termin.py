"""P3 E2E C1: Einladungs-Termin (inline Inputs) fließt in create_invitation-Payload.

Ablauf:
1. DB-Vorher sichern (status, aktualisiert_am, max hist, Task-Anzahl) — Setup: App 16 = 'angesehen'
2. Employer-Login → /employer/stellen → Expansion 'Aktive Bewerber' → Karte '#16'
3. Dauer ggf. auf 45 setzen, '→ eingeladen' klicken
4. DB prüfen: status='eingeladen', Task-Payload enthält termin_datum/termin_uhrzeit/termin_dauer_min
   (Dauer darf NICHT 20 sein = Runner-Fallback-Beweis)
5. Notfall-Restore in finally: status/aktualisiert_am/hist/Task zurück

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_invitation_termin.py
Hinweis: agent-runner waehrend Test gestoppt (keine Echtest-Mail).
"""
import json
import re
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
APP_ID = 16
ORIG_STATUS = "eingegangen"
ORIG_UPD = "2026-09-14 22:05:49"
ORIG_HIST_MAX = 34  # Originalzustand vor heutigen E2E-Setups
EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"


def read_state() -> dict:
    conn = sqlite3.connect(DB)
    status, upd = conn.execute(
        "SELECT status, aktualisiert_am FROM applications WHERE id=?", (APP_ID,)
    ).fetchone()
    hist_max = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM application_status_history WHERE application_id=?",
        (APP_ID,),
    ).fetchone()[0]
    tasks = conn.execute(
        "SELECT id, payload FROM agent_tasks WHERE task_type='create_invitation' "
        "AND json_extract(payload, '$.application_id') = ?",
        (APP_ID,),
    ).fetchall()
    conn.close()
    return {"status": status, "upd": upd, "hist_max": hist_max, "tasks": tasks}


def setup_angesehen() -> None:
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE applications SET status='angesehen', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?",
        (APP_ID,),
    )
    conn.execute(
        "INSERT INTO application_status_history (application_id, status, changed_by) "
        "VALUES (?, 'angesehen', 'e2e_setup')",
        (APP_ID,),
    )
    conn.commit()
    conn.close()


def restore(state_after_setup: dict) -> None:
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE applications SET status=?, aktualisiert_am=? WHERE id=?",
        (ORIG_STATUS, ORIG_UPD, APP_ID),
    )
    conn.execute(
        "DELETE FROM application_status_history WHERE application_id=? AND id > ?",
        (APP_ID, ORIG_HIST_MAX),
    )
    conn.execute(
        "DELETE FROM agent_tasks WHERE task_type='create_invitation' "
        "AND json_extract(payload, '$.application_id') = ?",
        (APP_ID,),
    )
    conn.commit()
    conn.close()


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.wait_for_timeout(1800)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(700)
    # Panel am Login-Button festmachen (2 E-Mail-Felder sichtbar waehrend Tab-Anim.)
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I))
    ).first
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    setup_angesehen()
    pre = read_state()
    print("Pre:", pre)
    if pre["status"] != "angesehen":
        print(f"FAIL: Setup erwartet status='angesehen', ist {pre['status']!r}")
        db_residue_report(pre_tasks)
        return 1

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    failures = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            login_employer(page)
            print("login ok, URL:", page.url)
            page.goto(f"{BASE}/employer/stellen", wait_until="networkidle")
            page.wait_for_timeout(1500)
            print("stellen URL:", page.url)

            # Expansion sicherstellen — P1-13 (30.09.2026): "Aktive Bewerber" ist
            # jetzt STANDARDMAESSIG AUFGEKLAPPT. Ein blinder Klick wuerde sie jetzt
            # ZUMACHEN und die Karte verstecken. Deshalb zustandsabhaengig.
            exp = page.get_by_text("Aktive Bewerber")
            try:
                exp.first.wait_for(state="visible", timeout=10000)
            except Exception:
                body = page.locator("body").inner_text()[:600]
                print("DEBUG BODY:", body.replace("\n", " | "))
                raise
            # Zustaendig ueber die SICHTBARKEIT des Ziel-Buttons entscheiden —
            # robuster als Quasar-interne aria-Attribute.
            _card0 = page.locator(".q-card").filter(has_text="#16").first
            _btn0 = _card0.get_by_role("button", name="→ eingeladen")
            if _btn0.count() and _btn0.first.is_visible():
                print("Expansion 'Aktive Bewerber' ist bereits aufgeklappt (P1-13) "
                      "-> kein Klick")
            else:
                exp.first.click()
                page.wait_for_timeout(600)

            # Karte der App #16 scopen
            card = page.locator(".q-card").filter(has_text="#16").first
            if card.count() == 0:
                failures.append("Karte '#16' nicht gefunden")
                raise RuntimeError("card missing")

            # Dauer waehlen (45) — Defaults (morgen/10:00) bleiben
            try:
                card.get_by_label("Dauer (Min.)").click()
                page.wait_for_timeout(300)
                card.get_by_role("option", name="45", exact=True).click()
                page.wait_for_timeout(200)
            except Exception as e:
                print(f"HINWEIS: Dauer-Select nicht klickbar ({e}) — Default 30 bleibt")

            card.get_by_role("button", name="→ eingeladen").click()
            page.wait_for_timeout(1500)

            # ── DB verifizieren ──
            post = read_state()
            if post["status"] != "eingeladen":
                failures.append(f"status={post['status']!r} != 'eingeladen'")
            if len(post["tasks"]) != 1:
                failures.append(f"genau 1 create_invitation erwartet, sind {len(post['tasks'])}")
            else:
                payload = json.loads(post["tasks"][0][1])
                print("Payload:", payload)
                for key in ("termin_datum", "termin_uhrzeit", "termin_dauer_min"):
                    if key not in payload:
                        failures.append(f"Payload fehlt {key}")
                if payload.get("termin_datum") != tomorrow:
                    failures.append(
                        f"termin_datum={payload.get('termin_datum')!r} != morgen {tomorrow!r}"
                    )
                dauer = payload.get("termin_dauer_min")
                if dauer not in (30, 45):
                    failures.append(f"termin_dauer_min={dauer!r} nicht in (30,45)")
                if dauer == 20:
                    failures.append("termin_dauer_min=20 = Runner-Fallback, C1-Defaults NICHT geflossen")
                if payload.get("trigger") != "hr_klick_portal":
                    failures.append(f"trigger={payload.get('trigger')!r}")

        finally:
            browser.close()
            restore(pre)
            final = read_state()
            print("Final:", final)
            if final["status"] != ORIG_STATUS:
                failures.append(f"Restore status: {final['status']!r}")
            if final["hist_max"] != ORIG_HIST_MAX:
                failures.append(f"Restore hist_max: {final['hist_max']} != {ORIG_HIST_MAX}")
            if final["tasks"]:
                failures.append(f"Restore Tasks: {len(final['tasks'])} verbleiben")

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: Termin-Inputs → create_invitation-Payload (termin_datum/uhrzeit/dauer) + Restore")
    return 0


if __name__ == "__main__":
    sys.exit(main())
