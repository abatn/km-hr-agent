"""P3 E2E Feature G (ii): Match-Score-Badge + Score-DESC im Candidate-Stellen-Tab.

Spec: knowledge/lifecycle/matching-criteria.md §2 (Option A: score DESC, Tie-Break
id DESC), §3 (Badge „{n} % passend" in der Titelzeile + score_bar im
Expansion-Body), §4 (live), §6 (CV-Gate ohne lebenslauf_text). GO 24.09.2026;
Option (iii) Erklärungs-Expander bleibt Folge-Go.

Ablauf:
1. Harness-F2 (Server-Precheck) + F3 (Task-Residue-Grenze)
2. DB-Erwartung: aktive Jobs + Score je Job via webui.logic.berechne_match_score
   (identische Codebasis + identische Gewichte wie der Serverprozess)
3. DB-Baseline: agent_tasks/feedback/gewichtung_historie/applications
4. Candidate-Login (#1, CV vorhanden, Status profil_vollstaendig)
   -> /candidate/stellen
5. (a) Anzahl Badges „N % passend" == Anzahl aktiver Jobs
6. (b) DOM-Reihenfolge == Erwartung (score DESC, Tie-Break id DESC)
7. (c) score_bar („N/100") im geoeffneten Expansion-Body des 1. Cards
8. DB-Baseline nach dem Render unveraendert (reines Display, kein Write)

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_candidate_score.py
"""
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import check_server, db_residue_report, pre_max_tasks  # noqa: E402
from webui import logic  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
EMAIL = "batniniabdelkader@yahoo.com"
PASSWORD = "Abdel15121978!"
CAND_ID = 1

CARD_ANCESTOR = "xpath=ancestor::*[contains(@class,'card-interactive')][1]"


def expected_scores() -> list:
    """[(job_id, score)] sortiert wie Spec §2: score DESC, Tie-Break id DESC."""
    conn = sqlite3.connect(DB)
    try:
        jobs = conn.execute(
            "SELECT j.id, j.hard_skills, j.soft_skills, j.berufserfahrung_jahre, "
            "j.deutsch_level, j.englisch_level, j.standort, j.stellentyp, e.branche "
            "FROM jobs j JOIN employers e ON j.employer_id = e.id "
            "WHERE j.status = 'aktiv'"
        ).fetchall()
        cand = conn.execute(
            "SELECT hard_skills, soft_skills, berufserfahrung_jahre, abschluss, "
            "deutsch, englisch, standort, lebenslauf_text "
            "FROM candidates WHERE id = ?",
            (CAND_ID,),
        ).fetchone()
    finally:
        conn.close()
    assert cand and (cand[7] or "").strip(), "CV-Gate: candidate #1 braucht lebenslauf_text"
    out = []
    for jid, hard, soft, exp, de, en, ort, typ, branche in jobs:
        k_data = {"hard_skills": cand[0], "soft_skills": cand[1],
                  "berufserfahrung_jahre": cand[2], "abschluss": cand[3],
                  "deutsch": cand[4], "englisch": cand[5],
                  "standort": cand[6], "lebenslauf_text": cand[7] or ""}
        j_data = {"hard_skills": hard, "soft_skills": soft,
                  "berufserfahrung_jahre": exp, "deutsch_level": de,
                  "englisch_level": en, "standort": ort,
                  "stellentyp": typ, "branche": branche}
        out.append((jid, logic.berechne_match_score(k_data, j_data)["total"]))
    out.sort(key=lambda t: (-t[1], -t[0]))
    return out


def db_baseline() -> tuple:
    conn = sqlite3.connect(DB)
    try:
        return (
            conn.execute("SELECT COALESCE(MAX(id),0) FROM agent_tasks").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM gewichtung_historie").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
        )
    finally:
        conn.close()


