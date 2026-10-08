"""M-17 (01.10.2026): SPA-Sprungverhalten von `navigate_to` (pushState) messen.

Befund: `components.py:73` aktualisiert die URL per `history.pushState` (Best-Effort,
in try/except). Live-Verhalten war „NICHT GEMESSEN". Diese Messung protokolliert:
  1. Ausgangsseite (URL + Inhalt),
  2. Klick auf einen `navigate_to(...)`-Knopf (Profil-Tab: Upload ODER Video),
  3. URL + Inhalt danach (Soll: URL UND Inhalt konsistent = SPA-Sprung),
  4. Browser-Zurück (popstate) → URL + Inhalt.

Ergebnis wird als Protokoll `ergebnisse/pushstate-protokoll-<datum>.md` geschrieben
(die Datei ist der Beweis; der Exit-Code ist PASS/FAIL).

Read-only: nur Login/Navigation/Klick/Auslesen.

Ausfuehren (isoliert):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8101 --only e2e_m17_pushstate
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE, check_server, seed_email  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAND_EMAIL, CAND_PW = seed_email("recruiting.e2e.2809b@kmailtest.de"), "Test1234!"
PROTO = ROOT / "ergebnisse" / f"pushstate-protokoll-{datetime.now():%Y-%m-%d}.md"

MARK_PRESCREEN = "Selbstpräsentation"  # _tab_prescreen (dort liegen die navigate_to-Knoepfe)
MARK_UPLOAD = "PDF oder TXT-Datei ablegen"  # Box "Lebenslauf hochladen" auf /candidate/profil
MARK_SPRACH = "CEFR-Niveautests"

zeilen: list[str] = []
fails: list[str] = []


def rec(txt: str) -> None:
    zeilen.append(txt)
    print("  ", txt)


def fail(msg: str) -> None:
    fails.append(msg)
    print("  FAIL:", msg)


def login_candidate(page) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1200)
    pan = page.locator(".q-tab-panel").filter(
        has=page.get_by_role("button", name="Einloggen")).first
    pan.get_by_label("E-Mail").first.fill(CAND_EMAIL)
    pan.get_by_label("Passwort", exact=True).first.fill(CAND_PW)
    pan.get_by_role("button", name="Einloggen").click()
    page.wait_for_url("**/candidate**", timeout=25000)


def sichtbar(page, text: str) -> bool:
    try:
        return page.get_by_text(text, exact=False).count() > 0
    except Exception:
        return False


def main() -> int:
    check_server()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(60000)
        try:
            login_candidate(page)
            page.goto(f"{BASE}/candidate/prescreen", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            url0 = page.url
            rec(f"1) Ausgang: URL={url0} · Pre-Screen-Marker={sichtbar(page, MARK_PRESCREEN)}")

            # navigate_to-Knopf auf dem Profil-Tab (CV-Status entscheidet welcher)
            knopftexte = [t.strip().replace("\n", " ") for t in
                          page.locator("button").all_inner_texts()]
            rec(f"1b) Knöpfe auf der Seite: {knopftexte[:25]}")
            _body = page.locator("body").inner_text()
            rec(f"1c) Text-Flags: CV-Pflicht={'CV-Pflicht' in _body} · "
                f"Video={'Video-Vorstellung' in _body} · "
                f"Lebenslauf={'Lebenslauf-Upload' in _body}")
            if page.get_by_role("button", name=re.compile("Video-Vorstellung", re.I)).count():
                btn_name, ziel, marker = "Zur Video-Vorstellung", "/candidate/sprachtest", MARK_SPRACH
            elif page.get_by_role("button", name=re.compile("Lebenslauf-Upload", re.I)).count():
                btn_name, ziel, marker = "Zum Lebenslauf-Upload", "/candidate/profil", MARK_UPLOAD
            else:
                fail("kein navigate_to-Knopf auf /candidate/prescreen gefunden")
                return 2
            rec(f"2) Klick-Knopf: '{btn_name}' (erwartet → {ziel})")

            page.get_by_role("button", name=re.compile(btn_name.split()[-1], re.I)).first.click()
            page.wait_for_timeout(2000)
            if ziel == "/candidate/profil":
                # Box "Lebenslauf hochladen" ist beim Wechsel geschlossen — Inhalt
                # (Marker) erst nach Klick auf den Titel sichtbar.
                try:
                    page.get_by_text("Lebenslauf hochladen", exact=True).first.click(timeout=8000)
                    page.wait_for_timeout(600)
                except Exception:  # noqa: BLE001 — Box evtl. bereits offen
                    pass
            url1 = page.url
            rec(f"3) nach Klick: URL={url1} · Ziel-Marker={sichtbar(page, marker)} "
                f"· Pre-Screen-Marker noch da={sichtbar(page, MARK_PRESCREEN)}")

            url_ok = ziel in url1
            inhalt_ok = sichtbar(page, marker)
            if not url_ok:
                fail(f"URL nicht aktualisiert (erwartet {ziel!r}, ist {url1!r})")
            if not inhalt_ok:
                fail(f"Content nicht gewechselt (Marker {marker!r} fehlt)")

            # Browser Back (popstate)
            page.go_back()
            page.wait_for_timeout(1500)
            url2 = page.url
            zurueck = sichtbar(page, MARK_PRESCREEN)
            rec(f"4) nach Back: URL={url2} · Pre-Screen-Marker={zurueck}")
            if not zurueck:
                fail("Browser-Back brachte nicht den Pre-Screen zurück")

            rec(f"Ergebnis: URL-Konsistenz={url_ok} · Inhalts-Konsistenz={inhalt_ok} "
                f"· Back-Konsistenz={zurueck}")
        finally:
            browser.close()

    kopf = (f"# M-17 — SPA-Sprungverhalten `navigate_to` (pushState)\n\n"
            f"**Datum:** {datetime.now():%Y-%m-%d %H:%M} · **Instanz:** {BASE} (isoliert)\n"
            f"**Messobjekt:** `components.py:73` `history.pushState` in `navigate_to()`\n"
            f"**Rohbeobachtungen:**\n")
    body = "\n".join(f"- {z}" for z in zeilen)
    status = "PASS" if not fails else "FAIL:\n" + "\n".join(f"- {f}" for f in fails)
    PROTO.write_text(kopf + body + f"\n\n**Status:** {status}\n", encoding="utf-8")
    print(f"Protokoll: {PROTO.relative_to(ROOT)}")

    if fails:
        print("FAIL:")
        for f in fails:
            print(" -", f)
        return 1
    print("PASS: M-17 — navigate_to: URL und Inhalt konsistent, Back stellt Profil her")
    return 0


if __name__ == "__main__":
    sys.exit(main())
