---
description: Länderspezifische Compliance-Prüfung für Kandidatenprofile (DE/FR/CH)
---

## Funktionierende MCP-Connector

| Connector | Land | Tool | Zweck | Auth |
|---|---|---|---|---|
| `filesystem` | – | `read_text_file` | Knowledge-Dateien + Profile lesen | Keine |
| `ansvar-german-law` | 🇩🇪 DE | `search`, `validate_citation`, `get_provision` | AGG, BDSG, MiLoG, EU AI Act (6.870 Gesetze) | ✅ OAuth-Token vorhanden |
| `ansvar-french-law` | 🇫🇷 FR | `search`, `validate_citation`, `get_provision` | Code du travail, Code pénal, RGPD (3.958 Gesetze) | ✅ OAuth-Token vorhanden |
| `ansvar-swiss-law` | 🇨🇭 CH | `search`, `validate_citation`, `get_provision` | OR, ArG, DSG, StGB (4.873 Gesetze) | ✅ OAuth-Token vorhanden |

**Gateway:** Alle 3 Ansvar-Connectors nutzen `https://gateway.ansvar.eu/mcp`
**Token:** `/home/batnini/.mcp-auth/mcp-remote-0.1.38/83c240cea87a307a99ab272acd787d05_tokens.json`
**32 Tools verfügbar** (Free-Tier)

---

## Schritte

### 1. Regelwerk einlesen
- **Connector:** `filesystem`
- **Tool:** `read_text_file`
- **Pfad:** `~/mimo-agents/km-hr-agent/knowledge/legal/compliance-rules.md`

### 2. Länderkennung
- Erkenne anhand von Stellenprofil und Kandidatenprofil das/die relevanten Länder
- **DE:** Stelle in Deutschland oder Kandidat mit DE-Bezug
- **FR:** Stelle in Frankreich oder Kandidat mit FR-Bezug
- **CH:** Stelle in der Schweiz oder Kandidat mit CH-Bezug

### 3. Compliance-Check je Land

#### 🇩🇪 Deutschland (ansvar-german-law)
- **AGG §1:** Diskriminierungsverbot (Alter, Geschlecht, Herkunft)
- **EU AI Act Art. 50:** Transparenz bei KI-entscheidung
- **BDSG §26:** Datenverarbeitung für Einstellung
- **MiLoG:** Gehalt ≥ Mindestlohn (13,90 EUR/h Stand 2026, Quelle: `knowledge/legal/contract-sources.md` Key `mindestlohn_2026` – sekundär belegt)
- **Tool:** `search_legislation(query="AGG §1 Diskriminierung Einstellung")`

#### 🇫🇷 Frankreich (ansvar-french-law)
- **Code du travail L.1132-1:** Diskriminierungsverbot
- **Loi sur le travail L.3121-27:** 35h-Woche
- **RGPD:** Datenschutz
- **SMIC:** Mindestlohn
- **Tool:** `search_legislation(query="Code du travail L.1132-1 discrimination")`

#### 🇨🇭 Schweiz (ansvar-swiss-law)
- **OR Art. 319:** Arbeitsvertrag
- **ArG Art. 9:** Arbeitszeit (45h/50h)
- **DSG Art. 6:** Datenschutz
- **Mindestlohn:** Je nach Kanton
- **Tool:** `search_legislation(query="OR Art. 319 Arbeitsvertrag")`

### 4. Ergebnis speichern
- **Connector:** `filesystem`
- **Tool:** `write_file`
- **Pfad:** `~/mimo-agents/km-hr-agent/ergebnisse/compliance-[name].md`

---

## Compliance-Score

| Status | Bedeutung | Aktion |
|---|---|---|
| ✅ COMPLIANT | Alle Prüfungen bestanden | Match fortsetzen |
| ⚠️ WARNUNG | Nicht-kritische Verstöße | Match mit Caveat |
| ❌ FEHLER | Kritische Verstöße | Match pausieren |

---

## Beispiel-Aufruf

### DE-Compliance prüfen
```json
{
  "name": "search",
  "arguments": {
    "query": "AGG Diskriminierung Einstellung",
    "jurisdictions": ["DE"]
  }
}
```

### FR-Compliance prüfen
```json
{
  "name": "search",
  "arguments": {
    "query": "Code du travail discrimination embauche",
    "jurisdictions": ["FR"]
  }
}
```

### CH-Compliance prüfen
```json
{
  "name": "search",
  "arguments": {
    "query": "OR Art. 319 Arbeitsvertrag Kündigung",
    "jurisdictions": ["CH"]
  }
}
```

### Zitation validieren
```json
{
  "name": "validate_citation",
  "arguments": {
    "article": "§ 823 BGB",
    "jurisdiction": "DE",
    "law": "BGB"
  }
}
```
