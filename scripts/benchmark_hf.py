#!/usr/bin/env python3
"""
Benchmark: DjallelBr/job-matching-dataset vs. KM-HR-Agent Matching-System.
Lädt Test-Zeilen von HuggingFace, parsed Features, berechnet unseren Score,
vergleicht mit dem LLM-Score aus dem Dataset.

Phase-E Runde 3 (25.09.2026) – P4-Option (y) "separater Benchmark-Adapter":
  N4      Endpunkt/Dataset/Split/Seitenlogik liegen in
          scripts/benchmark_hf_config.json (Fremd-URLs = Daten, kein Code).
  N2      Gewichte live aus webui.logic.get_current_weights(), Fallback =
          BASELINE_GEWINCHTE (webui/logic.py:182-185), Rundung auf 1
          Nachkommastelle = Design-Entscheidung (an P1a angelehnt).
  Adapter Separates Mapping auf die 4 Dataset-Kriterien
          (Empfehlung 4, ergebnisse/benchmark-huggingface-dataset.md:83) +
          partielle Korrelation nur Kern+Erfahrung+Bildung (Empfehlung 1, :80).
  N1      Die 4. Score-Kopie (berechne_match_score) bleibt bestehen (N3:
          Dataset-Felder ≠ DB-Felder) – Drift-Hinweis im Funktionsdocstring.
"""
import json
import random
import re
import statistics
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent

# ── 0. Konfiguration (N4: Fremd-URL raus aus dem Code) ────────────
CONFIG_PATH = Path(__file__).with_name("benchmark_hf_config.json")
if not CONFIG_PATH.is_file():
    sys.exit(
        "[FEHLER] Konfigurationsdatei fehlt.\n"
        f"  Gesucht: {CONFIG_PATH}\n"
        "  Erwartet: scripts/benchmark_hf_config.json (neben scripts/benchmark_hf.py)\n"
        "  Pflichtfelder: endpoint_base, dataset, config, split, max_rows, page_size\n"
        "  (P4/N4: Der HuggingFace-Endpunkt steht in dieser JSON-Datei, nicht im Code.)"
    )
try:
    with CONFIG_PATH.open(encoding="utf-8") as _fh:
        CFG = json.load(_fh)
except json.JSONDecodeError as _exc:
    sys.exit(f"[FEHLER] Konfiguration ist kein gültiges JSON: {CONFIG_PATH}\n  {_exc}")

for _pflicht in ("endpoint_base", "dataset", "config", "split", "max_rows", "page_size"):
    if _pflicht not in CFG:
        sys.exit(f"[FEHLER] Pflichtfeld '{_pflicht}' fehlt in {CONFIG_PATH}")

PAGE_SIZE = int(CFG["page_size"])
MAX_ROWS = int(CFG["max_rows"])

print("[0] Konfiguration (N4):")
print(f"    → {CONFIG_PATH}")
print(f"    → dataset={CFG['dataset']} · config={CFG['config']} · split={CFG['split']}"
      f" · max_rows={MAX_ROWS} · page_size={PAGE_SIZE}")


# ── 0.1 Gewichte (N2: Live-Gewichte statt harter Baseline-Konstante) ─
BASELINE_GEWINCHTE = {"kern": 30, "erfahrung": 25, "bildung": 15, "standort": 10,
                      "branche": 10, "soft": 10, "sprache": 0}
GEWICHTE_REIHENFOLGE = ("kern", "erfahrung", "bildung", "standort",
                        "branche", "soft", "sprache")


