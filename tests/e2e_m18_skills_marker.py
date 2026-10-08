"""M-18 (01.10.2026): Skills nicht mehr still gekürzt — Kürzung ist markiert.

Befund: `employer.py` schnitt die Hard-Skills hart bei 4 ab
(`str(h_skills).split(",")[:4]`) → Skills unvollständig. Fix: erste 4 Chips +
`+N weitere`-Chip (Tooltip listet die übrigen). Regel: `ui-design-system.md` §11.2.

Prüft am ECHT gerenderten Match-Tab (Playwright, isolierte Instanz, Spiegel-DB):
  1. Datenvorbedingung: es gibt Kandidaten mit >4 Hard-Skills,
  2. auf der Seite erscheint mindestens ein `+N weitere`-Marker,
  3. kein Marker `+0 weitere` (Kürzung nur wenn wirklich nötig),
  4. Screenshot `ergebnisse/screenshots/m18-skills-marker.png`.

Read-only: nur Login/Navigation/Auslesen — keine Writes.

Ausfuehren (isoliert):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8097 --only e2e_m18_skills_marker
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE, DB, check_server, seed_email  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ergebnisse" / "screenshots"
SHOT = OUT / "m18-skills-marker.png"
EMP_EMAIL, EMP_PW = seed_email("hr@techvision.de"), "sicher123"
URL = f"{BASE}/employer/match"

# JS: alle Chip-Texte sammeln
MEASURE = r"""
() => Array.from(document.querySelectorAll('.q-chip')).map(
  e => (e.innerText || '').replace(/\s+/g, ' ').trim())
"""

_fails: list[str] = []


def fail(msg: str) -> None:
    _fails.append(msg)
    print("  FAIL:", msg)


def vorbedingung() -> int:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM candidates "
            "WHERE hard_skills IS NOT NULL AND hard_skills != '' "
            "AND (LENGTH(hard_skills) - LENGTH(REPLACE(hard_skills, ',', '')) + 1) > 4"
        ).fetchone()[0]
    finally:
        conn.close()


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
    n_multi = vorbedingung()
    print(f"Pre: DB={DB}")
    print(f"  Kandidaten mit >4 Hard-Skills: {n_multi}")
    if n_multi == 0:
        fail("Datenvorbedingung fehlt (kein Kandidat mit >4 Skills)")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(180000)
        try:
            login_employer(page)
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_selector("text=Match-Score", timeout=180000)
            page.wait_for_timeout(3000)
            chips = page.evaluate(MEASURE)
            OUT.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOT))
        finally:
            browser.close()

    marker = [c for c in chips if re.fullmatch(r"\+\d+ weitere", c)]
    print(f"  Chips gesamt: {len(chips)}; Marker '+N weitere': {len(marker)} -> {marker}")
    if not marker:
        fail("kein '+N weitere'-Marker auf der Seite (Kürzung weiter still)")
    if any(re.fullmatch(r"\+0 weitere", m) for m in marker):
        fail("Marker '+0 weitere' vorhanden (Kürzung ohne Grund)")
    # Die Zahl im Marker muss >0 sein
    for m in marker:
        if int(re.findall(r"\d+", m)[0]) <= 0:
            fail(f"Marker ohne Rest: {m}")

    if _fails:
        print("FAIL:")
        for f in _fails:
            print(" -", f)
        return 1
    print(f"PASS: M-18 — Kürzung markiert ({len(marker)}× '+N weitere', "
          f"{n_multi} Kandidaten mit >4 Skills); Screenshot {SHOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
