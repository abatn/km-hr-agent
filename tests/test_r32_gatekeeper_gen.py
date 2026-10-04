"""R3-1 (Pförtner-Abfragen exakt) + R3-2 (Generation-Zähler), 30.09.2026.

R3-1 — `scripts/agent-runner.py::_maybe_gatekeeper` verglich die Bewerbung per
`payload LIKE '%"application_id": N%'`. Das ist KEIN exakter Vergleich:
Präfix-Kollision (N=1 trifft 10/11/160). Fix: `json_extract(payload,
'$.application_id') = ?` (SQLite 3.45.1 hier, `select sqlite_version()`).
Zweiter Fix: Ketten-Zustaende kommen mit `ORDER BY id` und werden in
Abfrage-Reihenfolge eingespeist → der letzte Eintrag je task_type gewinnt =
neuester Stand (vorher `dict()` aus unsortierten Zeilen, Zufalls-Gewinner).

R3-2 — Nach Rueckzug->„Erneut bewerben“ queue't `apply_to_job` dieselbe Kette
wie die Erstbewerbung, aber mit `gen` = MAX(gen)+1. Dedupe (queue_agent_task)
und notify_hr-Guard (_maybe_gatekeeper) sind gen-bewusst; Altbestand ohne
`gen`-Feld wird via COALESCE 0 gelesen.

SCHREIB-REGEL: Alles laeuft gegen `sqlite3.connect(":memory:")` (Teil a/b-
Gatekeeper) bzw. den pytest-Spiegel aus tests/conftest.py (Teil b/c, `db.`-
Aufrufe). Die Live-DB data/feedback.db wird NIE beschrieben.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from webui import db

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "agent_runner_r32", ROOT / "scripts" / "agent-runner.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

CHAIN = ("match_candidate", "check_compliance", "assess_culture_fit")


# ─── In-Memory-Helfer (Teil a + b-Gatekeeper) ──────────────────────────────

def _mem() -> sqlite3.Connection:
    """Eigene In-Memory-Queue. Spiegel-Neutral: conftest leitet nur Pfade um,
    die auf data/feedback.db zeigen — ":memory:" bleibt lokaler Speicher."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE agent_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        payload TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    return conn


def _add(conn, app_id, task_type, status="done", gen=None, **extra):
    p = {"application_id": app_id, "candidate_id": app_id, "job_id": 1}
    if gen is not None:
        p["gen"] = gen
    p.update(extra)
    conn.execute("INSERT INTO agent_tasks (task_type, status, payload) VALUES (?, ?, ?)",
                 (task_type, status, json.dumps(p, ensure_ascii=False, sort_keys=True)))
    conn.commit()


def _kette(conn, app_id, gen=None, assess_status="done"):
    for t in CHAIN:
        _add(conn, app_id, t, assess_status if t == "assess_culture_fit" else "done", gen=gen)


def _app_ids(conn, sql, params=()):
    return sorted({json.loads(p)["application_id"]
                   for (p,) in conn.execute(sql, params)})


def _notify_hr_count(conn, app_id, gen=None):
    if gen is None:
        sql = ("SELECT COUNT(*) FROM agent_tasks WHERE task_type='notify_hr' "
               "AND json_extract(payload, '$.application_id') = ?")
        return conn.execute(sql, (app_id,)).fetchone()[0]
    sql = ("SELECT COUNT(*) FROM agent_tasks WHERE task_type='notify_hr' "
           "AND json_extract(payload, '$.application_id') = ? "
           "AND COALESCE(json_extract(payload, '$.gen'), 0) = ?")
    return conn.execute(sql, (app_id, gen)).fetchone()[0]


def _gatekeeper(conn, app_id, payload, ja=True):
    """Ruft den echten Code mit gemockter Entscheidung (kein DB-/Connector-Zugriff)."""
    with patch.object(mod, "gatekeeper_decision", lambda a: (ja, 85, "passend")):
        mod._maybe_gatekeeper(conn, app_id, payload)


