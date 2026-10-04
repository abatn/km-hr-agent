---
description: DSGVO-Compliance-Prüfung für Kandidatenprofile
connector: filesystem
---

## Funktionierende MCP-Connector

| Connector | Tool | Parameter | Zweck |
|---|---|---|---|
| `filesystem` | `read_text_file` | `path` (string) | DSGVO-Rules und Profile lesen |

### Konfiguration (opencode.json)
```json
"filesystem": {
  "command": "uvx",
  "args": ["mcp-server-filesystem", "/home/batnini/mimo-agents/km-hr-agent"],
  "description": "KM-HR-Agent: TXT/MD lesen + schreiben"
}
```

## Schritte

### 1. DSGVO-Rules einlesen
- **Connector**: `filesystem`
- **Tool**: `read_text_file`
- **Parameter**: `path` = `~/mimo-agents/km-hr-agent/knowledge/legal/gdpr-policy.md`

### 2. Kandidatenprofil einlesen
- **Connector**: `filesystem`
- **Tool**: `read_text_file`
- **Parameter**: `path` = Kandidatenprofil-Pfad

### 3. DSGVO-Konformität prüfen
- Einwilligung zur Datenverarbeitung (Art. 6 DSGVO)
- Zweckbindung der Daten
- Speicherfristen
- Betroffenenrechte (Art. 15–20 DSGVO)

### 4. Ergebnis speichern
- **Tool**: `write_file` (internal)
- **Pfad**: `~/mimo-agents/km-hr-agent/ergebnisse/gdpr-[name].md`