def lade_gewichte() -> dict:
    """N2 (Phase-E Runde 3): Live-Gewichte des Produkt-Scoring.

    Lazy-Import von webui.logic.get_current_weights(); Projekt-Root wird vorher
    auf sys.path gesetzt (analog scripts/agent-runner.py:43). Jeder Fehler →
    Fallback auf die Baseline (webui/logic.py:182-185) + Log-Zeile, damit der
    Benchmark nie an den Gewichten scheitert.
    Rundung auf 1 Nachkommastelle = Design-Entscheidung (an P1a angelehnt).
    """
    sys.path.insert(0, str(PROJEKT_ROOT))
    try:
        from webui.logic import get_current_weights  # lazy Import (N2)
        roh = get_current_weights()
        gewichte = {k: round(float(roh[k]), 1) for k in GEWICHTE_REIHENFOLGE}
        quelle = "LIVE (webui.logic.get_current_weights)"
    except Exception as exc:  # noqa: BLE001 – bewusst breit: Benchmark läuft auch ohne Produkt-Import
        gewichte = {k: float(v) for k, v in BASELINE_GEWINCHTE.items()}
        quelle = ("FALLBACK Baseline (Design-Entscheidung 30/25/15/10/10/10/0)"
                  f" – Grund: {type(exc).__name__}: {exc}")
    print("[1] Gewichte (N2):")
    print(f"    → Quelle: {quelle}")
    print("    → " + " / ".join(f"{k} {gewichte[k]:.1f}" for k in GEWICHTE_REIHENFOLGE))
    return gewichte


GEWICHTE = lade_gewichte()


def pearson(xs, ys) -> float:
    """Pearson-Korrelation (Formel unverändert, nur als Funktion ausgekoppelt,
    damit Gesamt-, Adapter- und partielle Korrelation dieselbe rechnen)."""
    n = len(xs)
    if n < 2:
        return 0.0
    sum_xy = sum(a * b for a, b in zip(xs, ys))
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_x2 = sum(a**2 for a in xs)
    sum_y2 = sum(b**2 for b in ys)
    numerator = n * sum_xy - sum_x * sum_y
    denominator = ((n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2)) ** 0.5
    return numerator / denominator if denominator != 0 else 0.0


# ── 1. Dataset laden ──────────────────────────────────────────────
print("\n[2] Lade Test-Zeilen …")
all_rows = []
offset = 0
load_error = None
while offset < MAX_ROWS:
    url = "{}?{}".format(
        CFG["endpoint_base"],
        urllib.parse.urlencode({
            "dataset": CFG["dataset"],
            "config": CFG["config"],
            "split": CFG["split"],
            "offset": offset,
            "length": PAGE_SIZE,
        }),
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read())
    except Exception as exc:  # noqa: BLE001 – Rundenbefund statt Crash-Stapel
        load_error = f"{type(exc).__name__}: {exc}"
        break
    if not batch.get("rows"):
        break
    all_rows.extend(batch["rows"])
    offset += PAGE_SIZE
    if len(batch["rows"]) < PAGE_SIZE:
        break

if load_error:
    print(f"    ⚠ Abruffehler: {load_error}")
    print(f"      Endpunkt (aus Konfiguration): {CFG['endpoint_base']}"
          f" · dataset={CFG['dataset']} · split={CFG['split']}")
if len(all_rows) < 2:
    sys.exit(
        f"[FEHLER] Nur {len(all_rows)} Zeilen geladen – Statistik/Korrelation nicht berechenbar."
        + ("" if not load_error else
           f"\n         Ursache: {load_error}"
           "\n         → Netzwerk-/Endpunktfehler = Rundenbefund, kein Benchmark-Ergebnis.")
    )
print(f"    → {len(all_rows)} Zeilen geladen (Split={CFG['split']}).")

# ── 2. Prompt parsen ──────────────────────────────────────────────
def parse_prompt(text: str) -> dict:
    """Extrahiert Job- und Candidate-Features aus dem Dataset-Prompt."""
    result = {}
    fields = [
        "career_objective", "skills", "degree_names",
        "major_field_of_studies", "professional_company_names",
        "job_position_name", "educational_requirements",
        "experience_requirement", "responsibilities", "skills_required",
    ]
    for field in fields:
        other_fields = [f for f in fields if f != field]
        boundary = "|".join(re.escape(f + ":") for f in other_fields)
        pattern = rf"{re.escape(field)}:\s*(.*?)(?=\s*(?:{boundary})\s|Match score)"
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        result[field] = m.group(1).strip().rstrip("|").strip() if m else ""
    return result


