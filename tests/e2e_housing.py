"""D Housing E2E: HR-Klick 'Einstellen' -> Freigabe-Report mit Wohnungs-Abschnitt
-> Candidate-Onboarding zeigt Abschnitt (Code-Go 24.09.2026).

Spec: knowledge/portal/housing-search.md §§2/5, Plan entscheidungen.md
(USER-GO-Eintrag Code-Go). Tests NUR ueber echte Ausloeser (Portal-Klicks),
keine Hand-Queue-Payloads.

Ablauf:
1. Harness-Precheck (Server) + dynamische Kandidaten-Wahl: Kandidat mit
   'eingeladen'-Bewerbung UND 0 'eingestellt' (Datenkupplung06.10.2026 —
   cand1 hat inzwischen 3 davon), ggf. Passwort-Fixture (zurueckgesetzt)
2. Statischer MD-Check: Checklistenpunkt in 4 Templates
3. Employer-Login -> /employer/match -> Kandidaten-Card (per Klarnamen
   gescoped) -> 'Einstellen' -> Dialog-Bestaetigung 'Einstellen'.
   Do-Hire wirkt seit P0-3 auf die Bewerbung der angeklickten Aktionszeile
   (application_id) -> hired_app_id dynamisch aus DB.
4. onboarding_release-Task des UI-Klicks abwarten UND im E2E-Lauf
   deterministisch ausfuehren (e2e_isolation schaltet den Hintergrund-Runner
   ab, KMHR_RUNNER_AUTOSTART=0) -> report-{hired_app_id} enthaelt
   '## 🏠 Wohnungssuche (Checkliste + freie Quellen)'
5. Candidate-Login -> /candidate/onboarding -> Expansion oeffnen ->
   Wohnungs-Abschnitt sichtbar
6. Employer /employer/onboarding -> Karte des Kandidaten sichtbar
   (HR-Lesicht Spec §2.5, kein Report-Render dort)

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_housing.py
"""
import re
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import check_server, pre_max_tasks, db_residue_report, seed_email  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
HOUSING_HEADER = "## 🏠 Wohnungssuche (Checkliste + freie Quellen)"

# Test-Logins (Projekt-Testbestand, gleiche Quelle wie e2e_mentoring.py)
EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PASSWORD = "sicher123"
KNOWN_LOGINS = (
    (seed_email("batniniabdelkader@yahoo.com"), "Abdel15121978!"),
    (seed_email("e2e-beweis-phase1@example.com"), "E2EMentoring2026!"),
    (seed_email("recruiting.e2e.2809b@kmailtest.de"), "Test1234!"),
)
# Design-Entscheidung: Test-Passwort fuer Kandidaten ohne notiertes Login
HOUSING_PW = "E2EHousing2026!"

# dynamisch in pick_candidate() gesetzt
CAND_ID = 0
CAND_EMAIL = ""
CAND_PASSWORD = ""
CAND_NAME = ""
PW_FIXTURE: tuple[int, str | None] | None = None
# Fixture (AGENTS.md Klasse a, 13.10.2026): angelegte 'eingeladen'-Bewerbung,
# finally-Restore loescht sie wieder.
FIXTURE_APP: int | None = None

TEMPLATES = [
    ROOT / "knowledge" / "templates" / "onboarding-templates" / "onboarding-de.md",
    ROOT / "knowledge" / "templates" / "onboarding-templates" / "onboarding-fr.md",
    ROOT / "knowledge" / "templates" / "onboarding-templates" / "onboarding-ch.md",
    ROOT / "knowledge" / "onboarding-default.md",
]


def db_state() -> dict:
    conn = sqlite3.connect(str(DB))
    try:
        hired = conn.execute(
            "SELECT id FROM applications WHERE candidate_id=? AND status='eingestellt'",
            (CAND_ID,),
        ).fetchall()
        active = conn.execute(
            "SELECT id, status FROM applications WHERE candidate_id=? "
            "AND status IN ('eingegangen','angesehen','eingeladen')",
            (CAND_ID,),
        ).fetchall()
        cand = conn.execute(
            "SELECT email FROM candidates WHERE id=?", (CAND_ID,)
        ).fetchone()
        return {"hired": hired, "active": active,
                "cand_email": cand[0] if cand else None}
    finally:
        conn.close()


