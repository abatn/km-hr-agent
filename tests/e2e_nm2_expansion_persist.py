"""N-M2 (01.10.2026): Der 15-s-Timer zerstört offene Details nicht.

Befund war `ui.timer(interval=15.0, callback=match_content.refresh)` — alle 15 s
Neuberechnung → offene Klappen klappten zu. Soll/Ist: `_tick()` refresht nur bei
geänderter Datensignatur (`_data_signature()` aus COUNT/MAX). Regel/Quelle:
`ergebnisse/entscheidungen.md` §N-M2.

Prüft am ECHT gerenderten Match-Tab (Playwright, isolierte Instanz ohne Runner):
  1. eine Match-Klappe öffnen → `q-expansion-item--expanded`,
  2. > Timer-Intervall (18 s) warten,
  3. Klappe ist weiterhin offen (DOM-Klasse unverändert),
  4. Screenshot `ergebnisse/screenshots/nm2-expansion-persist.png`.

Read-only: nur Login/Navigation/Klick/Warten — keine Writes.

Ausfuehren (isoliert):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8098 --only e2e_nm2_expansion_persist
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE, check_server, seed_email  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ergebnisse" / "screenshots"
SHOT = OUT / "nm2-expansion-persist.png"
EMP_EMAIL, EMP_PW = seed_email("hr@techvision.de"), "sicher123"
URL = f"{BASE}/employer/match"

_fails: list[str] = []


def fail(msg: str) -> None:
    _fails.append(msg)
    print("  FAIL:", msg)


def login_employer(page) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1200)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(600)
    pan = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I))).first
    pan.get_by_label("E-Mail").fill(EMP_EMAIL)
    pan.get_by_label("Passwort", exact=True).fill(EMP_PW)
    pan.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=25000)


def offene_klappen(page) -> int:
    return page.locator(".q-expansion-item--expanded").count()


def main() -> int:
    check_server()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(180000)
        try:
            login_employer(page)
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_selector("text=Match-Score", timeout=180000)
            page.wait_for_timeout(2500)

            # erste Match-Klappe öffnen
            exp = page.locator(".q-expansion-item").first
            if not exp.count():
                fail("keine Match-Klappe gefunden")
                return 2
            hdr = exp.locator(".q-item").first
            hdr.click()
            page.wait_for_timeout(800)
            vorher = offene_klappen(page)
            print(f"  nach Öffnen: offene Klappen={vorher}")
            if vorher < 1:
                fail("Klappe ließ sich nicht öffnen (kein --expanded)")
                return 1

            # > Timer-Intervall warten (15 s)
            page.wait_for_timeout(18000)
            nachher = offene_klappen(page)
            print(f"  nach 18s (> 15s-Timer): offene Klappen={nachher}")
            if nachher < vorher:
                fail(f"Timer hat Klappen geschlossen ({vorher} -> {nachher})")

            OUT.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOT))
        finally:
            browser.close()

    if _fails:
        print("FAIL:")
        for f in _fails:
            print(" -", f)
        return 1
    print("PASS: N-M2 — offene Klappe bleibt nach dem 15-s-Timer offen "
          f"({vorher} -> {nachher}); Screenshot {SHOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