def _payload(app_id, gen=None):
    p = {"application_id": app_id, "candidate_id": app_id, "job_id": 1}
    if gen is not None:
        p["gen"] = gen
    return p


# ─── Teil a: Bewerbungen 1 / 10 / 11 / 160 gemischt ───────────────────────

@pytest.fixture()
def mixed():
    """app 1: Kette fertig, KEIN notify_hr · app 10: fertig + notify_hr ·
    app 11: assess pending · app 160: fertig in Generation 1."""
    conn = _mem()
    _kette(conn, 1)
    _kette(conn, 10)
    _add(conn, 10, "notify_hr")
    _kette(conn, 11, assess_status="pending")
    _kette(conn, 160, gen=1)
    yield conn
    conn.close()


def test_kettenzustand_nur_eigene_zeilen(mixed):
    """(1) Die Zustands-Abfrage des Pförtners liefert für app 1 NUR eigene Zeilen."""
    neu = _app_ids(mixed,
                   """SELECT payload FROM agent_tasks
                      WHERE json_extract(payload, '$.application_id') = ?
                        AND COALESCE(json_extract(payload, '$.gen'), 0) = 0
                        AND task_type IN ('match_candidate','check_compliance',
                                          'assess_culture_fit')
                      ORDER BY id""",
                   (1,))
    assert neu == [1], f"json_extract darf nur app 1 liefern, lieferte {neu}"

    # Gegenprobe: die ALTTE LIKE-Variante des Pförtners kreuzt fremde Bewerbungen
    alt = _app_ids(mixed,
                   """SELECT payload FROM agent_tasks
                      WHERE payload LIKE ? AND task_type IN
                      ('match_candidate','check_compliance','assess_culture_fit')""",
                   ('%"application_id": 1%',))
    assert alt == [1, 10, 11, 160], f"LIKE-Kollision nicht belegt: {alt}"


def test_neuester_task_gewinnt(mixed):
    """ORDER BY id + Einspeisen in Reihenfolge: app 11s pending ist der neueste
    Stand seines Typs (fremde app 160-Zeilen duerfen den Zustand nicht ueberschreiben)."""
    rows = mixed.execute(
        """SELECT task_type, status FROM agent_tasks
           WHERE json_extract(payload, '$.application_id') = 11
             AND task_type IN ('match_candidate','check_compliance','assess_culture_fit')
           ORDER BY id""").fetchall()
    states = {}
    for t, s in rows:
        states[t] = s  # gleiche Reihenfolge-Logik wie im Pförtner
    assert states == {"match_candidate": "done", "check_compliance": "done",
                      "assess_culture_fit": "pending"}, states


def test_alt_like_wuerde_app1_blockieren(mixed):
    """(2)+(3) Gegenprobe mit dem ALTEN Pförtner-Code:
    LIKE zaehlt app 10s notify_hr als „bereits evaluiert" → app 1 bleibt blockiert.
    Der neue Code sieht nur app 1 (kein Marker) → evaluiert und markiert."""
    before = _notify_hr_count(mixed, 1)

    # alte Fassung (Replik des Zustands vor R3-1), nur fuer die Gegenprobe
    c = mixed.cursor()
    c.execute("""SELECT task_type, status FROM agent_tasks
                 WHERE payload LIKE ? AND task_type IN
                 ('match_candidate', 'check_compliance', 'assess_culture_fit')""",
              ('%"application_id": 1%',))
    alt_states = dict(c.fetchall())
    c.execute("""SELECT COUNT(*) FROM agent_tasks
                 WHERE payload LIKE ? AND task_type = 'notify_hr'""",
              ('%"application_id": 1%',))
    alt_marker = c.fetchone()[0]
    assert set(alt_states) == set(CHAIN), alt_states   # fremde Zeilen machen die Kette „fertig"
    assert alt_marker >= 1, "fremder Marker (app 10) blockiert app 1 in der LIKE-Variante"

    # neue Fassung: app 1 wird NICHT von app 10 geblockt
    _gatekeeper(mixed, 1, _payload(1))
    assert _notify_hr_count(mixed, 1) == before + 1, "app 1 muss evaluiert werden"
    assert _notify_hr_count(mixed, 10) == 1, "app 10 bleibt unveraendert"

    # idempotent: zweiter Lauf fuegt kein zweites notify_hr hinzu
    _gatekeeper(mixed, 1, _payload(1))
    assert _notify_hr_count(mixed, 1) == before + 1


