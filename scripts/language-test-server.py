#!/usr/bin/env python3
"""
Language-Test-MCP-Server für KM-HR-Agent
Kostenlose CEFR-Niveautests mit LLM-Bewertung.
Quelle: knowledge/language-tests.md (732 Fragen: DE 120, EN 522, FR 90) + LLM-generiert (hybrid)
"""

from fastmcp import FastMCP
import json
import sys
import random
import os
import re
import requests
from pathlib import Path

mcp = FastMCP("language-test")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_FILE = PROJECT_ROOT / "knowledge" / "language-tests.md"

# ─── NVIDIA API (wie in agent-runner.py) ──────────────────────────────
_env_runner = PROJECT_ROOT / ".env-runner"
if _env_runner.exists():
    for _line in _env_runner.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

LLM_MODEL = os.environ.get("KMHR_LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b")
FALLBACK_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def _parse_questions() -> dict:
    """Liest knowledge/language-tests.md und parsst Fragen nach Sprache+Niveau."""
    if not TESTS_FILE.exists():
        return {}
    content = TESTS_FILE.read_text(encoding="utf-8")
    questions = {}
    current_lang = None
    current_level = None

    for line in content.split("\n"):
        line = line.strip()
        # Erkennung: "## Deutsch A1→A2" oder "## Englisch A2 (OpenExamPrep...)"
        m = re.match(r"^##\s+(Deutsch|Englisch|Französisch)\s+(A1|A2|B1|B2|C1|C2)", line)
        if m:
            current_lang = m.group(1)
            current_level = m.group(2)
            key = f"{current_lang}_{current_level}"
            if key not in questions:
                questions[key] = []
            continue

        # Fragen-Zeilen: "| ID | Frage | a | b | c | d | Lösung | Quelle |"
        if line.startswith("|") and current_lang and current_level:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 8 and parts[1] and not parts[1].startswith("---") and parts[1] != "ID":
                q_id = parts[1]
                frage = parts[2]
                # 8 Spalten: ID | Frage | a | b | c | d | Lösung | Quelle
                antworten = [parts[3], parts[4], parts[5], parts[6]]
                loesung = parts[7]
                quell_url = parts[8] if len(parts) > 8 else ""
                questions.setdefault(f"{current_lang}_{current_level}", []).append({
                    "id": q_id,
                    "frage": frage,
                    "antworten": antworten[:4],
                    "loesung": loesung.strip().lower() if loesung else "",
                    "quelle": quell_url
                })
    return questions


def _call_nvidia(prompt: str, model: str = None) -> str:
    """Ruft die NVIDIA API auf (wie in agent-runner.py)."""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return '{"punkte": 0, "korrekt": false, "feedback": "API-Key fehlt"}'
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "model": model or LLM_MODEL,
        # A2-Fix (01.10.2026): 200 reichte NICHT — nemotron-3-super ist ein
        # Reasoning-Modell (message.reasoning_content) und lieferte bei finish=length
        # HTTP 200 mit "content": null -> None -> AttributeError '.split' in
        # _generate_llm_questions (gemessen 01.10.2026, 3x reproduzierbar).
        # 4000 = Design-Entscheidung (Deckel für 20 Fragen-Tabelle + Reasoning-Overhead,
        # keine externe Quelle noetig — nur ein API-Parameter-Ceiling).
        "max_tokens": 4000,
        "stream": False,
        "temperature": 0,
    }
    # Latenz-Fix (14.10.2026): try/except PRO Modell — vorher umschloss EIN try die
    # ganze Schleife, ein ReadTimeout auf Modell 1 verliess den Block sofort und
    # FALLBACK_MODEL wurde nur bei HTTP != 200 via continue erreicht, nie bei
    # Netzfehlern (belegt: je 1 stderr-Meldung bei 2 gescheiterten EN-A1/20-Runs).
    # timeout 30->45: Baseline 14.10.2026 brauchte EN-A1/20 bei 30 s in 3/3 Laeufen
    # >33 s (ReadTimeout), anzahl=5 in 3/3 Laeufen nur 6,2-8,8 s; 45 s bleibt mit
    # 15 s Headroom unter dem 60-s-Budget aus agent-runner.py:147 (pdf-verify-mcp;
    # der Language-Test laeuft in-process via webui/pages/candidate.py, ohne Cap).
    for m in (model or LLM_MODEL, FALLBACK_MODEL):
        payload["model"] = m
        try:
            r = requests.post(API_URL, headers=headers, json=payload, timeout=45)
            if r.status_code != 200:
                continue
            # .get("content", "") wuerde None zurueckgeben, wenn der Key existiert,
            # aber null liefert -> "or \"\"" + leerer Inhalt = Fallback-Modell versuchen
            content = r.json()["choices"][0]["message"].get("content") or ""
            if content.strip():
                return content
        except Exception as ex:  # kein stilles pass (Regel): Fehler pro Modell sichtbar, Schleife faehrt fort
            print(f"[language-test] NVIDIA-Aufruf fehlgeschlagen ({m}): {type(ex).__name__}: {ex}",
                  file=sys.stderr)
    return '{"punkte": 0, "korrekt": false, "feedback": "API-Fehler"}'


