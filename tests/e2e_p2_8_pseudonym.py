"""P2-8 (01.10.2026): Klarname erst ab Status `eingeladen`.

Regel: `knowledge/portal/employer-portal-fields.md:110` +
`knowledge/lifecycle/application-status.md:80`. Umfang (Nutzer-Entscheidung
01.10.2026): nur die Stellenangebote-Seite.

Prüft am ECHT gerenderten `/employer/stellen` (Playwright, isolierte Instanz,
Spiegel-DB), datengetrieben (keine festen IDs):
  1. Kandidat mit EINER nicht-freigegebenen Bewerbung (abgelehnt/zurückgezogen/
     eingegangen/angesehen) → erscheint als „Kandidat #<id>", sein Klarname
     steht NICHT auf der Seite.
  2. Kandidat mit freigegebener Bewerbung (eingeladen/eingestellt) → Klarname
     ist sichtbar.
  3. Screenshot `ergebnisse/screenshots/p2-8-pseudonym.png`.

Read-only: nur Login/Navigation/Aufklappen — kein Statuswechsel, keine Writes.

Ausführen (isoliert, nie gegen die Live-DB):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8096 --only e2e_p2_8_pseudonym
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
SHOT = OUT / "p2-8-pseudonym.png"
EMP_EMAIL, EMP_PW = "hr@techvision.de", "sicher123"
URL = f"{BASE}/employer/stellen"

_fails: list[str] = []


def fail(msg: str) -> None:
    _fails.append(msg)
    print("  FAIL:", msg)


def note(msg: str) -> None:
    print("  ", msg)


def daten() -> tuple:
    """(single_nicht_freigegeben, freigegeben) aus der (Spiegel-)DB, employer 1.

    single = Kandidat mit genau EINER Bewerbung bei diesem Arbeitgeber (sonst
    könnte sein Name über eine andere, freigegebene Zeile sichtbar sein).
    """
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        emp_id = conn.execute("SELECT id FROM employers WHERE email=?", (EMP_EMAIL,)).fetchone()
        emp_id = emp_id[0] if emp_id else None
        rows = conn.execute(
            """SELECT a.candidate_id, c.name, a.status
               FROM applications a
               JOIN jobs j ON j.id = a.job_id
               LEFT JOIN candidates c ON c.id = a.candidate_id
               WHERE j.employer_id = ?""",
            (emp_id,),
        ).fetchall()
    finally:
        conn.close()
    per_cand: dict = {}
    for cid, name, status in rows:
        per_cand.setdefault(cid, {"name": name or "", "statuses": []})["statuses"].append(status)
    single_nicht, frei = None, None
    for cid, d in per_cand.items():
        if len(d["statuses"]) != 1:
            continue
        st = d["statuses"][0]
        if st not in emp.DOC_RELEASE_STATUS and d["name"] and single_nicht is None:
            single_nicht = (cid, d["name"], st)
        if st in emp.DOC_RELEASE_STATUS and d["name"] and frei is None:
            frei = (cid, d["name"], st)
    return single_nicht, frei


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
    single_nicht, frei = daten()
    note(f"nicht freigegeben (single): {single_nicht}")
    note(f"freigegeben: {frei}")
    if single_nicht is None:
        fail("kein Einzel-Bewerber mit nicht-freigegebenem Status gefunden (Testdaten)")
    if frei is None:
        fail("kein Bewerber mit freigegebenem Status gefunden (Testdaten)")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1200})
        login_employer(page)
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        # Archiv aufklappen, damit die Zeilen sicher gerendert sind
        arch = page.locator(".q-expansion-item").filter(has_text="Archiv")
        if arch.count():
            arch.first.click()
            page.wait_for_timeout(800)
        body = page.locator("body").inner_text()

        def _sichtbar(label: str) -> bool:
            # Zeilen-Anker: Label steht als eigener Name ODER als "Name – Titel"
            # (ggf. mit führendem Badge/Emoji). Substring-Treffer wie
            # "Test Kandidat" in "E2E Test Kandidat" zählen NICHT.
            pat = r"(?m)^[^\w]*" + re.escape(label) + r"(?:\s*$|\s+–)"
            return re.search(pat, body) is not None

        if single_nicht:
            cid, name, st = single_nicht
            pseudo = f"Kandidat #{cid}"
            if _sichtbar(pseudo):
                note(f"OK: {st} -> {pseudo} (Pseudonym)")
            else:
                fail(f"Pseudonym {pseudo} fehlt (Status {st})")
            if not _sichtbar(name):
                note(f"OK: Klarname {name!r} nicht sichtbar (nicht freigegeben)")
            else:
                fail(f"Klarname {name!r} sichtbar, obwohl Status {st} nicht freigegeben")

        if frei:
            cid, name, st = frei
            if _sichtbar(name):
                note(f"OK: freigegeben {st} -> Klarname {name!r} sichtbar")
            else:
                fail(f"Klarname {name!r} fehlt (freigegeben {st})")

        OUT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT), full_page=True)
        note(f"Screenshot: {SHOT}")
        browser.close()

    if _fails:
        print(f"FAIL — {len(_fails)} Prüfung(en) fehlgeschlagen")
        for f in _fails:
            print("   -", f)
        return 1
    print("PASS — Pseudonym bis `eingeladen` auf /employer/stellen bestätigt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
