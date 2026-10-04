# Referenz: SphinxATS Paper (ICSSAS 2026)

> **Stand:** 16.09.2026 · **Zweck:** Externe Validierung unseres Matching-Ansatzes
> **Quelle:** CrossRef API + Semantic Scholar (verifiziert 16.09.2026)

---

## Paper-Details

| Feld | Wert |
|---|---|
| **Titel** | SphinxATS: A Multi-Attribute AI-based Decision Support System for Automated Resume Screening and Candidate Ranking |
| **Autoren** | Kandrakota, Kumar, Vidmahi, Mesa (Sreenidhi Institute of Science and Technology, Hyderabad, India) |
| **Konferenz** | 2026 4th International Conference on Self Sustainable Artificial Intelligence Systems (ICSSAS), Erode, India |
| **Datum** | 28.–30. Mai 2026 |
| **Seiten** | 135–143 |
| **DOI** | `10.1109/ICSSAS68835.2026.11559449` |
| **Zitationen** | 0 (Stand 16.09.2026) |
| **Open Access** | ❌ Nicht verfügbar (IEEE-Paywall) |
| **GitHub** | `github.com/MANISH-K-07/SphinxATS` (Flask + NLP Implementation) |
| **LinkedIn** | `linkedin.com/posts/manish-k-kandrakota` (Autor-Post, Juli 2026) |

---

## Zusammenfassung (aus Abstract, Semantic Scholar)

Das Paper führt **SphinxATS** ein – ein KI-gesteuertes Framework für automatisiertes Resume-Screening und Entscheidungsunterstützung. Candidate Shortlisting wird als **strukturiertes Multi-Attribute-Optimierungsproblem** modelliert.

**Kernkomponenten:**
- Natural Language Processing (NLP)
- Semantische Ähnlichkeitsmodellierung
- Anpassbare gewichtete Scoring-Mechanismen
- Erklärbares Ranking-Modul

**Bewertungskriterien (Multi-Criteria Decision-Making):**
- Skills Alignment (Kernkompetenzen)
- Professional Experience Relevance (Berufserfahrung)
- Educational Background (Bildung)
- Contextual Semantic Fit (Kontextueller semantischer Fit)

**Ergebnis:** Improved matching consistency, ranking stability, semantic alignment vs. keyword-based baselines.

**Kern-Zitat (Autor, LinkedIn):**
> *"The core value lies in its dedicated explainability layer, which replaces vague rankings with fully transparent, attribute-level justifications for hiring teams."*

---

## Übertragung auf unser Projekt

| Paper-Komponente | Unser Pendant | Datei |
|---|---|---|
| Multi-Attribute Optimization | `berechne_match_score()` | `app.py` |
| NLP + Semantic Similarity | `extract_profile` + `match_candidate` | `agent-runner.py` |
| Adjustable Weighted Scoring | Feedback-Loop (Phase 4) | `adjust_weights_from_feedback()` |
| Explainable Ranking | `explain_match` (Skill 9) | `skills/explain-match/SKILL.md` |
| Skills Alignment | Kernkompetenzen (30%) | `knowledge/lifecycle/matching-criteria.md` |
| Experience Relevance | Berufserfahrung (25%) | `knowledge/lifecycle/matching-criteria.md` |
| Educational Background | Bildung (15%) | `knowledge/lifecycle/matching-criteria.md` |
| Contextual Semantic Fit | `assess_culture_fit` | `skills/assess-culture-fit/SKILL.md` |

---

## GitHub-Implementierung (verifiziert 17.09.2026)

**Quelle:** `github.com/MANISH-K-07/SphinxATS` → lokale Referenz: `docs/sphinxats-github-app.py`

### Gewichte im Code (app.py, Zeile ~170)

```python
final_score = (
    (0.6 * similarity_scores[i]) +   # TF-IDF Similarity
    (0.3 * skill_score) +             # Skill Matching
    (0.1 * exp_score)                 # Experience
)
```

| Kategorie | SphinxATS-Gewicht | Unser Gewicht | Differenz |
|---|---|---|---|
| Similarity/TF-IDF | **60%** | — (kein Äquivalent) | SphinxATS hat kein Separat-Skill-Scoring |
| Skills (Kern) | **30%** | 30% (Kern) | ✅ Identisch |
| Experience | **10%** | 25% (Erfahrung) | ⚠️ SphinxATS 2.5× niedriger |
| Bildung | — (fehlt) | 15% | Nur im Paper (nicht im Code) |
| Standort | — (fehlt) | 10% | Nur in unserem System |
| Branche | — (fehlt) | 10% | Nur in unserem System |
| Soft Skills | — (fehlt) | 10% | Nur in unserem System |
| Sprache | — (fehlt) | 0% | Nur in unserem System |

### Methodik (aus Code)

1. **TF-IDF + Cosine Similarity** für Candidate-JD-Ähnlichkeit
2. **Keyword-Matching** für Skills (vordefinierte Liste: 38 Skills)
3. **Regex-Extraktion** für Erfahrung ("2 years experience")
4. **KMeans-Clustering** für Kandidaten-Gruppierung (High/Moderate/Low)
5. **Specialization Detection** (Data Science, Backend, Frontend, Cloud/DevOps)

### Einschränkungen des GitHub-Code

- Kein Education-Score (nur im Paper erwähnt, nicht im Code)
- Kein Semantic Fit / Culture-Fit
- Skill-Liste hardcoded (38 Skills, nicht erweiterbar)
- Keine Explainability (nur Score, keine Begründung)
- Kein Feedback-Loop

## Validierung

| Aspekt | Paper-Aussage | GitHub-Code | Unser Status | Bewertung |
|---|---|---|---|---|
| Multi-Attribute als Optimierung | ✅ Bestätigt | ✅ 3 Kategorien | ✅ 7 Kategorien | Unser Ansatz ist erweitert |
| NLP für Resume-Screening | ✅ Bestätigt | ✅ TF-IDF | ✅ NVIDIA NIM + LLM | Unsere Methode ist fortschrittlicher |
| Gewichtete Scores | ✅ Bestätigt | ✅ 0.6/0.3/0.1 | ✅ 30/25/15/10/10/10/0 + Feedback | Unsere Gewichte differenzierter |
| Erklärbares Ranking | ✅ Empfohlen | ❌ Nicht im Code | ⚠️ Teilweise (explain_match) | Ausbaufähig |
| Semantic Fit für Culture-Fit | ✅ Bestätigt | ❌ Nicht im Code | ❌ Korrelation r=-0.06 | Hauptproblem |
| KMeans-Clustering | ✅ Im Code | ✅ Implementiert | ❌ Nicht implementiert | Könnte nützlich sein |

---

## Einschränkungen

- **0 Zitationen** → Early-Stage-Paper, nicht als Autorität zitieren
- **IEEE-Paywall** → Kein vollständiger Zugang zur Methodik
- **Konferenz-Panel** → Kein Top-Tier-Venue (ICSSAS ist regional)
- **Kein Vergleich mit Production-Systemen** → Nur akademischer Benchmark

**Nutzung:** Als Design-Validierung, nicht als Implementierungsanleitung.
