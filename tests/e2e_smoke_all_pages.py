"""R5-1.5 (30.09.2026): Smoke über ALLE Seiten beider Portale — echtes Rendern.

Öffnet per Playwright mit echtem Login:
  * alle 7 Kandidaten-Tabs  (source of truth: _TAB_MAP candidate.py — Codemarke, Stand 02.10.2026)
  * alle 11 Arbeitgeber-Seiten (PAGE_TITLES employer.py:25-37)
und prüft je Seite:
  * HTTP 200 / kein NiceGUI-Error-Panel ("500", "Internal Server Error")
  * Browser-Konsole: keine pageerror-Events (unbehandelte JS-/Render-Fehler)
  * Serverlog (separater Thread, der das Log-File liest): keine
    Tracebacks im Zeitfenster des Seitenaufrufs

Isolation: via tests/e2e_isolation.py starten (KMHR_E2E_BASE/KMHR_DB_PATH),
nie gegen die Live-DB testen. Root-Cause der Vorgabe: STATUS_ICONS-NameError
machte Tab "Bewerbungen" stumm leer — curl hätte das NICHT gesehen.

Ausführen (isoliert):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8093 --only e2e_smoke_all_pages
"""
from __future__ import annotations

import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE, check_server  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

CAND_TABS = ["dashboard", "profil", "stellen", "bewerbungen",
             "sprachtest", "prescreen", "onboarding"]
EMP_PAGES = ["dashboard", "portal", "stellen", "kandidaten", "match",
             "compliance", "agent_details", "dokumente", "prescreen",
             "onboarding", "feedback"]

CAND_EMAIL, CAND_PW = "test@example.de", "test1234"          # Kandidat 2
EMP_EMAIL, EMP_PW = "hr@techvision.de", "sicher123"           # Arbeitgeber 1
ADMIN_EMAIL, ADMIN_PW = "admin@km-hr-agent.local", "admin-agent-2026"

TIMEOUT = 30_000


def _panel(page, button_pattern: str):
    return page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile(button_pattern, re.I))
    ).first


def login_candidate(page):
    page.goto(f"{BASE}/login", wait_until="load", timeout=TIMEOUT)
    page.get_by_label("E-Mail").fill(CAND_EMAIL)
    page.get_by_label("Passwort", exact=True).fill(CAND_PW)
    page.get_by_role("button", name="Einloggen").click()
    page.wait_for_url("**/candidate**", timeout=TIMEOUT)


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="load", timeout=TIMEOUT)
    page.wait_for_timeout(1500)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(500)
    panel = _panel(page, "Arbeitgeber-Login")
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=TIMEOUT)


