"""N-K1 (01.10.2026): Kandidaten-Suche — Status-Filter in Klartext, nur reale Werte.

Befund: `ergebnisse/ui-analyse-2026-09-29.md:65` — „Kandidaten-Suche … Dropdown zeigt
DB-Slug `lebenslauf_hochgeladen` (`:522`) weiter (N-K1)“.
Regel (umgesetzt): `knowledge/ui-design-system.md` §11 „Dropdown-/Filter-Optionen“ —
Klartext über `status_label()`, nur real vorkommende Werte, Sammelwert „alle“.

Prüft am ECHTEN gerenderten Dropdown (Playwright, isolierte Instanz, Spiegel-DB):
  1. geklickte Optionen enthalten KEINEN Unterstrich (kein DB-Slug),
  2. Optionsmenge == {Sammelwert} ∪ {status_label(s) für Pool-Status mit COUNT>0}
     — direkt gegen die (Spiegel-)DB gerechnet, nicht gegen eine Testkopie,
  3. das geschlossene Feld zeigt ebenfalls Klartext (kein `lebenslauf_hochgeladen`),
  4. Screenshot `ergebnisse/screenshots/n-k1-kandidaten-filter.png` (offenes Menü).
Read-only: nur Login/Navigation/Klick auf das Dropdown — kein Statuswechsel, keine Writes.

Ausführen (isoliert, nie gegen die Live-DB):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8094 --only e2e_kandidaten_filter
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
sys.path.insert(0, str(ROOT))
from webui.components import status_label  # noqa: E402
from webui.pages.employer import CAND_CV_STATUS, CAND_POOL_ALL_LABEL  # noqa: E402

OUT = ROOT / "ergebnisse" / "screenshots"
SHOT = OUT / "n-k1-kandidaten-filter.png"
EMP_EMAIL, EMP_PW = seed_email("hr@techvision.de"), "sicher123"
URL = f"{BASE}/employer/kandidaten"

_fails: list[str] = []
_notes: list[str] = []


def note(msg: str) -> None:
    _notes.append(msg)
    print("  ", msg)


def fail(msg: str) -> None:
    _fails.append(msg)
    print("  FAIL:", msg)


def erwartete_optionen() -> tuple:
    """(set der Klartext-Labels, {status: count}) aus der (Spiegel-)DB."""
    ph = ",".join("?" * len(CAND_CV_STATUS))
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        counts = dict(conn.execute(
            f"SELECT status, COUNT(*) FROM candidates WHERE status IN ({ph}) "
            "GROUP BY status", list(CAND_CV_STATUS)).fetchall())
    finally:
        conn.close()
    labels = {CAND_POOL_ALL_LABEL} | {status_label(s) for s, n in counts.items() if n}
    return labels, counts


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
    labels, counts = erwartete_optionen()
    print(f"Pre: DB={DB}")
    note(f"Pool-Status mit COUNT>0: { {s: n for s, n in counts.items() if n} }")
    note(f"erwartete Optionen (Klartext): {sorted(labels)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(30000)
        try:
            login_employer(page)
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            feld = page.locator(".q-select").first
            if not feld.count():
                fail("kein .q-select auf /employer/kandidaten gefunden")
                return 1
            feldtext = feld.inner_text().strip()
            note(f"Feld-Anzeige (geschlossen): {feldtext!r}")
            # Nur den WERT pruefen: label ("Status") + Icon-Name (arrow_drop_down) abtrennen
            wert_zeilen = [z.strip() for z in feldtext.splitlines()
                           if z.strip() and z.strip() != "arrow_drop_down"]
            wert = wert_zeilen[-1] if wert_zeilen else ""
            note(f"Feld-Wert (ohne Label/Icon): {wert!r}")
            if "lebenslauf_hochgeladen" in wert:
                fail(f"Feld zeigt den DB-Slug: {wert!r}")
            if "_" in wert:
                fail(f"Feld-Wert enthaelt einen Unterstrich (Slug): {wert!r}")
            if wert != CAND_POOL_ALL_LABEL:
                fail(f"Feld-Wert {wert!r} != Sammelwert {CAND_POOL_ALL_LABEL!r}")

            feld.click()
            page.wait_for_timeout(800)
            items = [t.strip() for t in page.locator(".q-menu .q-item").all_inner_texts()]
            note(f"geoeffnete Optionen: {items}")
            if not items:
                fail("Dropdown geoeffnet, aber keine Optionen gelesen")
                return 1
            slugs = [t for t in items if "_" in t]
            if slugs:
                fail(f"Slug in den Optionen: {slugs}")
            if set(items) != labels:
                fail(f"Optionsmenge weicht ab: {sorted(items)} != {sorted(labels)}")
            if CAND_POOL_ALL_LABEL not in items:
                fail(f"Sammelwert {CAND_POOL_ALL_LABEL!r} fehlt")
            if len(items) < 2:
                fail("nur der Sammelwert angeboten (keine reale Status-Option)")

            OUT.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOT))          # offenes Menue = Beweisbild
            note(f"Screenshot: {SHOT}")
            if "(alle)" in "\n".join(items):
                fail("roher Wert statt Klartext gefunden")
        finally:
            browser.close()

    if _fails:
        print("FAIL:")
        for f in _fails:
            print(" -", f)
        return 1
    print("PASS: N-K1 — Kandidaten-Filter zeigt Klartext-Labels und nur real "
          f"vorkommende Pool-Status ({len(labels)} Optionen), kein DB-Slug; "
          f"Screenshot {SHOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
