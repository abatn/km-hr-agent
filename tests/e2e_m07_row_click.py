"""M-07 (01.10.2026): Klickziel je Feedback-Zeile — echter Klick, echte Wirkung.

Regel: `knowledge/ui-design-system.md` §11.1 „Klickziel je Tabellenzeile“.
Prüft am ECHT gerenderten Feedback-Tab (Playwright, isolierte Instanz, Spiegel-DB):
  1. auflösbare Zeile → Klick navigiert auf `/employer/match?kandidat=<id>`,
  2. nicht auflösbare Zeile (Altbestand) → Klick öffnet einen Detail-Dialog
     (kein Sprung auf eine falsche Seite),
  3. Screenshot `ergebnisse/screenshots/m07-feedback-row-click.png`.

Read-only: nur Login/Navigation/Suchfeld/Klick — kein Statuswechsel, keine Writes.
Datengetrieben: welche Zeile auflösbar ist, rechnet dieses Skript über
`employer._feedback_row_cid()` gegen die (Spiegel-)DB — keine festen IDs.

Ausführen (isoliert, nie gegen die Live-DB):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8095 --only e2e_m07_row_click
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE, DB, check_server  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webui.pages import employer as emp  # noqa: E402

OUT = ROOT / "ergebnisse" / "screenshots"
SHOT = OUT / "m07-feedback-row-click.png"
EMP_EMAIL, EMP_PW = "hr@techvision.de", "sicher123"
URL = f"{BASE}/employer/feedback"

_fails: list[str] = []
_notes: list[str] = []


def note(msg: str) -> None:
    _notes.append(msg)
    print("  ", msg)


def fail(msg: str) -> None:
    _fails.append(msg)
    print("  FAIL:", msg)


def _maps(pairs):
    nbi = {cid: nm for cid, nm in pairs}
    nti, ti = {}, {}
    for cid, nm in pairs:
        if not nm:
            continue
        nti.setdefault(nm.strip().casefold(), cid)
        toks = tuple(sorted(t for t in re.split(r"\s+", nm.casefold()) if t))
        ti.setdefault(toks, []).append(cid)
    return nbi, nti, ti


def ziele():
    """(aufloesbar: (name, cid), nicht_aufloesbar: (name, id)) aus der DB."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT id, match_id, kandidat_name FROM feedback ORDER BY id DESC LIMIT 20"
        ).fetchall()
        pairs = conn.execute("SELECT id, name FROM candidates").fetchall()
    finally:
        conn.close()
    nbi, nti, ti = _maps(pairs)
    resolvable, unresolvable = None, None
    for fid, mid, nm in rows:
        klass = emp._feedback_klarname(nm, nbi)
        cid = emp._feedback_row_cid(mid, nm, nbi, nti, ti)
        if cid is not None and resolvable is None:
            resolvable = (klass, cid, fid)
        if cid is None and unresolvable is None:
            unresolvable = (klass, fid)
    return resolvable, unresolvable


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


def suchen_und_klick(page, name: str) -> bool:
    """Zeile per Suchfeld heranholen und den Namens-Knopf anklicken."""
    feld = page.locator('input[placeholder="Suchen..."]').first
    if not feld.count():
        fail("kein Suchfeld auf /employer/feedback gefunden")
        return False
    feld.fill(name)
    page.wait_for_timeout(600)
    btn = page.locator("tbody tr").filter(has_text=name).locator(".q-btn").first
    if not btn.count():
        fail(f"keine klickbare Zeile (Namens-Knopf) für {name!r}")
        return False
    btn.click()
    return True


def main() -> int:
    check_server()
    resolvable, unresolvable = ziele()
    print(f"Pre: DB={DB}")
    note(f"auflösbare Zeile: {resolvable}")
    note(f"nicht auflösbare Zeile: {unresolvable}")
    if not resolvable:
        fail("keine auflösbare Feedback-Zeile in der DB — Test nicht aussagekräftig")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(30000)
        try:
            login_employer(page)

            # ── 1. auflösbar → Match-Sprung ──────────────────────────────
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            name, cid, fid = resolvable
            note(f"klicke auflösbare Zeile {name!r} (erwartet kandidat={cid})")
            if suchen_und_klick(page, name):
                ziel = f"/employer/match?kandidat={cid}"
                try:
                    page.wait_for_url(f"**{ziel}", timeout=15000)
                    note(f"URL nach Klick: {page.url}")
                except Exception:
                    fail(f"keine Navigation auf {ziel!r} (URL: {page.url})")

            # ── 2. nicht auflösbar → Dialog ──────────────────────────────
            if unresolvable:
                page.goto(URL, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                uname, ufid = unresolvable
                note(f"klicke nicht auflösbare Zeile {uname!r} (id={ufid}, Dialog erwartet)")
                if suchen_und_klick(page, uname):
                    try:
                        dlg = page.locator(".q-dialog").last
                        dlg.wait_for(state="visible", timeout=8000)
                        text = dlg.inner_text().strip()
                        note(f"Dialog sichtbar: {text[:120]!r}")
                        if "Feedback" not in text:
                            fail(f"Dialog ohne Feedback-Bezug: {text[:80]!r}")
                    except Exception:
                        fail(f"kein Detail-Dialog nach Klick auf {uname!r}")
            else:
                note("keine nicht-auflösbare Zeile in der DB — Dialog-Teil übersprungen")

            OUT.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOT))
            note(f"Screenshot: {SHOT.relative_to(ROOT)}")
        finally:
            browser.close()

    if _fails:
        print("FAIL:")
        for f in _fails:
            print(" -", f)
        return 1
    print("PASS: M-07 — auflösbare Feedback-Zeile springt zu "
          f"'/employer/match?kandidat=<id>', nicht auflösbare Zeile öffnet "
          f"Detail-Dialog; Screenshot {SHOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
