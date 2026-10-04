---
description: Erstellt Onboarding-Checkliste basierend auf Kandidatenprofil
connector: filesystem
---

## Funktionierende MCP-Connector

| Connector | Tool | Parameter | Zweck |
|---|---|---|---|
| `filesystem` | `read_text_file` | `path` (string) | Profile und Templates lesen |
| `filesystem` | `write_file` | `path`, `content` | Onboarding-Checkliste speichern |

### Konfiguration (opencode.json)
```json
"filesystem": {
  "command": "uvx",
  "args": ["mcp-server-filesystem", "/home/batnini/mimo-agents/km-hr-agent"],
  "description": "KM-HR-Agent: TXT/MD lesen + schreiben"
}
```

## Zugriff & Freigabe (v4.3, `knowledge/system/access-control.md`)

| Rolle | Rechte |
|---|---|
| EMPLOYER (HR) | Checkliste erstellen (wie bisher) + **„Onboarding für Kandidat freigeben"** – Freigabe setzt die Bewerbung auf `eingestellt` (bzw. Freigabe-Flag in der Bewerbungskette, siehe `application-status.md`) |
| CANDIDATE | Sieht NUR die eigene, freigegebene Checkliste (read-only). Ohne Freigabe: Meldung „Noch nicht freigegeben". |

---

## Schritte

### 1. Kandidatenprofil einlesen
- **Connector**: `filesystem`
- **Tool**: `read_text_file`
- **Parameter**: `path` = Kandidatenprofil-Pfad

### 2. Template einlesen (optional)
- **Connector**: `filesystem`
- **Tool**: `read_text_file`
- **Parameter**: `path` = `~/mimo-agents/km-hr-agent/knowledge/onboarding-default.md`

### 3. Onboarding-Checkliste generieren
- Arbeitsgeräte vorbereiten
- Systemzugänge anlegen
- Einweisung Software-Tools
- Team-Vorstellungsrunde
- Erste Aufgaben zuweisen

### 4. Ergebnis speichern
- **Connector**: `filesystem`
- **Tool**: `write_file`
- **Parameter**: `path` = `~/mimo-agents/km-hr-agent/ergebnisse/onboarding-[name]-[datum].md`
- **Parameter**: `content` = generierte Checkliste als String