def seed_invited_candidate() -> bool:
    """Fixture (AGENTS.md Klasse a, 13.10.2026): waehlt einen benannten Kandidaten
    OHNE Bewerbung auf der Zielstelle und legt eine 'eingeladen'-Bewerbung auf einer
    aktiven employer-1-Stelle im Spiegel an (FIXTURE_APP). Finally-Restore loescht
    die Zeile wieder. Liefert False, wenn keine Wahl moeglich (-> echter FAIL)."""
    global CAND_ID, CAND_EMAIL, CAND_NAME, FIXTURE_APP
    conn = sqlite3.connect(str(DB))
    try:
        job = conn.execute(
            "SELECT id FROM jobs WHERE employer_id=1 AND status='aktiv' "
            "ORDER BY id LIMIT 1").fetchone()
        if not job:
            return False
        cand = conn.execute(
            "SELECT c.id, c.email, c.name FROM candidates c "
            "WHERE COALESCE(c.name,'') != '' "
            "  AND NOT EXISTS (SELECT 1 FROM applications a "
            "                  WHERE a.candidate_id=c.id AND a.job_id=?) "
            "  AND NOT EXISTS (SELECT 1 FROM applications a2 "
            "                  WHERE a2.candidate_id=c.id AND a2.status='eingestellt') "
            "  AND NOT EXISTS (SELECT 1 FROM applications a3 "
            "                  WHERE a3.candidate_id=c.id AND a3.status='eingeladen') "
            "ORDER BY c.id LIMIT 1", (job[0],)).fetchone()
        if not cand:
            return False
        cur = conn.execute(
            "INSERT INTO applications (candidate_id, job_id, status) "
            "VALUES (?, ?, 'eingeladen')", (cand[0], job[0]))
        FIXTURE_APP = cur.lastrowid
        conn.commit()
    except sqlite3.Error:
        return False
    finally:
        conn.close()
    CAND_ID, CAND_EMAIL, CAND_NAME = cand[0], cand[1], cand[2]
    print(f"OK Fixture: 'eingeladen'-Bewerbung #{FIXTURE_APP} cand{CAND_ID} "
          f"({CAND_NAME!r}) auf job{job[0]} (wird entfernt)")
    return True


def pick_candidate() -> bool:
    """Waehlt dynamisch den Hire-Kandidaten (Datenkupplung06.10.2026).

    Kriterien: >=1 Bewerbung 'eingeladen' (Klick 'Einstellen' ist legal, ALLOWED_TRANSITIONS)
    UND 0 'eingestellt' (Vorbedingung hired==1) UND Klarnamen (Card-Scoping).
    Fehlt ein passender Kandidat, stellt die Fixture (Klasse a, 13.10.2026) die
    Vorbedingung selbst her. Bekanntes Test-Login wird bevorzugt, sonst
    Passwort-Fixture (in restore() rueckgaengig).
    """
    global CAND_ID, CAND_EMAIL, CAND_PASSWORD, CAND_NAME, PW_FIXTURE
    conn = sqlite3.connect(str(DB))
    try:
        rows = conn.execute(
            "SELECT c.id, c.email, COALESCE(c.name,'') FROM candidates c "
            "WHERE COALESCE(c.name,'') != '' "
            "  AND EXISTS (SELECT 1 FROM applications a WHERE a.candidate_id=c.id "
            "              AND a.status='eingeladen') "
            "  AND NOT EXISTS (SELECT 1 FROM applications a2 WHERE a2.candidate_id=c.id "
            "                  AND a2.status='eingestellt') ORDER BY c.id"
        ).fetchall()
    finally:
        conn.close()
    if not rows and seed_invited_candidate():
        rows = [(CAND_ID, CAND_EMAIL, CAND_NAME)]
    if not rows:
        print("FAIL: kein Kandidat mit 'eingeladen' ohne 'eingestellt'-Bewerbung "
              "und Fixture nicht anlegbar (kein benannter Kandidat ohne Zielstellen-"
              "Bewerbung / keine aktive employer-1-Stelle)")
        return False
    known = dict(KNOWN_LOGINS)
    rows.sort(key=lambda r: (r[1] not in known, r[0]))
    CAND_ID, CAND_EMAIL, CAND_NAME = rows[0]
    CAND_PASSWORD = known.get(CAND_EMAIL)
    if CAND_PASSWORD is None:
        CAND_PASSWORD = HOUSING_PW
        conn = sqlite3.connect(str(DB))
        try:
            old = conn.execute(
                "SELECT password_hash FROM candidates WHERE id=?", (CAND_ID,)
            ).fetchone()[0]
            from webui.logic import hash_password_argon2id
            conn.execute("UPDATE candidates SET password_hash=? WHERE id=?",
                         (hash_password_argon2id(HOUSING_PW), CAND_ID))
            conn.commit()
        finally:
            conn.close()
        PW_FIXTURE = (CAND_ID, old)
        print(f"OK Passwort-Fixture: cand{CAND_ID} ({CAND_EMAIL})")
    print(f"OK Kandidat dynamisch: #{CAND_ID} {CAND_NAME!r} ({CAND_EMAIL})")
    return True