# ─── Tool 1: generate_test ───────────────────────────────────────────

def _generate_llm_questions(sprache: str, niv: str, anzahl: int) -> list:
    """Generiert Fragen via LLM (NVIDIA API) als Ergänzung zu Seed-Fragen."""
    prompt = f"""Du bist ein Sprachlehrer. Erstelle {anzahl} Multiple-Choice-Fragen für Niveau {niv} in {sprache}.

Format (exakt einhalten, pipe-getrennt):
| ID | Frage | a | b | c | d | Lösung | Quelle |

Regeln:
- Jede Frage hat 4 Antwortoptionen (a, b, c, d)
- Lösung ist ein Buchstabe (a, b, c oder d)
- Niveau {niv} muss eingehalten werden (nicht zu einfach, nicht zu schwer)
- Themen: Alltag, Grammatik, Wortschatz, Leseverstehen
- KEINE Erklärungen, NUR die Tabelle
- ID-Format: LLM-{sprache[:2]}-{niv}-01, LLM-{sprache[:2]}-{niv}-02, etc.
- Quelle: LLM-generiert (NVIDIA {LLM_MODEL})"""

    result_text = _call_nvidia(prompt)
    fragen = []
    for line in result_text.split("\n"):
        line = line.strip()
        if line.startswith("|") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 8 and parts[1] and not parts[1].startswith("---"):
                fragen.append({
                    "id": parts[1],
                    "frage": parts[2],
                    "antworten": [parts[3], parts[4], parts[5], parts[6]],
                    "loesung": parts[7].strip().lower(),
                    "quelle": parts[8] if len(parts) > 8 else "LLM-generiert",
                    "typ": "llm"
                })
    return fragen[:anzahl]


@mcp.tool()
def generate_test(sprache: str, niv: str, anzahl: int = 10) -> str:
    """
    Generiert einen Sprachtest: Seed-Fragen (offiziell) + LLM-Fragen (ergänzend).

    Args:
        sprache: "Deutsch", "Englisch" oder "Französisch"
        niv: "A1", "A2", "B1", "B2" oder "C1"
        anzahl: Anzahl der Fragen (max. 20, default 10)

    Returns:
        JSON-String mit Fragen (id, frage, antworten, quelle, typ)
    """
    questions = _parse_questions()
    key = f"{sprache}_{niv}"
    seed_pool = questions.get(key, [])

    # Seed-Fragen nehmen (bis max. anzahl)
    seed_anzahl = min(anzahl, len(seed_pool))
    auswahl = random.sample(seed_pool, seed_anzahl) if seed_anzahl > 0 else []

    # LLM-Fragen generieren (Rest)
    llm_bedarf = anzahl - len(auswahl)
    if llm_bedarf > 0:
        llm_fragen = _generate_llm_questions(sprache, niv, llm_bedarf)
        auswahl.extend(llm_fragen)

    return json.dumps({
        "sprache": sprache,
        "niveau": niv,
        "anzahl": len(auswahl),
        # ehrliche Buchhaltung (14.10.2026): vorher "len(auswahl) - llm_bedarf" =>
        # -20 im Fehlerfall (0 Fragen, llm_bedarf=20); jetzt echte Seed-Treffer
        "seed": len(auswahl) - len(llm_fragen) if llm_bedarf > 0 else len(auswahl),
        "llm": len(llm_fragen) if llm_bedarf > 0 else 0,
        "fragen": auswahl
    }, ensure_ascii=False, indent=2)


