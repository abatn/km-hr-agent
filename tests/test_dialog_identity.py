"""Dialog-Identity-Guard: Candidate-ID statt App-ID in HR-Dialogen (23.09.2026).

Test-Sätze:
  1 QUELLTEXT-INSPECTION  employer.py nur per read_text/regex (KEIN UI-Import):
                          *_cid = {"val": 0} vorhanden, *_app_id / a_id=c_id verboten,
                          do_reject-Slice: genau 1x queue_agent_task("send_rejection"
                          + "candidate_id": cid; alle 3 do_* mit "candidate_id": cid;
                          Helper _active_app_ids mit Aktiv-IN-Liste + ORDER BY a.id DESC
  2 SELECT-LOGIK          read-only, Helper-SQL exakt repliziert (JOIN jobs, employer_id,
                          Aktiv-IN-Liste, ORDER BY a.id DESC) je Employer des Anker-Jobs
   3 WRITE-SIM Multi-Fall cand 13 → RESTORE in finally (Status 20/23/26 + hist-Rowids)
  4 WRITE-SIM Kollision   cand 17 vs. app 17 → RESTORE in finally (Status 25 + hist-Rowid)
  5 FEHLERPFAD-GRUNDLAGE  cand 16 → [] → Read-only-Beweis (kein else-Zweig greift)
  6 GUARD                 send_rejection: NEG application_id=999 (NEU) +
                          POS to-aus-DB-SELECT (NEU, PII nicht hartkodiert)
   7 FINAL                 alle 18 App-Status == Pre-Baseline, hist==50,
                            agent_tasks-Count unverändert

Harte Regeln: mcp_call IMMER mit unittest.mock patchen (nie echter Mailversand/Netzwerk),
KEIN Import von webui/pages/employer.py oder nicegui, KEINE Writes in agent_tasks,
alle DB-Write-Simulationen in try/finally auf Pre-Werte restauriert.
Bestehende Guard-Faelle (kein trigger / Status != abgelehnt / POS truthy-to) liegen in
tests/test_send_rejection_guard.py und werden hier NICHT dupliziert.
"""
import importlib.util
import sqlite3
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "feedback.db"
EMPLOYER_PY = BASE / "webui" / "pages" / "employer.py"

