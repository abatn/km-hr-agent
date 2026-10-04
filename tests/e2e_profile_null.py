"""E2E A3 (30.09.2026): Profil speichern erfindet keine Werte; Dropdowns leaken keine Fremddaten.

NUR gegen die Isolations-Instanz (setzt in der Spiegel-DB Felder von cand 1 auf NULL):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8091 --only e2e_profile_null

 1 Spiegel-DB: deutsch/englisch/verfuegbarkeit/visum_status/berufserfahrung/gehaltsvorstellung = NULL
 2 Profil-Tab -> "Profil bearbeiten": Abschluss- und Visum-Dropdown öffnen
   -> nur feste Liste + EIGENER Wert; Abschluss/Visum anderer Kandidaten (SELECT DISTINCT-Leck) fehlen
 3 Nur Standort ändern -> "Profil speichern" -> die NULL-Felder bleiben NULL
   (vorher: 'Sofort'/'B1'/0 wurden als Nutzerdaten geschrieben)
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import BASE, DB, check_server

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = (ROOT / "data" / "feedback.db").resolve()
CAND_ID = 1
EMAIL = "batniniabdelkader@yahoo.com"
PASSWORD = "Abdel15121978!"
NULL_FELDER = ("deutsch", "englisch", "verfuegbarkeit", "visum_status",
               "berufserfahrung_jahre", "gehaltsvorstellung")
FEST_ABSCHLUSS = ["Bachelor", "Master", "Diplom", "PhD", "Sonstiges"]
FEST_VISUM = ["EU-Bürger", "Arbeitsvisum", "Kein Visum", "Sonstiges"]


def login(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    panel = page.locator(".q-tab-panel:visible").first
    panel.get_by_label("E-Mail").fill(EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(PASSWORD)
    panel.get_by_role("button").first.click()
    page.wait_for_url("**/candidate**", timeout=15000)


def row() -> dict:
    conn = sqlite3.connect(str(DB))
    try:
        cols = ("standort", "abschluss") + NULL_FELDER
        r = conn.execute(f"SELECT {', '.join(cols)} FROM candidates WHERE id=?", (CAND_ID,)).fetchone()
        return dict(zip(cols, r))
    finally:
        conn.close()


def optionen(page, label: str) -> list:
    page.get_by_label(label, exact=True).click()
    page.wait_for_timeout(500)
    texte = [t.strip() for t in page.locator(".q-menu .q-item").all_inner_texts()]
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return texte


def main() -> int:
    if Path(DB).resolve() == LIVE_DB:
        print("ABBRUCH: DB-Pfad ist die Live-DB — nur via tests/e2e_isolation.py ausführen")
        return 2
    check_server()
    # Alle Skripte eines Isolations-Laufs teilen sich EINE Spiegel-DB -> Ausgangszustand
    # sichern und im finally wiederherstellen (sonst kippt z. B. e2e_profile_save).
    restore_cols = ("standort",) + NULL_FELDER
    conn = sqlite3.connect(str(DB))
    original = conn.execute(f"SELECT {', '.join(restore_cols)} FROM candidates WHERE id=?",
                            (CAND_ID,)).fetchone()
    conn.execute("UPDATE candidates SET " + ", ".join(f"{f}=NULL" for f in NULL_FELDER)
                 + " WHERE id=?", (CAND_ID,))
    conn.commit()
    conn.close()
    vorher = row()
    eigener_abschluss = vorher["abschluss"]
    print("Vorher:", {k: vorher[k] for k in NULL_FELDER}, "| abschluss:", eigener_abschluss)
    fehler = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        try:
            login(page)
            page.goto(f"{BASE}/candidate/profil", wait_until="load")
            page.wait_for_timeout(1500)
            page.get_by_text("Profil bearbeiten").first.click()
            page.wait_for_timeout(500)

            ab = optionen(page, "Abschluss")
            vi = optionen(page, "Visum-Status")
            print("Abschluss-Optionen:", ab)
            print("Visum-Optionen:", vi)
            erlaubt_ab = set(FEST_ABSCHLUSS) | ({eigener_abschluss} if eigener_abschluss else set())
            if set(ab) != erlaubt_ab:
                fehler.append(f"Abschluss-Optionen {ab} != fest+eigen {sorted(erlaubt_ab)}")
            if set(vi) != set(FEST_VISUM):
                fehler.append(f"Visum-Optionen {vi} != feste Liste {FEST_VISUM} (eigener Wert war NULL)")

            page.get_by_label("Standort", exact=True).fill("NullTest-Ort")
            page.get_by_role("button", name="Profil speichern").click()
            page.wait_for_timeout(1500)
            nachher = row()
            print("Nachher:", {k: nachher[k] for k in NULL_FELDER}, "| standort:", nachher["standort"])
            if nachher["standort"] != "NullTest-Ort":
                fehler.append(f"Speichern hat nicht gegriffen: standort={nachher['standort']!r}")
            for f in NULL_FELDER:
                if nachher[f] is not None:
                    fehler.append(f"{f} wurde von NULL auf {nachher[f]!r} gesetzt (erfundener Default)")
            if nachher["abschluss"] != eigener_abschluss:
                fehler.append(f"abschluss verändert: {nachher['abschluss']!r}")
        except Exception as ex:  # noqa: BLE001
            fehler.append(f"Exception: {ex!r}")
        finally:
            browser.close()
            conn = sqlite3.connect(str(DB))
            conn.execute("UPDATE candidates SET " + ", ".join(f"{c}=?" for c in restore_cols)
                         + " WHERE id=?", (*original, CAND_ID))
            conn.commit()
            conn.close()
            print("Restore Spiegel-DB: OK")
    if fehler:
        print("FAIL:")
        for f in fehler:
            print("  -", f)
        return 1
    print("PASS: NULL bleibt NULL, Dropdowns = feste Liste + eigener Wert (kein Fremddaten-Leck)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