def run_onboarding_release(app_id: int, timeout_s: int = 60) -> str | None:
    """Fuehrt den vom UI-Klick gequeueten onboarding_release-Task aus.

    e2e_isolation.py startet die App mit KMHR_RUNNER_AUTOSTART=0 — ohne diese
    Simulation laeuft kein Hintergrund-Runner und der Report entsteht nie
    (Ursache des roten Laufs, 06.10.2026). Muster: tests/e2e_contract_preflight.py
    (`_load_runner`), aber hier mit echtem process_task + DRY_RUN, damit kein
    Mailversand stattfindet.
    """
    deadline = time.time() + timeout_s
    row = None
    while time.time() < deadline:
        conn = sqlite3.connect(str(DB))
        try:
            row = conn.execute(
                "SELECT id, payload FROM agent_tasks WHERE task_type='onboarding_release' "
                "AND status='pending' AND json_extract(payload,'$.application_id')=? "
                "ORDER BY id DESC LIMIT 1", (app_id,)).fetchone()
        finally:
            conn.close()
        if row:
            break
        time.sleep(2)
    if not row:
        return f"kein pending onboarding_release-Task fuer app{app_id}"

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "agent_runner_e2e_housing", ROOT / "scripts" / "agent-runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB_PATH = Path(DB)
    mod.DRY_RUN = True
    conn = sqlite3.connect(str(DB))
    try:
        mod.process_task(conn, row[0], "onboarding_release", row[1], 0)
    finally:
        conn.close()
    print(f"OK runner simulation: Task #{row[0]} (app{app_id}, DRY_RUN)")
    return None


def report_path(app_id: int) -> Path:
    return ROOT / "ergebnisse" / f"onboarding-freigabe-bewerbung-{app_id}.md"


def check_templates() -> list:
    failures = []
    for path in TEMPLATES:
        if not path.exists():
            failures.append(f"Template fehlt: {path.name}")
            continue
        text = path.read_text(encoding="utf-8")
        if "Wohnungssuche" not in text and "Recherche de logement" not in text:
            failures.append(f"Template ohne Wohnungs-Punkt: {path.name}")
        else:
            print(f"OK template: {path.name}")
    return failures


