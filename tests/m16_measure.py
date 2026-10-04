"""M-16 Timing-Messung (READ-ONLY, kein Fix): 📄 Match-Ergebnis (/employer/match).

Misst Wandzeit je Ladung (goto bis stabile Karten-Anzahl) fuer:
  T1 = erste Ladung (kalter Connector-Cache, Server-Neustart davor),
  T2/T3 = Folgeladungen (warmer Cache).
Dazu DOM-Zaehlung der Einladen-Buttons (= gerenderte Karten mit Aktion).

Begleitend laeuft scripts/m16-spawn-watch.sh und zaehlt eindeutige PIDs der
Connector-Subprozesse (Log: ergebnisse/m16-spawn-watch.log).

Ausfuehren: .venv-streamlit/bin/python3 tests/m16_measure.py
Messregel: projektinternes Skript gegen :8080; keine Hand-Messung mit
verbotenen Werkzeugen (Projektregel: ui_measure.py-Prezedenz).
"""
import sys
import time

from playwright.sync_api import sync_playwright

from e2e_harness import BASE, check_server

from e2e_feedback_filter import login_employer  # noqa: E402 (Login-Pfad-Reuse)


def load_match(page, label: str) -> None:
    t0 = time.perf_counter()
    page.goto(f"{BASE}/employer/match", wait_until="load", timeout=120000)
    page.get_by_role("button", name="Einladen").first.wait_for(timeout=180000)
    # Endmarker: Anzahl der Karten-Buttons stabil ueber 3 Messpunkte
    last, stable = None, 0
    while stable < 2 and (time.perf_counter() - t0) < 180:
        n = page.get_by_role("button", name="Einladen").count()
        stable = stable + 1 if n == last else 0
        last = n
        page.wait_for_timeout(500)
    dt = time.perf_counter() - t0
    print(f"{label}={dt:.2f}s EINLADEN_BUTTONS={last}")


def main() -> int:
    check_server()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context()
            page = ctx.new_page()
            login_employer(page)
            page.wait_for_timeout(1500)
            load_match(page, "T1_ERSTE_LADUNG")
            load_match(page, "T2_FOLGELADUNG")  # page.goto = harter Neuaufbau
            load_match(page, "T3_FOLGELADUNG")
            ctx.close()
        finally:
            browser.close()
    print("MESSUNG_ENDE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
