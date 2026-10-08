"""P3 E2E (view-only) + P8.2: Agent-Details — Badges/Berichte aus der DB.

P8.2 (08.10.2026): Datenquelle ist `agent_tasks.result_json["text"]`
(db.get_candidate_agent_tasks) statt lokaler `ergebnisse/*.md`.
Spec: knowledge/system/p8-cloud-datenquellen.md.

Das Skript ist SELBST-SÄEND und damit unabhängig von Live-Kandidatennamen —
dadurch auch im CI (anonymisierter Seed) lauffähig. NUR isoliert: ohne
`KMHR_DB_PATH` wird nichts geschrieben und der Test endet als SKIP (rc=0).

Ablauf (isoliert via tests/e2e_isolation.py — NIE :8080):
1. Employer-Login → /employer/agent_details
2. Kandidat "Z E2E P8.2 Leer" (keine Tasks) → 9x "Kein Bericht vorhanden" (⚪)
3. Kandidat "Z E2E P8.2 Legacy" (9 Tasks `done`, OHNE `text`) → 9 Expander,
   Badge aus Status = 🟢, je Expander Hinweis "Kein Berichtstext gespeichert (Altbestand)"
4. Kandidat "Z E2E P8.2 DB-Text" (echtes `result_json["text"]`):
   - check_visa  → 🔴 ("Visum-Status: ERFORDERLICH")
   - check_gdpr  → 🟢 ("DSGVO-Status: KONFORM")
   - verify_documents → 🟡 ("Gesamtstatus: UNBEKANNT")
   Visa-Expander öffnen → Volltext sichtbar
5. Sichtbarkeit der Task-Queue (DB) prüfen

Ausfuehren: python3 tests/e2e_isolation.py --port <frei> --only e2e_agent_details
"""
import json
import os
import re
import sqlite3
import sys

from playwright.sync_api import sync_playwright

from e2e_harness import BASE, DB, check_server, db_residue_report, pre_max_tasks, seed_email

EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"

CAND_LEER = "Z E2E P8.2 Leer"
CAND_LEGACY = "Z E2E P8.2 Legacy"
CAND_TEXT = "Z E2E P8.2 DB-Text"
LEGACY_HINT = "Kein Berichtstext gespeichert (Altbestand)"
LEGACY_TASK_TYPES = [
    "extract_profile", "match_candidate", "check_compliance", "assess_culture_fit",
    "verify_documents", "check_visa", "check_gdpr", "explain_match", "notify_user",
]
DB_TEXT_TASKS = [
    ("check_visa", "Visum-Status: ERFORDERLICH"),
    ("check_gdpr", "DSGVO-Status: KONFORM"),
    ("verify_documents", "Gesamtstatus: UNBEKANNT"),
]


def seed():
    """Sät 3 Kandidaten mit Tasks in die (Wegwerf-)Spiegel-DB.

    NUR isoliert (KMHR_DB_PATH gesetzt) — sonst None (kein Live-Schreibzugriff).
    Gibt die angelegten IDs zurück (für `cleanup`), weil alle E2E-Skripte desselben
    Isolationslaufs EINE Spiegel-DB teilen → Reste würden spätere Skripte verfälschen.
    Alle `agent_tasks.created_at` bewusst auf einem Alt-Datum (F3-Residue=0).
    """
    if not os.environ.get("KMHR_DB_PATH"):
        return None
    conn = sqlite3.connect(DB)
    created = {"candidates": [], "applications": [], "agent_tasks": []}
    try:
        cur = conn.cursor()

        def _cand(name: str, email: str) -> int:
            cur.execute(
                "INSERT INTO candidates (email, password_hash, name, status) VALUES (?, 'x', ?, 'registriert')",
                (email, name),
            )
            cid = cur.lastrowid
            created["candidates"].append(cid)
            cur.execute(
                "INSERT INTO applications (candidate_id, job_id, status) VALUES (?, 1, 'eingegangen')",
                (cid,),
            )
            created["applications"].append(cur.lastrowid)
            return cur.lastrowid

        _cand(CAND_LEER, "z-e2e-p82-leer@example.com")
        app_l = _cand(CAND_LEGACY, "z-e2e-p82-legacy@example.com")
        for ttype in LEGACY_TASK_TYPES:
            cur.execute(
                "INSERT INTO agent_tasks (task_type, status, payload, result_json, created_at)"
                " VALUES (?, 'done', ?, NULL, '2020-01-01 00:00:00')",
                (ttype, json.dumps({"application_id": app_l, "gen": 0})),
            )
            created["agent_tasks"].append(cur.lastrowid)
        app_t = _cand(CAND_TEXT, "z-e2e-p82-text@example.com")
        for ttype, text in DB_TEXT_TASKS:
            cur.execute(
                "INSERT INTO agent_tasks (task_type, status, payload, result_json, created_at)"
                " VALUES (?, 'done', ?, ?, '2020-01-01 00:00:00')",
                (ttype, json.dumps({"application_id": app_t, "gen": 0}),
                 json.dumps({"text": text, "agent_chars": len(text), "result_path": "/x"})),
            )
            created["agent_tasks"].append(cur.lastrowid)
        conn.commit()
        return created
    finally:
        conn.close()


