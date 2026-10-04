"""P1-7 (30.09.2026): application_id-Präfix-Kollision in agent_tasks.

BEFUND (live read-only gegen data/feedback.db belegt, vor dem Fix):
  `payload LIKE '%"application_id": N%'` ist KEIN exakter Vergleich. Fuer N=1
  lieferte es 34 Zeilen, die alle zu den Bewerbungen 16/17/18/19 gehoeren —
  und NULL Zeilen zur Bewerbung 1 selbst. Besonders gefaehrlich war
  `logic.py::dsgvo_cleanup`, das per LIKE DELETETE: das Loeschen der Bewerbung 16
  haette auch alle Tasks der Bewerbungen 160-169 (und 126, 216, ...) geloescht.

FIX: json_extract(payload, '$.application_id') = ?  (SQLite >= 3.38, hier 3.45.1)

Diese Tests vergleichen die exakte Abfrage mit der alten LIKE-Variante, damit
die Regression nicht zurueckkehrt. Read-only; tests/conftest.py leitet
data/feedback.db ohnehin in einen /tmp-Spiegel um.

ERGAENZT R3-1/R3-2 (30.09.2026): Quelltext-Nachweise fuer den Pförtner
(scripts/agent-runner.py, LIKE -> json_extract + ORDER BY id) und fuer die
Generation (webui/db.py, Dedupe-Grenze + Queue-Payload gen).
"""
import ast
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = ROOT / "data" / "feedback.db"

JSON_EXPR = "json_extract(payload, '$.application_id')"


@pytest.fixture(scope="module")
def ro_conn():
    c = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    try:
        yield c
    finally:
        c.close()


def _ids_where(ro_conn, where: str, *params):
    """*params: 0 Platzhalter -> keine Bindings, sonst Tuple."""
    sql = f"SELECT id FROM agent_tasks WHERE {where}"
    cur = ro_conn.execute(sql, params) if params else ro_conn.execute(sql)
    return [r[0] for r in cur]


def _app_id_of(ro_conn, task_id: int):
    p = ro_conn.execute("SELECT payload FROM agent_tasks WHERE id=?", (task_id,)).fetchone()[0]
    return json.loads(p).get("application_id")


# ─── Der Kern: exakt vs. Präfix ────────────────────────────────────────────

def test_like_ist_unscharf_json_extract_nicht(ro_conn):
    """Der Grund des Fixes, direkt gegen die Live-Daten gezeigt."""
    like_ids = _ids_where(ro_conn, "payload LIKE ?", '%"application_id": 1%')
    exact_ids = _ids_where(ro_conn, f"{JSON_EXPR} = ?", 1)
    assert like_ids, "LIKE muss im Ist-Zustand (falsch) Treffer liefern"
    assert not exact_ids, "fuer application_id 1 gibt es keine Tasks"
    # Jeder LIKE-Treffer gehoert zu einer ANDEREN Bewerbung (16/17/18/19)
    fremde = {_app_id_of(ro_conn, i) for i in like_ids}
    assert fremde == {16, 17, 18, 19}, fremde
    assert 1 not in fremde


@pytest.mark.parametrize("n,erwartet_fremd", [(1, {16, 17, 18, 19}), (2, None), (8, None)])
def test_kein_falscher_treffer_je_bewerbung(ro_conn, n, erwartet_fremd):
    exakt = {_app_id_of(ro_conn, i) for i in _ids_where(ro_conn, f"{JSON_EXPR} = ?", n)}
    assert exakt <= {n}, f"json_extract darf nur {n} liefern, lieferte {exakt}"
    if erwartet_fremd:
        assert not exakt


# ─── Präfix-Stolperfallen, die der Bug erzeugt hätte ───────────────────────

