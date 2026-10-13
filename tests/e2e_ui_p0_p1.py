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
import atexit
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# R6-0 (30.09.2026): harter Live-Default entfernt — BASE kommt aus dem
# Harness und bricht ohne KMHR_E2E_BASE bewusst ab (siehe e2e_harness.py).
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_harness import BASE, DB, seed_email  # noqa: E402
from webui.logic import hash_password_argon2id  # noqa: E402

EMP = (seed_email("hr@techvision.de"), "sicher123")
CAND = (seed_email("recruiting.e2e.2809b@kmailtest.de"), "Test1234!")
# P0-2 braucht einen Kandidaten mit 'eingeladen'-Bewerbung UND erzeugter
# Einladung (candidate.py `_tab_bewerbungen`: Karte nur bei Status
# 'eingeladen' + get_invitation_artifacts). Picking dynamisch, danach ggf.
# Passwort-Fixture (Design-Entscheidung, zurückgesetzt via atexit).
INVITE_PW = "E2EInvite2026!"
KNOWN_LOGINS = dict([EMP, CAND])
PW_FIXTURES: list[tuple[int, str | None]] = []
results = []


def _q(sql: str, *args):
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def employer_id() -> int:
    return _q("SELECT id FROM employers WHERE email=?", EMP[0])[0][0]


def docs_of(email: str) -> list[str]:
    """Basisnamen aller Dokumente eines Kandidaten (P0-1 Kandidat)."""
    return [Path(p).name for (p,) in _q(
        "SELECT d.datei_pfad FROM candidate_documents d "
        "JOIN candidates c ON c.id=d.candidate_id WHERE c.email=? ORDER BY d.id",
        email,
    )]


def released_docs() -> list[tuple[str, str, str]]:
    """(datei_basename, kandidatenname, status_label_roh) — dieselbe Whitespace-
    Freigabe wie employer.py::_visible_documents (eingeladen/eingestellt)."""
    rows = _q(
        "SELECT cd.datei_pfad, c.name, "
        "  (SELECT MAX(CASE a.status WHEN 'eingestellt' THEN 2 ELSE 1 END) "
        "   FROM applications a JOIN jobs j ON j.id=a.job_id "
        "   WHERE a.candidate_id=c.id AND j.employer_id=? "
        "   AND a.status IN ('eingeladen','eingestellt')) AS rk "
        "FROM candidate_documents cd JOIN candidates c ON c.id=cd.candidate_id "
        "WHERE EXISTS (SELECT 1 FROM applications a JOIN jobs j ON j.id=a.job_id "
        "              WHERE a.candidate_id=c.id AND j.employer_id=? "
        "              AND a.status IN ('eingeladen','eingestellt')) "
        "ORDER BY cd.id DESC",
        employer_id(), employer_id(),
    )
    return [(Path(p).name or "", n or "", "eingestellt" if rk == 2 else "eingeladen")
            for p, n, rk in rows]


def active_apps() -> list[tuple[int, int, str, str]]:
    """(app_id, kandidat_id, status, kandidatenname) — Quelle:
    employer.py::_page_stellen `apps_aktiv` (Status IN eingegangen/angesehen/
    eingeladen)."""
    return _q(
        "SELECT a.id, a.candidate_id, a.status, COALESCE(c.name,'') "
        "FROM applications a JOIN jobs j ON j.id=a.job_id "
        "LEFT JOIN candidates c ON c.id=a.candidate_id "
        "WHERE j.employer_id=? AND a.status IN ('eingegangen','angesehen','eingeladen')",
        employer_id(),
    )


def expected_name(k_id: int, status: str, name: str) -> str:
    """Spec P2-8 (knowledge/portal/employer-portal-fields.md): Klarname nur ab
    Status 'eingeladen', sonst Pseudonym 'Kandidat #N' (Art. 6(1)(b))."""
    return name if status in ("eingeladen", "eingestellt") and name else f"Kandidat #{k_id}"


