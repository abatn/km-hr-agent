"""P1.3 Read-Only E2E: 12 Profil-Felder in NiceGUI Read-View vs. DB (candidate id=1).

Kein Save, keine DB-Änderung. Login → /candidate/profil → DOM-Abgleich.
"""
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
EMAIL = seed_email("batniniabdelkader@yahoo.com")
PASSWORD = "Abdel15121978!"
CAND_ID = 1


def db_fields() -> dict:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """SELECT standort, nationalitaet, visum_status, verfuegbarkeit,
                  aktuelle_position, berufserfahrung_jahre, hard_skills,
                  soft_skills, abschluss, deutsch, englisch, gehaltsvorstellung
           FROM candidates WHERE id = ?""",
        (CAND_ID,),
    ).fetchone()
    conn.close()
    assert row, f"candidate {CAND_ID} not found"
    return dict(row)


def fmt_gehalt(v) -> str:
    if not v:
        return None
    return f"{int(v):,.0f}".replace(",", ".") + " EUR"


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    db = db_fields()
    print("DB:", db)
    # Baseline: Status VOR dem Seitenaufruf (P0-1, 29.09.2026 – Beweis: nur Gleichheit,
    # kein Festwert mehr, damit Kand. #1 nach Datenreparatur nicht ins Test-Fail läuft)
    _conn0 = sqlite3.connect(DB)
    status_baseline = _conn0.execute("SELECT status FROM candidates WHERE id=?", (CAND_ID,)).fetchone()[0]
    _conn0.close()
    print("Status-Baseline:", status_baseline)

    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{BASE}/login", wait_until="networkidle")

        # Candidate-Login (Tab "Login" default)
        page.get_by_label("E-Mail").fill(EMAIL)
        page.get_by_label("Passwort", exact=True).fill(PASSWORD)
        page.get_by_role("button", name="Einloggen").click()
        page.wait_for_url("**/candidate**", timeout=15000)

        # Direkt auf Profil-Tab
        page.goto(f"{BASE}/candidate/profil", wait_until="networkidle")
        page.wait_for_timeout(1500)

        body = page.inner_text("body")

        # 12 Felder: Label + DB-Wert im DOM (Read-View, vor Edit-Expander)
        checks = [
            ("Standort", db["standort"]),
            ("Nationalitaet", db["nationalitaet"]),
            ("Visum-Status", db["visum_status"]),
            ("Verfuegbarkeit", db["verfuegbarkeit"]),
            ("Aktuelle Position", db["aktuelle_position"]),
            ("Abschluss", db["abschluss"]),
            ("Deutsch", db["deutsch"]),
            ("Englisch", db["englisch"]),
        ]
        for label, value in checks:
            if value and str(value) not in body:
                failures.append(f"{label}: DB-Wert '{value}' fehlt im DOM")

        # Jahre Erfahrung (stat_card formatiert)
        years = db["berufserfahrung_jahre"]
        if years and f"{years} Jahre" not in body:
            failures.append(f"Jahre Erfahrung: '{years} Jahre' fehlt im DOM")

        # Gehalt (formatiert mit Tausender-Punkt)
        g = fmt_gehalt(db["gehaltsvorstellung"])
        if g and g not in body:
            failures.append(f"Gehaltsvorstellung: '{g}' fehlt im DOM")

        # hard_skills: leer → "Noch keine Skills erfasst"; sonst Chips
        if not db["hard_skills"]:
            if "Noch keine Skills erfasst" not in body:
                failures.append("hard_skills leer, aber Empty-Hint fehlt")
        else:
            for s in str(db["hard_skills"]).split(","):
                if s.strip() and s.strip() not in body:
                    failures.append(f"hard_skill '{s.strip()}' fehlt im DOM")

        # soft_skills: leer → info_row darf fehlen
        if db["soft_skills"] and str(db["soft_skills"]) not in body:
            failures.append(f"soft_skills '{db['soft_skills']}' fehlt im DOM")

        # Read-View-Überschriften vorhanden
        for heading in ("Persoenliche Daten", "Fachkompetenzen", "Berufserfahrung", "Sprachen", "Gehaltsvorstellung"):
            if heading not in body:
                failures.append(f"Karten-Überschrift '{heading}' fehlt")

        # Kein versehentliches Save: Status darf sich nicht geändert haben
        conn = sqlite3.connect(DB)
        status = conn.execute("SELECT status FROM candidates WHERE id=?", (CAND_ID,)).fetchone()[0]
        conn.close()
        if status != status_baseline:
            failures.append(f"unerwartete Statusänderung: {status} (Baseline {status_baseline})")

        browser.close()

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: alle 12 Read-View-Felder + Überschriften, keine DB-Änderung")
    return 0


if __name__ == "__main__":
    sys.exit(main())
