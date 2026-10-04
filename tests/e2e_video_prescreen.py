"""E2E A4 (30.09.2026): Video-Link überlebt "Selbstpräsentation starten"; Sprung Pre-Screen -> Video.

NUR gegen die Isolations-Instanz:
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8091 --only e2e_video_prescreen

Die App schreibt die Selbstpräsentations-Dateien nach ergebnisse/ (Dateisystem, nicht DB).
Dieses Skript sichert alle Dateien von cand 1 vorher und stellt sie im finally-Block wieder her
(neue Dateien werden entfernt).

 1 Sprachtest-Tab: "Video-Link generieren" -> Link sichtbar
 2 Pre-Screen-Tab: Hinweis "bereits hinterlegt" + Button "→ Zur Video-Vorstellung" sichtbar
 3 "Selbstpräsentation starten" -> Datei von heute enthält Leitfragen UND den Video-Link
 4 Button "→ Zur Video-Vorstellung" führt zu /candidate/sprachtest, Link dort weiter sichtbar
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import BASE, DB, check_server

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = (ROOT / "data" / "feedback.db").resolve()
ERG = ROOT / "ergebnisse"
CAND_ID = 1
EMAIL = "batniniabdelkader@yahoo.com"
PASSWORD = "Abdel15121978!"


def login(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    panel = page.locator(".q-tab-panel:visible").first
    panel.get_by_label("E-Mail").fill(EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(PASSWORD)
    panel.get_by_role("button").first.click()
    page.wait_for_url("**/candidate**", timeout=15000)


def dateien() -> dict:
    return {p: p.read_bytes() for p in ERG.glob(f"self-presentation-kandidat-{CAND_ID}-*.md")}


def main() -> int:
    if Path(DB).resolve() == LIVE_DB:
        print("ABBRUCH: DB-Pfad ist die Live-DB — nur via tests/e2e_isolation.py ausführen")
        return 2
    check_server()
    vorher = dateien()
    print(f"Sicherung: {len(vorher)} Dateien von cand {CAND_ID}")
    fehler = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        try:
            login(page)

            page.goto(f"{BASE}/candidate/sprachtest", wait_until="load")
            page.get_by_role("button", name=re.compile("Video-Link generieren")).click()
            page.get_by_text("Video-Link:").first.wait_for()
            link = re.search(r"https://vdo\.ninja/\?push=vorstellung-\d+-\w+",
                             page.locator("body").inner_text())
            link = link.group(0) if link else None
            print("1 Video-Link:", link)
            if not link:
                fehler.append("1 kein Video-Link im Sprachtest-Tab sichtbar")

            page.goto(f"{BASE}/candidate/prescreen", wait_until="load")
            page.get_by_text("Video-Vorstellung bereits hinterlegt").wait_for()
            sprung = page.get_by_role("button", name=re.compile("Zur Video-Vorstellung"))
            print("2 Hinweis + Sprung-Button sichtbar:", sprung.count() == 1)
            if sprung.count() != 1:
                fehler.append("2 Button '→ Zur Video-Vorstellung' fehlt")

            page.get_by_role("button", name=re.compile("Selbstpräsentation starten")).click()
            page.get_by_text("Ihr Raum ist bereit!").wait_for()
            heute = ERG / f"self-presentation-kandidat-{CAND_ID}-{datetime.now().strftime('%Y-%m-%d')}.md"
            text = heute.read_text(encoding="utf-8") if heute.exists() else ""
            print("3 heutige Datei:", heute.name, "| Leitfragen:", "## Ihre Leitfragen" in text,
                  "| Link:", bool(link and link in text))
            if "## Ihre Leitfragen" not in text:
                fehler.append("3 Pre-Screen-Datei ohne Leitfragen")
            if not link or link not in text:
                fehler.append("3 Video-Link fehlt nach Pre-Screen-Start (Regression A4)")

            sprung.click()
            # SPA-Navigation: Content wird getauscht. Die Browser-URL wird von navigate_to()
            # nicht zuverlässig nachgezogen (bekannt: P1-5, components.py) -> Inhalt prüfen.
            page.get_by_text("CEFR-Niveautests").wait_for()
            page.get_by_text("Video-Link:").first.wait_for()
            body = page.locator("body").inner_text()
            print("4 nach Sprung: Sprachtest-Tab sichtbar (URL informativ:", page.url,
                  ") | Link weiter sichtbar:", bool(link and link in body))
            if not link or link not in body:
                fehler.append("4 Link nach Sprung/Pre-Screen nicht mehr im Sprachtest-Tab sichtbar")
        except Exception as ex:  # noqa: BLE001
            fehler.append(f"Exception: {ex!r}")
        finally:
            browser.close()
            # Restore: neue Dateien weg, Originale zurück
            for pth in dateien():
                if pth not in vorher:
                    pth.unlink()
            for pth, inhalt in vorher.items():
                if not pth.exists() or pth.read_bytes() != inhalt:
                    pth.write_bytes(inhalt)
            print("Restore:", "OK" if dateien() == vorher else "ABWEICHUNG")
            if dateien() != vorher:
                fehler.append("Restore der Selbstpräsentations-Dateien fehlgeschlagen")
    if fehler:
        print("FAIL:")
        for f in fehler:
            print("  -", f)
        return 1
    print("PASS: Video-Link bleibt nach Pre-Screen-Start erhalten; Sprung-Button funktioniert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