def login(page):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.get_by_label("E-Mail").fill(EMAIL)
    page.get_by_label("Passwort", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Einloggen").click()
    page.wait_for_url("**/candidate**", timeout=15000)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    failures = []
    expected = expected_scores()
    n_jobs = len(expected)
    baseline_before = db_baseline()
    print(f"Erwartung (Spec §2): {expected}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)
        try:
            login(page)
            # Erstlast nach Server-Restart: Connector-Cold-Cache (~26s) -> 90s
            page.goto(f"{BASE}/candidate/stellen", wait_until="load", timeout=90000)
            badges = page.get_by_text(re.compile(r"\d+ % passend"))
            badges.first.wait_for(timeout=60000)

            # (a) Badge-Anzahl == aktive Jobs
            n_badges = badges.count()
            print(f"(a) Badges gefunden: {n_badges} (erwartet {n_jobs})")
            if n_badges != n_jobs:
                failures.append(f"(a) Badge-Anzahl {n_badges} != {n_jobs}")

            # (b) DOM-Reihenfolge == Erwartung (score DESC, Tie-Break id DESC)
            dom = []
            for i in range(n_badges):
                b = badges.nth(i)
                m_sc = re.search(r"(\d+) % passend", b.inner_text())
                card = b.locator(CARD_ANCESTOR)
                m_id = re.search(r"#(\d+)", card.inner_text())
                if not m_sc or not m_id:
                    failures.append(f"(b) Badge #{i}: Titel/Score unlesbar "
                                    f"(card={card.count()})")
                    continue
                dom.append((int(m_id.group(1)), int(m_sc.group(1))))
            print(f"(b) DOM-Reihenfolge: {dom}")
            if dom != expected:
                failures.append(f"(b) DOM {dom} != Erwartung {expected}")
            else:
                scores_only = [s for _, s in dom]
                if scores_only != sorted(scores_only, reverse=True):
                    failures.append("(b) Scores nicht absteigend")
                # Tie-Break: bei gleicher Score muss id DESC gelten
                for (id1, s1), (id2, s2) in zip(dom, dom[1:]):
                    if s1 == s2 and id2 > id1:
                        failures.append(f"(b) Tie-Break verletzt: #{id1} vor #{id2} "
                                        f"bei Score {s1}")
                        break

            # (c) score_bar im Expansion-Body des 1. Cards
            page.get_by_text("Details anzeigen").first.click()
            page.wait_for_timeout(600)
            bar_label = page.get_by_text(re.compile(r"^\d+/100$"))
            bar_ok = bar_label.count() > 0 or page.locator(".q-linear-progress").count() > 0
            print(f"(c) score_bar sichtbar: {bar_ok}")
            if not bar_ok:
                failures.append("(c) score_bar/N/100 im Expansion-Body nicht gefunden")

            # (d) Feature G (iii): Erklärungs-Expander „Warum passt das?" + Disclaimer
            why = page.get_by_text("Warum passt das?")
            why_ok = why.count() > 0
            print(f"(d) Expander „Warum passt das?' sichtbar: {why_ok}")
            if not why_ok:
                failures.append("(d) Expander „Warum passt das?' fehlt (Feature (iii))")
            else:
                why.first.click()
                page.wait_for_timeout(500)
                disc = page.get_by_text(re.compile(r"Startgewichten .*Feedback-Loop"))
                disc_ok = disc.count() > 0
                print(f"(d) Disclaimer sichtbar: {disc_ok}")
                if not disc_ok:
                    failures.append("(d) Disclaimer (Startgewichte/Feedback-Loop) fehlt")
        except Exception as ex:  # noqa: BLE001
            failures.append(f"Exception: {ex!r}")
        finally:
            browser.close()

    # DB-Baseline: reines Display, kein Write
    baseline_after = db_baseline()
    print(f"DB-Baseline vor: {baseline_before}")
    print(f"DB-Baseline nach: {baseline_after}")
    if baseline_after != baseline_before:
        failures.append(f"DB-Baseline veraendert: {baseline_before} -> {baseline_after}")

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"Task-Residue {residue} != 0")

    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: (a) Badges (b) Score-DESC/id-DESC == Erwartung (c) score_bar "
          "(d) Erklärungs-Expander+Disclaimer, DB unveraendert, Residue 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
