"""Verhaltenstests der E3-Helfer (V-14, 21.10.2026).

Teil-0-Befund: für `_parse_score`, `_report_stelle`, `_score_from_ergebnisse` und
`_gatekeeper_signature` existierten **nur Quelltext-Assertions** (statische
Stringprüfung im Test) — kein einziger Funktionsaufruf. Diese Datei prüft das
**Verhalten** gegen den echten Runner (importlib), nicht gegen den Quelltext.

Geprüfte Regeln (Quelle: `knowledge/system/agent-automation.md`, Stand 21.10.2026):
* `_parse_score` — Dezimal-Scores werden gekürzt gelesen (61.5 → 61).
* `_report_stelle` — „Stelle #N" und „Poste #N" (Altbestand FR).
* `_score_from_ergebnisse` — **nie** der Score einer anderen Stelle; job-genau,
  sonst Ein-Stellen-Fallback, sonst `None` („unbekannt"), **nie** `0`.
* `_gatekeeper_signature` — enthält die Score-Basis ⇒ Basiswechsel ⇒ neue Signatur.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location(
        "runner_e3", ROOT / "scripts" / "agent-runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── _parse_score ─────────────────────────────────────────────────────────
def test_parse_score_liest_ganzzahligen_wert():
    mod = _runner()
    assert mod._parse_score("**Match-Score:** 84/100 (tauglich)") == 84


def test_parse_score_kuerzt_dezimalwerte():
    """Dezimal-Scores werden gekürzt gelesen (61.5 → 61) — Design-Entscheidung."""
    mod = _runner()
    assert mod._parse_score("Match-Score: 61.5/100 (gut)") == 61


def test_parse_score_ignoriert_komma_variante_als_nichtnumerisch():
    """Die Komma-Variante „61,5" ist **kein** gültiger Zahlenwert (Python-Decimal-
    wäre nötig) ⇒ der Wert wird nicht übernommen (kein erfundener Score)."""
    mod = _runner()
    assert mod._parse_score("Match-Score: 61,5/100 (gut)") is None


def test_parse_score_ignoriert_grenzwert_ueber_100():
    """Werte > 100 sind ungültig ⇒ kein Score."""
    mod = _runner()
    assert mod._parse_score("Match-Score: 120/100 (gut)") is None


def test_parse_score_ignoriert_falsch_positives_token():
    """Ein Token wie „100/100 (alt)" im Fließtext darf keinen Score liefern,
    wenn die eigentliche Score-Zeile fehlt."""
    mod = _runner()
    txt = "Der alte Bericht nannte 100/100 (alt), aber ohne Scorezeile."
    assert mod._parse_score(txt) is None


def test_parse_score_ignoriert_zeilen_ohne_marker():
    mod = _runner()
    assert mod._parse_score("Match-Score: 84/100\nAndere Zeile") == 84
    assert mod._parse_score("Compliance: 90/100") is None


def test_parse_score_liest_kultur_fit_marker():
    mod = _runner()
    assert mod._parse_score("Culture-Fit-Score: 77/100", "Culture-Fit-Score") == 77


# ── _report_stelle ───────────────────────────────────────────────────────
def test_report_stelle_liest_stelle_nr():
    mod = _runner()
    txt = "# Match Candidate – Kandidat #13 / Stelle #12\n\n**Match-Score:** 52/100"
    assert mod._report_stelle(txt) == 12


def test_report_stelle_liest_alten_poste_marker():
    """Altbestand (FR) nutzte „Poste #N"."""
    mod = _runner()
    assert mod._report_stelle("# Match – Candidat #13 / Poste #9") == 9


def test_report_stelle_bei_mehreren_treffern_nimmt_den_ersten():
    mod = _runner()
    txt = "Stelle #12\n\nWeiter unten: Stelle #99"
    assert mod._report_stelle(txt) == 12


def test_report_stelle_ohne_angabe_ist_none():
    mod = _runner()
    assert mod._report_stelle("# Match – Kandidat #13") is None


# ── _score_from_ergebnisse (Regel V-13) ──────────────────────────────────
def _report(cand: int, score: int, stelle: int | None, tag: str) -> str:
    kopf = f"# Match Candidate – Kandidat #{cand}"
    if stelle is not None:
        kopf += f" / Stelle #{stelle}"
    return (f"{kopf}\n\n**Match-Score:** {score}/100 (passend)\n"
            f"**Kategorie:** passend\n\n*Erstellt {tag}*\n")


