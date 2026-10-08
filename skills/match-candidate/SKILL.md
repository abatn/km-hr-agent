---
description: Vergleicht Kandidatenprofil mit Stellenprofil und erstellt Match-Score mit Begründung
tools:
  - pdf-reader (MCP)
  - filesystem (MCP)
---

## Regime: LLM-Lauf über NVIDIA-API (seit 13.09.2026), kein Such-Index

## Verfügbare Tools (Ist ⓘ08.10.2026)

| Tool | Typ | Zweck | Status |
|---|---|---|---|
| `pdf-reader` | MCP (local) | Lebenslauf-Text extrahieren | ✅ aktiv |
| `filesystem` | MCP (local) | Profile und Stellen lesen/schreiben | ✅ aktiv |
| LLM (Agent) | Inferenz (direkte NVIDIA-API) | Semantisches Matching + Score-Berechnung | ✅ aktiv |
| ~~`resume-parser-ats`~~ | CLI (npm) | Profil parsen | ❌ **nicht installiert / nicht konfiguriert** (0 Treffer in `opencode.json`) |
| ~~`semantic-search-mcp`~~ | MCP | Semantische Suche (FAISS) | ❌ **nicht installiert** (0 Treffer) → „Methode B" unten **nicht umgesetzt** |

## Schritte

### Voraussetzung: Profil-Check

**Regel:** Matching nur wenn Kandidat `lebenslauf_hochgeladen` oder besser hat.

```sql
SELECT status FROM candidates WHERE id = ?;
-- Erlaubt: lebenslauf_hochgeladen, profil_geprueft, match_berechnet, eingeladen
-- Verboten: registriert, profil_vollstaendig
```

**Fehlermeldung wenn nicht erfüllt:**
"❌ Kandidat muss Lebenslauf hochladen bevor Matching möglich ist. Aktueller Status: [status]"

---

### Methode A: LLM-basiertes Matching (einfach, empfohlen)

#### 1. Profile einlesen
- **Connector:** `filesystem`
- **Tool:** `read_text_file`
- **Parameter:** `path` für Kandidatenprofil
- **Parameter:** `path` für Stellenprofil

#### Beispiel-Anfragen
```json
[
  {
    "name": "read_text_file",
    "arguments": {
      "path": "~/mimo-agents/km-hr-agent/testdaten/profil-anna-schuster.md"
    }
  },
  {
    "name": "read_text_file",
    "arguments": {
      "path": "~/mimo-agents/km-hr-agent/testdaten/stellenprofil-cloud-devops-engineer.txt"
    }
  }
]
```

#### 2. LLM Matching durchführen
- **Prompt:** "Vergleiche das Kandidatenprofil mit der Stellenanforderung. Berechne einen Match-Score (0–100) mit detaillierter Begründung. Identifiziere:
  - Übereinstimmungen (Common Keywords)
  - Fehlende Skills (Gaps)
  - Stärken/Schwächen"

#### 3. Score berechnen (LLM erledigt dies)
- LLM analysiert beide Profile
- Extrahiert gemeinsame und fehlende Skills
- Berechnet Score basierend auf 7 Kategorien (Quelle: knowledge/lifecycle/matching-criteria.md):
  - Kernkompetenzen (30%)
  - Berufserfahrung (25%)
  - Bildung (15%)
  - Standort (10%)
  - Branchenkenntnis (10%)
  - Soft-Skills (10%)
  - Sprache (0% – aktiviert sich via Feedback-Loop)

#### 4. Score interpretieren
- **90–100**: Hervorragend → Sofort einladen
- **75–89**: Gut → Einladen
- **60–74**: Bedingt → Prüfung empfohlen
- **40–59**: Schwach → Bedenken
- **0–39**: Nicht passend → Ablehnen

> ⚠️ **Design-Entscheidung (15.09.2026):** Die Score-Bands 90/75/60/40 haben **keine externe Quelle**. **Alternative:** 85/70/55/40 oder 80/65/50/35. **Validierung:** Korrelation zwischen Score und Einstellungsentscheidung prüfen.

> ⚠️ **Design-Entscheidung (15.09.2026):** Pförtner-Schwelle ≥60 (JA/NEIN-Regel im Runner) hat **keine externe Quelle**. **Alternative:** Schwelle aus eigener Datenanalyse ableiten. **Validierung:** Nach 20+ Einstellungen prüfen ob 60 sinnvoll trennt.

> ⚠️ **Design-Entscheidung (15.09.2026):** Fallback-Score 70 bei fehlendem Extract hat **keine externe Quelle**. **Alternative:** 0 (transparenter, kein Schein-Score). **Validierung:** Prüfen ob Fallback-Scores den Feedback-Loop verfälschen.

