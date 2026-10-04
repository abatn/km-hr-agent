"""A1 (30.09.2026): Scoring-Logik des Sprachtests (webui/pages/candidate.py::score_answers).

Getestet wird die REINE Funktion (keine UI, keine DB). Die Fragen kommen echt
aus dem MCP-Server scripts/language-test-server.py (importlib + fastmcp-Client,
Tool "generate_test") für Deutsch/Englisch/Französisch x A1/B1 mit anzahl=20.

Nachgewiesen wird:
  * richtige Option je Frage        -> 100 %
  * jeweils eine falsche Option     -> 0 %
  * nicht beantwortet               -> 0 %
  * Frage ohne Lösung wird nie als korrekt gewertet ("" == "" ist kein Treffer)
  * doppelte Optionstexte werden über den Index eindeutig bewertet

Kombinationen, für die der Server (Seed-Pool leer und LLM nicht erreichbar)
0 Fragen liefert, werden mit Grund übersprungen — der 0-Fragen-Pfad selbst
wird separat getestet (kein Speichern, siehe candidate.py::show_results).
"""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from webui.pages.candidate import filter_valid_questions, score_answers  # noqa: E402

KOMBIS = [(sp, niv) for sp in ("Deutsch", "Englisch", "Französisch") for niv in ("A1", "B1")]


def _lade_fragen(sprache: str, niv: str) -> list:
    from fastmcp import Client

    spec = importlib.util.spec_from_file_location(
        "language_test_server", str(ROOT / "scripts" / "language-test-server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    async def _run():
        async with Client(mod.mcp) as cli:
            res = await cli.call_tool(
                "generate_test", {"sprache": sprache, "niv": niv, "anzahl": 20})
            return json.loads(res.data).get("fragen") or []

    return asyncio.run(_run())


@pytest.fixture(scope="module", params=KOMBIS, ids=[f"{s}-{n}" for s, n in KOMBIS])
def fragen(request):
    sprache, niv = request.param
    # wie candidate.py::load_questions: erst filtern, dann bewerten
    f = filter_valid_questions(_lade_fragen(sprache, niv))
    if not f:
        pytest.skip(f"Server liefert 0 Fragen für {sprache} {niv} "
                    "(Seed-Pool leer, LLM nicht erreichbar)")
    return f


def _richtiger_index(frage: dict) -> int:
    return "abcd".index(frage["loesung"].strip().lower())


def test_alle_richtig_index_100_prozent(fragen):
    antworten = {i: _richtiger_index(q) for i, q in enumerate(fragen)}
    punkte, details = score_answers(fragen, antworten)
    assert punkte == len(fragen)
    assert punkte / len(fragen) == 1.0
    assert all(d["korrekt"] for d in details)


def test_alle_richtig_optionstext_100_prozent(fragen):
    antworten = {i: q["antworten"][_richtiger_index(q)] for i, q in enumerate(fragen)}
    punkte, details = score_answers(fragen, antworten)
    assert punkte == len(fragen)


def test_alle_falsch_0_prozent(fragen):
    antworten = {}
    for i, q in enumerate(fragen):
        richtig = _richtiger_index(q)
        falsch = [k for k in range(len(q["antworten"])) if k != richtig]
        assert falsch, f"Frage {q.get('id')} hat keine falsche Option"
        antworten[i] = falsch[0]
    punkte, details = score_answers(fragen, antworten)
    assert punkte == 0
    assert not any(d["korrekt"] for d in details)


def test_nicht_beantwortet_0_prozent(fragen):
    punkte, details = score_answers(fragen, {})
    assert punkte == 0
    assert all(d["antwort"] == "" and d["korrekt"] is False for d in details)


def test_gemischt_zaehlt_nur_richtige(fragen):
    antworten = {}
    erwartet = 0
    for i, q in enumerate(fragen):
        if i % 2 == 0:
            antworten[i] = _richtiger_index(q)
            erwartet += 1
    punkte, _ = score_answers(fragen, antworten)
    assert punkte == erwartet


# ── Randfälle (synthetisch) ────────────────────────────────────────────

def test_leere_fragenliste():
    assert score_answers([], {}) == (0, [])


def test_frage_ohne_loesung_unbeantwortet_ist_nie_korrekt():
    fragen = [{"id": "X-1", "antworten": ["a1", "a2", "a3", "a4"], "loesung": ""}]
    assert score_answers(fragen, {})[0] == 0
    assert score_answers(fragen, {0: 0})[0] == 0


def test_loesung_gross_und_mit_leerzeichen():
    fragen = [{"id": "X-2", "antworten": ["p", "q", "r", "s"], "loesung": " C "}]
    assert score_answers(fragen, {0: 2})[0] == 1
    assert score_answers(fragen, {0: 1})[0] == 0


def test_doppelte_optionstexte_index_eindeutig():
    # Zwei identische Optionstexte: Bewertung per Index, nicht per erstem Text-Treffer
    fragen = [{"id": "X-3", "antworten": ["gleich", "gleich", "x", "y"], "loesung": "b"}]
    assert score_answers(fragen, {0: 1})[0] == 1
    assert score_answers(fragen, {0: 0})[0] == 0


def test_index_ausserhalb_und_unbekannter_text():
    fragen = [{"id": "X-4", "antworten": ["p", "q"], "loesung": "a"}]
    assert score_answers(fragen, {0: 7})[0] == 0
    assert score_answers(fragen, {0: "gibt es nicht"})[0] == 0
    assert score_answers(fragen, {0: True})[0] == 0  # bool ist kein Index


# ── filter_valid_questions ─────────────────────────────────────────────

def test_filter_entfernt_llm_platzhalterfrage():
    # Echter Fund: Französisch A1 lieferte {"id": "ID", "frage": "Frage", "loesung": "lösung"}
    platzhalter = {"id": "ID", "frage": "Frage", "antworten": ["a", "b", "c", "d"],
                   "loesung": "lösung", "quelle": "Quelle"}
    gut = {"id": "FR-A1-01", "frage": "Bonjour ?", "antworten": ["Oui", "Non", "-", "-"],
           "loesung": "a"}
    assert filter_valid_questions([platzhalter, gut]) == [gut]


def test_filter_randfaelle():
    assert filter_valid_questions([]) == []
    assert filter_valid_questions(None) == []
    ohne_loesung = {"id": "X", "frage": "Text?", "antworten": ["p", "q"], "loesung": ""}
    loesung_ausserhalb = {"id": "X", "frage": "Text?", "antworten": ["p", "q"], "loesung": "d"}
    nur_eine_option = {"id": "X", "frage": "Text?", "antworten": ["p", ""], "loesung": "a"}
    assert filter_valid_questions([ohne_loesung, loesung_ausserhalb, nur_eine_option, "kein dict"]) == []