def test_notify_hr_idempotenz_exakt(mixed):
    """(3) notify_hr existiert bei app 10, NICHT bei app 1."""
    assert _notify_hr_count(mixed, 10) == 1
    assert _notify_hr_count(mixed, 1) == 0
    _gatekeeper(mixed, 1, _payload(1))
    _gatekeeper(mixed, 10, _payload(10))
    assert _notify_hr_count(mixed, 1) == 1
    assert _notify_hr_count(mixed, 10) == 1
    # der neue Marker gehoert zu app 1 (json_extract, kein Präfix-Treffer)
    p = json.loads(mixed.execute(
        "SELECT payload FROM agent_tasks WHERE task_type='notify_hr' "
        "AND json_extract(payload,'$.application_id')=1").fetchone()[0])
    assert p["application_id"] == 1 and p["gen"] == 0


def test_unkomplette_eigene_kette_wird_nicht_durch_fremde_gerettet():
    """App 1 selbst unvollstaendig, alle fremden vollstaendig → kein notify_hr."""
    conn = _mem()
    try:
        _add(conn, 1, "match_candidate", "done")
        _add(conn, 1, "check_compliance", "done")
        _add(conn, 1, "assess_culture_fit", "pending")
        for foreign in (10, 11, 160):
            _kette(conn, foreign)
        _gatekeeper(conn, 1, _payload(1))
        assert _notify_hr_count(conn, 1) == 0, "unvollstaendige Kette darf nicht bewertet werden"
        assert _notify_hr_count(conn, 10) == 0
    finally:
        conn.close()


# ─── Teil b: Generation im Gatekeeper ──────────────────────────────────────

def test_alter_marker_gen0_blockiert_gen1_nicht():
    """Gen-0-notify_hr existiert, Gen-1-Kette fertig → genau EIN notify_hr gen 1,
    zweiter Sweep kein zweites."""
    conn = _mem()
    try:
        _kette(conn, 42, gen=0)
        _add(conn, 42, "notify_hr", gen=0)          # alte Generation
        _kette(conn, 42, gen=1)                      # Neubewerbung
        assert _notify_hr_count(conn, 42, gen=1) == 0

        _gatekeeper(conn, 42, _payload(42, gen=1))
        assert _notify_hr_count(conn, 42, gen=1) == 1, "alter Marker darf nicht blockieren"
        assert _notify_hr_count(conn, 42, gen=0) == 1, "alter Marker bleibt erhalten"

        _gatekeeper(conn, 42, _payload(42, gen=1))   # zweiter Sweep
        assert _notify_hr_count(conn, 42, gen=1) == 1, "idempotent pro Generation"
    finally:
        conn.close()


def test_altbestand_ohne_gen_wird_als_0_gelesen():
    """Bestands-Task ohne gen-Feld: COALESCE 0 — Verhalten unveraendert."""
    conn = _mem()
    try:
        _kette(conn, 7)                              # kein gen-Feld (Altbestand)
        _gatekeeper(conn, 7, _payload(7))            # muss wie bisher JA sagen
        assert _notify_hr_count(conn, 7, gen=0) == 1
        p = json.loads(conn.execute(
            "SELECT payload FROM agent_tasks WHERE task_type='notify_hr'").fetchone()[0])
        assert p["gen"] == 0, "notify_hr erbt current_gen (Altbestand = 0)"
    finally:
        conn.close()