# ── 3. Unser Matching-System ──────────────────────────────────────
# Kategorie-Maxima bleiben unangetastet (P4/y: nur die Gewichte werden live gespeist).
KATEGORIE_MAX = {"kern": 30, "erfahrung": 30, "bildung": 15, "standort": 10,
                 "branche": 10, "soft": 10, "sprache": 10}
# GEWICHTE ist hier KEINE Konstante mehr, sondern das Ergebnis von lade_gewichte() (N2).

SKILL_SYNONYME = {
    "kubernetes": "k8s", "k8s": "kubernetes",
    "javascript": "js", "js": "javascript",
    "python3": "python",
    "react.js": "react", "reactjs": "react",
    "node.js": "nodejs", "nodejs": "node.js",
    "c sharp": "c#", "c#": "c sharp",
    "ms office": "microsoft office",
    "microsoft office suite": "microsoft office",
}

def normalize_skill(s: str) -> str:
    return re.sub(r"[^a-z0-9+# ]", "", s.strip().lower())

def skills_match(job_skill: str, cand_skill: str) -> bool:
    nj, nc = normalize_skill(job_skill), normalize_skill(cand_skill)
    if nj == nc:
        return True
    syn = SKILL_SYNONYME.get(nj)
    if syn and normalize_skill(syn) == nc:
        return True
    return False

def score_kernkompetenzen(must_haves, k_skills):
    if not must_haves:
        return 15, []
    matches = [m for m in must_haves if any(skills_match(m, ks) for ks in k_skills)]
    score = int(round(len(matches) / len(must_haves) * 30))
    return score, matches

def score_berufserfahrung(k_erf, job_erf):
    job_erf = job_erf or 0
    basis = job_erf if job_erf > 0 else 3
    j = k_erf or 0
    if j >= basis + 2:
        return 25
    elif j >= basis:
        return 22
    elif j >= basis * 0.6:
        return 15
    elif j >= basis * 0.3:
        return 10
    return 5

def score_bildung(k_abschluss):
    a = (k_abschluss or "").strip().lower()
    if any(x in a for x in ("master", "m.sc", "diplom", "phd")):
        return 15
    if any(x in a for x in ("bachelor", "b.sc", "b.a", "b.tech")):
        return 12
    if a and a != "nan":
        return 8
    return 4

def score_sprache(k_de, k_en, job_de, job_en):
    return 0  # Phase 4.6 Fix: Default 0 statt 5 (Design-Entscheidung, 15.09.2026)

def score_standort(k_loc, job_loc):
    return 0  # Phase 4.6 Fix: Default 0 statt 5 (Design-Entscheidung, 15.09.2026)

def score_soft_skills(job_soft, k_soft):
    job_list = [s.strip() for s in (job_soft or "").split(",") if s.strip()]
    if not job_list:
        return 0  # Phase 4.6 Fix: Default 0 statt 7 (Design-Entscheidung, 15.09.2026)
    k_list = [s.strip() for s in (k_soft or "").split(",") if s.strip()]
    hits = sum(1 for js in job_list if any(skills_match(js, ks) for ks in k_list))
    return int(round(hits / len(job_list) * 10))

def score_branche(branche, cv_text):
    return 0  # Phase 4.6 Fix: Default 0 statt 6 (Design-Entscheidung, 15.09.2026)