def cleanup(created) -> None:
    """Entfernt die gesäten Zeilen wieder (Reihenfolge: Tasks → Applications → Kandidaten)."""
    if not created:
        return
    conn = sqlite3.connect(DB)
    try:
        for tid in created["agent_tasks"]:
            conn.execute("DELETE FROM agent_tasks WHERE id = ?", (tid,))
        for aid in created["applications"]:
            conn.execute("DELETE FROM applications WHERE id = ?", (aid,))
        for cid in created["candidates"]:
            conn.execute("DELETE FROM candidates WHERE id = ?", (cid,))
        conn.commit()
    finally:
        conn.close()


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="load", timeout=20000)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I))
    ).first
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def select_field(page, label, value):
    el = page.get_by_label(label, exact=True)
    el.click()
    page.wait_for_timeout(250)
    opt = page.get_by_role("option", name=str(value), exact=True)
    if opt.count() == 0:
        opt = page.get_by_text(str(value), exact=True).last
    opt.first.click()
    page.wait_for_timeout(500)


def main() -> int:
    check_server()
    created = seed()
    if created is None:
        print("SKIP: e2e_agent_details braucht die isolierte Spiegel-DB (KMHR_DB_PATH) "
              "— kein Seed, kein Live-Schreibzugriff.")
        return 0
    pre_tasks = pre_max_tasks()
    fails = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            login_employer(page)
            page.goto(f"{BASE}/employer/agent_details", wait_until="load", timeout=20000)
            page.wait_for_timeout(1200)

            # ── 2. Leer: keine Tasks → 9x ⚪ ──
            select_field(page, "Kandidat", CAND_LEER)
            n_empty = page.get_by_text("Kein Bericht vorhanden").count()
            if n_empty != 9:
                fails.append(f"leer: {n_empty}x 'Kein Bericht vorhanden' (erwartet 9)")
            if page.get_by_text("Status-Übersicht:").count() < 1:
                fails.append("leer: 'Status-Übersicht:' fehlt")

            # ── 3. Legacy: 9 Tasks ohne text → 9x Hinweis + 🟢 ──
            select_field(page, "Kandidat", CAND_LEGACY)
            if page.get_by_text("Kein Bericht vorhanden").count() != 0:
                fails.append("legacy: unerwartete 'Kein Bericht'-Meldungen")
            n_legacy = page.get_by_text(LEGACY_HINT).count()
            if n_legacy != 9:
                fails.append(f"legacy: {n_legacy}x Legacy-Hinweis (erwartet 9)")
            for lbl in ("Visum pruefen", "Dokumente verifizieren", "DSGVO pruefen"):
                if page.get_by_text(re.compile(rf"^🟢 \S+ {re.escape(lbl)} \(")).count() < 1:
                    fails.append(f"legacy: '{lbl}'-Expander nicht 🟢 (Status-Fallback)")

            # ── 4. DB-Text: Farben + Volltext ──
            select_field(page, "Kandidat", CAND_TEXT)
            if page.get_by_text(re.compile(r"🔴 🛂 Visum pruefen \(")).count() < 1:
                fails.append("db-text: Visum nicht 🔴 (ERFORDERLICH)")
            if page.get_by_text(re.compile(r"🟢 🔒 DSGVO pruefen \(")).count() < 1:
                fails.append("db-text: DSGVO nicht 🟢 (KONFORM)")
            if page.get_by_text(re.compile(r"🟡 📄 Dokumente verifizieren \(")).count() < 1:
                fails.append("db-text: Dokumente nicht 🟡 (UNBEKANNT)")
            visa = page.get_by_text(re.compile(r"🔴 🛂 Visum pruefen \(")).first
            visa.click()
            page.wait_for_timeout(400)
            if page.get_by_text("Visum-Status: ERFORDERLICH").count() < 1:
                fails.append("db-text: Visa-Volltext aus result_json nicht sichtbar")

            # ── 5. Task-Queue ──
            if page.get_by_text("Task-Queue (Datenbank)").count() < 1:
                fails.append("queue: 'Task-Queue (Datenbank)' fehlt")

        except Exception as e:  # noqa: BLE001
            fails.append(f"EXC: {type(e).__name__}: {e}")
        finally:
            browser.close()

    cleanup(created)
    residue = db_residue_report(pre_tasks)
    if residue:
        fails.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if fails:
        print("FAIL:")
        for f in fails:
            print(f" - {f}")
        return 1
    print("PASS: P8.2 Agent-Details aus der DB — 9x-Looper, DB-Text + Legacy-Fallback, "
          "🔴/🟢/🟡 + Visa-Volltext + Queue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