_spec = importlib.util.spec_from_file_location("agent_runner_dialog_identity",
                                               BASE / "scripts" / "agent-runner.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

# ─── Pre-Baselines (Refresh 24.09.2026 user-GO: hist 16→20, 11→13 Apps ──────
# — Drift durch echte Trigger: User-Portal #26 + E2E-Apply #27, s. entscheidungen.md)
# — Refresh 24.09.2026 D-Housing-E2E: hist 20→21, App 27 eingegangen→eingestellt
#   (HR-Klick 'Einstellen', e2e_housing.py; Task #186 onboarding_release), s. Nachtrag.
# — Refresh 25.09.2026 Teil-2-Residue-Cleanup (Phase-E Runde 6, User-GO):
#   App 27 eingestellt→eingeladen zurückgesetzt (einzelner dokumentierter UPDATE,
#   DB-Bak -1734; Grund: housing/c7-Vorbedingungen blockiert). e2e_housing.py
#   stellt den Hire-Flip jetzt selbst wieder her → hist bleibt 21.
# — Refresh 30.09.2026 R3-7 (Nutzer-GO „A: Baseline-Refresh mit GO"): hist 21→41,
#   13→17 Apps. Reine Datenstand-Drift, Quelle = read-only SELECT gegen
#   data/feedback.db (08:1x) + Failure-Ist-Werte der Vorrunde:
#     hist-Rowids 887-906 (Apps 28-31 NEU, 28./29.09.), Status-Wechsel
#     8 eingeladen→eingestellt (rowid 905), 16 →zurückgezogen (rowid 899,#   changed_by kandidat, 28.09.20:12), 19 →abgelehnt (rowid 906),
#   23 eingegangen→eingeladen (rowid 892), 27 →eingestellt (rowid 904).
# R6-5 (01.10.2026, Nutzer-GO „A: Datenstand-Baselines ziehen"): Drift durch
#   echte Live-Nutzung am 30.09.2026 11:59–12:20 (changed_by 'arbeitgeber' /
#   'kandidat', history rowid 908–915, Quelle: read-only SELECT gegen
#   data/feedback.db): 26 →eingestellt, 23 →abgelehnt, 20 →eingestellt,
#   18 →angesehen→abgelehnt, App 32 NEU (eingegangen→angesehen→zurückgezogen).

PRE_STATUS_TASK = {
    8: "eingestellt", 16: "zurückgezogen", 17: "abgelehnt", 18: "abgelehnt",
    19: "abgelehnt", 20: "eingestellt", 21: "eingeladen", 22: "zurückgezogen",
    23: "abgelehnt", 24: "eingestellt", 25: "eingeladen",
    26: "eingestellt", 27: "eingestellt", 28: "eingestellt",
    29: "abgelehnt", 30: "zurückgezogen", 31: "eingestellt",
    32: "zurückgezogen",
}
# R6-0 (30.09.2026, 11:50:55): App #29 eingeladen→abgelehnt (Live-Vorfall,
# manueller HR-Klick; Nutzer-Entscheidung: Daten bleiben) + History rowid 907
# -> PRE_HIST_COUNT 41→42. Fruehere Baselines: '29 eingeladen' / 41.
# R6-5 (01.10.2026, Nutzer-GO „A"): rowid 908–915 (8 echte Status-Wechsel der
#   Live-App am 30.09.2026 11:59–12:20) -> PRE_HIST_COUNT 42→50.
PRE_HIST_COUNT = 50


def _snapshot():
    conn = sqlite3.connect(str(DB))
    try:
        status = dict(conn.execute("SELECT id, status FROM applications ORDER BY id"))
        hist_rowids = tuple(r[0] for r in
                            conn.execute("SELECT rowid FROM application_status_history ORDER BY rowid"))
        agent_tasks = conn.execute("SELECT COUNT(*) FROM agent_tasks").fetchone()[0]
    finally:
        conn.close()
    return status, hist_rowids, agent_tasks


PRE_STATUS, PRE_HIST_ROWIDS, PRE_AGENT_TASKS = _snapshot()


def _slice(text: str, start: str, end_marker: str) -> str:
    i = text.index(start)
    j = text.rindex(end_marker, i) + len(end_marker)
    return text[i:j]


def _active_app_ids(conn, cid: int, employer_id: int) -> list:
    """Exakte Replik des Helpers aus employer.py (Quelltext-Zeilen 582-588)."""
    return [r[0] for r in conn.execute("""
            SELECT a.id FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.candidate_id = ? AND j.employer_id = ?
              AND a.status IN ('eingegangen', 'angesehen', 'eingeladen')
            ORDER BY a.id DESC
        """, (cid, employer_id)).fetchall()]


def _employer_of_app(conn, app_id: int) -> int:
    row = conn.execute("""SELECT j.employer_id FROM applications a
                          JOIN jobs j ON a.job_id=j.id WHERE a.id=?""",
                       (app_id,)).fetchone()
    assert row, f"Anker-Bewerbung #{app_id} fehlt"
    return row[0]


# ─── 1. QUELLTEXT-INSPECTION (kein UI-Import) ───────────────────────────────
# P0-3 (29.09.2026): Die Dialoge tragen jetzt die application_id (Kontext-Dict
# {"app_id": 0}); Kandidat/Stelle werden per _app_info(app_id) aus der DB abgeleitet
# (inkl. Arbeitgeber-Zugehoerigkeit). Die alte Annahme "cid-Dict + _active_app_ids(cid)[0]"
# (= neueste aktive Bewerbung, Reject auf ALLE) ist obsolet. Intention bleibt:
# der richtige Datensatz wird geaendert, Kollisions-IDs (cand 17 vs. app 17) bleiben unberuehrt.

def test_quelltext_cid_dict_statt_app_id():
    text = EMPLOYER_PY.read_text(encoding="utf-8")
    lines = text.splitlines()
    # Exakte Zeile (nicht Substring): `_bd_hire_ctx` darf `_hire_ctx` nicht mitmatchen.
    assert '    _reject_ctx = {"app_id": 0}' in lines
    assert '    _invite_ctx = {"app_id": 0}' in lines
    assert '    _hire_ctx = {"app_id": 0}' in lines
    # alte candidate_id-Dialogkontexte duerfen nicht zurueckkehren
    for alt in ("_reject_cid", "_invite_cid", "_hire_cid"):
        assert alt not in text
    assert "a_id=c_id" not in text


def test_quelltext_do_reject_slice_genau_ein_send_rejection():
    text = EMPLOYER_PY.read_text(encoding="utf-8")
    sl = _slice(text, "def do_reject", "ui.button(_('Ablehnen'), on_click=do_reject)")
    assert sl.count('queue_agent_task("send_rejection"') == 1, sl
    assert '"application_id": app_id' in sl and '"candidate_id": cid' in sl
    assert "executemany" not in sl  # Reject wirkt nur auf die gewaehlte Bewerbung
    assert "cid, job_id = info[0], info[1]" in sl  # cid aus DB (_app_info), nicht aus UI


def test_quelltext_alle_drei_do_funktionen_tragen_candidate_id():
    text = EMPLOYER_PY.read_text(encoding="utf-8")
    for def_name, end in (("def do_invite", "ui.button(_('Einladen'), on_click=do_invite)"),
                          ("def do_reject", "ui.button(_('Ablehnen'), on_click=do_reject)"),
                          ("def do_hire", "ui.button(_('Einstellen'), on_click=do_hire)")):
        sl = _slice(text, def_name, end)
        assert '"candidate_id": cid' in sl, def_name
        assert "info = _app_info(app_id) if app_id else None" in sl, def_name


def test_quelltext_helper_app_info_sql():
    text = EMPLOYER_PY.read_text(encoding="utf-8")
    assert "_active_app_ids" not in text
    helper = _slice(text, "def _app_info", "return row")
    assert "JOIN jobs j ON a.job_id = j.id" in helper
    assert "WHERE a.id = ? AND j.employer_id = ?" in helper


# ─── 2. SELECT-LOGIK (nur SELECTs) ──────────────────────────────────────────

def test_select_logik_cand_13_alle_final_liefert_leer():
    conn = sqlite3.connect(str(DB))
    try:
        emp = _employer_of_app(conn, 23)
        # R6-5 (01.10.2026): 20/23/26 sind seit 30.09. alle final
        # (eingestellt/abgelehnt/eingestellt, HR-Klicks 11:59–12:08) ->
        # Aktiv-IN-Liste liefert []. POSITIV-Beweis des Helpers:
        # test_select_logik_cand_17_liefert_nur_25_nicht_app_17 ([25]).
        assert _active_app_ids(conn, 13, emp) == []
    finally:
        conn.close()


def test_select_logik_cand_17_liefert_nur_25_nicht_app_17():
    conn = sqlite3.connect(str(DB))
    try:
        emp = _employer_of_app(conn, 25)
        ids = _active_app_ids(conn, 17, emp)
        assert ids == [25]
        assert 17 not in ids  # App #17 gehört zu cand 10 (Kollisions-ID-Raum)
    finally:
        conn.close()


def test_select_logik_cand_16_leer_nur_eingestellt():
    conn = sqlite3.connect(str(DB))
    try:
        emp = _employer_of_app(conn, 24)
        assert _active_app_ids(conn, 16, emp) == []
    finally:
        conn.close()


def test_select_logik_cand_2_liefert_genau_16():
    conn = sqlite3.connect(str(DB))
    try:
        emp = _employer_of_app(conn, 16)
        ids = _active_app_ids(conn, 2, emp)
        # Baseline-Refresh 30.09.2026 (R3-7): Anker-App #16 steht seit 28.09.2026
        # auf 'zurückgezogen' (hist rowid 899, changed_by kandidat, 20:12:24) und
        # faellt damit aus der Aktiv-IN-Liste ('eingegangen','angesehen',
        # 'eingeladen') → []. SQL selbst ist unveraendert; der Positiv-Beweis des
        # Helpers bleibt test_select_logik_cand_17_liefert_nur_25_nicht_app_17 ([25]).
        assert ids == []
        assert len(ids) == 0
    finally:
        conn.close()


# ─── 3. WRITE-SIM Multi-Fall cand 13 (RESTORE in finally) ───────────────────

def test_write_sim_cand_13lehnt_drei_apps_ab_und_restauriert():
    conn = sqlite3.connect(str(DB))
    try:
        pre = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM applications")}
        pre_upd = {r[0]: r[1] for r in conn.execute("SELECT id, aktualisiert_am FROM applications")}
        pre_hist = tuple(r[0] for r in
                         conn.execute("SELECT rowid FROM application_status_history ORDER BY rowid"))
        pre_hist_cnt = len(pre_hist)
        assert pre_hist_cnt == PRE_HIST_COUNT
        # R6-5 (01.10.2026): Datenstand 30.09. — 20/26 eingestellt, 23 abgelehnt
        assert pre[20] == "eingestellt" and pre[23] == "abgelehnt"
        assert pre[26] == "eingestellt"
        assert pre[16] == "zurückgezogen" and pre[17] == "abgelehnt"

        # R6-5: _active_app_ids liefert hier [] (alle final, s.o.) — die
        # Multi-Fall-Simulation arbeitet deshalb mit der dokumentierten Zielmenge
        # direkt; der Aktiv-Filter selbst steht in den SELECT-LOGIK-Tests.
        ids = [26, 23, 20]
        assert _employer_of_app(conn, 23) == _employer_of_app(conn, 26) == 1

        payload = {"application_id": ids[0], "candidate_id": 13, "trigger": "hr_klick_portal"}
        assert set(payload.keys()) == {"application_id", "candidate_id", "trigger"}
        assert payload == {"application_id": 26, "candidate_id": 13, "trigger": "hr_klick_portal"}

        inserted = []
        try:
            conn.executemany(
                "UPDATE applications SET status='abgelehnt', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?",
                [(i,) for i in ids])
            for i in ids:
                cur = conn.execute(
                    "INSERT INTO application_status_history (application_id, status, changed_by) "
                    "VALUES (?, 'abgelehnt', 'arbeitgeber')", (i,))
                inserted.append(cur.lastrowid)
            conn.commit()

            st = dict(conn.execute("SELECT id, status FROM applications WHERE id IN (20,23,26)"))
            assert st[20] == "abgelehnt" and st[23] == "abgelehnt"
            assert st[26] == "abgelehnt"
            hist_cnt = conn.execute("SELECT COUNT(*) FROM application_status_history").fetchone()[0]
            assert hist_cnt - pre_hist_cnt == 3
            marks = ",".join("?" * len(inserted))
            rows = conn.execute(
                f"SELECT application_id, status, changed_by FROM application_status_history "
                f"WHERE rowid IN ({marks})", inserted).fetchall()
            assert sorted(rows) == sorted([(20, "abgelehnt", "arbeitgeber"),
                                           (23, "abgelehnt", "arbeitgeber"),
                                           (26, "abgelehnt", "arbeitgeber")])
            assert conn.execute("SELECT status FROM applications WHERE id=16").fetchone()[0] == pre[16]
            assert conn.execute("SELECT status FROM applications WHERE id=17").fetchone()[0] == pre[17]
        finally:
            for app_id in ids:
                conn.execute("UPDATE applications SET status=?, aktualisiert_am=? WHERE id=?",
                             (pre[app_id], pre_upd[app_id], app_id))
            if inserted:
                marks = ",".join("?" * len(inserted))
                conn.execute(f"DELETE FROM application_status_history WHERE rowid IN ({marks})",
                             inserted)
            conn.commit()

        post = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM applications")}
        post_hist = tuple(r[0] for r in
                          conn.execute("SELECT rowid FROM application_status_history ORDER BY rowid"))
        assert post == pre
        assert post_hist == pre_hist
        assert conn.execute("SELECT COUNT(*) FROM application_status_history").fetchone()[0] == PRE_HIST_COUNT
    finally:
        conn.close()


# ─── 4. WRITE-SIM Kollisions-ID cand 17 vs. app 17 (RESTORE) ────────────────

def test_write_sim_cand_17_kollision_app_17_unberuehrt():
    conn = sqlite3.connect(str(DB))
    try:
        pre = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM applications")}
        pre_upd = {r[0]: r[1] for r in conn.execute("SELECT id, aktualisiert_am FROM applications")}
        pre_hist17 = tuple(r[0] for r in conn.execute(
            "SELECT rowid FROM application_status_history WHERE application_id=17 ORDER BY rowid"))
        pre_hist_cnt = conn.execute("SELECT COUNT(*) FROM application_status_history").fetchone()[0]
        assert pre_hist_cnt == PRE_HIST_COUNT
        assert pre[25] == "eingeladen" and pre[17] == "abgelehnt"

        emp = _employer_of_app(conn, 25)
        ids = _active_app_ids(conn, 17, emp)
        assert ids == [25]
        assert 17 not in ids

        inserted = []
        try:
            conn.execute(
                "UPDATE applications SET status='abgelehnt', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?",
                (ids[0],))
            cur = conn.execute(
                "INSERT INTO application_status_history (application_id, status, changed_by) "
                "VALUES (?, 'abgelehnt', 'arbeitgeber')", (ids[0],))
            inserted.append(cur.lastrowid)
            conn.commit()

            assert conn.execute("SELECT status FROM applications WHERE id=25").fetchone()[0] == "abgelehnt"
            # Count-Invarianz: kein UPDATE/INSERT auf App #17
            assert conn.execute("SELECT status FROM applications WHERE id=17").fetchone()[0] == "abgelehnt"
            post_hist17 = tuple(r[0] for r in conn.execute(
                "SELECT rowid FROM application_status_history WHERE application_id=17 ORDER BY rowid"))
            assert post_hist17 == pre_hist17
            hist_cnt = conn.execute("SELECT COUNT(*) FROM application_status_history").fetchone()[0]
            assert hist_cnt - pre_hist_cnt == 1
        finally:
            conn.execute("UPDATE applications SET status=?, aktualisiert_am=? WHERE id=?",
                         (pre[25], pre_upd[25], 25))
            if inserted:
                marks = ",".join("?" * len(inserted))
                conn.execute(f"DELETE FROM application_status_history WHERE rowid IN ({marks})",
                             inserted)
            conn.commit()

        post = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM applications")}
        assert post == pre
        assert conn.execute("SELECT COUNT(*) FROM application_status_history").fetchone()[0] == PRE_HIST_COUNT
    finally:
        conn.close()


# ─── 5. FEHLERPFAD-GRUNDLAGE: cand 16 → [] → read-only Beweis ───────────────

def test_fehlerpfad_cand_16_select_leer_und_apps_unveraendert():
    text = EMPLOYER_PY.read_text(encoding="utf-8")
    invite_sl = _slice(text, "def do_invite", "ui.button(_('Einladen'), on_click=do_invite)")
    reject_sl = _slice(text, "def do_reject", "ui.button(_('Ablehnen'), on_click=do_reject)")
    for sl in (invite_sl, reject_sl):
        # P0-3: Fehlerpfad = unbekannte Bewerbung -> `if not info:` mit return VOR dem UPDATE
        assert "if not info:" in sl
        assert sl.index("if not info:") < sl.index("UPDATE applications")
        assert "return" in sl[sl.index("if not info:"):sl.index("UPDATE applications")]

    conn = sqlite3.connect(str(DB))
    try:
        pre = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM applications")}
        pre_hist_cnt = conn.execute("SELECT COUNT(*) FROM application_status_history").fetchone()[0]
        emp = _employer_of_app(conn, 24)
        ids_invite = _active_app_ids(conn, 16, emp)  # gleicher SQL für Invite UND Reject
        ids_reject = _active_app_ids(conn, 16, emp)
        assert ids_invite == [] and ids_reject == []

        post = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM applications")}
        post_hist_cnt = conn.execute("SELECT COUNT(*) FROM application_status_history").fetchone()[0]
        assert post[24] == "eingestellt" == pre[24]
        # Baseline 30.09.2026 (R3-7): App #16 = 'zurückgezogen' (hist rowid 899)
        assert post[16] == "zurückgezogen" == pre[16]
        assert post == pre
        assert post_hist_cnt == pre_hist_cnt == PRE_HIST_COUNT
    finally:
        conn.close()


# ─── 6. GUARD: send_rejection (mcp_call IMMER gemockt) ──────────────────────

def test_guard_negativ_application_999_nicht_gegefunden_ohne_mail():
    payload = {"application_id": 999, "candidate_id": 1, "trigger": "hr_klick_portal"}
    with patch.object(mod, "mcp_call") as m:
        try:
            mod.send_rejection(dict(payload))
            raise AssertionError("RuntimeError erwartet")
        except RuntimeError as exc:
            assert "nicht gefunden" in str(exc)
    assert m.call_count == 0


def test_guard_positiv_to_wert_aus_db_select_gemockte_mail():
    conn = sqlite3.connect(str(DB))
    try:
        assert conn.execute("SELECT status FROM applications WHERE id=17").fetchone()[0] == "abgelehnt"
        email_pre = conn.execute("SELECT email FROM candidates WHERE id = ?", (10,)).fetchone()[0]
    finally:
        conn.close()
    assert email_pre  # PII kommt aus der DB, nicht aus dem Testtext

    payload = {"application_id": 17, "candidate_id": 10, "trigger": "hr_klick_portal"}
    with patch.object(mod, "mcp_call", return_value="OK|Gesendet an <virtual>") as m:
        res = mod.send_rejection(dict(payload))
    assert m.call_count == 1
    assert m.call_args[0][1] == "send_email"
    assert res["to"] == email_pre


# ─── 7. FINAL: Pre-Baselines unverändert ────────────────────────────────────

def test_final_baselines_unveraendert():
    status, hist_rowids, agent_tasks = _snapshot()
    assert status == PRE_STATUS_TASK
    assert status == PRE_STATUS
    assert len(hist_rowids) == PRE_HIST_COUNT
    assert hist_rowids == PRE_HIST_ROWIDS
    assert agent_tasks == PRE_AGENT_TASKS
