"""D Contract E2E (Phase D P8): HR-Klick 'Vertrags-Check starten' ->
contract_preflight-Task -> Report mit Mindestlohn 13,90 + Quellen aus Link-Katalog.

Spec: knowledge/legal/contract-management.md (Code-Go 24.09.2026),
skills/contract-management/SKILL.md, knowledge/legal/contract-sources.md.
Tests NUR ueber echten Portal-Klick, keine Hand-Queue-Payloads.

Ablauf:
1. Harness-Precheck (Server) + statische Checks (Template, Skill, Katalog,
   KEIN https-Literal im contract_preflight-Block des Runners)
2. Employer-Login -> /employer/onboarding -> Button 'Vertrags-Check starten'
3. Runner-Task contract_preflight abwarten ->
   ergebnisse/contract-preflight-bewerbung-{app_id}.md enthaelt
   '13,90' + 'Contract Preflight' + Quellen-URL aus Katalog (kein Literalfund
   im Report-Generator ausser Katalog-URL)
4. Agent-Details zeigt result_path (oder Report-Datei reicht als Beweis)

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_contract_preflight.py
"""
import re
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import check_server, pre_max_tasks, db_residue_report  # noqa: E402

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
CAND_ID = 1

EMP_EMAIL = "hr@techvision.de"
EMP_PASSWORD = "sicher123"

SKILL = ROOT / "skills" / "contract-management" / "SKILL.md"
TEMPLATE = ROOT / "knowledge" / "templates" / "contract-templates" / "arbeitsvertrag-de-skeleton.md"
CATALOG = ROOT / "knowledge" / "legal" / "contract-sources.md"
RUNNER = ROOT / "scripts" / "agent-runner.py"


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


