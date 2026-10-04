"""B2 E2E: Applicants-First im Feedback-Kandidaten-Picker (GO B2-4).

Spec: knowledge/portal/applicants-first.md — Bewerber dieser Stelle zuerst
(aktive Status 'eingegangen'/'angesehen'/'eingeladen', ASC nach Erstellt-Datum),
dann passive Matches; passive-Match-Ausschluss (De-Dup-Subquery) betrifft nur
aktive Bewerbungen (Paritaet app.py:3898-3900 + fb_bewerber-Ausschluss).
Ziel: employer.py::refresh_cands (Picker) — (c)3 Subtitle/Tab-Kandidaten bewusst
draussen (kein GO-Punkt).

Ablauf:
 A QUELLTEXT  beide Statuslisten (Bewerber-Query + De-Dup-Subquery) == app.py:3898;
              'all_cands = applicants + passive'
 B DB         Replik fuer die Stelle mit aktiven Bewerbern: Reihenfolge ASC ==
              Sortierung nach erstellungsdatum; kein aktiver Bewerber in der
              passiven Menge; abgelehnte Bewerber duerfen wieder passiv erscheinen
 C UI         /employer/feedback -> Stelle waehlen -> Kandidaten-Select oeffnen:
              fuehrende Optionen tragen 📩 in exakt der DB-Reihenfolge, dahinter
              passive Option(en) ohne Präfix, kein aktiver Bewerber doppelt
 Baselines: agent_tasks MAX + feedback-Zeilen (nur Lesen, kein Speichern).

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_applicants_first.py
"""
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
EMP_EMAIL = "hr@techvision.de"
EMP_PW = "sicher123"
TRIPLE = ("eingegangen", "angesehen", "eingeladen")


def _triples_in(text: str) -> list:
    out = []
    for m in re.finditer(r"status IN \(([^)]*)\)", text):
        out.append(tuple(p.strip().strip("'\"") for p in m.group(1).split(",")))
    return out


def check_a(failures) -> None:
    emp_src = (ROOT / "webui" / "pages" / "employer.py").read_text(encoding="utf-8")
    app_src = (ROOT / "app.py").read_text(encoding="utf-8")

    m_applicants = re.search(
        r"applicants = conn\.execute\(\"\"\"(.*?)\"\"\"", emp_src, re.S)
    m_passive = re.search(
        r"(?:passive|_p_rows) = conn\.execute\(\"\"\"(.*?)\"\"\"", emp_src, re.S)
    fb_idx = app_src.find("fb_bewerber")
    fb_window = app_src[max(0, fb_idx - 600):fb_idx] if fb_idx > 0 else ""
    if not (m_applicants and m_passive and fb_window):
        failures.append(f"A Quelltext-Bloecke fehlen (applicants={bool(m_applicants)}, "
                        f"passive={bool(m_passive)}, fb={bool(fb_window)})")
        return

    t_app = _triples_in(m_applicants.group(1))
    t_pass = _triples_in(m_passive.group(1))
    t_fb = _triples_in(fb_window)
    print(f"A Statuslisten: NiceGUI-Bewerber={t_app} | NiceGUI-Block={t_pass} | app.py={t_fb}")
    if not t_app or t_app[0] != TRIPLE:
        failures.append(f"A Bewerber-Query ohne Triple {TRIPLE}: {t_app}")
    if TRIPLE not in t_pass:
        failures.append(f"A De-Dup-Subquery ohne Triple {TRIPLE}: {t_pass}")
    if not t_fb or TRIPLE not in t_fb:
        failures.append(f"A app.py fb_bewerber-Fenster ohne Triple {TRIPLE}: {t_fb}")
    if "ORDER BY a.erstellungsdatum ASC" not in m_applicants.group(1):
        failures.append("A Bewerber-Query sortiert nicht ASC (app.py:3899-Paritaet)")
    if "ORDER BY a.erstellungsdatum ASC" not in fb_window:
        failures.append("A app.py:3898-3900 nicht ASC — Paritaetsziel fehlt")
    if "all_cands = applicants + passive" not in emp_src:
        failures.append("A 'all_cands = applicants + passive' fehlt (Bewerber zuerst)")
    else:
        print("A Reihenfolge-Beweis: all_cands = applicants + passive")