def test_score_ist_job_genau(tmp_path):
    """Der job-genau Report gewinnt — auch wenn er nicht der neueste ist."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-13-2026-09-17.md").write_text(
        _report(13, 84, 5, "17.09.2026"), encoding="utf-8")
    (tmp_path / "match_candidate-kandidat-13-2026-10-15.md").write_text(
        _report(13, 52, 12, "15.10.2026"), encoding="utf-8")
    score, kat = mod._score_from_ergebnisse(13, 12)
    assert score == 52, score
    assert kat == "passend", kat


def test_score_faellt_nie_auf_eine_andere_stelle_zurueck(tmp_path):
    """Kernregel V-13(a): der Score einer ANDEREN Stelle wird **nie** verwendet."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-13-2026-09-17.md").write_text(
        _report(13, 84, 5, "17.09.2026"), encoding="utf-8")
    score, kat = mod._score_from_ergebnisse(13, 12)
    assert score is None, f"fremder Score übernommen: {score}"
    assert "unbekannt" in kat, kat


def test_score_ein_stellen_fallback(tmp_path):
    """Regel V-13(c): genau eine Stelle ⇒ der Report dieser Stelle."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-13-2026-09-17.md").write_text(
        _report(13, 84, 5, "17.09.2026"), encoding="utf-8")
    score, _kat = mod._score_from_ergebnisse(13, None)
    assert score == 84, score


def test_score_zwei_reports_eine_stelle_liefert_den_neuesten(tmp_path):
    """V-13(c), Regression (22.10.2026): **zwei Reports, EINE Stelle** ⇒ der
    **neueste** Report dieser Stelle.

    Realfall: Kandidat 2 hat `…-2026-09-15.md` (80) und `…-2026-09-22.md` (90),
    beide mit „Stelle #1" ⇒ **eine** Stelle, **zwei** Reports. Der Code zählte
    vorher die *Reports* ⇒ Rückgabe „unbekannt" statt 90.
    """
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-2-2026-09-15.md").write_text(
        _report(2, 80, 1, "15.09.2026"), encoding="utf-8")
    (tmp_path / "match_candidate-kandidat-2-2026-09-22.md").write_text(
        _report(2, 90, 1, "22.09.2026"), encoding="utf-8")
    score, kat = mod._score_from_ergebnisse(2, None)
    assert score == 90, f"erwartet 90 (neuester Report der einzigen Stelle), war {score}"
    assert kat == "passend", kat
    # job-genau muss denselben Wert liefern
    assert mod._score_from_ergebnisse(2, 1)[0] == 90


def test_score_drei_reports_eine_stelle_liefert_den_neuesten(tmp_path):
    """V-13(c): die distinct-Stellen-Zählung ist unabhängig von der Report-Anzahl."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-3-2026-09-10.md").write_text(
        _report(3, 40, 7, "10.09.2026"), encoding="utf-8")
    (tmp_path / "match_candidate-kandidat-3-2026-09-18.md").write_text(
        _report(3, 55, 7, "18.09.2026"), encoding="utf-8")
    (tmp_path / "match_candidate-kandidat-3-2026-09-25.md").write_text(
        _report(3, 71, 7, "25.09.2026"), encoding="utf-8")
    score, _kat = mod._score_from_ergebnisse(3, None)
    assert score == 71, score


def test_score_zwei_reports_zwei_stellen_bleibt_unbekannt(tmp_path):
    """Gegenprobe: **zwei** distinct Stellen ⇒ kein Score (Regel V-13(d))."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-4-2026-09-15.md").write_text(
        _report(4, 80, 1, "15.09.2026"), encoding="utf-8")
    (tmp_path / "match_candidate-kandidat-4-2026-09-22.md").write_text(
        _report(4, 90, 2, "22.09.2026"), encoding="utf-8")
    score, kat = mod._score_from_ergebnisse(4, None)
    assert score is None, f"fremder Score übernommen: {score}"
    assert "unbekannt" in kat, kat


def test_score_zwei_reports_eine_stelle_und_report_ohne_stelle(tmp_path):
    """Gemischter Fall: ein Report **mit** Stelle, einer **ohne** ⇒ kein Score
    (die Zuordnung des stellenlosen Reports ist nicht belegbar)."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-5-2026-09-15.md").write_text(
        _report(5, 80, 1, "15.09.2026"), encoding="utf-8")
    (tmp_path / "match_candidate-kandidat-5-2026-09-22.md").write_text(
        "# Match – Kandidat #5\n\n**Match-Score:** 90/100 (passend)\n", encoding="utf-8")
    score, kat = mod._score_from_ergebnisse(5, None)
    assert score is None, f"nicht belegbarer Score übernommen: {score}"
    assert "unbekannt" in kat, kat


