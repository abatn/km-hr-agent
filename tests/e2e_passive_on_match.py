"""P3 E2E: Passiv-Matches auf /employer/match (GO §H-16 / (c)3 option (i)).

Spec: knowledge/portal/matching-filter.md Abschnitt (g) — STAGING 26.09.2026.
Dieser Test ist der ROTE BEWEIS: Teil A FAILT, solange E47/E48 (employer.py)
nicht angewandt sind.

A QUELLTEXT  Label "passiver Match" + Gate (Must-Have + 50%) + Pool == app.py:3898
             + Early-Return ohne conn.close()/return
             (A5-Parser normalisiert Zeilenumbrüche zwischen zwei Python-String-
              Literalen, A7 ignoriert Kommentarzeilen — beides Ergänzungen vom
              26.09.2026 nach GO des Nutzers, damit der Test mit dem Code des
              Stagings konsistent ist; Code employer.py bleibt unverändert)
B DB         Replik UNABHÄNGIG von employer.py (webui.logic): Passiv-Menge =
             Pool minus Bewerber des Employers (a.status != 'zurückgezogen'),
             Gate identisch, bester Job pro Kandidat, LIMIT 10
C UI         /employer/match: Replik >=1 -> Label "passiver Match" sichtbar;
             Replik 0 -> Label abwesend (view-only, kein DB-Write)

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_passive_on_match.py
"""
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import check_server, db_residue_report, pre_max_tasks  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
EMP_EMAIL = "hr@techvision.de"
EMP_PW = "sicher123"
POOL = ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")


def _triples_in(text: str) -> list:
    out = []
    for m in re.finditer(r"status IN \(([^)]*)\)", text):
        # Zeilenumbrüche/Whitespace zwischen zwei Python-String-Literalen
        # normalisieren (z. B. employer.py splittet die Pool-Liste über 2 Literale).
        raw = " ".join(m.group(1).split())
        out.append(tuple("".join(ch for ch in p if ch not in "'\"").strip()
                         for p in raw.split(",")))
    return out


def check_a(failures) -> None:
    emp = (ROOT / "webui" / "pages" / "employer.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    if "passiver Match" not in emp:
        failures.append("A1 employer.py ohne Label 'passiver Match' (roter Beweis, E48 fehlt)")
    if 'if not _r["matches"]:' not in emp:
        failures.append("A2 Must-Have-Gate fehlt")
    if "< _pj_exp * 0.5" not in emp:
        failures.append("A3 50%-Erfahrungs-Gate fehlt")
    if "if _treffer == 0 and not _passive:" not in emp:
        failures.append("A4 Leercase-Bedingung fehlt (soll 'and not _passive' sein)")
    if POOL not in _triples_in(emp) or POOL not in _triples_in(app):
        failures.append(f"A5 Pool-Tripel != app.py:3898 {POOL}")
    i = emp.find("# Kandidaten mit Bewerbungen fuer diesen Employer")
    if i < 0:
        failures.append("A6 Anker-Kommentar '# Kandidaten mit Bewerbungen...' fehlt")
    else:
        head = emp[i:emp.find("_treffer = 0", i)]
        # Kommentarzeilen ausblenden: der E47-Kommentar nennt 'conn.close()'
        # (Verweis auf das Ende von match_content) und würde sonst als
        # Early-Return-Beweis fehlalarmieren.
        code = "\n".join(ln for ln in head.splitlines()
                         if not ln.lstrip().startswith("#"))
        if "conn.close()" in code or "\n            return" in code:
            failures.append("A7 Early-Return (conn.close()/return) blockiert Passiv-Block (E47 fehlt)")


def check_b(failures) -> dict:
    from webui import logic
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    emp = conn.execute("SELECT id FROM employers WHERE lower(email) = lower(?)",
                       (EMP_EMAIL,)).fetchone()
    if not emp:
        failures.append("B1 Test-Employer fehlt")
        conn.close()
        return {}
    eid = emp[0]
    applicants = {r[0] for r in conn.execute(
        "SELECT DISTINCT a.candidate_id FROM applications a "
        "JOIN jobs j ON a.job_id = j.id "
        "WHERE j.employer_id = ? AND a.status != 'zurückgezogen'", (eid,))}
    jobs = conn.execute(
        "SELECT j.id, j.titel, j.hard_skills, j.soft_skills, j.berufserfahrung_jahre, "
        "j.deutsch_level, j.englisch_level, j.standort, j.stellentyp, e.branche "
        "FROM jobs j JOIN employers e ON e.id = j.employer_id "
        "WHERE j.employer_id = ? AND j.status = 'aktiv'", (eid,)).fetchall()
    cands = conn.execute(
        "SELECT id, name, hard_skills, soft_skills, berufserfahrung_jahre, abschluss, "
        "deutsch, englisch, standort, lebenslauf_text FROM candidates "
        "WHERE status IN (?,?,?,?)", POOL).fetchall()
    conn.close()
    best = {}
    for job in jobs:
        (_jid, titel, jh, js, jexp, jde, jen, jort, jtyp, br) = job
        for c in cands:
            if c[0] in applicants:
                continue
            try:
                r = logic.berechne_match_score(
                    {"hard_skills": c[2], "soft_skills": c[3],
                     "berufserfahrung_jahre": c[4], "abschluss": c[5], "deutsch": c[6],
                     "englisch": c[7], "standort": c[8], "lebenslauf_text": c[9] or ""},
                    {"hard_skills": jh, "soft_skills": js, "berufserfahrung_jahre": jexp,
                     "deutsch_level": jde, "englisch_level": jen, "standort": jort,
                     "stellentyp": jtyp, "branche": br})
            except Exception:
                continue
            if not r["matches"]:
                continue
            if jexp and (c[4] or 0) < jexp * 0.5:
                continue
            if c[0] not in best or r["total"] > best[c[0]][0]:
                best[c[0]] = (r["total"], c[1] or "Unbekannt", titel, r["kategorie"],
                              r["matches"])
    passive = sorted(best.values(), key=lambda t: t[0], reverse=True)[:10]
    if not jobs:
        failures.append("B2 keine aktiven Jobs des Test-Employers (Datenlage)")
    return {"applicants": len(applicants), "jobs": len(jobs), "pool": len(cands),
            "passive": passive, "passive_n": len(passive)}


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
    page.goto(f"{BASE}/employer/match", wait_until="load", timeout=60000)
    page.wait_for_timeout(4000)
    body = page.inner_text("body")
    if ctx["passive_n"] > 0:
        if "passiver Match" not in body:
            failures.append(
                f"C UI ohne 'passiver Match' trotz Replik {ctx['passive_n']} "
                "(E47/E48 nicht angewandt?)")
        elif f"{ctx['passive_n']} passiver Match" not in body:
            print(f"C Warnung: UI-Count != Replik {ctx['passive_n']} (Dedupe/Jobs-Race?)")
    elif "passiver Match" in body:
        failures.append("C UI zeigt Passiv-Label trotz Replik 0 (Gate zu lasch?)")


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
    print(f"PASS: P3 Passiv-Matches — Quelltext (Gate + Pool app.py:3898), "
          f"DB-Replik {ctx.get('passive_n', 0)} Passiv-Treffer, UI view-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
