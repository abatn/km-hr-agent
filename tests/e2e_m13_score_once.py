"""M-13 (01.10.2026): Schadensnachweis fuer den Match-Score-Fundort.

Befund M-13 (P2): `score_bar` rendert sein eigenes Bruch-Label UND daneben stand
das Kategorie-Label → „53/100" **und** „53/100 (Schwach)" (Doppel-Score). Fix:
`score_bar(total, show_label=False)`. Bisher gab es dafuer nur Vorher-/Nachher-
Screenshots, **keine numerische Messung** (ui-analyse:90 „Schaden NICHT GEMESSEN").

Diese Messung ersetzt das: am ECHT gerenderten Match-Tab (Playwright, isolierte
Instanz, Spiegel-DB) wird je Match-Klappe (`Match-Score`-Kopf) die Anzahl der
`<Zahl>/100`-Treffer gezaehlt. Soll: **genau 1** je Klappe — der nackte Bruch
(ohne Kategorie in Klammern) darf **nicht** zusaetzlich vorkommen.

Read-only: nur Login/Navigation/Auslesen — keine Writes.

Ausfuehren (isoliert, nie gegen die Live-DB):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8096 --only e2e_m13_score_once
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE, check_server, seed_email  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EMP_EMAIL, EMP_PW = seed_email("hr@techvision.de"), "sicher123"
URL = f"{BASE}/employer/match"

# JS: je Match-Klappe den Kopf-Text lesen; Treffer auf "<Zahl>/100".
MEASURE = r"""
() => {
  const rows = [];
  document.querySelectorAll('.q-expansion-item').forEach(e => {
    const t = (e.innerText || '').replace(/\s+/g, ' ').trim();
    if (t.includes('Match-Score')) rows.push(t);
  });
  return rows;
}
"""

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
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(180000)
        try:
            login_employer(page)
            page.goto(URL, wait_until="domcontentloaded")
            # M-16: Match-Seite rechnet live (langsam) → auf den Score-Kopf warten
            page.wait_for_selector("text=Match-Score", timeout=180000)
            page.wait_for_timeout(3000)
            rows = page.evaluate(MEASURE)
        finally:
            browser.close()

    print(f"Pre: BASE={BASE}")
    print(f"  Match-Klappen mit Score-Kopf: {len(rows)}")
    if not rows:
        fail("kein Score-Kopf gefunden — Test nicht aussagekraeftig")
        return 2

    for i, t in enumerate(rows, 1):
        treffer = re.findall(r"\d+\s*/\s*100", t)
        nackt = re.findall(r"\d+\s*/\s*100(?!\s*\()", t)
        mit_kat = re.findall(r"\d+\s*/\s*100\s*\(", t)
        print(f"  Klappe {i}: {t[:110]!r}")
        print(f"      Treffer gesamt={len(treffer)}  nackt(ohne Kategorie)={len(nackt)}  "
              f"mit Kategorie={len(mit_kat)}")
        if len(nackt) > 0:
            fail(f"Klappe {i}: nackter Score-Bruch zusaetzlich ({nackt}) → Doppel-Score")
        if len(mit_kat) != 1:
            fail(f"Klappe {i}: erwartet genau 1 Score mit Kategorie, gefunden {len(mit_kat)}")

    if _fails:
        print("FAIL:")
        for f in _fails:
            print(" -", f)
        return 1
    print(f"PASS: M-13 — kein Doppel-Score; je Match-Klappe genau ein 'N/100 (Kategorie)' "
          f"({len(rows)} Klappen gemessen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
