---
description: Exportiert Match-Ergebnisse als MD-Datei
---

## Trigger
- **Automatisch:** Nach `store_feedback` (app.py, wenn Feedback gespeichert wird)
- **Manuell:** Über Agent-Task `export_report` in der Queue

## Input
- Match-Ergebnis (Score, Begründung, Kultur-Fit, Compliance)
- Export-Format (PDF, Excel, oder beide)
- Empfänger (optional: für Direkt-Export)

## Schritte

### 1. Export-Format wählen

| Format | Use Case | Connector | Status ⓘ08.10.2026 |
|---|---|---|---|
| **Markdown** (Ist-Implementierung) | Bericht in `ergebnisse/` | keiner nötig (Runner schreibt MD) | ✅ aktiv (`export_report` in `scripts/agent-runner.py`) |
| **PDF** (HR-Liste) | Ausdruck, Archiv, E-Mail-Anhang | **reportlab** (kein MCP) | ✅ aktiv (`export_candidates_pdf` in `webui/components.py`) |
| ~~PDF via MCP~~ | – | ~~aspose-pdf-foss-mcp~~ | ❌ **nicht installiert** (`opencode.json` ohne Eintrag, 0 Treffer) |
| ~~Excel~~ | – | ~~excel-mcp~~ | ❌ **nicht installiert** — wird auch nicht benötigt (`instructions.md` Status „Nicht installiert / Nicht benötigt") |

> **Nur Markdown/PDF verwenden.** Die beiden MCP-Connector in der Tabelle sind **Phantom-Werkzeuge** (Tool-Namen-Pflicht: nur Server aus `opencode.json`, Spec `knowledge/system/mcp-connector-config.md`). Die folgenden Abschnitte 2+3 sind **Zukunftsoption / nicht umgesetzt** (Design-Entscheidung, Stand 08.10.2026).

### 2. PDF-Export (Zukunftsoption, NICHT umgesetzt)

#### Via aspose-pdf-foss-mcp (❌ nicht installiert):
1. Lese Template-Platzhalter aus `knowledge/export-templates/README.md`
2. Ersetze Platzhalter mit Match-Daten:
   - `{{KANDIDAT_NAME}}`, `{{STELLE}}`, `{{SCORE}}
   - `{{BEGRUENDUNG}}`, `{{STAERKEN}}`, `{{LUECKEN}}
   - `{{COMPLIANCE_STATUS}}`, `{{KULTUR_FIT}}
3. Generiere PDF via `aspose-pdf-foss-mcp`
4. Speichere unter: `~/mimo-agents/km-hr-agent/ergebnisse/export-[name]-[datum].pdf`

#### PDF-Inhalt:
```
┌─────────────────────────────────────────────┐
│         MATCH-BERICHT – KM-HR-Agent        │
├─────────────────────────────────────────────┤
│ Kandidat: [Name]                            │
│ Stelle: [Position] bei [Unternehmen]        │
│ Datum: [Datum]                              │
│ Score: [X]/100 ([Kategorie])                │
├─────────────────────────────────────────────┤
│ COMPLIANCE                                  │
│ Status: [✅/⚠️/❌] [DE/FR/CH]              │
├────────────────────────────────-------------─┤
│ BEGRÜNDUNG                                  │
│ [Detaillierte Begründung pro Kriterium]     │
├─────────────────────────────────────────────┤
│ KULTUR-FIT                                  │
│ Score: [X]/100                              │
│ [Top-3 Stärken + Risiken]                   │
├─────────────────────────────────────────────┤
│ NÄCHSTE SCHRITTE                            │
│ [ ] Kandidat anrufen                        │
│ [ ] Gespräch planen                         │
│ [ ] Referenzen einholen                     │
└─────────────────────────────────────────────┘
```

### 3. Excel-Export (Zukunftsoption, NICHT umgesetzt)

#### Via excel-mcp (❌ nicht installiert):
1. Erstelle Arbeitsmappe mit 3 Blättern:
   - **Blatt 1: Match-Übersicht** (eine Zeile pro Match)
   - **Blatt 2: Detaillierte Bewertung** (alle Kategorien)
   - **Blatt 3: Compliance** (Prüfpunkte)
2. Formatierung:
   - Überschriften fett
   - Score farblich (grün/gelb/rot)
   - Spaltenbreite automatisch
3. Speichere unter: `~/mimo-agents/km-hr-agent/ergebnisse/export-[name]-[datum].xlsx`

#### Excel-Spalten (Blatt 1):
| Kandidat | Stelle | Score | Kategorie | Compliance | Kultur-Fit | Empfehlung |
|---|---|---|---|---|---|---|
| [Name] | [Position] | [X] | [Kategorie] | [Status] | [X]/100 | [Empfehlung] |

### 4. Batch-Export (mehrere Matches)

Bei >1 Match:
1. Erstelle Zusammenfassungs-PDF mit allen Matches
2. Erstelle Excel-Datei mit einer Zeile pro Match
3. Erstelle Chart (Visuals-MCP) als Bild-PNG

### 5. Speichern
- Speichere Export via **Filesystem-Connector** (`write_file`)
- Pfad: `~/mimo-agents/km-hr-agent/ergebnisse/export-[name]-[datum].[pdf|xlsx]`

### 6. Rückgabe
- Gib Dateipfad zurück
- Gib Dateigröße zurück
- Bei E-Mail: Gib Sendestatus zurück
