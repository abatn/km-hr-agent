#!/usr/bin/env python3
"""UI-Nachweis-Messung: Screenshots + Kontrast + Klickziele + DOM-Fakten.
READ-ONLY: nur Navigation und Auslesen, keine Datenänderung.

Aufruf:  python3 ui_measure.py <vorher|nachher> <zielordner>
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# R6-0 (30.09.2026): harter Live-Default entfernt — BASE aus dem Harness;
# ohne KMHR_E2E_BASE bricht der Lauf bewusst ab (e2e_harness.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE  # noqa: E402
EMP = ("hr@techvision.de", "sicher123")
CAND = ("recruiting.e2e.2809b@kmailtest.de", "Test1234!")

PHASE = sys.argv[1]
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

# Seiten, die für Recruiterin / Kandidatin belegt werden
# 01.10.2026 (ui-mvp-plan.md, Befund N-P1): Messumfang = 11 Employer (PAGE_MAP)
# + 7 Candidate (_TAB_MAP, Codemarke) -> 18 Screenshots-Pflicht je Lauf.
# (Stand 02.10.2026: Upload/Dokumente sind Boxen in "Mein Profil", keine Tabs mehr.)
EMP_PAGES = ["dashboard", "portal", "stellen", "kandidaten", "match", "compliance",
             "agent_details", "dokumente", "prescreen", "onboarding", "feedback"]
CAND_PAGES = ["dashboard", "profil", "stellen", "bewerbungen",
              "sprachtest", "prescreen", "onboarding"]


def lum(rgb):
    def f(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def parse_color(s):
    if not s or s.startswith("rgba") is None:
        return None
    nums = re.findall(r"[\d.]+", s)
    if len(nums) < 3:
        return None
    a = float(nums[3]) if len(nums) > 3 else 1.0
    if a == 0:
        return None
    if a < 1:  # halbtransparent über unbekanntem Grund -> nicht messbar
        return None
    return tuple(int(float(x)) for x in nums[:3])


def contrast(fg_s, bg_s):
    fg, bg = parse_color(fg_s), parse_color(bg_s)
    if not fg or not bg:
        return None
    a, b = lum(fg), lum(bg)
    hi, lo = max(a, b), min(a, b)
    return round((hi + 0.05) / (lo + 0.05), 2)


def solid_bg(el_bg, fallback="#ffffff"):
    """Hintergrund solider alsgefarbiger Vorfahre, sonst fallback (weiß = hell)."""
    if el_bg and parse_color(el_bg):
        return el_bg
    return fallback


MEASURE = """
() => {
  // Tailwind v4 liefert oklch(...). Ohne Umrechnung wird daraus Unsinn
  // (VORHER-Messung meldete darum faelschlich 1.01:1). Quelle der Umrechnung:
  // CSS Color 4, oklch -> oklab -> lineares sRGB -> sRGB.
  const oklchToRgb = (L, C, Hdeg, a) => {
    const h = Hdeg * Math.PI / 180, A = C * Math.cos(h), B = C * Math.sin(h);
    const l_ = L + 0.3963377774*A + 0.2158037573*B;
    const m_ = L - 0.1055613458*A - 0.0638541728*B;
    const s_ = L - 0.0894841775*A - 1.2914855480*B;
    const l = l_**3, m = m_**3, s = s_**3;
    const lr =  4.0767416621*l - 3.3077115913*m + 0.2309699292*s;
    const lg = -1.2684380046*l + 2.6097574011*m - 0.3413193965*s;
    const lb = -0.0041960863*l - 0.7034186147*m + 1.7076147010*s;
    const g = x => { x = x <= 0.0031308 ? 12.92*x : 1.055*Math.pow(Math.max(x,0), 1/2.4) - 0.055;
                     return Math.min(255, Math.max(0, Math.round(x*255))); };
    return {rgb: [g(lr), g(lg), g(lb)], a: a};
  };
  const parse = s => {
    if (!s) return null;
    if (s.startsWith('oklch')) {
      const m = s.match(/[\\d.]+/g); if (!m || m.length < 3) return null;
      return oklchToRgb(parseFloat(m[0]), parseFloat(m[1]), parseFloat(m[2]),
                        m.length > 3 ? parseFloat(m[3]) : 1);
    }
    const m = s.match(/[\\d.]+/g); if (!m || m.length < 3) return null;
    return {rgb: m.slice(0,3).map(Number), a: m.length > 3 ? parseFloat(m[3]) : 1};
  };
  // Effektiver Hintergrund: alle Ebenen von hinten nach vorn ueberechnen,
  // sonst werden halbtransparente Badges faelschlich gegen ihre eigene Farbe gemessen.
  const effBg = el => {
    const layers = [];
    let n = el;
    while (n && n !== document.documentElement) {
      const p = parse(getComputedStyle(n).backgroundColor);
      if (p && p.a > 0) { layers.push(p); if (p.a === 1) break; }
      n = n.parentElement;
    }
    let base = [255, 255, 255];
    for (let i = layers.length - 1; i >= 0; i--) {
      const l = layers[i];
      base = [l.rgb[0]*l.a + base[0]*(1-l.a), l.rgb[1]*l.a + base[1]*(1-l.a), l.rgb[2]*l.a + base[2]*(1-l.a)];
    }
    return base;
  };
  const lum = c => { const f = v => { v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); };
                      return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2]); };
  const ratio = (f,b) => { const a=lum(f), d=lum(b); const hi=Math.max(a,d), lo=Math.min(a,d);
                           return Math.round((hi+0.05)/(lo+0.05)*100)/100; };
  const rgbStr = c => 'rgb(' + c.map(Math.round).join(',') + ')';

  const out = {badges: [], buttons: [], rows: [], selects: [], text_flags: []};

  document.querySelectorAll('.q-badge, .q-chip').forEach(e => {
    const r = e.getBoundingClientRect(); if (!r.width) return;
    const s = getComputedStyle(e);
    const bg = effBg(e);
    const fgp = parse(s.color);
    out.badges.push({t: e.innerText.trim().slice(0,40), fg: s.color, bg: rgbStr(bg),
                     ratio: fgp ? ratio(fgp.rgb, bg) : null,
                     h: Math.round(r.height), cls: e.className.split(' ').filter(c=>c.startsWith('bg-')||c.startsWith('text-')).join(' ')});
  });

  document.querySelectorAll('.q-btn, button').forEach(e => {
    const r = e.getBoundingClientRect(); if (!r.width) return;
    const s = getComputedStyle(e);
    const bg = effBg(e);
    const fgp = parse(s.color);
    out.buttons.push({t: e.innerText.trim().replace(/\\s+/g,' ').slice(0,28), bg: rgbStr(bg),
                      fg: s.color, ratio: fgp ? ratio(fgp.rgb, bg) : null,
                      w: Math.round(r.width), h: Math.round(r.height),
                      ok44: r.height >= 44, flat: e.className.includes('flat')});
  });

  document.querySelectorAll('tbody tr').forEach((e, i) => {
    const s = getComputedStyle(e);
    const btn = e.querySelector('.q-btn, button, a');
    let btnH = 0;
    if (btn) btnH = Math.round(btn.getBoundingClientRect().height);
    out.rows.push({i, cursor: s.cursor, clickable: s.cursor === 'pointer' || !!btn,
                   btn_h: btnH, links: e.querySelectorAll('a,button,input').length,
                   t: e.innerText.trim().replace(/\\s+/g,' ').slice(0,50)});
  });

  document.querySelectorAll('.q-field label, .q-field__label, label').forEach(e => {
    const t = e.innerText.trim();
    if (!t) return;
    if (/\\.md|\\*\\*|profil-|kandidat-\\d|#\\d+/.test(t))
      out.selects.push(t.slice(0,70));
  });

  const body = document.body.innerText;
  if (/lebenslauf_hochgeladen|zugeordnet|registriert\\b/.test(body) && !/_\\|/.test('')) {
    out.text_flags.push('status-slug-sichtbar');
  }
  if (/Meine Dokumente/.test(body)) out.text_flags.push('dokumentliste-sichtbar');
  if (/Noch keine Dokumente/.test(body)) out.text_flags.push('dokument-empty-state');
  if (/\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}/.test(body)) out.text_flags.push('termin-mit-zeit-sichtbar');
  if (/📅 Einladung/.test(body)) out.text_flags.push('einladungskarte');
  if (/vdo\\.ninja/.test(body)) out.text_flags.push('meeting-link');
  if (/Kandidat #\\d+/.test(body)) out.text_flags.push('kandidat-id-statt-name');
  out.invitation_count = (body.match(/📅 Einladung/g) || []).length;
  return out;
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
    else:
        pan = page.locator(".q-tab-panel").filter(has=page.get_by_role("button", name="Einloggen")).first
        pan.get_by_label("E-Mail").first.fill(email)
        pan.get_by_label("Passwort", exact=True).first.fill(pw)
        pan.get_by_role("button", name="Einloggen").click()
    page.wait_for_timeout(2500)
    if employer:
        page.wait_for_url("**/employer**", timeout=25000)
    else:
        page.wait_for_url("**/candidate**", timeout=25000)
    page.wait_for_timeout(1500)


report = {"phase": PHASE, "ts": None, "employer": {}, "candidate": {}}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ── Rolle 1: Recruiterin (eigener Context = eigene Session) ───────
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(90000)
    login(page, EMP[0], EMP[1], True)
    for slug in EMP_PAGES:
        # Frische Seite je URL: NiceGUI haelt Websocket + Timer-Refresh offen,
        # sonst blockiert die Verbindung den naechsten goto (Timeout 30 s).
        page = ctx.new_page()
        page.set_default_timeout(90000)
        page.goto(f"{BASE}/employer/{slug}", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2500)
        if slug == "stellen":
            exp = page.locator(".q-expansion-item").filter(has_text="Aktive Bewerber").first
            if exp.count():
                exp.click()
                page.wait_for_timeout(1800)
        page.screenshot(path=str(OUT / f"recruiter-{slug}.png"), full_page=True)
        report["employer"][slug] = page.evaluate(MEASURE)
        page.close()
    ctx.close()

    # ── Rolle 2: Kandidatin (frischer Context) ─────────────────────────
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    login(ctx.new_page(), CAND[0], CAND[1], False)
    for slug in CAND_PAGES:
        page = ctx.new_page()
        page.set_default_timeout(90000)
        page.goto(f"{BASE}/candidate/{slug}", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT / f"kandidat-{slug}.png"), full_page=True)
        report["candidate"][slug] = page.evaluate(MEASURE)
        page.close()
    ctx.close()

    browser.close()