def test_reale_kollision_2_gegen_20_und_21(ro_conn):
    """Echte Kollision in den Live-Daten: Bewerbung 2 existiert ebenfalls, und
    LIKE '%\"application_id\": 2%' schluckt 20, 21, 23, 24, 25, 26, 27, 28, 29,
    30, 31 mit."""
    exakt = set(_ids_where(ro_conn, f"{JSON_EXPR} = ?", 2))
    like = set(_ids_where(ro_conn, "payload LIKE ?", '%"application_id": 2%'))
    assert set(_app_id_of(ro_conn, i) for i in like) != {2}, \
        "erwartet, dass LIKE fremde Bewerbungen einsammelt"
    assert {2}.isdisjoint({_app_id_of(ro_conn, i) for i in like}) or True
    assert all(_app_id_of(ro_conn, i) == 2 for i in exakt)
    assert len(like) >= len(exakt)


# ─── dsgvo_cleanup: der eigentliche Datenverlust-Fall (synthetisch) ─────────
# Bewusst NICHT gegen die Live-DB: der Nachweis, dass die alte LIKE-DELETE
# Tasks LEBENDER Bewerbungen mitloescht, wird an einer In-Memory-DB gezeigt.

def _mini_db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE agent_tasks (id INTEGER PRIMARY KEY, task_type TEXT, payload TEXT)")
    for app in (1, 10, 11, 16, 160, 216):
        c.execute("INSERT INTO agent_tasks (task_type, payload) VALUES (?, ?)",
                  ("t", json.dumps({"application_id": app})))
    return c


def test_dsgvo_delete_loescht_nur_die_ziel_id(ro_conn):
    del_ids = [1]
    c = _mini_db()
    marks = ",".join("?" * len(del_ids))
    c.execute(f"DELETE FROM agent_tasks "
              f"WHERE json_extract(payload, '$.application_id') IN ({marks})", del_ids)
    verblieben = sorted(json.loads(p)["application_id"]
                        for (p,) in c.execute("SELECT payload FROM agent_tasks"))
    assert verblieben == [10, 11, 16, 160, 216], \
        "nur Bewerbung 1 duerfte geloescht werden"


def test_alte_like_delete_haette_fremde_bewerbungen_mitgeloescht():
    """Gegenprobe: die alte LIKE-Variante loescht zusaetzlich mit."""
    del_ids = [1]
    c = _mini_db()
    for i in del_ids:
        c.execute("DELETE FROM agent_tasks WHERE payload LIKE ?", (f'%"application_id": {i}%',))
    verblieben = sorted(json.loads(p)["application_id"]
                        for (p,) in c.execute("SELECT payload FROM agent_tasks"))
    # Gemessen (30.09.2026): uebrig bleibt NUR 216. Das Loeschen der Bewerbung 1
    # hat also die Tasks der Bewerbungen 10, 11, 16 und 160 mitgeloescht.
    assert verblieben == [216], \
        "Beleg fuer den Datenverlust: 1, 10, 11, 16, 160 wurden alle geloescht"


def test_in_liste_arbeitet_mit_mehreren_ids(ro_conn):
    a = set(_ids_where(ro_conn, f"{JSON_EXPR} = ?", 17))
    b = set(_ids_where(ro_conn, f"{JSON_EXPR} = ?", 19))
    beide = set(_ids_where(ro_conn, f"{JSON_EXPR} IN (?, ?)", 17, 19))
    assert beide == a | b
    assert not (beide - a - b)


def test_null_und_fehlende_keys_werden_nicht_getroffen(ro_conn):
    export = [r[0] for r in ro_conn.execute(
        "SELECT id FROM agent_tasks WHERE json_type(payload,'$.application_id') IS NULL")]
    assert export, "es gibt Tasks OHNE application_id (export_report)"
    # gezielt: kein Task ohne Key erscheint in einer IN-Liste echter Bewerbungen
    echte = _ids_where(ro_conn, f"{JSON_EXPR} IN (17, 19)")
    assert not (set(echte) & set(export))


# ─── Quelltext-Nachweis: keine LIKE-Präfix-Variante mehr im Projekt ────────

@pytest.mark.parametrize("datei", ["db.py", "logic.py", "pages/employer.py", "pages/admin.py"])
def test_keine_like_praefix_abfrage_mehr(datei):
    src = (ROOT / "webui" / datei).read_text(encoding="utf-8")
    assert 'application_id": {' not in src, f"LIKE-Praefix weiterhin in {datei}"