def test_score_ohne_bericht_ist_unbekannt_nicht_null(tmp_path):
    """Regel V-13(d): kein Bericht ⇒ `None` („unbekannt"), **kein** 0."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    score, kat = mod._score_from_ergebnisse(99, 1)
    assert score is None, score
    assert "unbekannt" in kat, kat


def test_score_ohne_stellenangabe_wird_verwendet(tmp_path):
    """Ein Report **ohne** Stellenangabe gilt für die Stelle (kein Stellenbezug
    ⇒ keine Verwechslungsgefahr)."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-7-2026-10-15.md").write_text(
        "# Match – Kandidat #7\n\n**Match-Score:** 66/100 (passend)\n", encoding="utf-8")
    score, _kat = mod._score_from_ergebnisse(7, 3)
    assert score == 66, score


def test_score_bevorzugt_den_neuesten_job_genauen_report(tmp_path):
    """Bei mehreren job-genauen Reports gewinnt der **neueste** (R5.1)."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-13-2026-09-17.md").write_text(
        _report(13, 40, 12, "17.09.2026"), encoding="utf-8")
    (tmp_path / "match_candidate-kandidat-13-2026-10-15.md").write_text(
        _report(13, 52, 12, "15.10.2026"), encoding="utf-8")
    score, _kat = mod._score_from_ergebnisse(13, 12)
    assert score == 52, score


# ── _gatekeeper_signature (Score-Basis) ─────────────────────────────────
def _db_mit_agent_tasks() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE agent_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending', payload TEXT NOT NULL, result_path TEXT,
        result_json TEXT, error_text TEXT, attempts INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, started_at TIMESTAMP,
        finished_at TIMESTAMP)""")
    conn.execute("""CREATE TABLE applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER, job_id INTEGER)""")
    return conn


def test_signatur_aendert_sich_bei_geaenderter_score_basis(tmp_path):
    """Score-Basis ist Teil der Signatur ⇒ Wechsel der Grundlage ⇒ Neubewertung."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    conn = _db_mit_agent_tasks()
    conn.execute("""INSERT INTO applications (id, candidate_id, job_id)
                    VALUES (39, 13, 12)""")
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('match_candidate', 'done',
                            '{"application_id": 39, "gen": 1}')""")
    conn.commit()
    sig1 = mod._gatekeeper_signature(conn.cursor(), 39, 1)
    # Gleiche Kette, aber die Score-Basis ändert sich (neuer Report).
    (tmp_path / "match_candidate-kandidat-13-2026-10-15.md").write_text(
        _report(13, 52, 12, "15.10.2026"), encoding="utf-8")
    sig2 = mod._gatekeeper_signature(conn.cursor(), 39, 1)
    conn.close()
    assert sig1 != sig2, (sig1, sig2)
    assert "score:" in sig2, sig2


def test_signatur_bleibt_stabil_bei_gleicher_basis(tmp_path):
    """Unveränderte Grundlage ⇒ **gleiche** Signatur (kein unnötiger Rebewertung)."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    (tmp_path / "match_candidate-kandidat-13-2026-10-15.md").write_text(
        _report(13, 52, 12, "15.10.2026"), encoding="utf-8")
    conn = _db_mit_agent_tasks()
    conn.execute("""INSERT INTO applications (id, candidate_id, job_id)
                    VALUES (39, 13, 12)""")
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('match_candidate', 'done',
                            '{"application_id": 39, "gen": 1}')""")
    conn.commit()
    sig1 = mod._gatekeeper_signature(conn.cursor(), 39, 1)
    sig2 = mod._gatekeeper_signature(conn.cursor(), 39, 1)
    conn.close()
    assert sig1 == sig2, (sig1, sig2)


def test_signatur_zeigt_unbekannten_score_ehrlich(tmp_path):
    """Ohne Bericht zur Stelle ⇒ „unbekannt" in der Signatur (kein 0)."""
    mod = _runner()
    mod.ERGEBNISSE = tmp_path
    conn = _db_mit_agent_tasks()
    conn.execute("""INSERT INTO applications (id, candidate_id, job_id)
                    VALUES (39, 13, 12)""")
    conn.commit()
    sig = mod._gatekeeper_signature(conn.cursor(), 39, 1)
    conn.close()
    assert "score:unbekannt" in sig, sig
