---
description: Speichert Feedback eines Kandidaten in eine MD-Datei
connector: filesystem
---

## Funktionierende MCP-Connector

| Connector | Tool | Parameter | Zweck |
|---|---|---|---|
| `filesystem` | `write_file` | `path`, `content` (string) | Feedback-Datei speichern |

### Konfiguration (opencode.json)
```json
"filesystem": {
  "command": "uvx",
  "args": ["mcp-server-filesystem", "/home/batnini/mimo-agents/km-hr-agent"],
  "description": "KM-HR-Agent: TXT/MD lesen + schreiben"
}
```

## Schritte

### 1. Feedback als String vorbereiten
- Format: Markdown
- Enthalten: Name, Datum, Bewertung, Kommentar

### 2. Datei schreiben
- **Connector**: `filesystem`
- **Tool**: `write_file`
- **Parameter**: `path` = `~/mimo-agents/km-hr-agent/data/feedback-[name]-[datum].md`
- **Parameter**: `content` = Feedback-String

---

## Beispiel-Pfad

```
~/mimo-agents/km-hr-agent/data/feedback-anna-schuster-2026-09-10.md
```