# ─── Tool 2: score_answer ────────────────────────────────────────────

@mcp.tool()
def score_answer(frage_id: str, antwort: str, sprache: str) -> str:
    """
    Bewertet eine Antwort mit LLM (NVIDIA API).

    Args:
        frage_id: ID der Frage (z.B. "DE-A1-01")
        antwort: Antwort des Kandidaten (Text oder a/b/c/d)
        sprache: Sprache für Feedback

    Returns:
        JSON-String mit punkte (0-1), korrekt (bool), feedback (str)
    """
    # Frage finden
    questions = _parse_questions()
    frage = None
    for key, pool in questions.items():
        for q in pool:
            if q["id"] == frage_id:
                frage = q
                break
        if frage:
            break

    if not frage:
        return json.dumps({"error": f"Frage {frage_id} nicht gefunden"})

    # LLM-Prompt
    prompt = f"""Du bist ein Sprachlehrer. Prüfe ob die Antwort korrekt ist.

Frage: {frage['frage']}
Antwortmöglichkeiten: {', '.join(frage['antworten'][:4])}
Richtige Antwort: {frage['loesung']}
Kandidaten-Antwort: {antwort}

Antworte NUR mit JSON: {{"punkte": 0 oder 1, "korrekt": true oder false, "feedback": "Kurze Erklärung"}}"""

    result_text = _call_nvidia(prompt)

    # JSON parsen
    try:
        # Versuche JSON aus dem LLM-Output zu extrahieren
        json_match = re.search(r'\{[^}]+\}', result_text)
        if json_match:
            return json_match.group(0)
    except Exception:
        pass

    # Fallback: Einfache Bewertung
    antwort_lower = antwort.strip().lower()
    loesung_lower = frage["loesung"].strip().lower()
    korrekt = antwort_lower == loesung_lower or antwort_lower in loesung_lower
    return json.dumps({
        "punkte": 1 if korrekt else 0,
        "korrekt": korrekt,
        "feedback": f"Richtige Antwort: {frage['loesung']}"
    }, ensure_ascii=False)


# ─── Tool 3: get_cefr_level ──────────────────────────────────────────

@mcp.tool()
def get_cefr_level(gesamtpunkte: float, sprache: str) -> str:
    """
    Berechnet das CEFR-Level basierend auf dem Gesamtscore.

    Args:
        gesamtpunkte: Durchschnittlicher Score (0.0-1.0)
        sprache: Sprache für Beschreibung

    Returns:
        JSON-String mit level, beschreibung, empfehlung
    """
    # Lookup-Tabelle (Design-Entscheidung: basierend auf CEFR Grid)
    levels = [
        (0.0, 0.2, "A1", "Anfänger", "Einfache Alltagssätze, Begrüßungen, Zahlen"),
        (0.2, 0.4, "A2", "Grundkenntnisse", "Leichte Texte verstehen, Formulare ausfüllen"),
        (0.4, 0.6, "B1", "Mittelstufe", "Alltagsgespräche, einfache Zusammenhänge"),
        (0.6, 0.8, "B2", "Obere Mittelstufe", "Komplexe Texte, Fachbegriffe"),
        (0.8, 1.0, "C1", "Fortgeschritten", "Fließend, Nuancen, Fachsprache"),
    ]

    for min_s, max_s, level, beschreibung, empfehlung in levels:
        if min_s <= gesamtpunkte < max_s or (max_s == 1.0 and gesamtpunkte >= min_s):
            return json.dumps({
                "level": level,
                "beschreibung": beschreibung,
                "empfehlung": empfehlung,
                "gesamtpunkte": round(gesamtpunkte, 2),
                "sprache": sprache
            }, ensure_ascii=False)

    return json.dumps({
        "level": "A1",
        "beschreibung": "Anfänger",
        "empfehlung": "Grundkurs empfohlen",
        "gesamtpunkte": round(gesamtpunkte, 2),
        "sprache": sprache
    }, ensure_ascii=False)


# ─── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
