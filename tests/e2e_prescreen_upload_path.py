#!/usr/bin/env python3
"""E2E P1-2 (29.09.2026): CV-Gate-Sackgasse hat jetzt einen klickbaren Upload-Weg.

Read-only-Nachweis gegen die Live-App:
1. Login als Kandidat, dessen Pre-Screen-Tab das CV-Gate zeigt
   (Gate iff Status ∉ {lebenslauf_hochgeladen, profil_geprueft,
   match_berechnet} UND keine Bewerbung 'eingeladen'/'eingestellt' —
   candidate.py::`_tab_prescreen`). DYNAMISCHE Auswahl (Cupplung06.10.2026):
   cand16 hatte früher Status 'registriert', hat seit App #24 'eingestellt'
   → Gate-Prüfung greift nicht mehr. Existiert kein solcher bekannter
   Test-Login, wird der Status eines geeigneten Kandidaten vorübergehend auf
   'registriert' gesetzt (Mirror-DB-Fixture, in finally zurückgesetzt — kein
   Lesen der echten DB).
2. Pre-Screen-Tab öffnen → Warn-Label + NEU: Button „→ Zum Lebenslauf-Upload".
3. Klick → Landung im Upload-Tab (Sackgasse behoben; Spec-Pfad
   navigate_to("candidate", "profil") — Upload-Tab ist seit 02.10.2026 Teil
   von „Mein Profil").
4. DB-Baseline vor == nach (read-only; die Fixture schreibt nur
   candidates.status, nicht applications/agent_tasks).

Spec: knowledge/portal/cv-pflicht.md §(h) · Plan: ergebnisse/ui-mvp-plan-v2.md §6 P1-2
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from e2e_harness import BASE, DB, check_server, seed_email  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

KNOWN_LOGINS = (
    (seed_email("batniniabdelkader@yahoo.com"), "Abdel15121978!"),
    (seed_email("e2e-beweis-phase1@example.com"), "E2EMentoring2026!"),
    (seed_email("recruiting.e2e.2809b@kmailtest.de"), "Test1234!"),
)
# candidate.py::_tab_prescreen – gleiche Mengen wie im Code (Prüfung dort)
CV_WHITELIST = ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet")
DOC_RELEASE = ("eingeladen", "eingestellt")

CAND_EMAIL = ""
CAND_PASSWORD = ""

# Fixture (Design-Entscheidung): (candidate_id, Original-Status) oder None
FIXTURE: tuple[int, str] | None = None

failures: list[str] = []


def pick_candidate() -> bool:
    """Wählt dynamisch den Test-Kandidaten (Datenkupplung06.10.2026)."""
    global CAND_EMAIL, CAND_PASSWORD, FIXTURE
    emails = [e for e, _ in KNOWN_LOGINS]
    conn = sqlite3.connect(str(DB))
    try:
        cand = conn.execute(
            f"SELECT id, email, status FROM candidates WHERE email IN "
            f"({','.join('?' * len(emails))}) ORDER BY id", emails,
        ).fetchall()
        for cid, email, status in cand:
            releasing = conn.execute(
                "SELECT 1 FROM applications WHERE candidate_id = ?"
                " AND status IN (?,?) LIMIT 1",
                (cid, *DOC_RELEASE),
            ).fetchone()
            if status not in CV_WHITELIST and not releasing:
                CAND_EMAIL, CAND_PASSWORD = email, dict(KNOWN_LOGINS)[email]
                FIXTURE = None
                print(f"OK Kandidat dynamisch: {email} (Status {status} → Gate offen, keine Fixture)")
                return True
        # Kein Kandidat zeigt das Gate nativ → Status-Fixture auf geeignetem Login
        for cid, email, status in cand:
            releasing = conn.execute(
                "SELECT 1 FROM applications WHERE candidate_id = ?"
                " AND status IN (?,?) LIMIT 1",
                (cid, *DOC_RELEASE),
            ).fetchone()
            if releasing:
                continue
            conn.execute("UPDATE candidates SET status='registriert' WHERE id=?", (cid,))
            conn.commit()
            FIXTURE = (cid, status)
            CAND_EMAIL, CAND_PASSWORD = email, dict(KNOWN_LOGINS)[email]
            print(f"OK Kandidat dynamisch: {email} (Status {status} → 'registriert' als Fixture, wird zurückgesetzt)")
            return True
    finally:
        conn.close()
    print("FAIL: kein bekannter Test-Login für das CV-Gate verfügbar")
    return False


def restore_fixture() -> None:
    if FIXTURE is None:
        return
    cid, status = FIXTURE
    conn = sqlite3.connect(str(DB))
    try:
        conn.execute("UPDATE candidates SET status=? WHERE id=?", (status, cid))
        conn.commit()
    finally:
        conn.close()
    print(f"OK Fixture zurückgesetzt: Kandidat {cid} → Status {status}")


def main() -> int:
    check_server()
    if not pick_candidate():
        return 1

    # DB-Baseline (read-only)
    conn = sqlite3.connect(str(DB))
    before_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    before_tasks = conn.execute("SELECT COALESCE(MAX(id),0) FROM agent_tasks").fetchone()[0]
    conn.close()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            try:
                # 1. Login (Default-Tab = Candidate Login)
                page.goto(f"{BASE}/login", wait_until="load")
                page.wait_for_timeout(2500)
                panel = page.locator(".q-tab-panel:visible").first
                panel.get_by_label("E-Mail").fill(CAND_EMAIL)
                panel.get_by_label("Passwort", exact=True).fill(CAND_PASSWORD)
                panel.get_by_role("button").first.click()
                page.wait_for_url("**/candidate**", timeout=15000)
                print(f"OK login {CAND_EMAIL}")

                # 2. Pre-Screen-Tab öffnen
                page.goto(f"{BASE}/candidate/prescreen", wait_until="load")
                page.wait_for_timeout(3000)
                body = page.inner_text("body")

                warn_ok = "CV-Pflicht" in body
                # Button-Text ist "→ Zum Lebenslauf-Upload" (Prefix) → Regex
                btn = page.get_by_role("button", name=re.compile("Zum Lebenslauf-Upload"))
                btn_ok = btn.count() >= 1
                print(f"OK warn_label={warn_ok} upload_button={btn_ok}")
                if not warn_ok:
                    failures.append("Warn-Label fehlt")
                if not btn_ok:
                    failures.append("klickbarer Upload-Weg fehlt (Sackgasse bestand weiterhin)")

                # 3. Klick → „Mein Profil" (enthält Expansion „Lebenslauf hochladen")
                if btn_ok:
                    btn.first.click()
                    page.wait_for_timeout(3000)
                    body2 = page.inner_text("body")
                    land_ok = "Lebenslauf hochladen" in body2
                    print(f"OK landing upload={land_ok} url={page.url}")
                    if not land_ok:
                        failures.append("Klick landet nicht im Upload")
                else:
                    failures.append("Kein Klick möglich (Button fehlt)")
            finally:
                ctx.close()
                browser.close()

        # 4. DB unverändert (read-only-Lauf)
        conn = sqlite3.connect(str(DB))
        after_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        after_tasks = conn.execute("SELECT COALESCE(MAX(id),0) FROM agent_tasks").fetchone()[0]
        conn.close()
        db_ok = (before_apps == after_apps) and (before_tasks == after_tasks)
        print(f"DB-CHECK: apps {before_apps}=={after_apps}, max_task {before_tasks}=={after_tasks}, unveraendert={db_ok}")
        if not db_ok:
            failures.append("DB wurde veraendert (read-only verletzt)")
    finally:
        restore_fixture()

    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("E2E P1-2 PASS: Warn-Label + klickbarer Upload-Weg + Klick landet im Upload, DB unveraendert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
