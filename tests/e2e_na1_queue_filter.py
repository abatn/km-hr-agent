"""N-A1 (01.10.2026): Task-Status-Filter in den Agent-Details zeigt Klartext.

Befund: `ui.select(options=["alle","pending","running","done","failed","queued"])`
→ DB-Slugs im Dropdown. Soll: Klartext über `components.status_label`.

Prüft am ECHT gerenderten Agent-Details-Tab (Playwright, isolierte Instanz):
  1. Task-Queue-Klappe öffnen,
  2. Status-Dropdown öffnen → Optionen == {Alle, Offen, Läuft, Erledigt,
     Fehlgeschlagen, In Warteschlange},
  3. kein DB-Slug (pending/running/done/failed/queued) in den Optionen,
  4. Screenshot `ergebnisse/screenshots/na1-queue-filter.png`.

Read-only: nur Login/Navigation/Klick/Auslesen.

Ausfuehren (isoliert):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8099 --only e2e_na1_queue_filter
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
SHOT = OUT / "na1-queue-filter.png"
EMP_EMAIL, EMP_PW = seed_email("hr@techvision.de"), "sicher123"
URL = f"{BASE}/employer/agent_details"

ERWARTET = {"Alle", "Offen", "Läuft", "Erledigt", "Fehlgeschlagen", "In Warteschlange"}
SLUGS = {"pending", "running", "done", "failed", "queued"}

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


def main() -> int:
    check_server()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(60000)
        try:
            login_employer(page)
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Task-Queue-Klappe öffnen
            exp = page.locator(".q-expansion-item").filter(has_text="Task-Queue").first
            if not exp.count():
                fail("Task-Queue-Klappe nicht gefunden")
                return 2
            exp.locator(".q-item").first.click()
            page.wait_for_timeout(800)

            # WICHTIG: der erste .q-select der Seite ist der Kandidaten-Picker;
            # der Status-Filter liegt INNERHALB der Task-Queue-Klappe.
            feld = exp.locator(".q-select").first
            if not feld.count():
                fail("kein Task-Status-.q-select in der Task-Queue-Klappe gefunden")
                return 1
            feld.click()
            page.wait_for_timeout(700)
            items = [t.strip() for t in page.locator(".q-menu .q-item").all_inner_texts()]
            print(f"  Optionen: {items}")

            gefunden = set(items)
            if gefunden != ERWARTET:
                fail(f"Optionsmenge weicht ab: {sorted(gefunden)} != {sorted(ERWARTET)}")
            roh = [t for t in items if t in SLUGS]
            if roh:
                fail(f"DB-Slug in den Optionen: {roh}")

            OUT.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOT))
        finally:
            browser.close()

    if _fails:
        print("FAIL:")
        for f in _fails:
            print(" -", f)
        return 1
    print("PASS: N-A1 — Task-Status-Filter zeigt Klartext "
          f"({sorted(ERWARTET)}), kein DB-Slug; Screenshot {SHOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