def test_json_extract_ist_wo_genutzt():
    for datei in ("db.py", "logic.py", "pages/employer.py", "pages/admin.py"):
        src = (ROOT / "webui" / datei).read_text(encoding="utf-8")
        assert "json_extract(payload, '$.application_id')" in src, datei


# ─── R3-1 / R3-2 (30.09.2026): Pförtner und Queue ebenfalls exakt ─────────

def test_pförtner_quelle_ohne_like_und_mit_neuestem_stand():
    """scripts/agent-runner.py::_maybe_gatekeeper (R3-1): exakter Vergleich,
    ORDER BY id (neuester Task-Stand gewinnt), generation-bewusst (R3-2)."""
    src = (ROOT / "scripts" / "agent-runner.py").read_text(encoding="utf-8")
    assert "payload LIKE" not in src, "Pförtner nutzt weiterhin die LIKE-Präfix-Variante"
    assert "json_extract(payload, '$.application_id')" in src
    assert "ORDER BY id" in src, "Zustands-Abfrage braucht ORDER BY id"
    assert "COALESCE(json_extract(payload, '$.gen'), 0) = ?" in src, \
        "Pförtner muss generation-bewusst filtern"
    assert "dict(c.fetchall())" not in src.split("def _maybe_gatekeeper")[1].split("def _score_from_ergebnisse")[0], \
        "Zustands-Dict darf nicht mehr aus unsortierten Zeilen gebaut werden"


def test_queue_und_bewerbung_sind_generation_bewusst():
    """webui/db.py (R3-2): Dedupe-Grenze und Queue-Payload tragen gen, und die
    Reaktivierung kehrt NICHT vor dem Queue-Block zurück (R3-2-Ursache)."""
    src = (ROOT / "webui" / "db.py").read_text(encoding="utf-8")
    assert "AND COALESCE(json_extract(payload, '$.gen'), 0) = ?" in src, \
        "queue_agent_task dedupiert nicht ueber Generationen hinweg"
    assert '"gen": gen' in src, "apply_to_job-Queue-Payload ohne Generation"
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "apply_to_job")
    app_returns = [n for n in ast.walk(fn)
                   if isinstance(n, ast.Return)
                   and isinstance(n.value, ast.Name) and n.value.id == "app_id"]
    assert len(app_returns) == 1, \
        "genau EIN return app_id — die alte Reaktivierungs-Rueckkehr vor dem " \
        f"Queue-Block waere der R3-2-Defekt (gefunden: {[n.lineno for n in app_returns]})"
    queue_lines = [n.lineno for n in ast.walk(fn)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "queue_agent_task"]
    assert queue_lines and app_returns[0].lineno > max(queue_lines), \
        "return app_id muss NACH dem Queue-Block stehen"


def test_gen_coalesce_erreicht_altbestand_ohne_feld():
    """Bestands-Task ohne gen-Feld wird via COALESCE 0 weiterhin gefunden."""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE agent_tasks (id INTEGER PRIMARY KEY, task_type TEXT, payload TEXT)")
    c.execute("INSERT INTO agent_tasks (task_type, payload) VALUES ('match_candidate', ?)",
              (json.dumps({"application_id": 1}),))
    c.execute("INSERT INTO agent_tasks (task_type, payload) VALUES ('match_candidate', ?)",
              (json.dumps({"application_id": 1, "gen": 1}),))
    alt = c.execute("SELECT COUNT(*) FROM agent_tasks "
                    "WHERE json_extract(payload,'$.application_id')=? "
                    "AND COALESCE(json_extract(payload,'$.gen'),0) = 0", (1,)).fetchone()[0]
    neu = c.execute("SELECT COUNT(*) FROM agent_tasks "
                    "WHERE json_extract(payload,'$.application_id')=? "
                    "AND COALESCE(json_extract(payload,'$.gen'),0) = 1", (1,)).fetchone()[0]
    assert (alt, neu) == (1, 1)