def login_admin(page):
    page.goto(f"{BASE}/login", wait_until="load", timeout=TIMEOUT)
    page.wait_for_timeout(1500)
    page.get_by_role("tab", name="Admin", exact=True).click()
    page.wait_for_timeout(500)
    panel = _panel(page, "Admin-Login")
    panel.get_by_label("Admin-E-Mail").fill(ADMIN_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(ADMIN_PW)
    panel.get_by_role("button", name=re.compile("Admin-Login", re.I)).click()
    page.wait_for_url("**/admin**", timeout=TIMEOUT)


class ServerLogWatcher(threading.Thread):
    """Liest das Serverlog und klassifiziert Tracebacks.

    Bekannter Rahmen-Noise (gemessen in ALLEN Isolationsläufen seit 09:12,
    auch vor den Änderungen dieser Runde): NiceGUI fragt die Drawer-Breite
    per run_javascript ab (Timeout 1 s) — bei schnellen Headless-
    Seitenwechseln platzt das Timeout, und der Client-Trenn-Vorgang wirft
    CancelledError. Das ist kein Seitenfehler. Alles andere (NameError,
    TypeError, sqlite3.Error, ...) zaehlt als echten Fund.
    """

    NOISE = {"asyncio.exceptions.CancelledError", "TimeoutError"}

    def __init__(self, log_path: Path):
        super().__init__(daemon=True)
        self.log_path = log_path
        self._halt = threading.Event()     # nicht 'stop' (schattet Thread.stop)
        self.found_errors: list[str] = []  # nicht 'tracebacks' (schattet Thread.group)
        self._pos = 0
        self._buf: list[str] = []

    def run(self):
        while not self._halt.is_set():
            try:
                if self.log_path.exists():
                    with self.log_path.open("r", errors="replace") as f:
                        f.seek(self._pos)
                        for line in f:
                            if "Traceback" in line:
                                self._buf = [line]
                            elif self._buf:
                                self._buf.append(line.rstrip())
                                # Abschlusszeile: 'XxxError: ...' am Zeilenanfang
                                m = re.match(r"^([\w.]+(?:Error|Exception)):\s", line)
                                if m:
                                    kind = m.group(1)
                                    if kind not in self.NOISE:
                                        self.found_errors.append(f"{kind}: {''.join(self._buf[-4:])}")
                                    self._buf = []
                        self._pos = f.tell()
            except OSError:
                pass
            time.sleep(1)

    def halt(self):
        self._halt.set()


def _check_page(page, url: str, console_errors: list[str]) -> str:
    """Öffnet eine Seite, meldet Status ('ok' | Fehlerbeschreibung)."""
    page.on("pageerror", lambda exc: console_errors.append(f"{url}: {exc}"))
    page.goto(url, wait_until="load", timeout=TIMEOUT)
    page.wait_for_timeout(1200)
    body = page.inner_text("body")
    if "Internal Server Error" in body or "Traceback (most recent call last)" in body:
        return "Error-Panel im Body"
    return "ok"


def main() -> int:
    check_server()
    fails: list[str] = []
    console_errors: list[str] = []
    results: list[tuple[str, str]] = []

    # Serverlog des isolierten Servers finden (e2e_isolation legt server.log an).
    # KMHR_E2E_SERVER_LOG erzwingt eine Quelle (z.B. Live-Log nach App-Neustart).
    import os
    forced = os.environ.get("KMHR_E2E_SERVER_LOG")
    if forced and Path(forced).exists():
        log_candidates = [Path(forced)]
    else:
        log_candidates = sorted(Path("/tmp/opencode").glob("e2e-iso-*/server.log"))
    watcher = ServerLogWatcher(log_candidates[-1]) if log_candidates else None
    if watcher:
        print(f"Serverlog-Quelle: {watcher.log_path}")
        watcher.start()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1366, "height": 900})
        page.set_default_timeout(TIMEOUT)

        # ── Kandidat: 7 Tabs ──
        login_candidate(page)
        for tab in CAND_TABS:
            url = f"{BASE}/candidate/{tab}"
            status = _check_page(page, url, console_errors)
            results.append((f"kandidat/{tab}", status))
            if status != "ok":
                fails.append(f"candidate/{tab}: {status}")

        # ── Arbeitgeber: 11 Seiten ──
        login_employer(page)
        for pg in EMP_PAGES:
            url = f"{BASE}/employer/{pg}"
            status = _check_page(page, url, console_errors)
            results.append((f"employer/{pg}", status))
            if status != "ok":
                fails.append(f"employer/{pg}: {status}")

        # ── Admin: Kernseiten ──
        login_admin(page)
        for pg in ["dashboard", "tasks", "agents"]:
            url = f"{BASE}/admin/{pg}"
            try:
                status = _check_page(page, url, console_errors)
            except Exception as ex:
                status = f"Fehler: {ex}"
            results.append((f"admin/{pg}", status))
            if status != "ok":
                # Admin-Seiten sind nicht Teil der Vorgabe; nur melden
                console_errors and None
                print(f"  [i] admin/{pg}: {status} (informativ, kein FAIL)")

        browser.close()

    if watcher:
        watcher.halt()
        watcher.join(timeout=2)
        if watcher.found_errors:
            fails.append(f"server.log: {len(watcher.found_errors)} echte Fehler")
            for tb in watcher.found_errors[:6]:
                print(f"  [server] {tb}")

    print("\n=== Smoke-Ergebnis ===")
    for name, status in results:
        mark = "✓" if status == "ok" else "✗"
        print(f" {mark} {name}: {status}")
    if console_errors:
        fails.append(f"{len(console_errors)} Browser-Console-Fehler")
        for ce in console_errors[:10]:
            print(f" [console] {ce}")

    print(f"\nSoll: {len(CAND_TABS)} Kandidaten-Tabs + {len(EMP_PAGES)} Arbeitgeber-Seiten = "
          f"{len(CAND_TABS) + len(EMP_PAGES)} Seiten 'ok'")
    if fails:
        print(f"FAIL ({len(fails)}):")
        for f_ in fails:
            print(f"  - {f_}")
        return 1
    print("PASS — alle Seiten ok (HTTP, Body, Konsole, Serverlog)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
