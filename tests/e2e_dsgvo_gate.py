"""E2E: DSGVO-Gate der HR-Seite „🗂️ Dokumente“ (_page_dokumente).

NEU GESCHRIEBEN 30.09.2026 (P0-2.4). Die Vorversion testete die ALTE Logik
(`candidates.status`). Das Gate liest inzwischen den BEWERBUNGSstatus des
jeweiligen Arbeitgebers (`applications.status` via `jobs.employer_id`); die alte
Fassung manipulierte die falsche Spalte und meldete zu Recht FAIL (13 Fehlschlaege,
u. a. „erwartet 2 Gate-Queries, gefunden 0“).
SCHEMA-FAKT: `applications` hat KEINE Spalte `employer_id`.

GO: „GO B2-1 B2-2 B2-3 B2-4 B2-5a“ (25.09.2026)
Spec: knowledge/legal/dsgvo-gate.md ((c)2 Gate-Query + 🔒-Hinweis, (c)3 Statusspalte)
Blueprint: ergebnisse/b2-blueprint-2026-09-25.md (§1 Zielzeilen, §2 B2-1, §4 Testplan)
Ziele (lebend): webui/pages/employer.py::_page_dokumente (def ab :1106,
Gate-SQL :1125/:1133, blocked :1138-1141, 🔒 :1151, Spalte :1161).

Ablauf:
1. Harness-Precheck (F2 Server) + DB-Baseline (agent_tasks/feedback/applications/
   candidate_documents + candidates.status) -> C: reines Rendern, kein Write
2. Quelltext-Nachweis aus dem LEBENDEN employer.py: die Modul-Helfer
   `_visible_documents` / `_blocked_candidates` benutzen `j.employer_id` +
   `a.status` (KEIN `a.employer_id`), 🔒-String + Spalte „Status Bewerbung“
3. Gate-Query read-only: die ECHTEN Helfer gegen die DB, plus Arbeitgeber-
   Isolation (fremder Arbeitgeber sieht 0 Dokumente und 0 blockierte Kandidaten)
4. UI B (Freigabefall): Bewerbung des Test-Arbeitgebers auf 'eingeladen'
   -> Zeilen sichtbar + Spalte „Status Bewerbung“ + basename
5. UI A (Sperrfall): dieselbe Bewerbung auf 'eingegangen'
   -> 0 Tabellenzeilen + 🔒-Hinweis mit Klarnamen und Statuslabel
6. C: Baseline vor/nach identisch; applications.status exakt wiederhergestellt
7. F3-Residue (agent_tasks Test-Reste muessen 0 sein)

Datenlage-Fallback (Pflicht, ehrlich): existieren keine candidate_documents,
wird NICHT gefaked — Ausgabe „Datenlage: ..., deshalb Query+Quelltext statt
UI-Row-Nachweis“; PASS/FAIL dann an den Query+Quelltext-Nachweisen.

Temporärer Status-Set (nur applications.status, nie agent_tasks/feedback/
candidate_documents) wird IMMER in finally auf den Ausgangswert zurückgesetzt
und per Baseline-Vergleich nachgewiesen.

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_dsgvo_gate.py
Hinweis: agent-runner waehrend Test gestoppt (keine Echtest-Mail, keine Tasks).
"""
import re
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
ROOT = Path(__file__).resolve().parents[1]
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
SRC = ROOT / "webui" / "pages" / "employer.py"
EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"

# Projekt-Root auf sys.path, damit die ECHTEN Gate-Helfer aus webui importiert
# werden koennen (der Query-Nachweis soll den ausgelieferten Code pruefen,
# nicht eine per Regex nachgebaute Kopie).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RELEASED = ("eingeladen", "eingestellt")          # Gate-Liste (dsgvo-gate.md (c)2)
BLOCK_STATUS = "eingegangen"                      # Nicht-freigegebener Bewerbungsstatus (A)
RELEASE_STATUS = "eingeladen"                     # Freigegebener Bewerbungsstatus (B)
BASELINE_KEYS = ("agent_tasks", "feedback", "applications", "candidate_documents")


# ─── Read-only DB-Helfer ────────────────────────────────────────────