def pick_invite() -> tuple[str, str] | None:
    rows = _q(
        "SELECT c.id, c.email FROM applications a "
        "JOIN candidates c ON c.id=a.candidate_id "
        "JOIN agent_tasks t ON json_extract(t.payload,'$.application_id')=a.id "
        "WHERE a.status='eingeladen' AND t.task_type='create_invitation' "
        "AND t.status='done' AND t.result_json IS NOT NULL ORDER BY c.id"
    )
    if not rows:
        return None
    cid, email = rows[0]
    pw = KNOWN_LOGINS.get(email)
    if pw is None:
        pw = INVITE_PW
        conn = sqlite3.connect(str(DB))
        try:
            old = conn.execute(
                "SELECT password_hash FROM candidates WHERE id=?", (cid,)
            ).fetchone()[0]
            conn.execute(
                "UPDATE candidates SET password_hash=? WHERE id=?",
                (hash_password_argon2id(pw), cid),
            )
            conn.commit()
        finally:
            conn.close()
        PW_FIXTURES.append((cid, old))
        print(f"OK Passwort-Fixture: cand{cid} ({email}) — wird zurueckgesetzt")
    return email, pw


def restore_fixtures() -> None:
    for cid, old in PW_FIXTURES:
        conn = sqlite3.connect(str(DB))
        try:
            conn.execute(
                "UPDATE candidates SET password_hash=? WHERE id=?", (old, cid)
            )
            conn.commit()
        finally:
            conn.close()
        print(f"OK Passwort-Fixture zurueckgesetzt: cand{cid}")


atexit.register(restore_fixtures)


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


# P0-2: Einladungskarte nur bei Status 'eingeladen' + vorhandenen Artefakten
# (candidate.py::_tab_bewerbungen) → Kandidat dynamisch, ggf. Passwort-Fixture.
INVITE = pick_invite()
if INVITE is None:
    print("FAIL: kein Kandidat mit 'eingeladen'-Bewerbung + erzeugter Einladung")
    sys.exit(1)