def _panel(page, button_pattern: str):
    return page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile(button_pattern, re.I))
    ).first


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(700)
    panel = _panel(page, "Arbeitgeber-Login")
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PASSWORD)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def login_candidate(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    panel = page.locator(".q-tab-panel:visible").first
    panel.get_by_label("E-Mail").fill(CAND_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(CAND_PASSWORD)
    panel.get_by_role("button").first.click()
    page.wait_for_url("**/candidate**", timeout=15000)


def wait_for_report(app_id: int, timeout_s: int = 90) -> bool:
    rep = report_path(app_id)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if rep.exists() and HOUSING_HEADER in rep.read_text(
            encoding="utf-8", errors="replace"
        ):
            return True
        time.sleep(2)
    return False


def main() -> int:
    check_server()
    if not pick_candidate():
        # Klasse a (13.10.2026): die Fixture stellt die Vorbedingung her; scheitert
        # das, ist das ein echter FAIL (kein SKIP-Weichspuelen, AGENTS.md Schritt 3).
        return 1
    pre = pre_max_tasks()
    failures = []
    before = db_state()
    print(f"Baseline: {before}")
    # Restore-Baseline (Teil-2-Residue-Fix 25.09.2026, Phase-E Runde 6): der
    # Hire-Klick darf keine bleibende Residue hinterlassen (sonst Vorb.-Fail
    # wie App #27 am 24.09. und Bruch fuer e2e_c7_downloads).
    _conn0 = sqlite3.connect(str(DB))
    pre_flip = {r[0]: (r[1], r[2]) for r in _conn0.execute(
        "SELECT id, status, aktualisiert_am FROM applications WHERE candidate_id=?",
        (CAND_ID,))}
    pre_hist_max = _conn0.execute(
        "SELECT COALESCE(MAX(id),0) FROM application_status_history").fetchone()[0]
    _conn0.close()
    print(f"Restore-Baseline: {len(pre_flip)} Apps, hist_max={pre_hist_max}")
    if before["hired"]:
        print(f"FAIL: cand{CAND_ID} hat bereits eingestellte Bewerbung: {before['hired']}")
        return 1
    if not before["active"]:
        print(f"FAIL: cand{CAND_ID} hat keine aktive Bewerbung")
        return 1
    if before["cand_email"] != CAND_EMAIL:
        print(f"FAIL: cand{CAND_ID} E-Mail {before['cand_email']!r} != {CAND_EMAIL!r}")
        return 1
    # Vorlauf-Cleanup: alter Report ohne Wohnungs-Abschnitt (von altem Runner)
    for app_row in before["active"]:
        stale = report_path(app_row[0])
        if stale.exists() and HOUSING_HEADER not in stale.read_text(
            encoding="utf-8", errors="replace"
        ):
            stale.unlink()
            print(f"removed stale report-{app_row[0]} (ohne Wohnungs-Abschnitt)")

    failures.extend(check_templates())

    hired_app_id = None
    created_report: int | None = None  # Report-Vorhandensein VOR dem Lauf merken

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            # ── 1) Employer: Einstellen-Klick (Variante A, echter Trigger) ──
            ctx_emp = browser.new_context()
            page_emp = ctx_emp.new_page()
            page_emp.set_default_timeout(60000)
            login_employer(page_emp)
            page_emp.goto(f"{BASE}/employer/match", wait_until="load", timeout=90000)
            page_emp.wait_for_timeout(3000)

            # Kandidaten-Card nach KLARNAMEN gescopen (`.q-card` mit
            # has_text reichte vorher fuer 'batnini' — der Name ist jetzt
            # dynamisch, Datenkupplung06.10.2026)
            # P0-3 (29.09.2026): Aktionen sind zustandsbewusst — 'Einstellen' erscheint nur
            # bei Bewerbungen im Status 'eingeladen' (frueher: immer 3 globale Buttons).
            cand_card = page_emp.locator(".q-card", has_text=re.compile(
                re.escape(CAND_NAME), re.I)).filter(
                has=page_emp.get_by_role("button", name="Einstellen")
            ).first
            if cand_card.count() == 0:
                raise AssertionError(
                    f"keine Match-Card mit 'Einstellen' fuer {CAND_NAME!r}")
            cand_card.scroll_into_view_if_needed()
            page_emp.wait_for_timeout(500)

            hire_btn = cand_card.get_by_role("button", name="Einstellen").first
            hire_btn.scroll_into_view_if_needed()
            hire_btn.click()
            page_emp.wait_for_timeout(1000)

            # Dialog-Bestaetigung (zweiter 'Einstellen'-Button in .q-dialog)
            dialog = page_emp.locator(".q-dialog")
            dialog.get_by_role("button", name="Einstellen").click()
            page_emp.wait_for_timeout(2500)

            mid = db_state()
            if len(mid["hired"]) != 1:
                failures.append(f"DB cand{CAND_ID} nach Klick: hired={mid['hired']}")
                hired_app_id = None
            else:
                hired_app_id = mid["hired"][0][0]
                if not report_path(hired_app_id).exists():
                    created_report = hired_app_id
                print(f"OK hire click: app{hired_app_id} status=eingestellt")

            # ── 2) Runner-Task ausfuehren (isolation: kein Hintergrund-Runner)
            #        und Report mit Wohnungs-Abschnitt abwarten ──
            if hired_app_id:
                err = run_onboarding_release(hired_app_id)
                if err:
                    failures.append(f"Runner-Simulation: {err}")
            if hired_app_id and wait_for_report(hired_app_id):
                print(f"OK report: onboarding-freigabe-bewerbung-{hired_app_id}.md "
                      "enthaelt Wohnungs-Abschnitt")
            elif hired_app_id:
                rep = report_path(hired_app_id)
                failures.append(
                    f"Report-{hired_app_id} ohne {HOUSING_HEADER!r} nach 90s "
                    f"(exists={rep.exists()})"
                )

            # ── 3) Candidate: Wohnungs-Abschnitt im Onboarding-Tab ──
            ctx_cand = browser.new_context()
            page_cand = ctx_cand.new_page()
            page_cand.set_default_timeout(60000)
            login_candidate(page_cand)
            page_cand.goto(f"{BASE}/candidate/onboarding", wait_until="load",
                           timeout=90000)
            page_cand.wait_for_timeout(3500)

            exp_items = page_cand.locator(".q-expansion-item")
            housing_seen = False
            for i in range(exp_items.count()):
                item = exp_items.nth(i)
                try:
                    item.locator(".q-item").first.click()
                    page_cand.wait_for_timeout(800)
                except Exception:
                    pass
                try:
                    if page_cand.get_by_text("Wohnungssuche (Checkliste + freie Quellen)").first.is_visible(timeout=2000):
                        housing_seen = True
                        break
                except Exception:
                    continue
            if housing_seen:
                print("OK candidate sees housing section")
            else:
                failures.append("Candidate-Onboarding zeigt Wohnungs-Abschnitt nicht")
            ctx_cand.close()

            # ── 4) Employer: Onboarding-Karte cand1 = eingestellt (HR-Lesicht) ──
            page_emp.goto(f"{BASE}/employer/onboarding", wait_until="load",
                          timeout=90000)
            page_emp.wait_for_timeout(2500)
            try:
                card = page_emp.locator(".q-card", has_text=re.compile(
                    re.escape(CAND_NAME), re.I)).first
                if card.count() and card.is_visible(timeout=5000):
                    print(f"OK employer onboarding card for cand{CAND_ID} visible")
                else:
                    failures.append(
                        f"Employer-Onboarding: Karte cand{CAND_ID} nicht sichtbar")
            except Exception as e:
                failures.append(f"Employer-Onboarding Karte: {e}")
            ctx_emp.close()

        except Exception as e:
            failures.append(f"Exception: {e}")
        finally:
            browser.close()
            # Restore (Teil-2 25.09.2026): Hire-Flip rueckgaengig + History-Zeile
            # des UI-Klicks entfernt -> PRE_HIST_COUNT=21 und c7-Vorbedingung stabil.
            _conn9 = sqlite3.connect(str(DB))
            for _aid, (_st, _ts) in pre_flip.items():
                _conn9.execute(
                    "UPDATE applications SET status=?, aktualisiert_am=? WHERE id=?",
                    (_st, _ts, _aid))
            _conn9.execute("DELETE FROM application_status_history WHERE id > ?",
                           (pre_hist_max,))
            # Test-Residue aus der Runner-Simulation entfernen (Task-Zeile +
            # von dieser Runde erzeugter Report), damit db_residue_report(pre)
            # == 0 bleibt und der naechste Lauf den Report echt prueft.
            if hired_app_id:
                _conn9.execute(
                    "DELETE FROM agent_tasks WHERE task_type='onboarding_release' "
                    "AND json_extract(payload,'$.application_id')=?", (hired_app_id,))
            if FIXTURE_APP:
                # Fixture (Klasse a): angelegte Bewerbung wieder entfernen.
                _conn9.execute("DELETE FROM applications WHERE id=?", (FIXTURE_APP,))
            _conn9.commit()
            _conn9.close()
            if created_report is not None:
                _rep = report_path(created_report)
                if _rep.exists():
                    _rep.unlink()
                    print(f"removed report-{created_report} (Test-Erzeugnis)")
            if PW_FIXTURE is not None:
                _cid, _old = PW_FIXTURE
                _conn9 = sqlite3.connect(str(DB))
                _conn9.execute("UPDATE candidates SET password_hash=? WHERE id=?",
                               (_old, _cid))
                _conn9.commit()
                _conn9.close()
                print(f"OK Passwort-Fixture zurueckgesetzt: cand{_cid}")
            _final = db_state()
            print(f"Final (nach Restore): {_final}")
            if _final["hired"]:
                failures.append(f"Restore hired: {_final['hired']} nicht leer")
            # Vor dem Restore angelegte Fixture-Bewerbung zaehlt nicht als Diff.
            _exp_active = ([r for r in before["active"] if r[0] != FIXTURE_APP]
                           if FIXTURE_APP else before["active"])
            if _final["active"] != _exp_active:
                failures.append(
                    f"Restore active: {_final['active']} != {_exp_active}")

    # Klasse a (14.10.2026): db_residue_report Rückgabe an failures anbinden
    # (alle Schwester-Skripte machen das; diese Datei hat es verworfen)
    _residue = db_residue_report(pre)
    if _residue:
        failures.append(f"DB-Residue nach Restore: {_residue}")
    if failures:
        print("E2E HOUSING FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("E2E HOUSING PASS (hire click -> report housing -> candidate view -> hr card)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