#### 5. Ergebnis speichern
- **Connector:** `filesystem`
- **Tool:** `write_file`
- **Parameter:** `path` = `~/mimo-agents/km-hr-agent/ergebnisse/match-[kandidat]-[stelle]-[datum].md`
- **Parameter:** `content` = Match-Bericht als Markdown

#### Beispiel-Output
```markdown
# Match-Bericht: Anna Schuster vs. Cloud DevOps Engineer

## Match-Score: 82/100 (Gut)

### Übereinstimmungen (Common Keywords)
- Kubernetes ✅
- AWS ✅
- Python ✅
- DevOps ✅
- Docker ✅

### Fehlende Skills (Gaps)
- Terraform ❌ (im JD vorhanden, im Profil nicht)
- CI/CD Pipeline (nur grundlegend im Profil)

### Stärken
- 3+ Jahre Kubernetes-Erfahrung
- AWS Certified Solutions Architect
- Scrum Master Zertifikat

### Schwächen
- Keine Terraform-Erfahrung
- Kein Cloud Migration Projekt erwähnt

### Empfehlung
Einladung mit Hinweis auf Terraform-Lücke – Kandidatin zeigt Lernbereitschaft
```

---

### Methode B: Mit semantic-search-mcp — ❌ NICHT umgesetzt (Zukunftsoption)

> **Status 08.10.2026:** `semantic-search-mcp` ist **nicht installiert** (0 Treffer in `opencode.json`). Dieser Abschnitt ist ein Entwurf, kein Ausführungsweg. Tatsächlich liefert die Kandidatenliste `_page_kandidaten`/`_page_match` (`webui/pages/employer.py`), das Matching rechnet `berechne_match_score()` (`webui/logic.py`) über die DB — kein Index, kein CLI-Aufruf.

#### Voraussetzung (nicht erfüllt)
- semantic-search-mcp installiert
- Profile als Markdown im knowledge/profiles/ Verzeichnis

#### 1. Index erstellen
```bash
CONTENT_PATH=/home/batnini/mimo-agents/km-hr-agent/knowledge semantic-search index
```

#### 2. Semantische Suche
```bash
semantic-search search "Kubernetes DevOps AWS Python Terraform" --top-k 5
```

#### 3. Ergebnisse interpretieren
- semantic-search gibt Ähnlichkeits-Scores (0–1) zurück
- Skalieren auf 0–100
- Top-K Ergebnisse als Kandidaten ranken

---

## Beispiel-Aufrufe

### LLM Matching (einfach)
```json
{
  "prompt": "Vergleiche folgendes Kandidatenprofil mit der Stellenanforderung und berechne einen Match-Score (0–100) mit Begründung:\n\nKANDIDATEN-PROFIL:\n{{profil-text}}\n\nSTELLENANFORDERUNG:\n{{jd-text}}"
}
```

### Semantische Suche (optional)
```bash
semantic-search search "Kubernetes DevOps AWS" --top-k 3
```

### Ergebnis speichern
```json
{
  "name": "write_file",
  "arguments": {
    "path": "/home/batnini/mimo-agents/km-hr-agent/ergebnisse/match-anna-schuster-devops-2026-09-10.md",
    "content": "# Match-Bericht\n\n## Score: 82/100\n\n..."
  }
}
```

## Gewichtsquelle (Phase-E Runde 2, Stand 24.09.2026)

Die Matching-Gewichte kommen **live aus der Datenbank**, nicht aus einer
Festwert-Liste im Prompt:

| Aspekt | Wert | Quelle |
|---|---|---|
| Quelle der Wahrheit | `gewichtung_historie` (normalisiert auf Summe 100) | `webui/logic.py:338` `get_current_weights()` |
| Verbrauch im Prompt | `scripts/agent-runner.py:754` `_gewichts_prompt_zeile()`, eingebaut `:851` | Codeweis `grep -n "_gewichts_prompt_zeile" scripts/agent-runner.py` |
| Live-Stand 24.09.2026 | kern 25.0 / erfahrung 29.2 / bildung 12.5 / standort 8.3 / branche 8.3 / soft 8.3 / sprache 8.3 | Beweis-Snippet in `ergebnisse/entscheidungen.md` (Phase-E Runde 2) |
| Baseline (Startwert) | 30/25/15/10/10/10/0 | `knowledge/lifecycle/matching-criteria.md:23` |

**Design-Entscheidungen:** Rundung auf **1 Nachkommastelle**; **Fallback = Baseline**,
wenn die Historie leer ist oder die DB nicht erreichbar (robust, kein Task-Abbruch).

**Konsistenz:** Prompt-Werte und Portal-Score sind damit identisch (gleiche Funktion).
Die Differenz-Warning des archivierten `app.py:1927` ist dadurch gegenstandslos —
NiceGUI `webui/` hat bewusst keine (Nutzerentscheidung 24.09.2026, siehe
`ergebnisse/entscheidungen.md`, Phase-E Runde 2).
