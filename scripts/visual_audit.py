"""Visueller Glassmorphism-Audit (KM-HR-Agent NiceGUI).
Misst im echten Chromium:
  1. WCAG-Kontrast (Text vs. effektiv komponierter Hintergrund über rgba-Glass)
  2. backdrop-filter-Anwendung (.glass/.header-glass/...)
  3. Screenshots Light+Dark pro Seite → ergebnisse/screenshots/
Ausführen: .venv-streamlit/bin/python3 scripts/visual_audit.py
"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
OUT = Path("/home/batnini/mimo-agents/km-hr-agent/ergebnisse/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

TEXT_SELS = [
    ".glass", ".glass-strong", ".glass-subtle", ".header-glass", ".sidebar-glass",
    ".btn-glass", ".btn-glass-ghost", ".btn-glass-green", ".btn-glass-red", ".btn-glass-purple",
    ".badge-glass", ".badge-glass-green", ".badge-glass-amber", ".badge-glass-red",
    ".input-glass",
    '[class*="text-gray-"]', '[class*="text-slate-"]', '[class*="text-blue-"]',
    '[class*="text-red-"]', '[class*="text-green-"]', '[class*="text-amber-"]',
    '[class*="text-white"]', '[class*="text-purple-"]',
]

JS_COLLECT = """
(sels) => {
  function parse(s) {
    if (!s || s === 'transparent') return null;
    const m = s.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x));
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  }
  // ── F-1 (Fix, Phase-E Runde 3): Gradient-Support für effBg ──────────────
  // Design-Entscheidung: Ein CSS-Gradient (background-image) kann in JS nicht
  // pixelgenau am Text-Position gesampelt werden (kein Rasterzugriff auf das
  // gerenderte Bild). Repräsentative Farbe = alpha-gewichteter Mittelwert aller
  // Farbstops des Gradients (hex / rgb(a) / hsl(a) / transparent).
  // Fallback-Logik (Design-Entscheidung): Gradient vorhanden, aber keiner der
  // Stops parsebar (z.B. var(...)) → 'UNMEASURABLE' → effBg liefert null →
  // Python überspringt den Kontrast-Check, statt ein weiß-auf-Weiß-Artefakt
  // gegen die Canvas-Default-Farbe (255,255,255) zu melden.
  // ── F-4 (Fix, Phase-E Runde 3, Ergänzung 25.09.2026): oklch → sRGB ──────
  // Beweis (25.09.2026, Live-Dump): Tailwind-v4 liefert computed colors als
  // oklch(...) – z.B. Login-Überschrift "Willkommen zurueck" =
  // oklch(0.21 0.034 264.665). parse() (nur rgb()) scheitert → fg = null →
  // alte Filter-Logik wertete es als "transparent" → Element wurde NIE geprüft
  // (= eigentliche Ursache der "0 geprüft"-Fälle, F-4).
  // Rechnung: oklch → OKLab (Ottosson-Matrix) → lineares sRGB → Gamma → 8-Bit.
  // Validierung 25.09.2026 (/tmp/validate_oklch.py): 7/7 Farben byteidentisch
  // mit Chromes eigener Canvas-Rasterisierung (Δ=0 pro Kanal) – Design-Entscheidung.
  function oklchToRgb(L, C, Hdeg) {
    const h = Hdeg * Math.PI / 180;
    const a = C * Math.cos(h), b = C * Math.sin(h);
    const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
    const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
    const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
    const l = l_ * l_ * l_, m = m_ * m_ * m_, s = s_ * s_ * s_;
    const r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
    const g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
    const bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;
    const enc = (x) => {
      x = Math.min(1, Math.max(0, x));
      return Math.round((x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055) * 255);
    };
    return {r: enc(r), g: enc(g), b: enc(bb)};
  }
  function parseColor(tok) {
    tok = (tok || '').trim();
    if (tok === 'transparent') return {r: 0, g: 0, b: 0, a: 0};
    if (tok[0] === '#') {
      let h = tok.slice(1);
      if (h.length === 3 || h.length === 4) h = h.split('').map(c => c + c).join('');
      if (h.length < 6) return null;
      const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
      if (isNaN(r) || isNaN(g) || isNaN(b)) return null;
      return {r, g, b, a: h.length >= 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1};
    }
    if (tok.startsWith('oklch(')) {
      const m = tok.match(/^oklch\\(\\s*([\\d.]+)\\s+([\\d.]+)\\s+([\\d.]+)(?:\\s*\\/\\s*([\\d.]+)(%))?\\s*\\)$/);
      if (!m) return null;
      const c = oklchToRgb(parseFloat(m[1]), parseFloat(m[2]), parseFloat(m[3]));
      c.a = m[4] === undefined ? 1 : (m[5] ? parseFloat(m[4]) / 100 : parseFloat(m[4]));
      return c;
    }
    const rgb = parse(tok);
    if (rgb) return rgb;
    const m = tok.match(/hsla?\\(([^)]+)\\)/);
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x));
    if (p.length < 3 || isNaN(p[0]) || isNaN(p[1]) || isNaN(p[2])) return null;
    const hh = ((p[0] % 360) + 360) % 360, s = p[1] / 100, l = p[2] / 100;
    const c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs((hh / 60) % 2 - 1)), mm = l - c / 2;
    let rr = 0, gg = 0, bb = 0;
    if (hh < 60) { rr = c; gg = x; } else if (hh < 120) { rr = x; gg = c; }
    else if (hh < 180) { gg = c; bb = x; } else if (hh < 240) { gg = x; bb = c; }
    else if (hh < 300) { rr = x; bb = c; } else { rr = c; bb = x; }
    return {r: Math.round((rr + mm) * 255), g: Math.round((gg + mm) * 255),
            b: Math.round((bb + mm) * 255), a: p.length > 3 && !isNaN(p[3]) ? p[3] : 1};
  }
  function gradLayer(img) {
    if (!img || img === 'none' || img.indexOf('gradient(') === -1) return 'NONE';
    // oklch-Stops (Tailwind-v4-Gradienten) + Wortgrenzen-Fix: im alten Quelltext
    // stand hier \b als EIN Backslash → Python dekodiert es zu 0x08 (Backspace) →
    // JS bekam 0x08 statt \b und „transparent"-Stops wurden nie tokenisiert.
    const re = /#[0-9a-fA-F]{8}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3,4}|oklch\\([^)]*\\)|rgba?\\([^)]*\\)|hsla?\\([^)]*\\)|\\btransparent\\b/g;
    const toks = [];
    let m;
    while ((m = re.exec(img)) !== null) { const c = parseColor(m[0]); if (c) toks.push(c); }
    if (!toks.length) return 'UNMEASURABLE';
    let r = 0, g = 0, b = 0, w = 0, a = 0;
    for (const t of toks) {
      a += t.a;                       // Alpha der Stops durchschnittlich
      if (t.a > 0) {                  // transparente Stops nicht ins RGB-Mittel
        r += t.r * t.a; g += t.g * t.a; b += t.b * t.a; w += t.a;
      }
    }
    return {r: w ? Math.round(r / w) : 0, g: w ? Math.round(g / w) : 0,
            b: w ? Math.round(b / w) : 0, a: a / toks.length};
  }
  function effBg(el) {
    // background von innen nach außen sammeln (backgroundColor UND
    // background-image/Gradient desselben Elements), dann komponieren.
    // CSS-Paint-Reihenfolge: der Gradient liegt über der backgroundColor des
    // eigenen Elements und unter dem Hintergrund der Eltern.
    // Body-/Elternklassen werden erfasst, weil bis documentElement hochgelaufen
    // wird (body mit .body--dark/.body--light und sein Gradient sind dabei).
    const layers = [];
    let e = el;
    while (e) {
      const cs = getComputedStyle(e);
      const col = parseColor(cs.backgroundColor);
      const grad = gradLayer(cs.backgroundImage);
      if (grad === 'UNMEASURABLE') return null;
      if (grad === 'NONE') {
        if (col && col.a > 0) { layers.push(col); if (col.a >= 0.999) break; }
      } else if (grad.a >= 0.999) {
        layers.push(grad); break;   // opaker Gradient deckt alle Eltern ab
      } else {
        layers.push(grad);          // transluzenter Gradient: darunter liegende
        if (col && col.a > 0) layers.push(col);  // Farbe des eigenen Elements sichtbar
      }
      if (e === document.documentElement) break;
      e = e.parentElement;
    }
    let out = {r: 255, g: 255, b: 255};  // Canvas-Default weiß (nur ohne jedes Layer)
    for (let i = layers.length - 1; i >= 0; i--) {
      const L = layers[i];
      out = {
        r: Math.round(L.r * L.a + out.r * (1 - L.a)),
        g: Math.round(L.g * L.a + out.g * (1 - L.a)),
        b: Math.round(L.b * L.a + out.b * (1 - L.a)),
      };
    }
    return out;
  }
  const out = [];
  const seen = new Set();
  for (const sel of sels) {
    for (const el of document.querySelectorAll(sel)) {
      const cs = getComputedStyle(el);
      // Gradient-Texte (bg-clip-text) ausklammern: Farbe steckt im background-image,
      // Kontrast-Regel für einfarbigen Text gilt hier nicht (Auditor-Artefakt).
      const clip = cs.webkitBackgroundClip || cs.backgroundClip;
      if (clip === 'text') continue;
      const fill = cs.getPropertyValue('-webkit-text-fill-color');
      const text = (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 50);
      const hasText = el.children.length === 0 && text.length > 0;
      const key = sel + '|' + text + '|' + cs.color;
      if (seen.has(key)) continue;
      seen.add(key);
      // ── F-4 (Fix, Phase-E Runde 3) ────────────────────────────────────
      // Die alte Prüfung cs.color.includes('0)') fing auch OPAKE Farben mit
      // Kanal-Endung 0 ab (z.B. "rgb(0, 0, 0)" oder "rgb(50, 60, 70)" enthält
      // "0)") → alle Treffer wurden fälschlich als transparent übersprungen
      // (employer·light: 0 Elemente geprüft).
      // Korrektur: nur echte Transparenz zählt – Alpha=0 in text-fill-color
      // (inkl. "transparent") oder Alpha=0 in der Textfarbe selbst.
      const fg = parseColor(cs.color);
      const fillP = parseColor(fill);
      const transparent = fill === 'transparent'
        || (fillP !== null && fillP.a === 0)
        || fg === null || fg.a === 0;
      out.push({
        sel,
        text: hasText ? text : '',
        color: cs.color,
        color_rgb: fg ? ('rgba(' + fg.r + ', ' + fg.g + ', ' + fg.b + ', ' + fg.a + ')') : null,
        bg: effBg(el),
        fs: parseFloat(cs.fontSize),
        fw: parseInt(cs.fontWeight) || 400,
        transparent: transparent,
      });
      if (out.length > 500) return out;
    }
  }
  return out;
}
"""

JS_GLASS_INFO = """
() => {
  const res = {};
  for (const sel of ['.glass', '.glass-strong', '.header-glass', '.sidebar-glass', '.btn-glass', '.badge-glass', '.input-glass']) {
    const el = document.querySelector(sel);
    res[sel] = el ? (getComputedStyle(el).backdropFilter || getComputedStyle(el).webkitBackdropFilter || 'none') : 'ELEMENT_FEHLT';
  }
  return res;
}
"""


def hex_to_rgb(h):
    h = h.lstrip('#')
    return {r: None} if False else {'r': int(h[0:2], 16), 'g': int(h[2:4], 16), 'b': int(h[4:6], 16)}


def parse_rgb(s):
    m = re.match(r'rgba?\(([^)]+)\)', s or '')
    if not m:
        return None
    p = [float(x) for x in m.group(1).split(',')]
    return {'r': p[0], 'g': p[1], 'b': p[2], 'a': p[3] if len(p) > 3 else 1}


def luminance(c):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c['r']) + 0.7152 * f(c['g']) + 0.0722 * f(c['b'])


def ratio(fg, bg):
    l1, l2 = sorted([luminance(fg), luminance(bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def audit_page(page, name, mode):
    # F-7 (Fix, Phase-E Runde 3): Full-Page-Screenshot statt nur Viewport
    # (1440×900), damit auch Below-the-fold-Bereiche erfasst werden.
    page.screenshot(path=str(OUT / f"{name}-{mode}.png"), full_page=True)
    glass = page.evaluate(JS_GLASS_INFO)
    items = page.evaluate(JS_COLLECT, TEXT_SELS)
    fails, checked, unmeasurable = [], 0, 0
    for it in items:
        if it['transparent'] or not it['text']:
            continue
        # F-1: bg == None → Gradient ohne parsebare Farbstops (Design-Entscheidung:
        # nicht messbar, statt gegen Canvas-Weiß zu messen und ein Artefakt-Fail
        # wie "Weiß auf Weiß" zu erzeugen).
        if it['bg'] is None:
            unmeasurable += 1
            continue
        # color_rgb = normalisiertes rgba aus parseColor (oklch-fähig); die
        # rohe computed color (z.B. oklch(...)) kann parse_rgb() nicht lesen →
        # ohne diese Zeile blieb es bei "0 geprüft" trotz oklch-Support im JS.
        fg = parse_rgb(it.get('color_rgb') or it['color'])
        if not fg or fg['a'] < 0.5:
            continue
        checked += 1
        large = it['fs'] >= 24 or (it['fs'] >= 18.66 and it['fw'] >= 700)
        thr = 3.0 if large else 4.5
        r = ratio(fg, it['bg'])
        if r < thr:
            fails.append({
                'sel': it['sel'], 'text': it['text'][:40],
                'fg': it.get('color_rgb') or it['color'], 'bg': it['bg'],
                'ratio': round(r, 2), 'thr': thr, 'fs': it['fs'],
            })
    fails.sort(key=lambda x: x['ratio'])
    return {'page': name, 'mode': mode, 'checked': checked,
            'unmeasurable': unmeasurable,
            'fails': fails[:12], 'n_fails': len(fails), 'glass': glass}


def set_mode(page, dark):
    page.evaluate("""(d) => {
        document.documentElement.classList.toggle('dark', d);
        document.body.classList.toggle('dark', d);
        document.body.classList.toggle('body--dark', d);
        document.body.classList.toggle('body--light', !d);
    }""", dark)
    page.wait_for_timeout(600)


def try_login(page, tab, email, pw, dest):
    """Login über das UI (testet gleichzeitig die neue Login-Seite)."""
    page.goto(f"{BASE}/login")
    page.wait_for_timeout(1800)
    btn_re = {
        "Login": r"einloggen",
        "Arbeitgeber": r"arbeitgeber-login",
        "Admin": r"admin-login",
    }[tab]
    tab_el = page.get_by_role("tab", name=tab)
    if tab_el.count():
        tab_el.first.click()
        # F-6b (Fix, Phase-E Runde 3, 25.09.2026 – v2): Rennsituation nach
        # Tab-Klick. Bis die serverseitige Umstellung des ui.tab_panels durch ist,
        # liegen Alt- UND Neu-Panel im DOM (Beweis: 3-Lauf-Diagnose 25.09.2026,
        # 1 von 3 Läufen mit 2 Panels / 4 sichtbaren Inputs). Eine Wartezeit allein
        # reichte NICHT (count==1 trifft auch noch beim ALT-Panel zu → Füllung
        # landete im KANDIDATEN-Formular → "E-Mail und Passwort sind Pflichtfelder."
        # → kein Navigate → "Login fehlgeschlagen"; employer UND admin betroffen).
        # Korrektur: Locators auf das Panel beschränken, das den Submit-Button des
        # GEWÄHLTEN Tabs enthält (in jeder Rennphase eindeutig).
        # Design-Entscheidung: Button-Labels laut webui/pages/login.py (Einloggen /
        # Arbeitgeber-Login / Admin-Login); Panel-Timeout 8 s → Login = False.
        panel = page.locator(
            ".q-tab-panel",
            has=page.get_by_role("button", name=re.compile(btn_re, re.I)),
        )
        try:
            panel.first.wait_for(state="visible", timeout=8000)
        except Exception:
            return False
        inputs = panel.first.locator("input")
        inputs.nth(0).fill(email)
        panel.first.locator("input[type=password]").first.fill(pw)
        panel.first.get_by_role("button", name=re.compile(btn_re, re.I)).first.click()
    else:
        # Tab nicht gefunden (trat in keinem Lauf auf) → alter Flow unverändert
        inputs = page.locator("input:visible")
        inputs.nth(0).fill(email)
        page.locator("input[type=password]:visible").first.fill(pw)
        page.get_by_role("button", name=re.compile(r"login|einloggen", re.I)).first.click()
    try:
        # F-6 (Fix, Phase-E Runde 3): 8000 → 12000 – Argon2-Verify + Navigate
        # brauchen bei /admin messbar länger als 8 s (Sondierung 12 s = OK).
        page.wait_for_url(f"**{dest}", timeout=12000)
        page.wait_for_timeout(2000)
        return True
    except Exception:
        return False


results, shots = [], []

ROLES = [
    ("candidate", "Login", "batninitaoufik@gmail.com", "Abd15121978!", "/candidate"),
    ("employer", "Arbeitgeber", "hr@techvision.de", "sicher123", "/employer"),
    ("admin", "Admin", "admin@km-hr-agent.local", "admin-agent-2026", "/admin"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/google-chrome",
        headless=True, args=["--no-sandbox", "--force-color-profile=srgb"],
    )

    # ── 1. Login-Seite (GAST, eigener Kontext) ─────────────────────────
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE}/login")
    page.wait_for_timeout(2500)
    for dark, mode in [(False, "light"), (True, "dark")]:
        set_mode(page, dark)
        results.append(audit_page(page, "login", mode))
    ctx.close()

    # ── 2-4. Rollenportale (jeweils frischer Kontext = saubere Session) ─
    for name, tab, email, pw, dest in ROLES:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        if try_login(page, tab, email, pw, dest):
            page.wait_for_timeout(2500)
            for dark, mode in [(False, "light"), (True, "dark")]:
                set_mode(page, dark)
                results.append(audit_page(page, name, mode))
        else:
            results.append({"page": name, "mode": "-", "error": "Login fehlgeschlagen"})
        ctx.close()

    browser.close()

(OUT / "audit-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))

print(f"{'Seite':<10} {'Mode':<6} {'Geprüft':>8} {'Fails':>6}  backdrop-filter")
for r in results:
    if 'error' in r:
        print(f"{r['page']:<10} {r['mode']:<6}  FEHLER: {r['error']}")
        continue
    bf = ','.join(f"{k.split('.')[-1]}={v[:9]}" for k, v in r['glass'].items() if v != 'ELEMENT_FEHLT')
    missing = [k for k, v in r['glass'].items() if v == 'ELEMENT_FEHLT']
    print(f"{r['page']:<10} {r['mode']:<6} {r['checked']:>8} {r['n_fails']:>6}  {bf}" + (f"  FEHLT: {missing}" if missing else ""))
    for f in r['fails'][:6]:
        print(f"    ❌ {f['ratio']:.2f} (min {f['thr']}) {f['sel']:<28} '{f['text'][:32]}' fg={f['fg']} bg={f['bg']}")