def test_queue_dedupe_grenzt_ueber_gen_ab():
    """Gleicher Tag + Typ + App: gen 0 und gen 1 BEIDE gequeued, gleiches gen deduped.
    Laeuft gegen den pytest-Spiegel (tests/conftest.py), nie gegen die Live-DB."""
    app_id = 990301
    base = {"application_id": app_id, "candidate_id": 990301, "job_id": 990301}
    try:
        assert db.queue_agent_task("match_candidate", {**base, "gen": 0}) is not None
        assert db.queue_agent_task("match_candidate", {**base, "gen": 0}) is None, \
            "gleiches gen am selben Tag wird geduped"
        assert db.queue_agent_task("match_candidate", {**base, "gen": 1}) is not None, \
            "neues gen umgeht den Dedupe der alten Generation"
        conn = db.get_conn()
        try:
            gens = [json.loads(p)["gen"] for (p,) in conn.execute(
                "SELECT payload FROM agent_tasks WHERE task_type='match_candidate' "
                "AND json_extract(payload,'$.application_id') = ?", (app_id,))]
        finally:
            conn.close()
        assert sorted(gens) == [0, 1], gens
    finally:
        conn = db.get_conn()
        try:
            conn.execute("DELETE FROM agent_tasks "
                         "WHERE json_extract(payload,'$.application_id') = ?", (app_id,))
            conn.commit()
        finally:
            conn.close()


# ─── Teil c: apply_to_job queue't die Kette mit Generation ─────────────────

def _employer(conn) -> int:
    c = conn.cursor()
    c.execute("INSERT INTO employers (email, password_hash, firma, kontaktperson) "
              "VALUES ('r32-employer@example.invalid', 'x', 'R32 GmbH', 'HR')")
    return c.lastrowid


def _candidate(conn, nr: int) -> int:
    c = conn.cursor()
    c.execute("INSERT INTO candidates (name, email, status, password_hash) "
              "VALUES (?, ?, 'lebenslauf_hochgeladen', 'x')",
              (f"R32 K{nr}", f"r32-cand-{nr}@example.invalid"))
    return c.lastrowid


def _job(conn, emp_id: int, nr: int) -> int:
    c = conn.cursor()
    c.execute("INSERT INTO jobs (employer_id, titel, beschreibung, standort, "
              "stellentyp, hard_skills, status) "
              "VALUES (?, ?, 'R32 Teststelle', 'Berlin', 'Vollzeit', 'Python', 'aktiv')",
              (emp_id, f"R32 Job {nr}"))
    return c.lastrowid


def _tasks_for(app_id: int) -> list:
    conn = db.get_conn()
    try:
        return conn.execute(
            "SELECT task_type, payload FROM agent_tasks "
            "WHERE json_extract(payload, '$.application_id') = ? ORDER BY id",
            (app_id,)).fetchall()
    finally:
        conn.close()


def _set_zurueckgezogen(app_id: int) -> None:
    conn = db.get_conn()
    try:
        conn.execute("UPDATE applications SET status='zurückgezogen' WHERE id=?", (app_id,))
        conn.execute("INSERT INTO application_status_history "
                     "(application_id, status, changed_by) VALUES (?, 'zurückgezogen', 'kandidat')",
                     (app_id,))
        conn.commit()
    finally:
        conn.close()


