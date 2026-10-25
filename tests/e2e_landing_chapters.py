"""E2E: Landingpage-Animation „Das Agenten-Prinzip" (25.10.2026).

Prüft am ECHT gerenderten Three.js-Canvas (isolierte Instanz, Spiegel-DB):
  1. Fenster/Canvas/`window.__kmhr` sind da (kein Reduced-Motion-Fallback).
  2. Genau 5 Kapitel; jedes Kapitel hat Titel, Kamera-Ziel und aktiven Dot.
  3. Countdown 30→0 und Fortschrittsbalken laufen; Autoplay schreitet voran.
  4. Klick auf Dot 5 seekt zum Ergebnis-Kapitel.
  5. Pause stoppt die Zeit, erneuter Klick setzt sie fort.
  6. `prefers-reduced-motion: reduce` liefert ein statisches Bild (t/Countdown fix).
  7. Der Login-Link bleibt erreichbar (Regression: bestehende Navigation).
  8. Screenshots als Beweis in `ergebnisse/screenshots/`.

Read-only: keine DB-Writes, kein Login, keine Formulare.

Ausführen (isoliert, nie gegen 8080):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8097 --only e2e_landing_chapters
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE, check_server  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ergebnisse" / "screenshots"
SHOT_CHAPTER = OUT / "landing-agent-prinzip.png"
SHOT_RESULT = OUT / "landing-agent-ergebnis.png"

CHAPTERS = [
    ("Das Gehirn", 0.0, 5.2),
    ("Die Loop", 6.0, 11.2),
    ("Die Sub-Agenten", 12.0, 17.2),
    ("Die Werkzeuge", 18.0, 23.2),
    ("Das Ergebnis", 24.0, 30.0),
]

_fails: list[str] = []


def fail(msg: str) -> None:
    _fails.append(msg)
    print("  FAIL:", msg)


def state(page) -> dict:
    return page.evaluate("() => window.__kmhr.state()")


def wait_ready(page) -> None:
    page.goto(f"{BASE}/", wait_until="domcontentloaded")
    page.wait_for_selector("#kmhr-anim-host canvas", timeout=30000)
    page.wait_for_function("() => window.__kmhr && window.__kmhr.state", timeout=30000)
    page.wait_for_timeout(400)


def seek(page, sec: float) -> None:
    page.evaluate(f"() => window.__kmhr.seek({sec})")
    # setCaption ist absichtlich 160 ms entkoppelt (DOM-Overlay).
    page.wait_for_timeout(350)


def main() -> int:
    check_server()
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Pre: BASE={BASE}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(60000)
        try:
            wait_ready(page)
            s0 = state(page)
            print("  state:", s0)
            if s0.get("total") != 30.0:
                fail(f"TOTAL != 30.0: {s0.get('total')}")
            if len(s0.get("stationZ", [])) != 5:
                fail(f"erwartet 5 Stationen, gefunden {len(s0.get('stationZ', []))}")
            if s0.get("reduce"):
                fail("Seite startet im Reduced-Motion-Modus (Canvas/Animation fehlt)")

            # 1) Autoplay läuft
            t_before = float(state(page)["t"])
            page.wait_for_timeout(900)
            t_after = float(state(page)["t"])
            if t_after <= t_before:
                fail(f"Autoplay steht: t {t_before} -> {t_after}")

            # 2) Alle 5 Kapitel: Titel, Dot, Kamera
            for i, (title, t0, _t1) in enumerate(CHAPTERS):
                seek(page, t0 + 0.25)
                st = state(page)
                cap = page.locator("#kmhr-cap-title").inner_text().strip()
                kicker = page.locator("#kmhr-cap-kicker").inner_text().strip()
                dots_on = page.locator(".kmhr-dot-on").count()
                print(f"  Kapitel {i + 1}: idx={st['idx']} title={cap!r} kicker={kicker!r}")
                if st["idx"] != i:
                    fail(f"Kapitel {i + 1}: idx={st['idx']} statt {i}")
                if cap != title:
                    fail(f"Kapitel {i + 1}: Titel {cap!r} statt {title!r}")
                if dots_on != 1:
                    fail(f"Kapitel {i + 1}: {dots_on} aktive Dots statt 1")
                expected_cam = st["stationZ"][i] + 13.0
                if abs(st["camZ"] - expected_cam) > 1.0:
                    fail(f"Kapitel {i + 1}: camZ={st['camZ']} statt ~{expected_cam}")
                count = page.locator("#kmhr-count-n").inner_text().strip()
                if not count.isdigit() or not (0 <= int(count) <= 30):
                    fail(f"Kapitel {i + 1}: Countdown ungueltig: {count!r}")

            # 3) Fortschritt + Screenshot Kapitel 3
            seek(page, 12.4)
            width = page.evaluate(
                "() => parseFloat(document.getElementById('kmhr-progress-fill').style.width)")
            if not (35.0 <= width <= 45.0):
                fail(f"Fortschrittsbalken bei 12.4 s: {width}% (erwartet ~41%)")
            # Screenshot bei eingefrorener Zeit (sonst läuft die Szene während
            # des langsamen Canvas-Screenshots weiter).
            page.locator("#kmhr-pause").click()
            page.locator("#kmhr-anim-host").screenshot(path=str(SHOT_CHAPTER))
            page.locator("#kmhr-pause").click()

            # 4) Ergebnis-Kapitel + Screenshot
            seek(page, 27.0)
            if not page.locator("#kmhr-end.kmhr-end-show").count():
                fail("Login-CTA im Ergebnis-Kapitel nicht sichtbar")
            page.locator("#kmhr-pause").click()
            page.locator("#kmhr-anim-host").screenshot(path=str(SHOT_RESULT))
            page.locator("#kmhr-pause").click()

            # 5) Dot-Klick (Kapitel 5) setzt die Zeit
            page.locator(".kmhr-dot").nth(4).click()
            page.wait_for_timeout(500)
            if state(page)["idx"] != 4:
                fail(f"Dot-Klick Kapitel 5: idx={state(page)['idx']} statt 4")

            # 6) Pause / Weiter
            seek(page, 13.0)
            page.locator("#kmhr-pause").click()
            p1 = float(state(page)["t"])
            page.wait_for_timeout(700)
            p2 = float(state(page)["t"])
            if abs(p2 - p1) > 0.25:
                fail(f"Pause stoppt nicht: {p1} -> {p2}")
            page.locator("#kmhr-pause").click()
            page.wait_for_timeout(700)
            p3 = float(state(page)["t"])
            if p3 <= p2 + 0.2:
                fail(f"Weiter laeuft nicht: {p2} -> {p3}")

            # 7) Regression: Login bleibt erreichbar
            page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            if "login" not in page.url:
                fail(f"Login nicht erreichbar: {page.url}")
            if page.locator(".q-tab").count() < 3:
                fail("Login-Tabs (Kandidat/Arbeitgeber/Admin) fehlen")
        finally:
            browser.close()

        # 8) Reduced Motion: statisches Bild, kein Zeitfortschritt
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  reduced_motion="reduce")
        page = ctx.new_page()
        page.set_default_timeout(60000)
        try:
            wait_ready(page)
            st = state(page)
            print("  reduced:", st)
            if not st.get("reduce"):
                fail("prefers-reduced-motion nicht erkannt")
            t1 = float(st["t"])
            page.wait_for_timeout(900)
            t2 = float(state(page)["t"])
            if abs(t2 - t1) > 0.05:
                fail(f"Reduced Motion laeuft weiter: {t1} -> {t2}")
            if page.locator("#kmhr-count-n").inner_text().strip() != "30":
                fail("Reduced Motion: Countdown nicht auf 30 fixiert")
            if not page.locator("#kmhr-pause[disabled]").count():
                fail("Reduced Motion: Pause-Button nicht deaktiviert")
        finally:
            browser.close()

    for shot in (SHOT_CHAPTER, SHOT_RESULT):
        if not shot.is_file() or shot.stat().st_size < 10_000:
            fail(f"Screenshot fehlt/zu klein: {shot}")
        else:
            from PIL import Image
            img = Image.open(shot).convert("RGB")
            colors = img.getcolors(maxcolors=1_000_000) or []
            print(f"  Screenshot {shot.name}: {shot.stat().st_size} B, {len(colors)} Farben")
            if len(colors) < 200:
                fail(f"Screenshot wirkt leer ({len(colors)} Farben): {shot}")

    if _fails:
        print("FAIL:")
        for f in _fails:
            print(" -", f)
        return 1
    print(f"PASS: Agenten-Prinzip, 5 Kapitel, Countdown/Pause/Reduced-Motion; "
          f"Screenshots {SHOT_CHAPTER.relative_to(ROOT)}, {SHOT_RESULT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
