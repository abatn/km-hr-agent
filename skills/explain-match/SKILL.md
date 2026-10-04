---
description: Erstellt detaillierte Begründung für den Match-Score
connector: filesystem
---

## Funktionierende MCP-Connector

| Connector | Tool | Parameter | Zweck |
|---|---|---|---|
| `filesystem` | `read_text_file` | `path` (string) | Profile und Wissensdateien lesen |

### Konfiguration (opencode.json)
```json
"filesystem": {
  "command": "uvx",
  "args": ["mcp-server-filesystem", "/home/batnini/mimo-agents/km-hr-agent"],
  "description": "KM-HR-Agent: TXT/MD lesen + schreiben"
}
```

## Schritte

### 1. Profile einlesen
- **Connector**: `filesystem`
- **Tool**: `read_text_file`
- **Parameter**: `path` = Kandidatenprofil
- **Parameter**: `path` = Stellenprofil

### 2. Match-Kriterien einlesen
- **Tool**: `read_text_file`
- **Parameter**: `path` = `~/mimo-agents/km-hr-agent/knowledge/lifecycle/explanation-templates.md`

### 3. Detaillierte Begründung erstellen
- Ausgangspunkt: Score aus `match-candidate`
- Kategorien: Erfahrung, Skills, Standort, Kultur-Fit, Gehaltserwartung
- Für jede Kategorie: Stärke/Schwäche erklären

### 4. Ergebnis speichern
- **Tool**: `write_file` (internal)
- **Pfad**: `~/mimo-agents/km-hr-agent/ergebnisse/erklärung-[name]-[datum].md`

### 5. Rückgabe
- Gib vollständige Begründung als Text zurück