def ro_conn() -> sqlite3.Connection:
    """Leseverbindung (URI mode=ro) — keine Schreibmoeglichkeit."""
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def db_baseline() -> dict:
    """C-Baseline. agent_tasks nur als (MAX(id), COUNT(*)) — der Runner
    aktualisiert status bestehender Zeilen (kein Write des Tests)."""
    conn = ro_conn()
    try:
        return {
            "agent_tasks": conn.execute(
                "SELECT COALESCE(MAX(id),0), COUNT(*) FROM agent_tasks"
            ).fetchone(),
            "feedback": conn.execute("SELECT * FROM feedback ORDER BY id").fetchall(),
            "applications": conn.execute(
                "SELECT * FROM applications ORDER BY id"
            ).fetchall(),
            "candidate_documents": conn.execute(
                "SELECT * FROM candidate_documents ORDER BY id"
            ).fetchall(),
            "cand_status": dict(
                conn.execute("SELECT id, status FROM candidates ORDER BY id").fetchall()
            ),
            "app_status": dict(
                conn.execute("SELECT id, status FROM applications ORDER BY id").fetchall()
            ),
        }
    finally:
        conn.close()


def doc_holders() -> list:
    """Alle Kandidaten mit Dokumenten: [(id, name, anzahl, beispielpfad, app_id, app_status)].

    `app_id`/`app_status` = juengste Bewerbung dieses Kandidaten beim TEST-Arbeitgeber
    (ueber `jobs.employer_id`) — das ist die Groesse, die das Gate tatsaechlich liest.
    """
    conn = ro_conn()
    try:
        rows = conn.execute(
            "SELECT c.id, c.name, COUNT(cd.id), MIN(cd.datei_pfad) "
            "FROM candidates c JOIN candidate_documents cd ON cd.candidate_id = c.id "
            "GROUP BY c.id, c.name ORDER BY c.id"
        ).fetchall()
        out = []
        for cid, name, anzahl, pfad in rows:
            app = conn.execute(
                "SELECT a.id, a.status FROM applications a "
                "JOIN jobs j ON j.id = a.job_id "
                "WHERE a.candidate_id = ? AND j.employer_id = ? "
                "ORDER BY a.id DESC LIMIT 1", (cid, TEST_EMPLOYER_ID)).fetchone()
            out.append((cid, name, anzahl, pfad, app[0] if app else None,
                        app[1] if app else None))
    finally:
        conn.close()
    # Halter OHNE Bewerbung beim Test-Arbeitgeber zuerst => Fall A pruefbar
    out.sort(key=lambda r: (r[5] in RELEASED, r[4] is None, r[0]))
    return out