# Auswertung
summary = {"phase": PHASE, "kontrast_verstoesse": [], "klickziel_verstoesse": [],
           "zeilen_nicht_klickbar": [], "dateinamen_im_label": [], "flags": {}}
for rolle, pages in report.items():
    if rolle in ("phase", "ts"):
        continue
    for slug, d in pages.items():
        key = f"{rolle}/{slug}"
        seen = set()
        for b in d["badges"]:
            k = (b["t"], b["fg"], b["bg"])
            if k in seen:
                continue
            seen.add(k)
            if b["ratio"] is not None and b["ratio"] < 4.5:
                summary["kontrast_verstoesse"].append(
                    {"wo": key, "badge": b["t"], "fg": b["fg"], "bg": b["bg"], "ratio": b["ratio"]})
        for b in d["buttons"]:
            if b["t"] and b["ratio"] is not None and b["ratio"] < 4.5:
                summary["kontrast_verstoesse"].append(
                    {"wo": key, "element": "button", "text": b["t"], "fg": b["fg"], "bg": b["bg"], "ratio": b["ratio"]})
            elif b["t"] and not b["ok44"]:
                summary["klickziel_verstoesse"].append({"wo": key, "button": b["t"], "h": b["h"]})
        for r in d["rows"]:
            if not r["clickable"]:
                summary["zeilen_nicht_klickbar"].append({"wo": key, "zeile": r["t"][:40]})
            elif r.get("btn_h") and r["btn_h"] < 44:
                summary["zeilen_nicht_klickbar"].append(
                    {"wo": key, "zeile_klickziel_zu_klein": r["btn_h"], "zeile": r["t"][:40]})
        for s in d["selects"]:
            summary["dateinamen_im_label"].append({"wo": key, "label": s})
        summary["flags"][key] = d["text_flags"] + [f"einladung_karten={d['invitation_count']}"]

report["summary"] = summary
(OUT / f"messung-{PHASE}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))

print(f"=== {PHASE.upper()} ===")
print("Kontrastverstöße (<4.5:1):", len(summary["kontrast_verstoesse"]))
for v in summary["kontrast_verstoesse"][:12]:
    print("   ", v)
print("Klickziele <44px:", len(summary["klickziel_verstoesse"]))
for v in summary["klickziel_verstoesse"][:8]:
    print("   ", v)
print("Zeilen ohne Pointer-Cursor:", len(summary["zeilen_nicht_klickbar"]))
for v in summary["zeilen_nicht_klickbar"][:6]:
    print("   ", v)
print("Labels mit Dateinamen/IDs:", len(summary["dateinamen_im_label"]))
for v in summary["dateinamen_im_label"][:6]:
    print("   ", v)
print("Flags:")
for k, v in summary["flags"].items():
    if v:
        print("   ", k, "→", v)
