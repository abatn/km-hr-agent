"""B2-5a E2E: Whitelist-Guard `_legal` gegen `ALLOWED_TRANSITIONS` (statisch, read-only).

GO: „GO B2-1 B2-2 B2-3 B2-4 B2-5a“ (25.09.2026)
Spec: knowledge/lifecycle/status-automation.md ((c-a)1-4)
Blueprint: ergebnisse/b2-blueprint-2026-09-25.md (§1 Zielzeilen, §2 B2-5a, §4 Testplan)
Ziele (lebend): webui/pages/employer.py ALLOWED_TRANSITIONS :574, `_legal` :580-587,
Call-Sites do_invite :625 / do_reject :657 / do_hire :687; Parität app.py erl_hr :3136.

Ablauf (KEINE DB-Schreibungen, KEINE schreibenden UI-Interaktionen, KEIN App-Start):
A  Definition + Matrix: Versuch Modul-Import; da `_legal`/`ALLOWED_TRANSITIONS`
   Closures INNERHALB `_page_match` sind (nicht Modul-Level) -> per Import nicht
   erreichbar -> AST-Auswertung des Quelltexts (Begruendung wird ausgegeben).
   Assertions: Matrix == {eingegangen:{angesehen,abgelehnt},
   angesehen:{eingeladen,abgelehnt}, eingeladen:{eingestellt,abgelehnt}};
   `_legal` liest `SELECT status FROM applications` + prueft
   `ALLOWED_TRANSITIONS.get(old, set())`; 4 Call-Sites (seit P0-3: +do_seen) in den richtigen
   Handlern UND VOR dem jeweiligen UPDATE.
B  Parität: app.py:3136 `erl_hr` (nur GELESEN) == NiceGUI ALLOWED_TRANSITIONS
   (Leer-Keys in app.py als set() normalisiert).
C  Guard-Wirkung: lese-sichere DB-Abfrage (URI mode=ro) der Bewerbungs-Status
   + Repplika von `_legal` (nur LESEN) gegen echte app_ids -> unzulaessige
   Uebergaenge (z.B. eingegangen -> eingestellt) werden abgelehnt;
   Ausgabe der 3 relevanten Matrix-Eintraege.
D  R3-5 (30.09.2026, Nutzer-GO „A: Anbinden"): ECHTER HR-Klick „→ eingeladen"
   auf /employer/stellen (Playwright, employer hr@techvision.de) ->
   Pruefung in der Spiegel-DB (KMHR_DB_PATH) der notifications-Zeile
   (role="candidate", user_id=candidate_id, titel="Bewerbungsstatus",
   gelesen=0, Text nennt Firma + Stelle) + status='eingeladen'.
   DANACH vollstaendiger Restore (Status/Historie/Notification/Task), damit
   F3 (agent_tasks-Reste) weiter 0 ist. D laeuft NUR gegen einen Spiegel —
   ohne Env (DB == data/feedback.db, LIVE) wird D uebersprungen, damit der
   Direkt-Lauf read-only bleibt (Regel Runde 3).

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_transition_guard.py
  (D-Sektion: .venv-streamlit/bin/python3 tests/e2e_isolation.py
   --only e2e_transition_guard --port 8092)
"""
import ast
import importlib
import sqlite3
import sys
from pathlib import Path

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

ROOT = Path(__file__).resolve().parents[1]
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
from e2e_harness import BASE  # Env KMHR_E2E_BASE (Sektion D)
SRC = ROOT / "webui" / "pages" / "employer.py"
APP = ROOT / "app.py"
EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"

EXPECTED = {
    "eingegangen": {"angesehen", "abgelehnt"},
    "angesehen": {"eingeladen", "abgelehnt"},
    "eingeladen": {"eingestellt", "abgelehnt"},
}
TERMINAL = ("eingestellt", "abgelehnt", "zurückgezogen")


# ─── A: Definition + Matrix per AST ( Closure, s.u. ) ───────────────

