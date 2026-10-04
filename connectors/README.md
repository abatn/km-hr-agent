# MCP-Connector README

> **Stand:** 17.09.2026  
> **Zweck:** Übersicht der 3 HR-Connectoren + language-test MCP-Server mit Formeln und Tests

---

## Übersicht

| Connector | Datei | Formel | Quelle | Status |
|-----------|-------|--------|--------|--------|
| hr-benchmark | `hr-benchmark-server.py` | `(score/max) × weight` | ZYTHR | ✅ AKTIV (app.py: 4×) |
| salary-data | `salary-data-server.py` | `Min/Mid/Max = 25th/50th/75th` | BambooHR | ✅ AKTIV (app.py: 1×) |
| prescreen-config | `prescreen-config-server.py` | `15-30 Minuten` | CareerPlug | ✅ AKTIV (runner: 1×) |

---

## 1. HR-Benchmark-Connector

**Quelle:** [ZYTHR](https://zythr.com/resources/candidate-scoring-model-in-recruiting-what-it-is-and-how-to-build-one)

### Formel
```
Weighted contribution = (Candidate score / Max score) × Criterion weight
```

### Tools
| Tool | Input | Output |
|------|-------|--------|
| `calculate_weighted_score` | scores, weights, max_score | total_score, details |
| `get_score_category` | score | category (Strong/Consider/Weak) |
| `get_weight_ranges` | – | empfohlene Bereiche |

### Score-Schwellen (ZYTHR)
- 80-100 = "Strong"
- 60-79 = "Consider"
- <60 = "Weak"

---

## 2. Salary-Data-Connector

**Quelle:** [BambooHR](https://www.bamboohr.com/blog/salary-bands-explained)

### Formel
```
Min = 25th Percentile
Mid = 50th Percentile (Median)
Max = 75th Percentile
```

### Tools
| Tool | Input | Output |
|------|-------|--------|
| `calculate_salary_band` | market_data, role | band (min/mid/max) |
| `calculate_salary_position` | salary, band | position_percent, level |
| `calculate_salary_tolerance` | midpoint | tolerance_min/max |

---

## 3. Pre-Screen-Connector

**Quelle:** [CareerPlug](https://www.careerplug.com/how-to-conduct-phone-screen-interview/)

### Logik
```
"Keep the phone screen short – aim for 15 minutes and no more than 30."
```

### Tools
| Tool | Input | Output |
|------|-------|--------|
| `get_optimal_duration` | – | min/opt/max minutes |
| `get_screening_questions` | – | 10 Fragen |
| `get_screening_structure` | – | Struktur |

---

## Installierte Connectoren

```bash
# Connectoren testen
python3 connectors/hr-benchmark-server.py
python3 connectors/salary-data-server.py
python3 connectors/prescreen-config-server.py
python3 scripts/language-test-server.py  # MCP-Server für Sprachtests
```

## 4. Language-Test-Connector (NEU 16.09.2026)

**Quelle:** CEFR Grid (Council of Europe) + Cambridge English

### Tools
| Tool | Input | Output |
|------|-------|--------|
| `generate_test` | sprache, niv, anzahl | JSON mit Fragen |
| `score_answer` | frage_id, antwort | Punkte + Feedback |
| `get_cefr_level` | punkte, sprache | CEFR-Level (A1-C2) |
| `get_reference_links` | sprache, niv | URLs zu Tests |

### Status
- 732 Fragen (DE 120, EN 522, FR 90, offiziell) + LLM-generierte Zusatzfragen (hybrid)
- ID-Schema (einheitlich 20.09.2026): `DE-<Level>-NN` · `EN-<Level>-NNN` · `FR-<Level>-NN` (Seed, Quelle: `knowledge/language-tests.md`) · `LLM-<Sprache>-<Level>-NN` (Zusatzfragen, z.B. `LLM-DE-A1-01`)
- LLM-Bewertung via NVIDIA API
- Trigger: Manuell (kein automatischer Trigger in app.py)
- Regressionstest 20.09.2026: 522 EN-IDs (`cambridge-*` → `EN-*`) vereinheitlicht; Parser 15 Sektionen/732 Fragen, generate_test (6 Kombinationen), score_answer bestanden

---

## Quellen

| Quelle | URL | Verifiziert |
|--------|-----|-------------|
| ZYTHR | zythr.com/resources/candidate-scoring-model-in-recruiting | ✅ 15.09.2026 |
| BambooHR | bamboohr.com/blog/salary-bands-explained | ✅ 15.09.2026 |
| CareerPlug | careerplug.com/how-to-conduct-phone-screen-interview | ✅ 15.09.2026 |

---

*Erstellt am 15.09.2026 für den KM-HR-Agenten.*
