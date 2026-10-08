"""P3 E2E Save-Test: 12-Felder-Save via UI + verpflichtender DB-Restore.

Ablauf:
1. Originalwerte aus DB lesen (id=1)
2. Login → /candidate/profil → Expander "Profil bearbeiten" öffnen
3. Standort + Deutsch ändern → "Profil speichern"
4. DB-UPDATE verifizieren (mind. geänderte Felder)
5. Originalwerte via UI wiederherstellen → erneut speichern
6. DB == Original verifizieren

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_profile_save.py
"""
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
EMAIL = seed_email("batniniabdelkader@yahoo.com")
PASSWORD = "Abdel15121978!"
CAND_ID = 1

FIELDS = [
    "standort", "nationalitaet", "visum_status", "verfuegbarkeit",
    "aktuelle_position", "berufserfahrung_jahre", "hard_skills",
    "soft_skills", "abschluss", "deutsch", "englisch", "gehaltsvorstellung",
]


def read_db() -> dict:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cols = ", ".join(FIELDS)
    row = conn.execute(f"SELECT {cols} FROM candidates WHERE id = ?", (CAND_ID,)).fetchone()
    conn.close()
    return dict(row)


def login(page):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.get_by_label("E-Mail").fill(EMAIL)
    page.get_by_label("Passwort", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Einloggen").click()
    page.wait_for_url("**/candidate**", timeout=15000)


def open_edit(page):
    page.goto(f"{BASE}/candidate/profil", wait_until="networkidle")
    page.wait_for_timeout(800)
    page.get_by_text("Profil bearbeiten").first.click()
    page.wait_for_timeout(400)


def set_field(page, label, value):
    # NiceGUI input/select: Label-Feld direkt befüllen
    el = page.get_by_label(label, exact=True)
    el.fill(str(value))
    page.wait_for_timeout(100)


def select_field(page, label, value):
    el = page.get_by_label(label, exact=True)
    el.click()
    page.wait_for_timeout(200)
    # Quasar Select: Option im Popup wählen
    opt = page.get_by_role("option", name=str(value), exact=True)
    if opt.count() == 0:
        opt = page.get_by_text(str(value), exact=True).last
    opt.first.click()
    page.wait_for_timeout(150)


def save(page):
    page.get_by_role("button", name="Profil speichern").click()
    page.wait_for_timeout(1200)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    original = read_db()
    print("Original:", original)

    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            login(page)

            # ── Schritt 3: ändern (Standort + Deutsch) ──
            open_edit(page)
            TEST_STANDORT = "Berlin-Teststadt"
            TEST_DE = "C1"
            set_field(page, "Standort", TEST_STANDORT)
            select_field(page, "Deutsch", TEST_DE)
            save(page)

            # ── Schritt 4: DB-UPDATE verifizieren ──
            time.sleep(0.5)
            after = read_db()
            if after["standort"] != TEST_STANDORT:
                failures.append(f"Save fehlgeschlagen: standort={after['standort']!r} != {TEST_STANDORT!r}")
            if after["deutsch"] != TEST_DE:
                failures.append(f"Save fehlgeschlagen: deutsch={after['deutsch']!r} != {TEST_DE!r}")

            # Nicht geänderte Felder dürfen identisch bleiben
            for f in FIELDS:
                if f in ("standort", "deutsch"):
                    continue
                if after[f] != original[f]:
                    failures.append(f"Nicht-Zielfeld verändert: {f}: {original[f]!r} -> {after[f]!r}")

            # ── Schritt 5: Restore via UI ──
            open_edit(page)
            # Reload, damit Edit-Formular aktuellen (geänderten) DB-Stand zeigt
            set_field(page, "Standort", original["standort"] or "")
            select_field(page, "Deutsch", original["deutsch"] or "B1")
            save(page)

            # ── Schritt 6: Restore verifizieren ──
            time.sleep(0.5)
            restored = read_db()
            for f in FIELDS:
                if restored[f] != original[f]:
                    failures.append(f"Restore fehlgeschlagen {f}: {restored[f]!r} != {original[f]!r}")

        finally:
            # Notfall-Restore immer, auch bei Testfehlern
            final = read_db()
            if final != original:
                print("NOTFALL-RESTORE via SQL ...")
                conn = sqlite3.connect(DB)
                sets = ", ".join(f"{f}=?" for f in FIELDS)
                conn.execute(
                    f"UPDATE candidates SET {sets} WHERE id=?",
                    [original[f] for f in FIELDS] + [CAND_ID],
                )
                conn.commit()
                conn.close()
                print("Notfall-Restore ausgeführt.")
                failures.append("Hinweis: Notfall-Restore noetig (UI-Restore reichte nicht)")
            browser.close()

    print("Final DB:", read_db())
    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: Save (2 Felder) + unveränderte Restfelder + vollständiger Restore")
    return 0


if __name__ == "__main__":
    sys.exit(main())