def berechne_match_score(kandidat, job):
    """N1 (P4-Vorprüfung): DIESE Funktion bleibt bestehen – sie ist die 4.
    Score-Kopie im Projekt. Produkt: webui/logic.py:439, Archiv: app.py:656.
    Nicht durch einen Import ersetzbar, weil die Benchmark-Felder Dataset-Felder
    sind (skills_required, degree_names, responsibilities …), keine DB-Felder (N3).

    DRIFT-HINWEIS: Die Eigenkopie teilt die Kategorie-Maxima mit dem Produkt,
    historisch aber NICHT die Gewichte (harte Baseline 30/25/15/10/10/10/0).
    Seit N2 (Phase-E Runde 3) speist sie dieselben Live-Gewichte wie das Produkt
    (webui/logic.get_current_weights()); die Produktfunktion ruft
    get_current_weights() intern ebenfalls auf. Verbleibender Drift: die
    Roh-Score-Routinen hier sind gekürzte Fassungen (z. B. ohne den +3-Bonus
    für Teamführung/Mentoring aus webui/logic.py:237-239).
    """
    must_haves = [s.strip() for s in job.get("skills_required", "").split(",") if s.strip()]
    k_skills = [s.strip() for s in kandidat.get("skills", "").strip("[]").split(",") if s.strip()]

    kern, matches = score_kernkompetenzen(must_haves, k_skills)

    erf_text = job.get("experience_requirement", "")
    erf_jahre = 0
    m = re.search(r"(\d+)\s*(?:to|bis|-)\s*(\d+)\s*year", erf_text, re.I)
    if m:
        erf_jahre = (int(m.group(1)) + int(m.group(2))) / 2
    else:
        m2 = re.search(r"(\d+)\s*year", erf_text, re.I)
        if m2:
            erf_jahre = int(m2.group(1))
    erfahrung = score_berufserfahrung(erf_jahre, erf_jahre)

    bildung = score_bildung(kandidat.get("degree_names", ""))
    standort = score_standort(None, None)
    soft = score_soft_skills(job.get("responsibilities", ""), kandidat.get("skills", ""))
    sprache = score_sprache(None, None, None, None)
    branche = score_branche(None, "")

    roh = {"kern": kern, "erfahrung": erfahrung, "bildung": bildung,
           "standort": standort, "branche": branche, "soft": soft, "sprache": sprache}
    skaliert = {key: (val / KATEGORIE_MAX[key]) * GEWICHTE[key] for key, val in roh.items()}
    total = min(int(round(sum(skaliert.values()))), 100)
    return total, roh


# ── 4. Alle Scores berechnen ──────────────────────────────────────
print("\n[3] Berechne Scores …\n")
all_results = []
for i, row in enumerate(all_rows):
    p = parse_prompt(row["row"]["prompt"])
    llm = row["row"]["label"]

    skills_raw = p.get("skills", "")
    skills_list = re.findall(r"'([^']+)'", skills_raw)

    kandidat = {
        "hard_skills": ", ".join(skills_list),
        "degree_names": p.get("degree_names", "").strip("[]"),
    }
    job = {
        "hard_skills": p.get("skills_required", ""),
        "experience_requirement": p.get("experience_requirement", ""),
        "responsibilities": p.get("responsibilities", ""),
        "skills": p.get("skills_required", ""),
    }

    our_score, detail = berechne_match_score(kandidat, job)
    all_results.append({
        "idx": i, "job": p.get("job_position_name", "?"),
        "llm": llm, "ours": our_score, "detail": detail,
    })

print(f"    → {len(all_results)} Paare ausgewertet.")
if len(all_results) < 2:
    sys.exit(f"[FEHLER] Nur {len(all_results)} Paare – Statistik nicht berechenbar.")

# ── 5. Beispiel-Anzeige (10 zufällige) ────────────────────────────
random.seed(42)
example_indices = random.sample(range(len(all_results)), min(10, len(all_results)))
example_results = [all_results[i] for i in sorted(example_indices)]

print("\n[4] 10 Beispiel-Paare:\n")
print(f"  {'#':>3s} | {'Job':35s} | {'LLM':>4s} | {'Uns':>4s} | {'Diff':>5s}")
print(f"  {'-'*3}-+-{'-'*35}-+-{'-'*4}-+-{'-'*4}-+-{'-'*5}")
for r in example_results:
    print(f"  {r['idx']+1:3d} | {r['job'][:35]:35s} | {r['llm']:4d} | {r['ours']:4d} | {r['ours']-r['llm']:+5d}")

# ── 6. Gesamtstatistik ────────────────────────────────────────────
llm_all = [r["llm"] for r in all_results]
our_all = [r["ours"] for r in all_results]
diffs_all = [r["ours"] - r["llm"] for r in all_results]