def check_b(failures) -> dict:
    conn = sqlite3.connect(str(DB))
    try:
        job = conn.execute("""
            SELECT j.id, j.titel FROM jobs j
            WHERE EXISTS (SELECT 1 FROM applications a WHERE a.job_id = j.id
                          AND a.status IN ('eingegangen', 'angesehen', 'eingeladen'))
            ORDER BY j.id LIMIT 1
        """).fetchone()
        if not job:
            failures.append("B keine Stelle mit aktiven Bewerbern (Datenlage)")
            return {}
        job_id, job_titel = job
        active = conn.execute("""
            SELECT c.id, c.name, a.id, a.erstellungsdatum
            FROM candidates c JOIN applications a ON a.candidate_id = c.id
            WHERE a.job_id = ? AND a.status IN ('eingegangen', 'angesehen', 'eingeladen')
            ORDER BY a.erstellungsdatum ASC
        """, (job_id,)).fetchall()
        passive = conn.execute("""
            SELECT c.id, c.name FROM candidates c
            WHERE c.status IN ('lebenslauf_hochgeladen', 'zugeordnet', 'aktiv')
            AND c.id NOT IN (SELECT candidate_id FROM applications
                             WHERE job_id = ? AND status IN ('eingegangen', 'angesehen', 'eingeladen'))
            ORDER BY c.id DESC LIMIT 20
        """, (job_id,)).fetchall()
        print(f"B Stelle #{job_id} {job_titel!r}: aktiv={[(a[0], a[1]) for a in active]} "
              f"passiv={[(p[0], p[1]) for p in passive]}")
        if not active:
            failures.append("B gewaehlte Stelle hat keine aktiven Bewerber")
        dates = [a[3] for a in active]
        if dates != sorted(dates):
            failures.append(f"B ASC verletzt: {dates}")
        act_ids = {a[0] for a in active}
        if act_ids & {p[0] for p in passive}:
            failures.append(f"B aktiver Bewerber auch passiv: {act_ids & {p[0] for p in passive}}")
        return {"job_id": job_id, "job_titel": job_titel,
                "active_names": [(a[0], a[1]) for a in active],
                "passive_ids": [p[0] for p in passive]}
    finally:
        conn.close()


def login(page):
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


def check_c(page, ctx: dict, failures) -> None:
    if not ctx:
        print("C uebersprungen (kein DB-Kontext)")
        return
    page.goto(f"{BASE}/employer/feedback", wait_until="load", timeout=60000)
    page.wait_for_timeout(3000)

    job_in = page.locator('input[aria-label="Stelle"]')
    job_in.click()
    page.wait_for_timeout(500)
    page.get_by_role("option").filter(has_text=ctx["job_titel"]).first.click()
    page.wait_for_timeout(1200)

    cand_in = page.locator('input[aria-label="Kandidat"]')
    if cand_in.count() < 1:
        failures.append("C kein Kandidaten-Select gefunden")
        return
    cand_in.first.click()
    page.wait_for_timeout(700)
    opts = [t.strip() for t in page.get_by_role("option").all_inner_texts()]
    page.keyboard.press("Escape")
    print(f"C Optionen: {opts}")

    expected_first = [f"📩 {name or f'Kandidat #{cid}'}" for cid, name in ctx["active_names"]]
    n = len(expected_first)
    if opts[:n] != expected_first:
        failures.append(f"C Bewerber-Reihenfolge abweichend: erwartet {expected_first} / "
                        f"gefunden {opts[:n]}")
    else:
        print(f"C erste {n} Optionen = aktive Bewerber in ASC-Reihenfolge ✓")
    tail = opts[n:]
    if any(o.startswith("📩") for o in tail):
        failures.append(f"C passiver Bereich enthaelt 📩-Bewerber: {tail}")
    else:
        print(f"C passiver Anhang ohne 📩: {tail}")
    if not tail:
        print("C Hinweis: keine passiven Optionen (Datenlage)")
    dup = [o for o in expected_first if opts.count(o) > 1]
    if dup:
        failures.append(f"C doppelte Optionen: {dup}")


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    failures = []
    check_a(failures)
    ctx = check_b(failures)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)
        try:
            login(page)
            check_c(page, ctx, failures)
        except Exception as ex:  # noqa: BLE001
            failures.append(f"Exception: {ex!r}")
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
    print("PASS: B2-4 Applicants-First — Quelltext/Paritaet app.py:3898, DB-Reihenfolge ASC, "
          "UI-Bewerber zuerst, kein aktiver Bewerber passiv, view-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