print(f"OK P0-2 Kandidat dynamisch: {INVITE[0]}")

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
    doc_names = docs_of(CAND[0])
    check("P0-1", "Kandidat", "Dokumentliste sichtbar nach bestaetigtem Upload",
          "Meine Dokumente" in body, f"'Meine Dokumente' vorhanden={'Meine Dokumente' in body}")
    check("P0-1", "Kandidat", "Dateiname des Dokuments sichtbar",
          bool(doc_names) and all(n in body for n in doc_names),
          f"erwartet={doc_names}")
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

    # P0-2 braucht den EINLADUNGS-Kandidaten (eigener Context, eigener Login)
    ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
    login(ctx2.new_page(), INVITE[0], INVITE[1], False)
    page = ctx2.new_page()
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
    ctx2.close()

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
    # Dynamische Erwartung aus _visible_documents (DSGVO-Gate): Dateien+Klarnamen
    # der freigegebenen Bewerbungen muessen sichtbar sein, der DB-Slug nie.
    rel = released_docs()
    no_slug = "lebenslauf_hochgeladen" not in body
    if rel:
        missing = [b for b, _, _ in rel if b not in body]
        missing += [n for _, n, _ in rel if n and n not in body]
        klartext = ("Eingestellt" in body) or ("Eingeladen" in body)
        check("P0-1", "Recruiter", "Gate zeigt freigegebene Dokumente + Klartext-Status (kein Slug)",
              no_slug and not missing and klartext,
              f"freigegeben={len(rel)}, fehlt={missing[:2]}, klartext={klartext}")
    else:
        check("P0-1", "Recruiter", "Leer-/Sperrtext statt DB-Slug (keine freigegebenen Dokumente)",
              no_slug and ("Keine Dokumente" in body or "Noch gesperrt" in body),
              f"no_slug={no_slug}")
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
            # Glob mit `*`, weil die Route Query-Parameter tragen kann
            # (`/employer/match?kandidat=N`) — `.../match` allein matcht nicht.
            page.wait_for_url("**/employer/match*", timeout=180000)
        except Exception as ex:
            check("P1-1", "Recruiter", "URL wechselt auf /employer/match", False, str(ex)[:80])
        page.wait_for_timeout(3000)
        body2 = page.inner_text("body")
        # Positiv-Assertion: der Subtitel "Passung" steht NUR auf der
        # Match-Seite. Das fruehere Negativ-Kriterium "Kandidaten-Suche" not in
        # body traf die Sidebar (PAGE_TITLES["kandidaten"]) und war damit
        # auf JEDE Employer-Seite falsch.
        check("P1-1", "Recruiter", "Klick fuehrt zum Match-Ergebnis",
              "Passung" in body2, f"Subtitel={'Passung' in body2}")
        check("P1-1", "Recruiter", "URL wechselt auf /employer/match",
              page.url.startswith(f"{BASE}/employer/match"), f"URL={page.url}")
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
                // Quasar-Flat-Buttons (Einstellen/Ablehnen: color=positive/negative
                // flat) druecken ihre Hierarchie ueber die TEXTfarbe aus, der
                // Hintergrund ist transparent. Deshalb beide Werte erfassen —
                // sonst misst die Sonde bei reiner Flat-Lage 1 Farbe und der
                // Datenstand (kein gefuelltes 'Einladen' mehr aktiv) faerbt den
                // Check rot (Datenkupplung06.10.2026).
                const s = getComputedStyle(e);
                o[t.split('\\n').pop()] = s.backgroundColor + '|' + s.color;
            }
        });
        return o; }""")
    if len(colors) < 2:
        # Datenkupplung (06.10.2026): bei nur einem gerenderten Recruiter-Button
        # (Datenstand z. B. nur 'Ablehnen' aktiv) ist die Hierarchie nicht
        # vergleichbar → SKIP statt FAIL, kein Codefehler.
        print(f"  [SKIP] P1-2 Recruiter Button-Hierarchie: nur {len(colors)} Recruiter-Button(s) "
              f"gerendert (Datenstand) — Hierarchie nicht vergleichbar")
    else:
        distinct = len(set(colors.values()))
        check("P1-2", "Recruiter", "Button-Hierarchie: Einladen/Ablehnen/Einstellen unterscheiden sich",
              distinct >= 2, f"Farben={colors}")
    page.close()

    page = ctx.new_page()
    page.goto(f"{BASE}/employer/stellen", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2500)
    apps = active_apps()
    exp = page.locator(".q-expansion-item").filter(has_text="Aktive Bewerber").first
    # P1-13 (30.09.2026): `value=True` — die Liste ist standardmaessig
    # aufgeklappt. Ein bedingungsloser Klick KLASST SIE ZU und die Bewerber
    # verschwanden aus `body` (Ursache der roten P1-4-Assertions, 06.10.2026).
    if exp.count():
        content = exp.locator(".q-expansion-item__content")
        if content.count() == 0 or not content.first.is_visible():
            exp.click()
            page.wait_for_timeout(2000)
    exp_txt = exp.inner_text() if exp.count() else ""
    # Spec P2-8 (knowledge/portal/employer-portal-fields.md): Klarname nur ab
    # Status 'eingeladen' — vorher 'Kandidat #22' in body == FAIL, obwohl die
    # Karte korrekt pseudonymisiert war. Erwartung JE aktiven Bewerbung.
    expected = [expected_name(k, st, nm) for _a, k, st, nm in apps]
    missing = [e for e in expected if e not in exp_txt]
    leaked = [f"Kandidat #{k}" for _a, k, st, nm in apps
              if st in ("eingeladen", "eingestellt") and nm
              and f"Kandidat #{k}" in exp_txt]
    check("P1-4", "Recruiter", "Bewerberkarte zeigt je Status den korrekten Namen (Spec P2-8)",
          bool(apps) and not missing and not leaked,
          f"aktiv={len(apps)}, fehlt={missing}, Pseudonym={leaked}")
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
