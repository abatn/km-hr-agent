"""P3 E2E C3: Gehalts-Check live im Match-View (Display-only, keine DB-Schreibung).

Ablauf:
1. Employer-Login → /employer/match
2. Klappen oeffnen — ui.expansion hat NiceGUI-Default value=False (geschlossen),
   der 'Gehalt:'-Text liegt im Klapfen-Body (employer.py:838).
3. Erwartete Varianten aus DB + webui/logic replizieren: exakt die Karten-Regel aus
   employer.py::_page_match — BEWERBER UNGEFILTERT (Paritaet app.py:3635-3640
   „Abschnitt 1: Aktive Bewerber“; der Must-Have/50%-Filter app.py:3844-3848 gilt
   nur passive Matches). Korrektur 25.09.2026 (Phase-E Runde 6): die
   B2-2-(c)1-Filterung wurde aus _page_match entfernt (Paritaetsbruch, deckte
   e2e_housing auf). Inkl. jobs[:3]-Limit; Gehalts-Text = logic.gehalt_check.
   Rendering-Menge muss exakt der Erwartung entsprechen (keine hartkodierten
   Kandidaten-IDs — B2-2 filtert die Kandidatenmenge, vorherige 3-Varianten-Liste
   entsprach dem alten NiceGUI-Verhalten ohne Filter).
4. Kein Restore noetig (nur Lesen).

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_gehalt_match.py
"""
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webui import logic  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(700)
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I))
    ).first
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def expected_gehalt() -> list:
    """Replik der Karten-Regel aus employer.py::_page_match (B2-2)."""
    conn = sqlite3.connect(str(DB))
    out = []
    try:
        emp_row = conn.execute("SELECT id FROM employers WHERE email = ?", (EMP_EMAIL,)).fetchone()
        employer_id = emp_row[0] if emp_row else 1
        cands = conn.execute("""
            SELECT DISTINCT c.id, c.name, c.hard_skills, c.soft_skills,
                   c.berufserfahrung_jahre, c.abschluss, c.deutsch, c.englisch,
                   c.standort, c.gehaltsvorstellung, c.lebenslauf_text
            FROM candidates c
            JOIN applications a ON a.candidate_id = c.id
            JOIN jobs j ON a.job_id = j.id
            WHERE j.employer_id = ? AND a.status != 'zurückgezogen'
            ORDER BY c.id DESC
        """, (employer_id,)).fetchall()
        for cand in cands:
            c_id, _name, h_skills, s_skills, exp, abschluss, de, en, standort, gevh, cv_text = cand
            jobs = conn.execute("""
                SELECT a.id, a.status, j.id, j.titel, j.hard_skills, j.soft_skills,
                       j.berufserfahrung_jahre, j.deutsch_level, j.englisch_level,
                       j.standort, j.stellentyp, e.branche, j.gehaltsrahmen_min, j.gehaltsrahmen_max
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                JOIN employers e ON j.employer_id = e.id
                WHERE a.candidate_id = ? AND j.employer_id = ? AND a.status != 'zurückgezogen'
                ORDER BY a.erstellungsdatum DESC
            """, (c_id, employer_id)).fetchall()
            for job in jobs[:3]:
                (_a_id, _a_st, _j_id, _titel, j_hard, j_soft, j_exp, j_de, j_en,
                 j_st, j_typ, branche, min_g, max_g) = job
                k_data = {"hard_skills": h_skills, "soft_skills": s_skills,
                          "berufserfahrung_jahre": exp, "abschluss": abschluss,
                          "deutsch": de, "englisch": en, "standort": standort,
                          "lebenslauf_text": cv_text or ""}
                j_data = {"hard_skills": j_hard, "soft_skills": j_soft,
                          "berufserfahrung_jahre": j_exp, "deutsch_level": j_de,
                          "englisch_level": j_en, "standort": j_st,
                          "stellentyp": j_typ, "branche": branche}
                try:
                    res = logic.berechne_match_score(k_data, j_data)
                except Exception:
                    continue
                # Kein Gate: Bewerber-Karten sind ungefiltert (Paritaet
                # app.py:3635-3640); res wird nur fuer spaetere Checks geladen.
                out.append(f"{c_id}x{_j_id}: {logic.gehalt_check(gevh, min_g, max_g)}")
    finally:
        conn.close()
    return out


def open_expansions(page):
    heads = page.locator(".q-expansion-item .q-item")
    for i in range(heads.count()):
        heads.nth(i).click()
        page.wait_for_timeout(350)
    page.wait_for_timeout(600)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    failures = []
    expected = expected_gehalt()
    print(f"Erwartet ({len(expected)} Karten): {sorted(expected)}")
    if not expected:
        print("HINWEIS: Datenlage liefert keine Karte — Pruefung bleibt UI-leer")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            login_employer(page)
            # Erstlast nach Server-Restart ~26s (Connector-Cold-Cache, C3) → 60s Timeout
            page.goto(f"{BASE}/employer/match", wait_until="load", timeout=60000)
            page.wait_for_timeout(3500)

            # (a) Sichtbarkeits-Nachweis: eine Klappe oeffnen -> Label sichtbar.
            # ACHTUNG: ui.timer(15s) match_content.refresh schliesst Klappen wieder
            # (Runde 6: 24 Klappen > 15s Fenster → 0 sichtbar), deshalb nur 1 Klappe
            # und der Multiset-Nachweis unten aus dem gerenderten DOM.
            heads = page.locator(".q-expansion-item .q-item")
            n_heads = heads.count()
            print(f"Expansionen: {n_heads}")
            if n_heads < 1:
                failures.append("keine Expansion auf /employer/match (C3 nicht gerendert)")
            else:
                heads.nth(0).click()
                page.wait_for_timeout(600)
                vis = page.locator("body").inner_text().count("Gehalt:")
                print(f"sichtbare 'Gehalt:'-Label nach Klappe 1: {vis}")
                if vis < 1:
                    failures.append("(a) 'Gehalt:'-Label nach Klappen-Open nicht sichtbar")

            # Multiset aller gerenderten Labels (display:none-Klappen zaehlen — der
            # Text steht im DOM; JSON-State-Blob der Seite enthaelt jede Zeile doppelt,
            # deshalb exakt das >…</div>-Muster des gerenderten Elements).
            html = page.content()
            rendered = [m.strip()
                        for m in re.findall(r">Gehalt:\s*([^<]+)</div>", html)]
            print(f"'Gehalt:'-Labels im DOM: {len(rendered)} -> {sorted(rendered)}")
            if not rendered:
                failures.append("kein 'Gehalt:'-Label im DOM von /employer/match (C3 nicht gerendert)")

            exp_variants = sorted(v.split(": ", 1)[1] for v in expected)
            got_variants = sorted(rendered)
            if exp_variants != got_variants:
                failures.append(f"Gehalts-Varianten abweichend: erwartet {exp_variants} / gerendert {got_variants}")
            else:
                print(f"OK: gerenderte Varianten == Erwartung aus B2-2-Replik ({len(got_variants)})")

            for variant in ("✅", "❓", "⚠️"):
                hits = [v for v in got_variants if v.startswith(variant)]
                print(f"  Vorkommen {variant}: {hits or 'keins (Datenlage)'}")

        finally:
            browser.close()

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: gehalt_check live in /employer/match (Sichtbarkeit + Varianten == B2-2-Replik, view-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