mean_llm = statistics.mean(llm_all)
mean_ours = statistics.mean(our_all)
mean_diff = statistics.mean(diffs_all)
std_llm = statistics.stdev(llm_all)
std_ours = statistics.stdev(our_all)
median_llm = statistics.median(llm_all)
median_ours = statistics.median(our_all)

n = len(llm_all)
correlation = pearson(llm_all, our_all)

# MAE
mae = statistics.mean(abs(d) for d in diffs_all)

print(f"\n{'='*72}")
print("ERGEBNISSE (gesamter Test-Datensatz)")
print(f"{'='*72}\n")

print(f"| Metrik                      | Dataset (LLM) | Unser System | Differenz  |")
print(f"|-----------------------------|---------------|--------------|------------|")
print(f"| N (Test-Paare)              | {n:>13d} | {n:>12d} |            |")
print(f"| Durchschnittlicher Score    | {mean_llm:>13.1f} | {mean_ours:>12.1f} | {mean_diff:+10.1f} |")
print(f"| Median                      | {median_llm:>13.1f} | {median_ours:>12.1f} |            |")
print(f"| Standardabweichung          | {std_llm:>13.1f} | {std_ours:>12.1f} |            |")
print(f"| Min                         | {min(llm_all):>13d} | {min(our_all):>12d} |            |")
print(f"| Max                         | {max(llm_all):>13d} | {max(our_all):>12d} |            |")
print(f"| MAE (Mean Absolute Error)   |               |              | {mae:>10.1f} |")
print(f"| Pearson-Korrelation (r)     |               |              | {correlation:>+10.3f} |")

print(f"\nScore-Verteilung (Buckets):")
for bucket_start in range(0, 100, 20):
    bucket_end = bucket_start + 20
    llm_count = sum(1 for s in llm_all if bucket_start <= s < bucket_end)
    our_count = sum(1 for s in our_all if bucket_start <= s < bucket_end)
    llm_pct = llm_count / n * 100
    our_pct = our_count / n * 100
    print(f"  {bucket_start:3d}–{bucket_end:3d}: LLM {llm_count:4d} ({llm_pct:4.1f}%) | Uns {our_count:4d} ({our_pct:4.1f}%)")

# ── 7. Kategorie-Analyse ──────────────────────────────────────────
print(f"\n{'='*72}")
print("KATEGORIE-ANALYSE (Mittelwerte der Roh-Scores)")
print(f"{'='*72}\n")

kateg_keys = ["kern", "erfahrung", "bildung", "standort", "branche", "soft", "sprache"]
print(f"| Kategorie       | Roh-Score (0–Max) | Gewicht (live) | Gew.-Anteil |")
print(f"|-----------------|-------------------|----------------|-------------|")
for k in kateg_keys:
    vals = [r["detail"][k] for r in all_results]
    avg = statistics.mean(vals)
    maxv = KATEGORIE_MAX[k]
    g = GEWICHTE[k]
    print(f"| {k:15s} | {avg:8.1f} / {maxv:5d}      | {g:13.1f}    | {g:10.1f}% |")

