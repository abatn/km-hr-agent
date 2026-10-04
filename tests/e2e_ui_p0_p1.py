#!/usr/bin/env python3
"""E2E-Kette fuer die UI-Fixes vom 28.09.2026 — beide Rollen, read-only.

Deckt ab:
  P0-1  Dokumente nach Upload sichtbar (Kandidat) + Datenzugriff (HR-Pfad)
  P0-2  Termin in der Einladungskarte sichtbar
  P0-3  Auswahlfelder zeigen Klarnamen statt Dateinamen (HR)
  P0-4  Status-Komponente: Kontrast >= 4.5:1 und Klartext (beide Rollen)
  UI    Klickziele >= 44 px (beide Rollen)
  P1-1  Kandidaten-Suche: Zeile klickbar, URL wechselt auf /employer/match
  P1-3  Dashboard-Kachel fuehrt zum Ziel
  P1-4  Bewerberkarte zeigt Klarnamen

Aufruf:  python3 tests/e2e_ui_p0_p1.py
READ-ONLY: keine Statusaenderung, kein Speichern, kein Loeschen.
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# R6-0 (30.09.2026): harter Live-Default entfernt — BASE kommt aus dem
# Harness und bricht ohne KMHR_E2E_BASE bewusst ab (siehe e2e_harness.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE  # noqa: E402
EMP = ("hr@techvision.de", "sicher123")
CAND = ("recruiting.e2e.2809b@kmailtest.de", "Test1234!")

results = []


def check(tid, rolle, desc, ok, detail=""):
    results.append((tid, rolle, desc, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {tid} {rolle:9s} {desc}" + (f" — {detail}" if detail else ""))


# Kontrast + Klickziele (identische Logik wie tests/ui_measure.py)
AUDIT = """
() => {
  const oklchToRgb = (L, C, Hdeg, a) => {
    const h = Hdeg * Math.PI / 180, A = C * Math.cos(h), B = C * Math.sin(h);
    const l_ = L + 0.3963377774*A + 0.2158037573*B, m_ = L - 0.1055613458*A - 0.0638541728*B,
          s_ = L - 0.0894841775*A - 1.2914855480*B;
    const l = l_**3, m = m_**3, s = s_**3;
    const lr = 4.0767416621*l - 3.3077115913*m + 0.2309699292*s;
    const lg = -1.2684380046*l + 2.6097574011*m - 0.3413193965*s;
    const lb = -0.0041960863*l - 0.7034186147*m + 1.7076147010*s;
    const g = x => { x = x <= 0.0031308 ? 12.92*x : 1.055*Math.pow(Math.max(x,0), 1/2.4) - 0.055;
                     return Math.min(255, Math.max(0, Math.round(x*255))); };
    return {rgb: [g(lr), g(lg), g(lb)], a: a};
  };
  const parse = s => {
    if (!s) return null;
    if (s.startsWith('oklch')) { const m = s.match(/[\\d.]+/g);
      if (!m || m.length < 3) return null;
      return oklchToRgb(+m[0], +m[1], +m[2], m.length > 3 ? +m[3] : 1); }
    const m = s.match(/[\\d.]+/g); if (!m || m.length < 3) return null;
    return {rgb: m.slice(0,3).map(Number), a: m.length > 3 ? +m[3] : 1};
  };
  const effBg = el => { const layers = []; let n = el;
    while (n && n !== document.documentElement) { const p = parse(getComputedStyle(n).backgroundColor);
      if (p && p.a > 0) { layers.push(p); if (p.a === 1) break; } n = n.parentElement; }
    let base = [255,255,255];
    for (let i = layers.length-1; i >= 0; i--) { const l = layers[i];
      base = [l.rgb[0]*l.a + base[0]*(1-l.a), l.rgb[1]*l.a + base[1]*(1-l.a), l.rgb[2]*l.a + base[2]*(1-l.a)]; }
    return base; };
  const lum = c => { const f = v => { v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); };
                      return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2]); };
  const ratio = (f,b) => { const a=lum(f), d=lum(b); const hi=Math.max(a,d), lo=Math.min(a,d);
                           return Math.round((hi+0.05)/(lo+0.05)*100)/100; };
  const bad = [], small = [];
  document.querySelectorAll('.q-badge, .q-chip, .q-btn').forEach(e => {
    const r = e.getBoundingClientRect(); if (!r.width) return;
    const s = getComputedStyle(e);
    const fp = parse(s.color);
    if (fp) { const v = ratio(fp.rgb, effBg(e));
      if (v < 4.5) bad.push({t: e.innerText.trim().replace(/\\s+/g,' ').slice(0,30), r: v}); }
    if (e.classList.contains('q-btn') && r.height < 44)
      small.push({t: e.innerText.trim().replace(/\\s+/g,' ').slice(0,24), h: Math.round(r.height)});
  });
  return {bad, small};
}
"""


def login(page, email, pw, employer):
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1200)
    if employer:
        page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
        page.wait_for_timeout(600)
        pan = page.locator(".q-tab-panel:visible").filter(
            has=page.get_by_role("button", name="Arbeitgeber-Login")).first
        pan.get_by_label("E-Mail").fill(email)
        pan.get_by_label("Passwort", exact=True).fill(pw)
        pan.get_by_role("button", name="Arbeitgeber-Login").click()
        page.wait_for_url("**/employer**", timeout=25000)
    else:
        pan = page.locator(".q-tab-panel").filter(has=page.get_by_role("button", name="Einloggen")).first
        pan.get_by_label("E-Mail").first.fill(email)
        pan.get_by_label("Passwort", exact=True).first.fill(pw)
        pan.get_by_role("button", name="Einloggen").click()
        page.wait_for_url("**/candidate**", timeout=25000)
    page.wait_for_timeout(1500)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ─────────── Rolle Kandidatin ───────────
    print("\n== Rolle: Kandidatin ==")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    login(ctx.new_page(), CAND[0], CAND[1], False)

    page = ctx.new_page()
    page.goto(f"{BASE}/candidate/profil", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2500)
    try:
        page.get_by_text("Dokumente", exact=True).first.click(timeout=8000)
        page.wait_for_timeout(800)
    except Exception:
        pass
    body = page.inner_text("body")
    check("P0-1", "Kandidat", "Dokumentliste sichtbar nach bestaetigtem Upload",
          "Meine Dokumente" in body, f"'Meine Dokumente' vorhanden={'Meine Dokumente' in body}")
    check("P0-1", "Kandidat", "Dateiname des Dokuments sichtbar",
          "kandidat-22-Zeugnis" in body)
    check("P0-1", "Kandidat", "kein Empty-State obwohl Datei existiert",
          "Noch keine Dokumente hochgeladen" not in body)
    check("P0-4", "Kandidat", "kein DB-Slug 'lebenslauf_hochgeladen' im Text",
          "lebenslauf_hochgeladen" not in body)
    aud = page.evaluate(AUDIT)
    check("UI", "Kandidat", "Kontrast >= 4.5:1 auf /candidate/profil",
          not aud["bad"], str(aud["bad"][:3]))
    check("UI", "Kandidat", "Klickziele >= 44 px auf /candidate/profil",
          not aud["small"], str(aud["small"][:3]))
    page.close()

    page = ctx.new_page()
    page.goto(f"{BASE}/candidate/bewerbungen", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    m = re.search(r"Termin:\s*(\d{4}-\d{2}-\d{2}[^E\n]*)", body)
    check("P0-2", "Kandidat", "Termin in der Einladungskarte sichtbar",
          bool(m), (m.group(1).strip()[:40] if m else "kein Termin gefunden"))
    check("P0-2", "Kandidat", "Uhrzeit sichtbar", bool(re.search(r"\d{1,2}:\d{2}", body)))
    check("P0-2", "Kandidat", "genau eine Einladungskarte",
          body.count("📅 Einladung") == 1, f"Anzahl={body.count('📅 Einladung')}")
    check("P0-2", "Kandidat", "Meeting-Link als Eingabefeld (Klartext) statt Anker",
          page.evaluate("""() => [...document.querySelectorAll('input')]
              .filter(i => (i.value || '').includes('vdo.ninja')).length""") == 1
          and page.evaluate("""() => [...document.querySelectorAll('a')]
              .filter(a => (a.href || '').includes('vdo.ninja')).length""") == 0)
    check("P0-2", "Kandidat", "ICS-Kalender-Knopf vorhanden (Render nicht abgebrochen)",
          page.get_by_text("Termin in Kalender speichern").count() >= 1)
    aud = page.evaluate(AUDIT)
    check("UI", "Kandidat", "Kontrast >= 4.5:1 auf /candidate/bewerbungen",
          not aud["bad"], str(aud["bad"][:3]))
    check("UI", "Kandidat", "Klickziele >= 44 px auf /candidate/bewerbungen",
          not aud["small"], str(aud["small"][:3]))
    page.close()

    for slug in ("profil", "stellen"):
        page = ctx.new_page()
        page.goto(f"{BASE}/candidate/{slug}", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2500)
        aud = page.evaluate(AUDIT)
        check("UI", "Kandidat", f"Kontrast + Klickziele auf /candidate/{slug}",
              not aud["bad"] and not aud["small"], f"bad={aud['bad'][:2]} small={aud['small'][:2]}")
        b = page.inner_text("body")
        check("P0-4", "Kandidat", f"kein DB-Slug auf /candidate/{slug}",
              "lebenslauf_hochgeladen" not in b)
        page.close()
    ctx.close()

    # ─────────── Rolle Recruiterin ───────────
    print("\n== Rolle: Recruiterin (Arbeitgeber) ==")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    login(ctx.new_page(), EMP[0], EMP[1], True)

    page = ctx.new_page()
    page.goto(f"{BASE}/employer/dokumente", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    check("P0-1", "Recruiter", "Gate-Hinweis mit Klartext-Status (kein Slug)",
          "lebenslauf_hochgeladen" not in body and ("Lebenslauf hochgeladen" in body or "Keine" in body),
          f"Klartext-Status vorhanden={'Lebenslauf hochgeladen' in body}")
    page.close()

    for slug in ("prescreen", "onboarding", "feedback"):
        page = ctx.new_page()
        page.goto(f"{BASE}/employer/{slug}", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2500)
        labels = page.eval_on_selector_all(
            "label", "els => els.map(e => e.innerText.trim()).filter(t => /Kandidat:/.test(t))")
        bad = [t for t in labels if ".md" in t or "**" in t or "profil-" in t]
        check("P0-3", "Recruiter", f"Auswahlfeld zeigt Klarnamen (/employer/{slug})",
              bool(labels) and not bad, f"geprüfte Labels={len(labels)}, Dateinamen={bad[:1]}")
        page.close()

    page = ctx.new_page()
    page.goto(f"{BASE}/employer/kandidaten", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(3000)
    body = page.inner_text("body")
    check("P0-4", "Recruiter", "Status-Spalte zeigt Klartext",
          "lebenslauf_hochgeladen" not in body and "Lebenslauf hochgeladen" in body)
    aud = page.evaluate(AUDIT)
    check("UI", "Recruiter", "Kontrast >= 4.5:1 auf /employer/kandidaten",
          not aud["bad"], str(aud["bad"][:3]))
    # P0-5: Wartezeit des Match-Aufrufs messbar machen
    import time as _time
    _t0 = _time.time()
    page.goto(f"{BASE}/employer/match", wait_until="domcontentloaded", timeout=180000)
    _dt = _time.time() - _t0
    check("P0-5", "Recruiter", "Match-Seite laedt in <= 10 s", _dt <= 10, f"{_dt:.1f}s")
    page.close()
    page = ctx.new_page()
    page.goto(f"{BASE}/employer/kandidaten", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(3000)

    # P1-1: Zeile klickbar (Namenszelle) → Match-Seite + URL
    btn = page.locator("tbody .q-btn").first
    check("P1-1", "Recruiter", "Namenszelle ist ein Klickziel (>=44px)", btn.count() > 0)
    if btn.count():
        h = btn.first.evaluate("e => Math.round(e.getBoundingClientRect().height)")
        check("P1-1", "Recruiter", "Namens-Knopf Hoehe >= 44 px", h >= 44, f"h={h}px")
        # no_wait_after: der Klick loest eine echte Route-Navigation aus
        # (ui.navigate.to). Die Match-Seite braucht aktuell ~68 s
        # (gemessen: tests/measure_timing.sh, P0-5) → 180 s Fenster.
        btn.first.click(no_wait_after=True)
        try:
            page.wait_for_url("**/employer/match", timeout=180000)
        except Exception as ex:
            check("P1-1", "Recruiter", "URL wechselt auf /employer/match", False, str(ex)[:80])
        page.wait_for_timeout(3000)
        body2 = page.inner_text("body")
        check("P1-1", "Recruiter", "Klick fuehrt zum Match-Ergebnis",
              "Match-Ergebnis" in body2 and "Kandidaten-Suche" not in body2)
        check("P1-1", "Recruiter", "URL wechselt auf /employer/match",
              page.url.endswith("/employer/match"), f"URL={page.url}")
    page.close()

    page = ctx.new_page()
    page.goto(f"{BASE}/employer/match", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(3500)
    aud = page.evaluate(AUDIT)
    check("UI", "Recruiter", "Kontrast + Klickziele auf /employer/match",
          not aud["bad"] and not aud["small"], f"bad={aud['bad'][:2]} small={aud['small'][:2]}")
    body = page.inner_text("body")
    check("P1-2", "Recruiter", "Score nicht doppelt angezeigt",
          not re.search(r"(\d+)/100\s*\n\s*\1/100", body))
    colors = page.evaluate("""() => {
        const o = {};
        document.querySelectorAll('.q-btn').forEach(e => {
            const t = e.innerText.trim();
            if (/EINLADEN|ABLEHNEN|EINSTELLEN/i.test(t)) {
                o[t.split('\\n').pop()] = getComputedStyle(e).backgroundColor;
            }
        });
        return o; }""")
    distinct = len(set(colors.values()))
    check("P1-2", "Recruiter", "Button-Hierarchie: Einladen/Ablehnen/Einstellen unterscheiden sich",
          distinct >= 2, f"Farben={colors}")
    page.close()

    page = ctx.new_page()
    page.goto(f"{BASE}/employer/stellen", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2500)
    exp = page.locator(".q-expansion-item").filter(has_text="Aktive Bewerber").first
    if exp.count():
        exp.click()
        page.wait_for_timeout(2000)
    body = page.inner_text("body")
    check("P1-4", "Recruiter", "Bewerberkarte zeigt Klarnamen statt 'Kandidat #22'",
          "Kandidat #" not in body, f"'Kandidat #' noch vorhanden={'Kandidat #' in body}")
    check("P1-4", "Recruiter", "Klarname 'Kandidatin Test B' in der Bewerberliste",
          "Kandidatin Test B" in body)
    page.close()

    page = ctx.new_page()
    page.goto(f"{BASE}/employer/dashboard", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2500)
    tile = page.locator(".q-card").filter(has_text="Bewerbungen").first
    check("P1-3", "Recruiter", "Dashboard-Kachel ist Klickziel", tile.count() > 0)
    if tile.count():
        cursor = tile.evaluate("e => getComputedStyle(e).cursor")
        check("P1-3", "Recruiter", "Dashboard-Kachel zeigt Pointer-Cursor",
              cursor == "pointer", f"cursor={cursor}")
        tile.click(no_wait_after=True)
        try:
            page.wait_for_url("**/employer/stellen", timeout=60000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        check("P1-3", "Recruiter", "Klick auf Kachel navigiert zu den Bewerbungen",
              "/employer/stellen" in page.url, f"URL={page.url}")
    page.close()
    ctx.close()
    browser.close()

print("\n== Zusammenfassung ==")
passed = sum(1 for r in results if r[3])
print(f"  {passed}/{len(results)} Pruefungen bestanden")
for tid, rolle, desc, ok, detail in results:
    if not ok:
        print(f"  OFFEN: {tid} {rolle} — {desc} ({detail})")
sys.exit(0 if passed == len(results) else 1)
