---
description: Protokolliert Fehler und gibt dem Nutzer klare, hilfreiche Fehlermeldungen
connector: filesystem
---

## Funktionierende MCP-Connector

| Connector | Tool | Parameter | Zweck |
|---|---|---|---|
| `filesystem` | `write_file` | `path`, `content` | Fehler in Log-Datei schreiben |
| `filesystem` | `read_text_file` | `path` | Fehlerstatistiken lesen |

### Konfiguration (opencode.json)
```json
"filesystem": {
  "command": "uvx",
  "args": ["mcp-server-filesystem", "/home/batnini/mimo-agents/km-hr-agent"],
  "description": "KM-HR-Agent: TXT/MD lesen + schreiben"
}
```

---

## Input
- Fehlertyp (technisch, Daten, Logik, Connector)
- Fehlermeldung (roh)
- Kontext (welcher Skill, welche Datei, welcher Connector)

---

## Schritte

### 1. Fehler klassifizieren

| Typ | Beschreibung | Schwere |
|---|---|---|
| `TECHNISCH` | Systemfehler, Timeout, Speicher voll | HOCH |
| `DATEN` | Ungültiges Format, fehlende Felder, inkonsistente Daten | MITTEL |
| `LOGIK` | Score-Berechnung fehlgeschlagen, ungültiger Score | MITTEL |
| `CONNECTOR` | MCP-Server nicht erreichbar, API-Fehler | HOCH |
| `DSGVO` | Datenschutz-Verstoß, fehlende Einwilligung | KRITISCH |
| `COMPLIANCE` | Gesetzesverstoß, regulatorisches Problem | KRITISCH |
| `USER` | Ungültige Eingabe, fehlende Parameter | NIEDRIG |

### 2. Fehler-Metadaten erfassen

```json
{
  "timestamp": "2026-09-10T14:30:00Z",
  "typ": "CONNECTOR",
  "schwere": "HOCH",
  "skill": "extract-profile",
  "connector": "filesystem",
  "fehlermeldung": "Datei nicht gefunden",
  "kontext": {
    "datei": "lebenslauf-anna-schuster.txt",
    "aktion": "read_text_file"
  },
  "loesung_vorgeschlagen": [
    "Prüfe den Dateipfad",
    "Nutze list_directory, um verfügbare Dateien zu prüfen",
    "Erstelle die Datei mit write_file"
  ]
}
```

### 3. In Log-Datei schreiben

**Connector:** `filesystem`
**Tool:** `write_file`
**Pfad:** `~/mimo-agents/km-hr-agent/logs/agent-errors.log`

Format:
```
[2026-09-10 14:30:00] [HOCH] [CONNECTOR] filesystem: Datei nicht gefunden
  Skill: extract-profile | Datei: lebenslauf-anna-schuster.txt
  Lösung: Prüfe den Dateipfad
```

### 4. Nutzer-Fehlermeldung erstellen

#### Klare, hilfreiche Sprache:
- ❌ SCHLECHT: "Ein unerwarteter Fehler ist aufgetreten."
- ✅ GUT: "Die Datei wurde nicht gefunden. Bitte prüfe den Dateipfad oder erstelle die Datei mit write_file."

#### Format:
```
⚠️ Fehler: [Kurzbeschreibung]

Was ist passiert: [Technische Erklärung in einfacher Sprache]
Was du tun kannst: [Konkrete Lösungsschritte]
Alternative: [Workaround falls vorhanden]
```

### 5. Fallback-Strategie anbieten

| Fehlertyp | Fallback |
|---|---|
| pdf-reader (Python MCP) | PyMuPDF Fallback in app.py |
| filesystem | Prüfe Dateipfad mit list_directory |
| Ansvar-Gateway (DE-Recht) | Manuelle Prüfung via Knowledge-Datei |
| SQLite | Filesystem (MD-Datei) |
| API-Timeout | Retry nach 5s, max. 3 Versuche |
| Ungültige Daten | Standardwerte verwenden + Warning |

### 6. Fehlerstatistiken aktualisiere

**Connector:** `filesystem`
**Tool:** `write_file`
**Pfad:** `~/mimo-agents/km-hr-agent/knowledge/error-statistics.md`

Erstelle/aktualisiere:
- Gesamtzahl Fehler (nach Typ)
- Häufigste Fehler
- Durchschnittliche Lösungszeit
- Erfolgsrate der Fallbacks

### 7. Rückgabe
- Gib Fehlermeldung für Nutzer zurück
- Gib Log-Eintrag zurück
- Gib Fallback-Vorschlag zurück

---

## Beispiel-Aufruf

### Fehler loggen
```json
{
  "name": "write_file",
  "arguments": {
    "path": "/home/batnini/mimo-agents/km-hr-agent/logs/agent-errors.log",
    "content": "[2026-09-10 14:30:00] [HOCH] [CONNECTOR] filesystem: Datei nicht gefunden\n  Skill: extract-profile | Datei: lebenslauf-anna-schuster.txt\n  Lösung: Prüfe den Dateipfad\n"
  }
}
```