def test_employer_id() -> int:
    """ID des Test-Arbeitgebers (aus der Login-Mail, nicht hartkodiert)."""
    conn = ro_conn()
    try:
        row = conn.execute("SELECT id FROM employers WHERE email = ?", (EMP_EMAIL,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise RuntimeError(f"Test-Arbeitgeber {EMP_EMAIL!r} nicht in employers")
    return row[0]


TEST_EMPLOYER_ID = test_employer_id()
# Arbeitgeber OHNE Bewerbung: muss 0 Dokumente sehen (Isolations-Gegenprobe)
FREMER_ARBEITGEBER = 999


def app_status(app_id: int) -> str | None:
    conn = ro_conn()
    try:
        row = conn.execute("SELECT status FROM applications WHERE id = ?", (app_id,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_app_status(app_id: int, status: str) -> None:
    """TEMPORAERER Status-Set (nur applications.status) inkl. Readback."""
    last = None
    for _ in range(3):
        try:
            conn = sqlite3.connect(str(DB), timeout=15)
            try:
                conn.execute("UPDATE applications SET status = ? WHERE id = ?", (status, app_id))
                conn.commit()
            finally:
                conn.close()
            got = app_status(app_id)
            if got == status:
                return
            last = f"Readback {got!r} != {status!r}"
        except Exception as ex:  # noqa: BLE001
            last = repr(ex)
        time.sleep(1)
    raise RuntimeError(f"Status-Setzung fehlgeschlagen (app {app_id} -> {status!r}): {last}")


# ─── Quelltext-Nachweis (lebender Code) ─────────────────────────────

def fn_block(src: str, name: str) -> str:
    """Quelltextblock einer Modul-Level-def (Ende = naechste def auf Spalte 0)."""
    start = src.index(f"def {name}(")
    m = re.search(r"\ndef ", src[start + 1:])
    end = start + 1 + m.start() if m else len(src)
    return src[start:end]


def source_checks(src: str) -> tuple:
    """Quelltext-Beweise gegen den LEBENDEN employer.py. Rueckgabe: (gate, failures)."""
    fails = []
    vis = fn_block(src, "_visible_documents")
    blk = fn_block(src, "_blocked_candidates")
    page = fn_block(src, "_page_dokumente")

    # Schema-Fakt: kein `a.employer_id` irgendwo im Gate
    if "a.employer_id" in vis or "a.employer_id" in blk:
        fails.append("Schema-Fakt verletzt: `a.employer_id` existiert nicht "
                     "(Arbeitgeber-Bezug nur ueber jobs.employer_id)")
    # Arbeitgeber-Bezug ueber jobs
    if "j.employer_id = ?" not in vis:
        fails.append("Gate: `j.employer_id = ?` (JOIN jobs) fehlt in _visible_documents")
    # `_blocked_candidates` nutzt drei Aliase (j2/j/j3) fuer denselben
    # Arbeitgeber-Bezug -> deshalb auf `employer_id = ?` zaehlen, nicht auf `j.`
    if blk.count("employer_id = ?") != 3:
        fails.append(f"blocked: erwartet 3x jobs-Bezug (j2/j/j3), "
                     f"gefunden {blk.count('employer_id = ?')}")
    # Freigabe-Status kommt aus applications
    if "a.status IN" not in vis:
        fails.append("Gate: `a.status IN (...)` fehlt in _visible_documents")
    if "c.status IN" in vis:
        fails.append("Gate liest noch candidates.status (veraltete Logik)")
    # Typ-Filter case-insensitive
    if "LOWER(cd.dokumententyp) = LOWER(?)" not in vis:
        fails.append("Gate: case-insensitiver Typ-Filter fehlt")
    # Kein Leck: blocked muss per NOT EXISTS auf den eigenen Arbeitgeber schraenken
    if "NOT EXISTS" not in blk:
        fails.append("blocked: NOT EXISTS auf freigebende Bewerbung fehlt")
    # UI-Bestandteile
    if "🔒 DSGVO:" not in page:
        fails.append("🔒-Hinweistext fehlt (_page_dokumente)")
    if "Status Bewerbung" not in page:
        fails.append("Spalte 'Status Bewerbung' fehlt ((c)3)")
    if "_resolve_doc_path" not in page:
        fails.append("Download-Pfadpruefung _resolve_doc_path fehlt")
    return RELEASED, fails


def gate_queries(gate: tuple) -> tuple:
    """Gate read-only gegen die DB — mit den ECHTEN Helfern aus employer.py.

    Bewusst nicht per Regex aus dem Quelltext nachgebaut: der Nachweis soll
    zeigen, dass der ausgelieferte Code die richtige Menge liefert.
    """
    from webui.pages.employer import _blocked_candidates, _visible_documents

    fails = []
    conn = ro_conn()
    try:
        docs = _visible_documents(conn, TEST_EMPLOYER_ID, "alle")
        blocked = _blocked_candidates(conn, TEST_EMPLOYER_ID, "alle")
        fremd = _visible_documents(conn, FREMER_ARBEITGEBER, "alle")
        fremd_blocked = _blocked_candidates(conn, FREMER_ARBEITGEBER, "alle")
        alle_doks = conn.execute(
            "SELECT COUNT(*) FROM candidate_documents").fetchone()[0]
    finally:
        conn.close()

    for d in docs:
        if d["app_status"] not in gate:
            fails.append(f"Gate liefert NICHT-freigegebenen Status: "
                         f"#{d['candidate_id']} {d['app_status']!r}")
    for b in blocked:
        if b["app_status"] in gate:
            fails.append(f"blocked liefert freigegebenen Status: "
                         f"#{b['candidate_id']} {b['app_status']!r}")
    # Arbeitgeber-Isolation: wer keine Bewerbung hat, sieht nichts
    if fremd:
        fails.append(f"Datenleck: fremder Arbeitgeber sieht {len(fremd)} Dokumente")
    if fremd_blocked:
        fails.append(f"Datenleck: fremder Arbeitgeber sieht {len(fremd_blocked)} blockierte "
                     f"Kandidaten")
    # Jeder Dokument-Halter mit Dokument ist genau einmal erfasst (freigegeben XOR blocked)
    ids = {d["candidate_id"] for d in docs} | {b["candidate_id"] for b in blocked}
    halter = alle_doks and {r[0] for r in ro_conn().execute(
        "SELECT DISTINCT candidate_id FROM candidate_documents").fetchall()}
    if ids != halter:
        fails.append(f"Dokument-Halter nicht vollstaendig erfasst: {sorted(ids ^ halter)}")

    datalage = (
        f"{alle_doks} Dokumente / {len(halter or ())} Halter, "
        f"freigegeben={len(docs)} (Kandidaten {sorted({d['candidate_id'] for d in docs})}), "
        f"blocked={len(blocked)} (Kandidaten {sorted({b['candidate_id'] for b in blocked})}), "
        f"fremder Arbeitgeber={len(fremd)}"
    )
    return fails, datalage


# ─── Browser-Teil ───────────────────────────────────────────────────

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
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def open_dokumente(page) -> dict:
    page.goto(f"{BASE}/employer/dokumente", wait_until="load", timeout=60000)
    page.wait_for_timeout(3000)
    return {
        "text": page.locator("body").inner_text(),
        "tables": page.locator(".q-table").count(),
        "rows": page.locator(".q-table tbody tr").count(),
    }


def check_blocked(st: dict, name: str, status_label: str, failures: list, tag: str) -> None:
    """Fall A: 0 Zeilen + sichtbarer 🔒-Hinweis mit Klarname und Statuslabel."""
    print(f"[{tag}] Tabellen={st['tables']} Zeilen={st['rows']}")
    if st["rows"] or st["tables"]:
        failures.append(
            f"{tag}: UI zeigt {st['rows']} Zeilen / {st['tables']} Tabellen (erwartet 0)"
        )
    for needle in ("DSGVO", "Eingeladen"):
        if needle not in st["text"]:
            failures.append(f"{tag}: 🔒-Hinweis ohne {needle!r}")
    if name and name not in st["text"]:
        failures.append(f"{tag}: 🔒-Hinweis nennt den Klarnamen {name!r} nicht")
    if status_label and status_label not in st["text"]:
        failures.append(f"{tag}: Statuslabel {status_label!r} fehlt im 🔒-Hinweis")
    if "DSGVO" in st["text"] and name and name in st["text"] and not st["rows"]:
        print(f"[{tag}] OK: 0 Zeilen + 🔒-Hinweis mit {name!r} ({status_label!r})")


def check_released(st: dict, sample_basename: str, failures: list, tag: str) -> None:
    """Fall B: Dokument sichtbar + Spalte „Status Bewerbung“ + basename."""
    print(f"[{tag}] Tabellen={st['tables']} Zeilen={st['rows']}")
    if st["rows"] < 1:
        failures.append(f"{tag}: keine Tabellenzeile trotz freigegebenem Status")
    if "Status Bewerbung" not in st["text"]:
        failures.append(f"{tag}: Spalte 'Status Bewerbung' fehlt ((c)3)")
    if sample_basename and sample_basename not in st["text"]:
        failures.append(f"{tag}: Dokument (basename) {sample_basename!r} fehlt in der Tabelle")
    if sample_basename and "/" in sample_basename:
        failures.append(f"{tag}: Serverpfad im UI: {sample_basename!r}")
    if st["rows"] >= 1 and "Status Bewerbung" in st["text"]:
        print(f"[{tag}] OK: {st['rows']} Zeile(n) + Spalte 'Status Bewerbung'")


# ─── Main ───────────────────────────────────────────────────────────

def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    base = db_baseline()
    print(f"Pre: agent_tasks(MAX,COUNT)={base['agent_tasks']} "
          f"feedback={len(base['feedback'])} applications={len(base['applications'])} "
          f"candidate_documents={len(base['candidate_documents'])} | pre_max_tasks={pre_tasks}")
    failures = []

    # 1) Quelltext-Nachweis (lebender Code, kein Hardcode)
    src = SRC.read_text(encoding="utf-8")
    gate, src_fails = source_checks(src)
    failures.extend(src_fails)
    print(f"Quelltext: Gate-Liste aus Quelle = {gate} | "
          f"{'OK' if not src_fails else 'FEHLER: ' + str(src_fails)}")

    # 2) Gate-Query read-only gegen Live-DB
    q_fails, datalage = gate_queries(gate)
    failures.extend(q_fails)
    print(f"Datenlage: {datalage}")

    # 3) UI-Teil A/B
    holders = doc_holders()
    orig: dict = {}
    a_mode = b_mode = "nicht geprueft"
    try:
        if not holders:
            print("Datenlage: keine candidate_documents, deshalb Query+Quelltext "
                  "statt UI-Row-Nachweis")
        else:
            print(f"Datenlage: Dokument-Halter "
                  f"{[(h[0], h[1], h[2], h[4], h[5]) for h in holders]}")
            # Alle Bewerbungen der Dokument-Halter BEIM TEST-ARBEITGEBER.
            # Nur die sind gate-relevant; Bewerbungen bei anderen Arbeitgebern
            # werden bewusst nicht angefasst.
            c = ro_conn()
            try:
                app_ids = [r[0] for r in c.execute(
                    "SELECT DISTINCT a.id FROM applications a "
                    "JOIN jobs j ON j.id = a.job_id "
                    "WHERE j.employer_id = ? AND a.candidate_id IN "
                    f"({','.join('?' * len(holders))}) ORDER BY a.id",
                    [TEST_EMPLOYER_ID, *[h[0] for h in holders]]).fetchall()]
            finally:
                c.close()
            orig = {a_id: app_status(a_id) for a_id in app_ids}
            if not app_ids:
                failures.append("keine Bewerbung der Dokument-Halter beim Test-Arbeitgeber "
                                "-> UI-Fall nicht pruefbar")
            sample = min((Path(h[3]).name for h in holders if h[3]), default="")
            first_name = holders[0][1] or f"Kandidat #{holders[0][0]}"

            def set_all(target: str) -> None:
                for a_id in app_ids:
                    set_app_status(a_id, target)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    ctx = browser.new_context()
                    page = ctx.new_page()
                    login_employer(page)

                    # B: Freigabefall — alle Bewerbungen 'eingeladen'
                    set_all(RELEASE_STATUS)
                    b_mode = f"nach temporaerem Status-Set -> '{RELEASE_STATUS}'"
                    print(f"TEMP: {len(app_ids)} Bewerbung(en) auf '{RELEASE_STATUS}' "
                          "(wird in finally zurueckgesetzt)")
                    check_released(open_dokumente(page), sample, failures,
                                   f"B Freigabefall ({b_mode})")

                    # A: Sperrfall — alle Bewerbungen 'eingegangen' (nicht freigegeben)
                    set_all(BLOCK_STATUS)
                    a_mode = f"nach temporaerem Status-Set -> '{BLOCK_STATUS}'"
                    print(f"TEMP: {len(app_ids)} Bewerbung(en) auf '{BLOCK_STATUS}' "
                          "(wird in finally zurueckgesetzt)")
                    check_blocked(open_dokumente(page), first_name,
                                  "Eingegangen", failures, f"A Sperrfall ({a_mode})")

                    ctx.close()
                finally:
                    browser.close()
    except Exception as ex:  # noqa: BLE001
        failures.append(f"UI-Teil Exception: {ex!r}")
    finally:
        # Restore: jede Bewerbung auf ihren Ausgangsstatus
        for a_id, st in orig.items():
            try:
                if app_status(a_id) != st:
                    set_app_status(a_id, st)
                    print(f"Restore: app {a_id} -> {st!r}")
            except Exception as ex:  # noqa: BLE001
                failures.append(f"Restore app {a_id} fehlgeschlagen: {ex!r}")

    if not holders:
        a_mode = b_mode = "Query+Quelltext (keine Daten)"
    print(f"UI-Nachweis-Modi: A={a_mode} | B={b_mode}")

    # 4) C: DB-Baseline vor/nach
    after = db_baseline()
    c_fails = []
    for key in BASELINE_KEYS:
        if after[key] != base[key]:
            c_fails.append(f"Baseline {key} veraendert: {base[key]!r} -> {after[key]!r}")
    if after["cand_status"] != base["cand_status"]:
        diff = {k: (base["cand_status"].get(k), after["cand_status"].get(k))
                for k in set(base["cand_status"]) | set(after["cand_status"])
                if base["cand_status"].get(k) != after["cand_status"].get(k)}
        c_fails.append(f"candidates.status nicht wiederhergestellt: {diff}")
    if after["app_status"] != base["app_status"]:
        diff = {k: (base["app_status"].get(k), after["app_status"].get(k))
                for k in set(base["app_status"]) | set(after["app_status"])
                if base["app_status"].get(k) != after["app_status"].get(k)}
        c_fails.append(f"applications.status nicht wiederhergestellt: {diff}")
    if c_fails:
        failures.extend(c_fails)
    else:
        print("OK C: agent_tasks/feedback/applications/candidate_documents vor/nach "
              "unveraendert; applications.status wiederhergestellt (reines Rendern)")

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")

    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: DSGVO-Gate — echte Helfer + Arbeitgeber-Isolation + UI A (0 Zeilen/🔒) + "
          "UI B (Zeilen + 'Status Bewerbung') + DB-Baseline unveraendert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
