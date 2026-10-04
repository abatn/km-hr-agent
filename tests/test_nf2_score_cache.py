"""N-F2 (01.10.2026): Score-Berechnung je Passivkandidat — Connector-Zähler + Cache.

Befund: der Feedback-Picker (`_page_feedback.refresh_cands`) ruft `berechne_match_score`
je Passivkandidat (bis zu 20 je Render). Soll: keine Subprozess-/Connector-Calls je
Kandidat + Gewichtungs-Cache mit Signatur (Muster wie M-16).

Belege:
  1. Connector-Zähler: 0 `_mcp_connector_call`/`_static_connector_call` bei N Kandidaten.
  2. `get_current_weights` cached per Signatur (COUNT, MAX(id) der gewichtung_historie);
     neue Zeile → Signatur ändert sich → Neuberechnung.

Ohne Live-DB: temporäre DB-Datei.
"""
import sqlite3
from pathlib import Path

from webui import logic


def _mk_k():
    return {"hard_skills": "python,docker,kubernetes", "soft_skills": "team",
            "berufserfahrung_jahre": 6, "abschluss": "Master",
            "deutsch": "B2", "englisch": "C1", "standort": "Berlin",
            "lebenslauf_text": "python docker kubernetes berlin"}


def _mk_j():
    return {"hard_skills": "python,docker", "soft_skills": "team",
            "berufserfahrung_jahre": 5, "deutsch_level": "B1", "englisch_level": "B2",
            "standort": "Berlin", "stellentyp": "Vollzeit", "branche": "IT"}


# ─── 1. kein Connector-Aufruf je Kandidat ──────────────────────────────────

def test_berechne_match_score_ohne_connector(monkeypatch):
    calls = []
    monkeypatch.setattr(logic, "_mcp_connector_call",
                        lambda *a, **k: calls.append(("mcp", a)) or {})
    monkeypatch.setattr(logic, "_static_connector_call",
                        lambda *a, **k: calls.append(("static", a)) or {})
    for _ in range(20):  # simuliert einen Picker-Render mit 20 Passivkandidaten
        r = logic.berechne_match_score(_mk_k(), _mk_j())
        assert "total" in r
    assert calls == [], f"Connector-Aufrufe je Kandidat: {calls}"


# ─── 2. Signatur-Cache ─────────────────────────────────────────────────────

def _tmp_db(tmp_path: Path) -> Path:
    p = tmp_path / "w.db"
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE gewichtung_historie (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                 "kategorie TEXT, neue_gewichtung INTEGER)")
    conn.commit()
    conn.close()
    return p


def test_weights_cache_trifft_und_invalidiert(tmp_path, monkeypatch):
    p = _tmp_db(tmp_path)
    monkeypatch.setattr(logic, "DB_PATH", p)
    logic._WEIGHTS_CACHE.clear()

    a = logic.get_current_weights()          # 1. Aufruf → Query + Cache
    assert len(logic._WEIGHTS_CACHE) == 1
    b = logic.get_current_weights()          # 2. Aufruf → Cache-Hit
    assert a == b
    assert len(logic._WEIGHTS_CACHE) == 1    # kein zweiter Eintrag

    # neue Zeile → Signatur (COUNT, MAX(id)) ändert sich → Neuberechnung
    conn = sqlite3.connect(str(p))
    conn.execute("INSERT INTO gewichtung_historie (kategorie, neue_gewichtung) "
                 "VALUES ('Berufserfahrung', 40)")
    conn.commit()
    conn.close()
    c = logic.get_current_weights()
    assert c != b, "Cache haette nach neuer gewichtung_historie-Zeile invalidieren muessen"
    assert len(logic._WEIGHTS_CACHE) == 2


def test_weights_cache_hit_vor_query(tmp_path, monkeypatch):
    """Strukturbeleg: Cache-Hit kehrt VOR dem SELECT zurueck (keine Query)."""
    import inspect
    src = inspect.getsource(logic.get_current_weights)
    i_hit = src.index("_WEIGHTS_CACHE.get(sig)")
    # Die Signatur-Query ist der erste conn.execute; die CACHE-Pruefung muss vor
    # der eigentlichen Gewichtungs-Query stehen (sonst waere sie wirkungslos).
    i_query = src.index("SELECT kategorie, neue_gewichtung")
    assert i_hit < i_query, "Cache-Pruefung muss vor der Gewichtungs-Query stehen"