# ── 8. Benchmark-Adapter auf die 4 Dataset-Kriterien (P4/y) ───────
# Mapping-Tabelle (identisch mit dem Report-Print unten):
#
#   | Dataset-Kriterium | Unsere Kategorie(n) | Heuristik                              |
#   |-------------------|---------------------|----------------------------------------|
#   | Skills match      | kern + soft         | Must-Have-Skill-Overlap (kern) +       |
#   |                   |                     | responsibilities vs. Skills (soft)     |
#   | Education match   | bildung             | Abschluss-Score aus degree_names       |
#   | Experience match  | erfahrung           | Erfahrungs-Score aus                   |
#   |                   |                     | experience_requirement                 |
#   | Career alignment  | — (keine Zuordnung) | career_objective /                     |
#   |                   |                     | professional_company_names fließen     |
#   |                   |                     | nicht ein (N3) → nicht messbar         |
#
# JEDE Zuordnung in dieser Tabelle = Design-Entscheidung (25.09.2026), keine
# externe Quelle; Beleg der 4 Dataset-Kriterien: benchmark-huggingface-dataset.md:18,
# Empfehlung (separate Benchmark-Funktion): benchmark-huggingface-dataset.md:83.
ADAPTER_MAPPING = [
    ("Skills match", ["kern", "soft"],
     "kern = Must-Have-Overlap, soft = responsibilities vs. Skills"),
    ("Education match", ["bildung"],
     "Abschluss-Score aus degree_names"),
    ("Experience match", ["erfahrung"],
     "Erfahrungs-Score aus experience_requirement"),
    ("Career alignment", [],
     "keine Kategorie zugeordnet (Felder fehlen im Produkt-Score, N3)"),
]
# Design-Entscheidung: Kriterien gleichgewichtet, weil das Dataset keine
# Kriterien-Gewichte publiziert (benchmark-huggingface-dataset.md:18 nennt nur die
# 4 Kriterien). Renormalisierung nach unseren Live-Gewichten wäre mathematisch
# identisch mit dem Gesamt-Score: die ausgeschlossenen Kategorien (standort,
# branche, sprache) liegen konstant bei 0, und eine additive Konstante ändert
# die Pearson-Korrelation nicht.
ADAPTER_PARTIELL = ["kern", "erfahrung", "bildung"]  # Empfehlung 1, :80


def adapter_teilscore(detail: dict, kategorien: list) -> float:
    """0–100-Teilscore über eine Kategorie-Teilmenge (arithm. Mittel der
    normierten Roh-Scores)."""
    if not kategorien:
        return 0.0
    return statistics.mean(detail[k] / KATEGORIE_MAX[k] * 100 for k in kategorien)


def partiel_score(detail: dict, kategorien: list) -> float:
    """Renormiert nach den Live-Gewichten der Teilmenge auf 0–100."""
    nenner = sum(GEWICHTE[k] for k in kategorien)
    if nenner <= 0:
        return 0.0
    return sum((detail[k] / KATEGORIE_MAX[k]) * GEWICHTE[k] for k in kategorien) / nenner * 100


messbare_kriterien = [kg for _, kg, _ in ADAPTER_MAPPING if kg]
adapter_all = [
    statistics.mean(adapter_teilscore(r["detail"], kg) for kg in messbare_kriterien)
    for r in all_results
]
partial_all = [partiel_score(r["detail"], ADAPTER_PARTIELL) for r in all_results]
r_adapter = pearson(llm_all, adapter_all)
r_partial = pearson(llm_all, partial_all)

print(f"\n{'='*72}")
print("BENCHMARK-ADAPTER (P4/y) – Abbildung auf die 4 Dataset-Kriterien")
print(f"{'='*72}\n")
print("| Dataset-Kriterium | Unsere Kategorie(n)   | Heuristik (Design-Entscheidung)              |")
print("|-------------------|-----------------------|----------------------------------------------|")
for krit, kats, heur in ADAPTER_MAPPING:
    kat_txt = ", ".join(kats) if kats else "— (nicht messbar)"
    print(f"| {krit:17s} | {kat_txt:21s} | {heur:44s} |")
print(f"\n  Messbare Kriterien: {len(messbare_kriterien)} von {len(ADAPTER_MAPPING)}"
      " (Career alignment ohne Entsprechung → nicht messbar, Design-Entscheidung).")
print(f"  Teilscores je Kriterium = 0–100; Adapter = gleicher Mittelwert der messbaren"
      f" Kriterien (Design-Entscheidung, s. Code-Kommentar).")
print(f"  Partielle Korrelation (Empfehlung 1): nur {', '.join(ADAPTER_PARTIELL)}"
      ", renormalisiert nach den Live-Gewichten.")

