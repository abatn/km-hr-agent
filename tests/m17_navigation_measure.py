#!/usr/bin/env python3
"""M-17 (P1-5, 29.09.2026): Sprung-Mechanik der SPA-Navigation LIVE messen.

READ-ONLY: nur Klicks/Navigation, keine Formulare, keine Statuswechsel.
Gemessen wird (Plan ergebnisse/ui-mvp-plan-v2.md §6 P1-5, AK "gemessener,
protokollierter Sprung-Lauf, kein Alt-Claim"):

  A) Sidebar-Klick (employer)  -> _client.run_javascript(pushState)  components.py:1266
  B) Browser-Back nach SPA-Sprung -> popstate-Listener (laut Doku :30, im Code?)
  C) navigate_to()-Pfad (candidate, P1-2-Knopf) -> ui.run_javascript(pushState) components.py:73
  D) harte Navigation (goto) auf dieselbe URL -> Kontrast: Reload + Dauer
  E) Kontextverlust: Expander auf /employer/stellen geoeffnet -> Sprung -> zurueck

Je Sprung: URL, history.length, Reload-Marker (window.__m17), Inhalts-
Signatur, Dauer (ms), Dokument-Requests, Drawer-Status, Scrollposition.

Aufruf:  python3 tests/m17_navigation_measure.py [outdir]
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from e2e_harness import BASE, DB, check_server  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1
           else ROOT / "ergebnisse" / "reports" / "m17-20260929")
OUT.mkdir(parents=True, exist_ok=True)

EMP = ("hr@techvision.de", "sicher123")
CAND = ("e2e-beweis-phase1@example.com", "E2EMentoring2026!")  # Kandidat #16

SIG_JS = """() => {
  const el = document.querySelector('.page-transition');
  return (el ? el.innerText : document.body.innerText).replace(/\\s+/g,' ').trim().slice(0,140);
}"""
STATE_JS = """() => ({
  url: location.pathname,
  hist: history.length,
  marker: window.__m17 || null,
  scroll: Math.round(window.scrollY),
  drawer: !!document.querySelector('.q-drawer--on-top, .q-drawer--left.q-drawer--standard')
          && !document.querySelector('.q-drawer--standard').classList.contains('q-drawer--mini')
          ? 'open?' : '?',
  sig: null,
})"""


def state(page):
    s = page.evaluate(STATE_JS)
    s["sig"] = page.evaluate(SIG_JS)
    return s


def mark(page, tag):
    page.evaluate("t => { window.__m17 = t; }", tag)


def timed_jump(page, click, label, expect_sig_change=True, log_docs=True):
    """Klick ausfuehren, bis sich die Inhalts-Signatur aendert; Dauer messen."""
    before = state(page)
    docs_before = docs[0]
    t0 = time.monotonic()
    click()
    changed = True
    try:
        page.wait_for_function(
            "sig => { const el = document.querySelector('.page-transition');"
            " return (el ? el.innerText : document.body.innerText).replace(/\\s+/g,' ').trim().slice(0,140) !== sig; }",
            arg=before["sig"], timeout=20000)
    except Exception as exc:  # Timeout -> Inhalt blieb gleich
        changed = False
        page.wait_for_timeout(1500)
    ms = round((time.monotonic() - t0) * 1000)
    page.wait_for_timeout(1200)  # pushState/Nachlauf abwarten
    after = state(page)
    res = {
        "sprung": label,
        "dauer_ms": ms,
        "inhalt_gewechselt": changed,
        "url_vor": before["url"], "url_nach": after["url"],
        "url_geaendert": before["url"] != after["url"],
        "history_vor": before["hist"], "history_nach": after["hist"],
        "history_gewachsen": after["hist"] > before["hist"],
        "reload": after["marker"] != before["marker"],   # Marker weg = Full-Reload
        "marker_vor": before["marker"], "marker_nach": after["marker"],
        "dokument_requests": (docs[0] - docs_before) if log_docs else None,
        "scroll_vor": before["scroll"], "scroll_nach": after["scroll"],
        "sig_vor": before["sig"][:70], "sig_nach": after["sig"][:70],
    }
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return res, before, after


def login(page, email, pw, employer):
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    if employer:
        page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
        page.wait_for_timeout(700)
        pan = page.locator(".q-tab-panel:visible").filter(
            has=page.get_by_role("button", name="Arbeitgeber-Login")).first
        pan.get_by_label("E-Mail").fill(email)
        pan.get_by_label("Passwort", exact=True).fill(pw)
        pan.get_by_role("button", name="Arbeitgeber-Login").click()
        page.wait_for_url("**/employer**", timeout=30000)
    else:
        pan = page.locator(".q-tab-panel:visible").first
        pan.get_by_label("E-Mail").fill(email)
        pan.get_by_label("Passwort", exact=True).fill(pw)
        pan.get_by_role("button", name="Einloggen").first.click()
        page.wait_for_url("**/candidate**", timeout=30000)
    page.wait_for_timeout(2000)


report = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "base": BASE,
          "code_referenz": {
              "navigate_to": "webui/components.py:37-73 (pushState via ui.run_javascript, Zeile 73)",
              "sidebar_klick": "webui/components.py:1260-1268 (pushState via _client.run_javascript, Zeile 1266)",
              "popstate_doku": "webui/components.py:30 ('popstate-Listener behandelt Browser Back/Forward')",
          },
          "messungen": []}
docs = [0]

failures: list[str] = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ── A/B/E Employer ────────────────────────────────────────────────
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(60000)
    page.on("request", lambda r: docs.__setitem__(0, docs[0] + 1)
            if r.resource_type == "document" and r.is_navigation_request() else None)
    login(page, EMP[0], EMP[1], True)
    page.goto(f"{BASE}/employer/dashboard", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    mark(page, "M17-A")
    report["messungen"].append({"startzustand_employer": state(page)})

    # A) Sidebar-Klick dashboard -> kandidaten
    res, _, after_a = timed_jump(
        page, lambda: page.get_by_role("button", name="Kandidaten-Suche", exact=False).first.click(),
        "A) Sidebar-Klick employer: dashboard -> kandidaten")
    report["messungen"].append(res)
    if not res["inhalt_gewechselt"]:
        failures.append("A: Inhalt wechselte beim Sidebar-Klick nicht")
    if not res["url_geaendert"]:
        failures.append("A: URL wechselte beim Sidebar-Klick nicht (pushState wirkte nicht)")

    # A2) zweiter Sprung zurueck auf dashboard (Mehrfach-Kette)
    mark(page, "M17-A2")
    res2, _, _ = timed_jump(
        page, lambda: page.get_by_role("button", name="Dashboard", exact=False).first.click(),
        "A2) Sidebar-Klick employer: kandidaten -> dashboard")
    report["messungen"].append(res2)

    # B) Browser-Back nach genau EINEM Sidebar-Sprung (Referenz = Zustand VOR dem Back)
    page.goto(f"{BASE}/employer/dashboard", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    mark(page, "M17-B")
    timed_jump(page, lambda: page.get_by_role("button", name="Kandidaten-Suche", exact=False).first.click(),
               "B0) Ausgangssprung employer: dashboard -> kandidaten")
    vor = state(page)
    page.go_back()
    page.wait_for_timeout(3000)
    nach = state(page)
    resb = {
        "sprung": "B) Browser-Back nach Sidebar-Sprung (popstate-Listener?)",
        "url_und_inhalt_vor_back": vor["url"], "sig_vor": vor["sig"][:70],
        "url_erwartet_nach_back": vor["url"].rsplit("/", 1)[0] + "/dashboard",
        "url_ist_nach_back": nach["url"], "sig_ist_nach_back": nach["sig"][:70],
        "url_und_inhalt_konsistent": nach["url"].endswith(vor["url"].rsplit("/", 1)[-1]),
        "reload": nach["marker"] != "M17-B",
        "history_nach": nach["hist"],
    }
    print(json.dumps(resb, ensure_ascii=False, indent=1))
    report["messungen"].append(resb)
    if not resb["url_und_inhalt_konsistent"]:
        failures.append("B: Nach Browser-Back stimmen URL und Inhalt nicht ueberein")

    # E) Kontextverlust: Expander auf /employer/stellen oeffnen, echter Sprung, zurueck
    page.goto(f"{BASE}/employer/stellen", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    exp = page.locator(".q-expansion-item").filter(has_text="Aktive Bewerber").first
    exp_clicked = False
    if exp.count():
        exp.locator(".q-item").first.click(force=True)
        page.wait_for_timeout(2000)
        exp_clicked = True
    scroll_before = page.evaluate("() => { window.scrollTo(0, 400); return Math.round(window.scrollY); }")
    page.wait_for_timeout(400)
    mark(page, "M17-E")
    rese, _, _ = timed_jump(
        page, lambda: page.get_by_role("button", name="Kandidaten-Suche", exact=False).first.click(),
        "E1) Sprung von /employer/stellen -> /employer/kandidaten")
    page.get_by_role("button", name="Stellenangebote", exact=False).first.click()
    page.wait_for_timeout(2500)
    back_exp = page.locator(".q-expansion-item").filter(has_text="Aktive Bewerber").first
    content = back_exp.locator(".q-expansion-item__content")
    rese2 = {
        "sprung": "E2) Rueckkehr auf /employer/stellen",
        "expander_geoeffnet_vorher": exp_clicked,
        "expander_offen_nachher": bool(content.count()) and content.first.is_visible(),
        "scroll_vor": scroll_before,
        "scroll_nach": page.evaluate("() => Math.round(window.scrollY)"),
        "url_nach": state(page)["url"],
    }
    print(json.dumps(rese2, ensure_ascii=False, indent=1))
    report["messungen"].append(rese)
    report["messungen"].append(rese2)
    page.screenshot(path=str(OUT / "employer-stellen-zurueck.png"), full_page=True)
    ctx.close()

    # ── C/D Kandidat ──────────────────────────────────────────────────
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(60000)
    page.on("request", lambda r: docs.__setitem__(0, docs[0] + 1)
            if r.resource_type == "document" and r.is_navigation_request() else None)
    login(page, CAND[0], CAND[1], False)
    page.goto(f"{BASE}/candidate/prescreen", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    mark(page, "M17-C")
    report["messungen"].append({"startzustand_candidate": state(page)})
    btn = page.get_by_role("button", name="Zum Lebenslauf-Upload")
    if btn.count():
        resc, _, _ = timed_jump(page, lambda: btn.first.click(),
                                "C) navigate_to(): candidate prescreen -> profil (ui.run_javascript pushState)")
        report["messungen"].append(resc)
    else:
        failures.append("C: Knopf 'Zum Lebenslauf-Upload' nicht gefunden")
    page.screenshot(path=str(OUT / "candidate-upload-nach-sprung.png"), full_page=True)

    # D) Kontrast: harte Navigation auf dieselbe URL
    t0 = time.monotonic()
    page.goto(f"{BASE}/candidate/profil", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    hard_ms = round((time.monotonic() - t0) * 1000)
    resd = {"sprung": "D) harte Navigation (goto) auf /candidate/profil",
            "dauer_ms": hard_ms, "reload": state(page)["marker"] != "M17-C",
            "url_nach": state(page)["url"]}
    print(json.dumps(resd, ensure_ascii=False, indent=1))
    report["messungen"].append(resd)
    ctx.close()
    browser.close()

# DB-Baseline read-only pruefen
conn = sqlite3.connect(str(DB))
db_info = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
           for t in ("applications", "agent_tasks", "candidates", "feedback")}
conn.close()
report["db_zeilen"] = db_info

(OUT / "m17-navigation.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
print("DB-CHECK (read-only erwartet):", db_info)
print("FAIL:", failures if failures else "keine")
print(f"JSON: {OUT / 'm17-navigation.json'}")