def test_frische_bewerbung_queue_t_kette_mit_gen0():
    conn = db.get_conn()
    try:
        emp = _employer(conn)
        cid = _candidate(conn, 1)
        jid = _job(conn, emp, 1)
        conn.commit()  # apply_to_job nutzt EIGENE Verbindung -> Setup muss sichtbar sein
    finally:
        conn.close()
    try:
        app_id = db.apply_to_job(cid, jid, "R32 Erstbewerbung")
        tasks = _tasks_for(app_id)
        # Kettensaetze: apply_to_job listet 10 Task-Typen (Docstring „10-fach",
        # webui/db.py::apply_to_job) — der Aufgabentext nennt "9"; Befund in der
        # Runden-Meldung. Geprueft wird der vollstaendige Satz + Gen 0.
        assert len(tasks) == 10, [t for t, _ in tasks]
        assert {t for t, _ in tasks} == {
            "send_confirmation", "extract_profile", "match_candidate",
            "check_compliance", "assess_culture_fit", "verify_documents",
            "check_visa", "explain_match", "check_gdpr", "notify_user"}
        assert all(json.loads(p).get("gen") == 0 for _, p in tasks)
    finally:
        _cleanup_app(cid, emp)


def test_reaktivierung_queue_t_kette_mit_gen1():
    conn = db.get_conn()
    try:
        emp = _employer(conn)
        cid = _candidate(conn, 2)
        jid = _job(conn, emp, 2)
        conn.commit()  # apply_to_job nutzt EIGENE Verbindung -> Setup muss sichtbar sein
    finally:
        conn.close()
    try:
        app_id = db.apply_to_job(cid, jid, "R32 Erstbewerbung")
        _set_zurueckgezogen(app_id)
        neu = db.apply_to_job(cid, jid, "R32 Neubewerbung")
        assert neu == app_id, "Reaktivierung nutzt dieselbe applications-Zeile"

        tasks = _tasks_for(app_id)
        assert len(tasks) == 20, f"10 + 10 Tasks erwartet, bekam {len(tasks)}"
        gen0 = [json.loads(p)["gen"] for _, p in tasks[:10]]
        gen1 = [json.loads(p)["gen"] for _, p in tasks[10:]]
        assert gen0 == [0] * 10, gen0
        assert gen1 == [1] * 10, gen1
        assert {t for t, _ in tasks[10:]} == {t for t, _ in tasks[:10]}, \
            "Reaktivierung queue't dieselben Task-Typen wie die Erstbewerbung"

        conn = db.get_conn()
        try:
            apps = conn.execute("SELECT COUNT(*) FROM applications "
                                "WHERE candidate_id=? AND job_id=?", (cid, jid)).fetchone()[0]
            hist = [r[0] for r in conn.execute(
                "SELECT status FROM application_status_history "
                "WHERE application_id=? ORDER BY id", (app_id,))]
        finally:
            conn.close()
        assert apps == 1, "keine Doppelzeile"
        assert hist == ["eingegangen", "zurückgezogen", "eingegangen"], hist

        # Zweite Reaktivierung am selben Tag: Dedupe darf die neue Gen-Kette
        # nicht schlucken (gen 2), die Gen-1-Zeilen bleiben unangetastet.
        _set_zurueckgezogen(app_id)
        assert db.apply_to_job(cid, jid, "R32 Dritte Runde") == app_id
        tasks3 = _tasks_for(app_id)
        assert len(tasks3) == 30, f"30 Tasks erwartet, bekam {len(tasks3)}"
        assert [json.loads(p)["gen"] for _, p in tasks3[20:]] == [2] * 10
    finally:
        _cleanup_app(cid, emp)


def _cleanup_app(cid: int, emp: int) -> None:
    conn = db.get_conn()
    try:
        apps = [r[0] for r in conn.execute(
            "SELECT id FROM applications WHERE candidate_id=?", (cid,))]
        for a in apps:
            conn.execute("DELETE FROM application_status_history WHERE application_id=?", (a,))
            conn.execute("DELETE FROM agent_tasks "
                         "WHERE json_extract(payload,'$.application_id')=?", (a,))
            conn.execute("DELETE FROM applications WHERE id=?", (a,))
        conn.execute("DELETE FROM jobs WHERE employer_id=?", (emp,))
        conn.execute("DELETE FROM candidates WHERE id=?", (cid,))
        conn.execute("DELETE FROM employers WHERE id=?", (emp,))
        conn.commit()
    finally:
        conn.close()