def _mod_fn(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def try_import_module() -> tuple:
    """Versuch: Modul-Import ohne App-Start. Rueckgabe: (matrix|None, begruendung)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        mod = importlib.import_module("webui.pages.employer")
    except Exception as ex:  # noqa: BLE001
        return None, f"Modul-Import fehlgeschlagen ({type(ex).__name__}: {ex})"
    has_m = hasattr(mod, "ALLOWED_TRANSITIONS")
    has_l = hasattr(mod, "_legal")
    if has_m and has_l:
        return getattr(mod, "ALLOWED_TRANSITIONS"), "per Import geladen"
    return None, (f"Import ok, aber hasattr(ALLOWED_TRANSITIONS)={has_m}, "
                  f"hasattr(_legal)={has_l} -> beide sind Closures in _page_match "
                  f"(Zeilen 574/580), nicht Modul-Level -> AST statt Import")


def ast_symbols(src: str) -> dict:
    tree = ast.parse(src)
    fn = _mod_fn(tree, "_page_match")
    out = {"fn": fn, "matrix": None, "matrix_line": None,
           "legal": None, "legal_line": None, "calls": []}
    if fn is None:
        return out
    # P0-3 (29.09.2026): ALLOWED_TRANSITIONS liegt seit der Auslagerung der reinen
    # Helfer (_legal_actions) auf Modulebene -> Matrix im ganzen Modul suchen.
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "ALLOWED_TRANSITIONS":
                    out["matrix"] = ast.literal_eval(node.value)
                    out["matrix_line"] = node.lineno
    for node in ast.walk(fn):
        if isinstance(node, ast.FunctionDef) and node.name == "_legal":
            out["legal"] = node
            out["legal_line"] = node.lineno
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_legal" and node.args
                and isinstance(node.args[0], ast.Constant)):
            out["calls"].append((node.lineno, str(node.args[0].value)))
    return out


def _owner(fn_node: ast.FunctionDef, line: int):
    best = None
    for n in ast.walk(fn_node):
        if isinstance(n, ast.FunctionDef) and n.name != "_page_match":
            if n.lineno <= line <= (n.end_lineno or n.lineno):
                if best is None or n.lineno > best.lineno:
                    best = n
    return best


def check_a(src: str) -> tuple:
    fails, notes = [], []
    sym = ast_symbols(src)
    if sym["fn"] is None:
        return ["kein Modul-Level FunctionDef '_page_match' in employer.py"], notes
    notes.append(f"_page_match ab Zeile {sym['fn'].lineno}")

    if sym["matrix"] is None:
        fails.append("ALLOWED_TRANSITIONS nicht gefunden (B2-5a (c-a)1)")
    else:
        notes.append(f"ALLOWED_TRANSITIONS Zeile {sym['matrix_line']}: {sym['matrix']}")
        if sym["matrix"] != EXPECTED:
            fails.append(f"Matrix {sym['matrix']} != erwartet {EXPECTED}")
        if len(sym["matrix"]) != 3:
            fails.append(f"Matrix hat {len(sym['matrix'])} Keys (erwartet 3)")

    if sym["legal"] is None:
        fails.append("_legal nicht gefunden (B2-5a (c-a)1)")
    else:
        seg = ast.get_source_segment(src, sym["legal"]) or ""
        notes.append(f"_legal Zeile {sym['legal_line']}")
        if "SELECT status FROM applications" not in seg:
            fails.append("_legal liest nicht den Ausgangsstatus aus applications")
        if "ALLOWED_TRANSITIONS.get(old, set())" not in seg:
            fails.append("_legal prueft nicht ALLOWED_TRANSITIONS.get(old, set())")

    calls = sym["calls"]
    notes.append(f"Call-Sites: {[(l, v) for l, v in sorted(calls)]}")
    # P0-3: 4. Call-Site do_seen ("Als angesehen markieren", eingegangen -> angesehen)
    if len(calls) != 4:
        fails.append(f"{len(calls)} _legal-Call-Sites (erwartet 4: seen/invite/reject/hire)")
    expected_owner = {"angesehen": "do_seen", "eingeladen": "do_invite",
                      "abgelehnt": "do_reject", "eingestellt": "do_hire"}
    for line, val in calls:
        owner = _owner(sym["fn"], line)
        want = expected_owner.get(val)
        if owner is None or owner.name != want:
            fails.append(f"_legal({val!r}) in {owner.name if owner else '?'} "
                         f"(erwartet {want})")
            continue
        upd = None
        for n in ast.walk(owner):
            if (isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant)
                    and isinstance(n.args[0].value, str)
                    and n.args[0].value.lstrip().startswith("UPDATE applications")):
                upd = n
                break
        if upd is None:
            fails.append(f"{owner.name}: kein UPDATE applications gefunden")
        elif line > upd.lineno:
            fails.append(f"{owner.name}: _legal-Call Zeile {line} NACH UPDATE "
                         f"Zeile {upd.lineno} (Guard muss davor stehen)")
        else:
            notes.append(f"{owner.name}: _legal Zeile {line} VOR UPDATE Zeile {upd.lineno}")
    return fails, notes


# ─── B: Parität app.py erl_hr (nur lesen) ───────────────────────────

def check_b(app_src: str, matrix: dict) -> tuple:
    fails, notes = [], []
    if matrix is None:
        return ["NiceGUI-Matrix fehlt -> Paritaet nicht pruefbar"], notes
    tree = ast.parse(app_src)
    erl, erl_line = None, None
    alt, alt_line = None, None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if not isinstance(t, ast.Name):
                    continue
                if t.id == "erl_hr":
                    erl, erl_line = ast.literal_eval(node.value), node.lineno
                elif t.id == "allowed_transitions":
                    alt, alt_line = ast.literal_eval(node.value), node.lineno
    if erl is None:
        return ["erl_hr in app.py nicht gefunden (erwartet app.py:3136)"], notes

    a = {k: set(v) for k, v in erl.items()}
    b = {k: set(v) for k, v in matrix.items()}
    notes.append(f"app.py:{erl_line} erl_hr = {erl}")
    notes.append(f"NiceGUI ALLOWED_TRANSITIONS = {b}")
    for key in sorted(set(a) | set(b)):
        if a.get(key, set()) != b.get(key, set()):
            fails.append(f"Paritaet-Bruch {key!r}: app.py {a.get(key, set())} != "
                         f"NiceGUI {b.get(key, set())}")
    extra = sorted(k for k in a if k not in b and not a[k])
    if extra:
        notes.append(f"app.py hat zusaetzliche Leer-Keys {extra} (inhaltlich gleich)")
    if alt is not None:
        alt_sets = {k: set(v) for k, v in alt.items()}
        rel = "==" if alt_sets == b else "!="
        notes.append(f"app.py:{alt_line} allowed_transitions (Selectbox-Pfad) {rel} "
                     "NiceGUI (Nebenbefund)")
    return fails, notes


# ─── C: Guard-Wirkung gegen echte DB-Zeilen (read-only) ─────────────

def ro_conn() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def check_c(matrix: dict) -> tuple:
    fails, notes = [], []
    if matrix is None:
        return ["NiceGUI-Matrix fehlt -> Guard-Wirkung nicht pruefbar"], notes
    conn = ro_conn()
    try:
        observed = conn.execute(
            "SELECT status, COUNT(*) FROM applications GROUP BY status ORDER BY status"
        ).fetchall()
        samples = dict(conn.execute(
            "SELECT status, MIN(id) FROM applications GROUP BY status"
        ).fetchall())
        hist = [r[0] for r in conn.execute(
            "SELECT DISTINCT status FROM application_status_history ORDER BY status"
        ).fetchall()]
    finally:
        conn.close()

    notes.append(f"applications-Status (read-only): {observed}")
    notes.append(f"application_status_history-Status: {hist}")
    notes.append(f"Matrix-Eintraege (die 3 relevanten): "
                 f"eingegangen->{sorted(matrix.get('eingegangen', set()))}, "
                 f"angesehen->{sorted(matrix.get('angesehen', set()))}, "
                 f"eingeladen->{sorted(matrix.get('eingeladen', set()))}")
    if not observed:
        fails.append("keine applications in der DB (Datenlage pruefen)")

    def legal(new_status: str, app_id: int) -> bool:
        """Repplika von employer.py::_legal (Zeile 580-587) — NUR LESEN."""
        c2 = ro_conn()
        try:
            row = c2.execute("SELECT status FROM applications WHERE id = ?",
                             (app_id,)).fetchone()
        finally:
            c2.close()
        old = row[0] if row else None
        return new_status in matrix.get(old, set())

    # Kanonischer Verbot-Fall: eingegangen -> eingestellt
    if "eingegangen" in samples:
        app_id = samples["eingegangen"]
        for bad in ("eingestellt", "eingeladen", "eingegangen"):
            if legal(bad, app_id):
                fails.append(f"Guard versagt: _legal({bad!r}, app {app_id} "
                             f"'eingegangen') == True")
            else:
                notes.append(f"ok: _legal({bad!r}, app {app_id}) == False "
                             f"(nicht in ALLOWED_TRANSITIONS)")
        for good in ("angesehen", "abgelehnt"):
            if not legal(good, app_id):
                fails.append(f"Guard zu streng: _legal({good!r}, app {app_id}) == False")
    else:
        notes.append("Datenlage: keine Bewerbung mit Status 'eingegangen' -> "
                     "Kanonen-Probe uebersprungen (Matrix-Check in A greift)")

    if "eingeladen" in samples:
        app_id = samples["eingeladen"]
        if legal("eingegangen", app_id):
            fails.append(f"Guard versagt: rueckwaerts eingegangen fuer app {app_id}")
        if not legal("eingestellt", app_id):
            fails.append(f"Guard zu streng: eingestellt fuer app {app_id} verweigert")
        notes.append(f"ok: app {app_id} 'eingeladen' -> eingestellt erlaubt, "
                     "eingegangen verweigert")
    else:
        notes.append("Datenlage: keine Bewerbung mit Status 'eingeladen' -> "
                     "Probe uebersprungen")

    for st in TERMINAL:
        if matrix.get(st, set()):
            fails.append(f"terminaler Status {st!r} hat Ziele {matrix[st]} "
                         "(app.py erl_hr: leer)")
    return fails, notes


# ─── D: Echter HR-Klick „→ eingeladen" -> notifications-Zeile (R3-5) ───

def login_employer(page) -> None:
    import re as _re
    page.goto(f"{BASE}/login", wait_until="load", timeout=20000)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=_re.compile("Arbeitgeber-Login", _re.I))
    ).first
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=_re.compile("Arbeitgeber-Login", _re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


def check_d(pre_tasks: int) -> tuple:
    """D: HR-Klick „→ eingeladen" -> notifications-Zeile in der SPIEGEL-DB.

    Schreibt NUR, wenn DB != Live-DB (e2e_isolation setzt KMHR_DB_PATH).
    Restore am Ende: Status, application_status_history, notifications,
    create_invitation-Task -> F3-Residue bleibt 0.
    """
    fails, notes = [], []
    live = (ROOT / "data" / "feedback.db").resolve()
    try:
        ist_live = Path(DB).resolve() == live
    except Exception:  # noqa: BLE001
        ist_live = True
    if ist_live:
        notes.append("D uebersprungen: DB == data/feedback.db (LIVE) — nur Spiegel-Lauf "
                     "ueber tests/e2e_isolation.py (Regel Runde 3, kein Schreiben in die "
                     "Live-DB)")
        return fails, notes

    conn = sqlite3.connect(DB)
    try:
        # R6-5 (01.10.2026): Datenstand — es gibt keine Bewerbung mit Status
        # 'eingegangen'/'angesehen' mehr (Drift 30.09.2026: alle final bzw.
        # 'eingeladen', gemessen read-only). D braucht nur EINE Bewerbung des
        # Arbeitgebers: das Setup setzt sie ohnehin auf 'angesehen' (dann
        # erscheint '→ eingeladen') und stellt orig_status am Ende vollstaendig
        # wieder her (inkl. History/Notification/Task-Delete).
        row = conn.execute(
            "SELECT a.id, a.candidate_id, a.status, e.firma, j.titel, a.aktualisiert_am "
            "FROM applications a JOIN jobs j ON j.id = a.job_id "
            "JOIN employers e ON e.id = j.employer_id "
            "WHERE j.employer_id = 1 AND a.status IN ('eingegangen','angesehen','eingeladen') "
            "ORDER BY a.id LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return ["D: keine passende Bewerbung (employer 1, Status "
                "eingegangen/angesehen/eingeladen) fuer den Klick-Test"], notes
    app_id, cand_id, orig_status, firma, titel, orig_upd = row

    conn = sqlite3.connect(DB)
    try:
        hist_max = conn.execute(
            "SELECT COALESCE(MAX(id),0) FROM application_status_history "
            "WHERE application_id = ?", (app_id,)).fetchone()[0]
        notif_max = conn.execute(
            "SELECT COALESCE(MAX(id),0) FROM notifications").fetchone()[0]
        conn.execute(
            "UPDATE applications SET status='angesehen', "
            "aktualisiert_am=CURRENT_TIMESTAMP WHERE id = ?", (app_id,))
        conn.execute(
            "INSERT INTO application_status_history (application_id, status, changed_by) "
            "VALUES (?, 'angesehen', 'e2e_setup')", (app_id,))
        conn.commit()
    finally:
        conn.close()
    notes.append(f"D Setup: app {app_id} (cand {cand_id}) {orig_status} -> angesehen | "
                 f"Firma={firma} | Stelle={titel!r}")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                login_employer(page)
                page.goto(f"{BASE}/employer/stellen", wait_until="networkidle")
                page.wait_for_timeout(1500)

                def _btn():
                    card = page.locator(".q-card").filter(has_text=f"#{app_id}").first
                    return card, card.get_by_role("button", name="→ eingeladen")

                card, btn = _btn()
                if not (btn.count() and btn.first.is_visible()):
                    # P1-13: Expansion ist standardmaessig offen; nur klicken wenn zu
                    exp = page.get_by_text("Aktive Bewerber")
                    if exp.count():
                        exp.first.click()
                        page.wait_for_timeout(600)
                    card, btn = _btn()
                if not btn.count():
                    fails.append(f"D: Button '→ eingeladen' fuer app {app_id} nicht gefunden")
                else:
                    btn.first.click()
                    page.wait_for_timeout(2500)
                    notes.append("D Klick: '→ eingeladen' auf /employer/stellen ausgefuehrt")
            finally:
                browser.close()
    except Exception as ex:  # noqa: BLE001
        fails.append(f"D: Playwright-Fehler {type(ex).__name__}: {ex}")

    conn = sqlite3.connect(DB)
    try:
        status = conn.execute("SELECT status FROM applications WHERE id = ?",
                              (app_id,)).fetchone()[0]
        rows = conn.execute(
            "SELECT id, titel, nachricht, gelesen FROM notifications "
            "WHERE user_id = ? AND role = 'candidate' AND id > ?",
            (cand_id, notif_max)).fetchall()
    finally:
        conn.close()
    notes.append(f"D DB: status={status!r} | neue notifications={rows}")
    if status != "eingeladen":
        fails.append(f"D: status={status!r} != 'eingeladen'")
    if len(rows) != 1:
        fails.append(f"D: {len(rows)} notifications-Zeilen (role=candidate) statt 1")
    else:
        _nid, ntitel, msg, gelesen = rows[0]
        if ntitel != "Bewerbungsstatus":
            fails.append(f"D: titel={ntitel!r} != 'Bewerbungsstatus'")
        if gelesen != 0:
            fails.append(f"D: gelesen={gelesen!r} != 0")
        for pfand in (firma, titel, "eingeladen"):
            if pfand not in (msg or ""):
                fails.append(f"D: {pfand!r} fehlt in Nachricht {msg!r}")
        if not (msg or "").startswith("Deine Bewerbung bei"):
            fails.append(f"D: Nachricht ist nicht der deutsche R3-5-Text: {msg!r}")

    # ── Restore (immer) ──
    conn = sqlite3.connect(DB)
    try:
        conn.execute("UPDATE applications SET status = ?, aktualisiert_am = ? WHERE id = ?",
                     (orig_status, orig_upd, app_id))
        conn.execute("DELETE FROM application_status_history "
                     "WHERE application_id = ? AND id > ?", (app_id, hist_max))
        conn.execute("DELETE FROM notifications WHERE id > ? AND user_id = ?",
                     (notif_max, cand_id))
        conn.execute(
            "DELETE FROM agent_tasks WHERE id > ? AND task_type = 'create_invitation' "
            "AND json_extract(payload, '$.application_id') = ?", (pre_tasks, app_id))
        conn.commit()
        st2 = conn.execute("SELECT status FROM applications WHERE id = ?",
                           (app_id,)).fetchone()[0]
        hist2 = conn.execute("SELECT COALESCE(MAX(id),0) FROM application_status_history "
                             "WHERE application_id = ?", (app_id,)).fetchone()[0]
        n2 = conn.execute("SELECT COALESCE(MAX(id),0) FROM notifications").fetchone()[0]
        tasks2 = conn.execute(
            "SELECT COUNT(*) FROM agent_tasks WHERE id > ? AND task_type = "
            "'create_invitation' AND json_extract(payload, '$.application_id') = ?",
            (pre_tasks, app_id)).fetchone()[0]
    finally:
        conn.close()
    notes.append(f"D Restore: status={st2!r} (soll {orig_status!r}) hist_max={hist2} "
                 f"(soll {hist_max}) notif_max={n2} (soll {notif_max}) tasks={tasks2}")
    if st2 != orig_status:
        fails.append(f"D Restore: status={st2!r} != {orig_status!r}")
    if hist2 != hist_max:
        fails.append(f"D Restore: hist_max={hist2} != {hist_max}")
    if n2 != notif_max:
        fails.append(f"D Restore: notifications max={n2} != {notif_max}")
    if tasks2:
        fails.append(f"D Restore: {tasks2} create_invitation-Task verbleiben")
    return fails, notes


# ─── Main ───────────────────────────────────────────────────────────

def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    failures = []
    print(f"Pre: pre_max_tasks={pre_tasks} | Ziele: {SRC.name} (lesen), {APP.name} (lesen)")

    src = SRC.read_text(encoding="utf-8")
    app_src = APP.read_text(encoding="utf-8")

    # A — Import-Versuch (ehrliche Begruendung) + AST
    mod_matrix, reason = try_import_module()
    print(f"A Import-Check: {reason}")
    a_fails, a_notes = check_a(src)
    failures.extend(a_fails)
    for n in a_notes:
        print("  A:", n)
    if mod_matrix is not None and a_fails and mod_matrix == EXPECTED:
        print("  A: Hinweis — Modul-Import liefert die erwartete Matrix, AST weicht ab")
    if mod_matrix is not None:
        matrix = mod_matrix
    else:
        matrix = ast_symbols(src)["matrix"]

    # B — Parität app.py:3136 erl_hr (nur lesen)
    b_fails, b_notes = check_b(app_src, matrix)
    failures.extend(b_fails)
    for n in b_notes:
        print("  B:", n)

    # C — Guard-Wirkung (lese-sichere DB-Abfrage + _legal-Repplika)
    c_fails, c_notes = check_c(matrix)
    failures.extend(c_fails)
    for n in c_notes:
        print("  C:", n)

    # D — R3-5: echter HR-Klick „→ eingeladen" -> notifications-Zeile (Spiegel)
    d_fails, d_notes = check_d(pre_tasks)
    failures.extend(d_fails)
    for n in d_notes:
        print("  D:", n)

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")

    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: B2-5a Whitelist-Guard — _legal definiert + Matrix korrekt + "
          "4 Call-Sites vor dem UPDATE + Parität app.py:3136 erl_hr + "
          "unzulaessige Uebergaenge read-only abgelehnt"
          + (" + R3-5 notifications-Zeile nach HR-Klick „→ eingeladen\""
             if not d_fails and d_notes and any("Klick" in n for n in d_notes)
             else " (R3-5 D: uebersprungen oder ohne Klick)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