print(f"\n| Auswertung                                     |   N |   Ø |    σ |        r |")
print(f"|------------------------------------------------|-----|-----|------|----------|")
for label, vals, rr in (
    ("Gesamt (7 Kategorien, Produktformel)", our_all, correlation),
    ("Adapter (4 Dataset-Kriterien, gleichgew.)", adapter_all, r_adapter),
    ("Partiell (Kern+Erfahrung+Bildung, Empf. 1)", partial_all, r_partial),
):
    print(f"| {label:45s} | {n:3d} | {statistics.mean(vals):4.1f} | {statistics.stdev(vals):4.1f} | {rr:>+8.3f} |")

# ── 9. Fazit ──────────────────────────────────────────────────────
print(f"\n{'='*72}")
print("FAZIT")
print(f"{'='*72}\n")
print(f"Dataset:  {CFG['dataset']} (HuggingFace)")
print(f"          9,544 Einträge (7,640 Train / 1,910 Test)")
print(f"          Job-Kategorien: IT, Engineering, HR, Business, Data Science, u.a.")
print(f"          Candidate-Features: skills, degree_names, major_field_of_studies,")
print(f"                              career_objective, professional_company_names")
print(f"          LLM-Referenzscore (GPT-4 o.ä.) auf 4 Kriterien:")
print(f"          Skills match, Education match, Experience match, Career alignment")
print()
print(f"Unser System: Regeln (webui/logic.py) mit 7 Kategorien.")
print(f"          Gewichte live (N2): "
      + ", ".join(f"{k} {GEWICHTE[k]:.1f}%" for k in kateg_keys))
print(f"          r Gesamt (7 Kategorien):          {correlation:+.3f}")
print(f"          r Adapter (4 Dataset-Kriterien):  {r_adapter:+.3f}")
print(f"          r Partiell (Kern+Erf+Bildung):    {r_partial:+.3f}")
print()
print(f"Schwelle r ≥ 0.5 = Design-Entscheidung (kein externer Bebelleg, Auftrag P4).")
print(f"Rest-Ursachen (belegt: benchmark-huggingface-dataset.md):")
print(f"  :67 Semantik vs. Syntax – LLM versteht 'Teamführung' als Leadership-Skill,")
print(f"      wir prüfen exakte String-Matches (Fuzzy-Matching fehlt)")
print(f"  :68 Fehlende Kategorien – Standort/Branche/Soft Skills fließen ins LLM ein,")
print(f"      liegen bei uns aber (überwiegend) bei 0")
print(f"  :66 Feature-Mismatch – career_objective, professional_company_names")
print(f"      fließen ins LLM ein, bei uns nicht (Adapter bildet sie deshalb als")
print(f"      'nicht messbar' ab – N3)")
if correlation >= 0.7:
    print(f"\nKORRELATION: r={correlation:+.3f} → Starke Übereinstimmung.")
    print(f"  Unser Regelwerk bildet die LLM-Bewertung gut ab.")
elif correlation >= 0.5:
    print(f"\nKORRELATION: r={correlation:+.3f} → Moderate Übereinstimmung.")
    print(f"  Unser System korreliert akzeptabel mit dem LLM-Referenzscore.")
elif correlation >= 0.3:
    print(f"\nKORRELATION: r={correlation:+.3f} → Schwache Übereinstimmung.")
    print(f"  Hauptursachen:")
    print(f"  1. Feature-Mismatch: Dataset hat career_objective, professional_company_names")
    print(f"     → diese fließen in LLM-Bewertung ein, bei uns nicht")
    print(f"  2. Fehlende Kategorien: Standort/Sprache/Branche liegen im Dataset nicht vor")
else:
    print(f"\nKORRELATION: r={correlation:+.3f} → Keine Korrelation.")

print(f"\nEmpfehlung: Für eine valide Benchmark-basierte Validierung müsste")
print(f"  unser System mit denselben Inputs (Skills, Abschluss, Erfahrung)")
print(f"  getestet werden – ohne die Kategorien, die im Dataset fehlen.")
print(f"  => Partielle Korrelation nur auf Kern+Erfahrung+Bildung geprüft (oben).")
