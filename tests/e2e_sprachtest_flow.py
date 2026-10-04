"""E2E A1 (30.09.2026): Sprachtest-Flow im Candidate-Portal (webui/pages/candidate.py::_tab_sprachtest).

NUR gegen die Isolations-Instanz (schreibt language_tests, ändert die Datei-Rechte der
Spiegel-DB im Teil D):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8091 --only e2e_sprachtest_flow

Ablauf:
 A  Test 1 (Deutsch A1, 5 Fragen): jede Frage RICHTIG (Lösung aus dem Seed-Pool des Servers
    per Fragetext ermittelt) -> "Score: 100%", DB-Zeile punkte=1.0; "Weiter" ist vor der
    Auswahl deaktiviert; Ergebnisliste "Deine Ergebnisse" zeigt den neuen Test OHNE Reload.
 B  Test 2 (Deutsch A1, 5 Fragen): jede Frage FALSCH -> "Score: 0%", DB-Zeile punkte=0.0.
 C  Englisch A1 (Seed-Pool leer): sichtbare Fehlerkarte + "Erneut versuchen", KEINE neue
    DB-Zeile (Sonderfall: liefert das LLM doch Fragen, wird der Teil mit Grund übersprungen).
 D  Speicherfehler: Spiegel-DB read-only (chmod 444) -> Test zu Ende -> Meldung "Ergebnis
    konnte nicht gespeichert werden" statt "Test beendet!"; Rechte zurück -> "Erneut
    speichern" -> "Test beendet!" + DB-Zeile.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from e2e_harness import BASE, DB, check_server

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = (ROOT / "data" / "feedback.db").resolve()
CAND_ID = 1
CAND_EMAIL = "batniniabdelkader@yahoo.com"
CAND_PW = "Abdel15121978!"
N = 5


def seed_lookup() -> dict:
    """Fragetext -> (optionen, loesung) aus dem Seed-Pool des Servers (Deutsch A1)."""
    spec = importlib.util.spec_from_file_location(
        "language_test_server", str(ROOT / "scripts" / "language-test-server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pool = mod._parse_questions().get("Deutsch_A1", [])
    return {re.sub(r"\s+", " ", q["frage"]).strip(): q for q in pool}


def db_rows() -> list:
    conn = sqlite3.connect(DB)
    try:
        return conn.execute(
            "SELECT id, sprache, niveau, fragen_anzahl, punkte, cefr_level FROM language_tests "
            "WHERE candidate_id=? ORDER BY id", (CAND_ID,)).fetchall()
    finally:
        conn.close()


def login(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    panel = page.locator(".q-tab-panel:visible").first
    panel.get_by_label("E-Mail").fill(CAND_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(CAND_PW)
    panel.get_by_role("button").first.click()
    page.wait_for_url("**/candidate**", timeout=15000)


def pick_option(page, label: str, text: str):
    page.locator(".q-select").filter(has_text=label).first.click()
    page.locator(".q-menu .q-item").filter(has_text=re.compile(rf"^\s*{re.escape(text)}\s*$")).first.click()
    # Bestätigung statt fester Pause: Auswahl muss im Select sichtbar UND serverseitig
    # angekommen sein (Flake: Anzahl blieb sonst bei 10 → "Frage 1/5" erschien nie).
    page.locator(".q-select").filter(has_text=label).filter(has_text=text).first.wait_for()
    page.wait_for_timeout(800)


def run_test(page, lookup: dict, richtig: bool, fehler: list, tag: str) -> None:
    """Startet einen Test (Deutsch A1, N Fragen) und beantwortet alle Fragen."""
    for k in range(1, N + 1):
        page.get_by_text(f"Frage {k}/{N}").wait_for(timeout=30000)
        body = re.sub(r"\s+", " ", page.locator("body").inner_text())
        q = next((v for t, v in lookup.items() if t in body), None)
        if q is None:
            fehler.append(f"{tag}: Frage {k} nicht im Seed-Pool gefunden")
            return
        weiter = page.get_by_role("button", name=re.compile("Weiter"))
        if k == 1 and not weiter.is_disabled():
            fehler.append(f"{tag}: 'Weiter' ist vor der Auswahl NICHT deaktiviert")
        if page.locator(".q-radio[aria-checked='true']").count() != 0:
            fehler.append(f"{tag}: Radio hat eine Vorauswahl")
        richtig_idx = "abcd".index(q["loesung"])
        if richtig:
            idx = richtig_idx
        else:
            idx = next(i for i in range(len(q["antworten"])) if i != richtig_idx)
        page.locator(".q-radio").nth(idx).click()
        try:  # Server-Roundtrip (on_change → next_button.enable) abwarten, nicht 200 ms raten
            expect(weiter).to_be_enabled(timeout=5000)
        except Exception:
            pass
        if weiter.is_disabled():
            fehler.append(f"{tag}: 'Weiter' nach Auswahl weiterhin deaktiviert")
            return
        weiter.click()
        page.wait_for_timeout(300)


def main() -> int:
    if DB.resolve() == LIVE_DB:
        print("ABBRUCH: KMHR_DB_PATH zeigt auf die Live-DB — nur über tests/e2e_isolation.py starten")
        return 2
    check_server()
    lookup = seed_lookup()
    print(f"Seed-Pool Deutsch A1: {len(lookup)} Fragen")
    fehler: list = []
    rows0 = db_rows()
    print(f"DB vorher: {len(rows0)} language_tests-Zeilen für cand{CAND_ID}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        try:
            login(page)
            page.goto(f"{BASE}/candidate/sprachtest", wait_until="load", timeout=60000)
            page.wait_for_timeout(2500)
            pick_option(page, "Anzahl Fragen", str(N))

            # ── A: alles richtig ─────────────────────────────────────────
            page.get_by_role("button", name="Test starten").click()
            run_test(page, lookup, True, fehler, "A")
            page.get_by_text("Test beendet!").wait_for(timeout=15000)
            body = page.locator("body").inner_text()
            print("A: 'Test beendet!' sichtbar")
            if f"{N}/{N}" not in body or "Score: 100%" not in body:
                fehler.append(f"A: erwartet {N}/{N} und 'Score: 100%'")
            rows1 = db_rows()
            print("A: neue DB-Zeilen:", rows1[len(rows0):])
            if len(rows1) != len(rows0) + 1 or rows1[-1][4] != 1.0 or rows1[-1][3] != N:
                fehler.append(f"A: DB-Zeile falsch: {rows1[len(rows0):]}")
            # Ergebnisliste ohne Reload aktualisiert? (A1.3) — erste Karte mit 'CEFR:'
            first = page.locator(".q-card").filter(has_text="CEFR:").first
            ft = first.inner_text() if first.count() else ""
            print("A: erste Ergebnis-Karte:", ft.replace("\n", " | "))
            if "Deutsch A1" not in ft or "Score: 100%" not in ft:
                fehler.append(f"A: Ergebnisliste nicht aktualisiert: {ft!r}")

            # ── B: alles falsch ──────────────────────────────────────────
            page.get_by_role("button", name="Neuen Test starten").first.click()
            page.wait_for_timeout(500)
            page.get_by_role("button", name="Test starten").click()
            run_test(page, lookup, False, fehler, "B")
            page.get_by_text("Test beendet!").wait_for(timeout=15000)
            body = page.locator("body").inner_text()
            if f"0/{N}" not in body or "Score: 0%" not in body:
                fehler.append(f"B: erwartet 0/{N} und 'Score: 0%'")
            rows2 = db_rows()
            print("B: neue DB-Zeilen:", rows2[len(rows1):])
            if len(rows2) != len(rows1) + 1 or rows2[-1][4] != 0.0:
                fehler.append(f"B: DB-Zeile falsch: {rows2[len(rows1):]}")

            # ── C: 0 Fragen (Englisch A1) ────────────────────────────────
            page.get_by_role("button", name="Neuen Test starten").first.click()
            page.wait_for_timeout(500)
            pick_option(page, "Sprache", "Englisch")
            pick_option(page, "Niveau", "A1")
            page.get_by_role("button", name="Test starten").click()
            page.wait_for_selector("text=/konnten keine Fragen geladen werden|Fehler beim Laden|Frage 1\\//",
                                   timeout=60000)
            body = page.locator("body").inner_text()
            if "Frage 1/" in body:
                print("C: SKIP — LLM lieferte Fragen für Englisch A1 (0-Fragen-Pfad nicht auslösbar)")
            else:
                print("C: Fehlerkarte sichtbar")
                if page.get_by_role("button", name="Erneut versuchen").count() != 1:
                    fehler.append("C: Button 'Erneut versuchen' fehlt")
                rows3 = db_rows()
                if len(rows3) != len(rows2):
                    fehler.append(f"C: 0-Fragen-Test wurde gespeichert: {rows3[len(rows2):]}")
                else:
                    print("C: keine neue DB-Zeile (OK)")

            # ── D: Speicherfehler (DB read-only) ─────────────────────────
            page.goto(f"{BASE}/candidate/sprachtest", wait_until="load", timeout=60000)
            page.wait_for_timeout(2000)
            pick_option(page, "Anzahl Fragen", str(N))
            page.get_by_role("button", name="Test starten").click()
            n_vorher = len(db_rows())
            os.chmod(DB, 0o444)
            try:
                run_test(page, lookup, True, fehler, "D")
                page.get_by_text("Ergebnis konnte nicht gespeichert werden").wait_for(timeout=15000)
                print("D: Fehlermeldung 'Ergebnis konnte nicht gespeichert werden' sichtbar")
                if page.get_by_text("Test beendet!").count() != 0:
                    fehler.append("D: 'Test beendet!' trotz Speicherfehler angezeigt")
            finally:
                os.chmod(DB, 0o644)
            if len(db_rows()) != n_vorher:
                fehler.append("D: DB-Zeile trotz read-only geschrieben?")
            page.get_by_role("button", name="Erneut speichern").click()
            page.get_by_text("Test beendet!").wait_for(timeout=15000)
            rows4 = db_rows()
            print("D: nach 'Erneut speichern':", rows4[n_vorher:])
            if len(rows4) != n_vorher + 1 or rows4[-1][4] != 1.0:
                fehler.append(f"D: Retry-Speichern fehlgeschlagen: {rows4[n_vorher:]}")
        except Exception as ex:  # noqa: BLE001
            fehler.append(f"Exception: {ex!r}")
            try:
                print("DIAG Seitentext:", re.sub(r"\s+", " ", page.locator("body").inner_text())[-500:])
                page.screenshot(path="/tmp/opencode/e2e_sprachtest_flow_fail.png")
            except Exception:
                pass
        finally:
            try:
                os.chmod(DB, 0o644)
            except Exception:
                pass
            browser.close()

    if fehler:
        print("FAIL:")
        for f in fehler:
            print("  -", f)
        return 1
    print("PASS: Sprachtest-Flow (richtig 100%, falsch 0%, 0 Fragen, Speicherfehler+Retry, Liste aktuell)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