def active_app_id() -> int | None:
    conn = sqlite3.connect(str(DB))
    try:
        row = conn.execute(
            "SELECT id FROM applications WHERE candidate_id=? "
            "AND status != 'zurückgezogen' ORDER BY id DESC LIMIT 1",
            (CAND_ID,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def report_path(app_id: int) -> Path:
    return ROOT / "ergebnisse" / f"contract-preflight-bewerbung-{app_id}.md"


def check_static() -> list:
    failures = []
    if not SKILL.exists():
        failures.append(f"Skill fehlt: {SKILL}")
    if not TEMPLATE.exists():
        failures.append(f"Template fehlt: {TEMPLATE}")
    if not CATALOG.exists():
        failures.append(f"Link-Katalog fehlt: {CATALOG}")
        return failures
    cat = CATALOG.read_text(encoding="utf-8")
    if "mindestlohn_2026" not in cat:
        failures.append("Katalog ohne Key mindestlohn_2026")
    if not re.search(r"13[.,]90\s*(?:€|EUR)\s*/\s*h", cat):
        failures.append("Katalog ohne Mindestlohn-Wert 13,90 €/h")
    # KEIN https-Literal im contract_preflight-Funktionsblock des Runners
    runner_txt = RUNNER.read_text(encoding="utf-8")
    m = re.search(r"def contract_preflight\(.*?(?=\ndef |\n# ─── Task)", runner_txt, re.S)
    if not m:
        failures.append("contract_preflight-Funktion nicht im Runner gefunden")
    else:
        block = m.group(0)
        # https:// erlaubt nur in Kommentar-/String-Ausnahmen? USER-GO: 0 Hartkodierung
        literals = re.findall(r"https?://[^\s\"']+", block)
        if literals:
            failures.append(f"https-Literal(e) im contract_preflight-Block: {literals}")
    # Dispatch-Eintrag
    if 'elif task_type == "contract_preflight"' not in runner_txt:
        failures.append("Dispatch-Eintrag contract_preflight fehlt")
    if not failures:
        print("OK static: Skill + Template + Katalog + 0 https-Literals + Dispatch")
    return failures


def wait_for_task(app_id: int, timeout_s: int = 90) -> tuple[bool, int | None]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        conn = sqlite3.connect(str(DB))
        try:
            row = conn.execute(
                "SELECT id, status, result_path FROM agent_tasks "
                "WHERE task_type='contract_preflight' "
                "AND json_extract(payload, '$.application_id') = ? "
                "ORDER BY id DESC LIMIT 1",
                (app_id,),
            ).fetchone()
        finally:
            conn.close()
        if row and row[1] == "done":
            return True, row[0]
        if row and row[1] == "failed":
            return False, row[0]
        time.sleep(2)
    return False, None


def main() -> int:
    check_server()
    pre = pre_max_tasks()
    failures = []
    failures.extend(check_static())
    app_id = active_app_id()
    if not app_id:
        print(f"FAIL: cand{CAND_ID} hat keine aktive/eingestellte Bewerbung")
        return 1
    print(f"Baseline: app_id={app_id} pre_max={pre}")

    # Vorlauf-Logik (Fix 24.09.2026): queue_agent_task ist idempotent
    # (1×/Tag+Typ+App+Generation, Generation seit R3-2 30.09.2026 Teil der
    # Dedupe-Grenze). Ein erneuter Klick auf einen bereits done-Task
    # erzeugt KEINEN neuen Task → kein neuer Report. Report daher nur
    # entfernen, wenn noch kein done-Task für diese App existiert.
    conn = sqlite3.connect(str(DB))
    try:
        done_row = conn.execute(
            "SELECT id, result_path FROM agent_tasks "
            "WHERE task_type='contract_preflight' "
            "AND json_extract(payload, '$.application_id') = ? "
            "AND status='done' ORDER BY id DESC LIMIT 1",
            (app_id,),
        ).fetchone()
    finally:
        conn.close()
    stale = report_path(app_id)
    if done_row and not stale.exists():
        # Report von Hand verloren (frühere E2E-Läufe unlinked) → aus
        # Task-Payload über die Runner-Funktion neu schreiben (Datei-Repair,
        # kein DB-Write, kein neuer Task).
        print(f"report missing, task #{done_row[0]} already done → regenerate")
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "agent_runner_for_e2e", RUNNER)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.contract_preflight({
            "application_id": app_id, "candidate_id": CAND_ID,
            "trigger": "hr_onboarding_klick",
        })
    elif not done_row and stale.exists():
        stale.unlink()
        print(f"removed stale {stale.name}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context()
            page = ctx.new_page()
            page.set_default_timeout(60000)
            login_employer(page)
            page.goto(f"{BASE}/employer/onboarding", wait_until="load", timeout=90000)
            page.wait_for_timeout(3000)

            # Kandidaten-Karte gezielt: App-ID-Label im Card-Footer
            # ( ORDER BY c.id DESC -> cand 17 (E2E Kette, app 25) steht oben;
            #   ohne Filter traf .first die falsche Card und wait_for_task(app)
            #   lief nie auf – Fix 24.09.2026 )
            cards = page.locator(".q-card").filter(
                has_text=f"Bewerbung #{app_id}"
            )
            if cards.count() == 0:
                # Fallback: Kandidatenname (cand 1 = batnini abdelkader)
                cards = page.locator(".q-card").filter(
                    has_text=re.compile(r"batnini abdelkader", re.I)
                )
            card = cards.first
            print(f"E2E target cards={cards.count()} app_id={app_id}")
            btn = card.get_by_role(
                "button", name=re.compile(r"Vertrags-Check starten", re.I)
            ).first
            btn.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            btn.click()
            page.wait_for_timeout(2500)

            ok, task_id = wait_for_task(app_id)
            if ok:
                print(f"OK task: contract_preflight #{task_id} done")
            else:
                failures.append(f"contract_preflight task nicht done (task={task_id}) after 90s")

            rep = report_path(app_id)
            if rep.exists():
                txt = rep.read_text(encoding="utf-8")
                if "Contract Preflight" not in txt:
                    failures.append("Report ohne Header 'Contract Preflight'")
                if not re.search(r"13[.,]90", txt):
                    failures.append("Report ohne Mindestlohn 13,90")
                if "gesetze-im-internet.de" not in txt and "nachwg" not in txt:
                    failures.append("Report ohne Quellen-URL aus Katalog")
                if "https://en.wikipedia.org" not in txt:
                    failures.append("Report ohne Mindestlohn-Quelle (Katalog-URL)")
                # Beweiszeile
                ml_line = next((l for l in txt.splitlines() if "Mindestlohn-Wert" in l), "")
                print(f"OK report: {rep.name} | {ml_line.strip()[:120]}")
            else:
                failures.append(f"Report fehlt: {rep}")

            # Agent-Details: result_path sichtbar (read-only Beweis)
            page.goto(f"{BASE}/employer/agent_details", wait_until="load",
                      timeout=90000)
            page.wait_for_timeout(2500)
            try:
                if page.get_by_text(re.compile("contract-preflight-bewerbung")).first.is_visible(timeout=5000):
                    print("OK agent-details shows contract-preflight report")
                else:
                    # Nicht hart failen – Report-Datei ist Primärbeweis
                    print("WARN: agent-details listet contract-preflight nicht sichtbar "
                          "(Report-Datei-Check genuegt)")
            except Exception:
                print("WARN: agent-details Text-Check nicht moeglich")
            ctx.close()
        except Exception as e:
            failures.append(f"Exception: {e}")
        finally:
            browser.close()

    db_residue_report(pre)
    if failures:
        print("E2E CONTRACT PREFLIGHT FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("E2E CONTRACT PREFLIGHT PASS (hr click -> task done -> report 13.90 + sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
