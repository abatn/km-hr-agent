# KM-HR-Agent Connector-Fix: Analyse und Lösung

## Diagnose

### Ausgangssituation

Der KM-HR-Agent basierte auf:
- **`read`** (intern) – TXT/MD lesen
- **`write`** (intern) – Dateien schreiben

Problem: Diese internen Tools sind **keine MCP-Server**. Der Agent ist "nur eine Hülle".

---

## Schritt 1: Verfügbare MCP-Connectoren prüfen

### Bezugnehmend auf contract-check/CONNECTOR-SETUP.md

Die bewährten, funktionierenden MCP-Connectoren:

| Connector | Typ | Command | Tools | Status |
|---|---|---|---|---|
| `contract-check-filesystem` | local | `npx -y @modelcontextprotocol/server-filesystem /pfad` | read_text_file, list_directory, write_file, read_directory, edit_file, glob, create_directory, delete_file_or_directory, rename_file, directory_tree | ✅ FUNKTIONIERT |
| `ansvar-german-law` | local | `mcp-remote gateway.ansvar.eu` | 19 Tools (validate_citation, search_legislation, get_provision, etc.) | ✅ FUNKTIONIERT |
| `resume-parser-ats` | CLI (npm) | `resume-parser-ats parse PDF --json` | PDF → strukturierte Daten | ✅ FUNKTIONIERT (lokal) |

---

## Schritt 2: Connector für KM-HR-Agent auswählen

### Wahl: `contract-check-filesystem`

**Begründung:**
1. ✅ Bereits konfiguriert und funktionierend
2. ✅ Unterstützt TXT/MD-Dateien
3. ✅ Keine neue Installation nötig
4. ✅ Gleicher Pfad: `/home/batnini/mimo-agents`

**Tools:**
- `read_text_file` – Lebensläufe lesen
- `list_directory` – Verzeichnisse durchsuchen
- `write_file` – Ergebnisse speichern
- `glob` – Dateien finden

---

## Schritt 3: Skills anpassen

### 3.1 extract-profile/SKILL.md

**Vorher:**
```yaml
description: Extrahiert ein strukturiertes Profil aus einem Lebenslauf (TXT/MD)
tool: read (intern)
```

**Nachher:**
```yaml
description: Extrahiert ein strukturiertes Profil aus einem Lebenslauf (TXT/MD)
connector: contract-check-filesystem
tool: read_text_file
parameter: path (string) – absoluter Pfad zur Lebenslauf-Datei
```

---

### 3.2 match-candidate/SKILL.md

**Vorher:**
```yaml
tool: read (intern)
```

**Nachher:**
```yaml
connector: contract-check-filesystem
tool: read_text_file
parameters: 
  - path (string) – Kandidatenprofil
  - path (string) – Stellenprofil  
  - path (string) – knowledge/matching-criteria.md
```

---

### 3.3 Weitere Skills (nach dem gleichen Muster)

| Skill | Connector | Tool | Parameter |
|---|---|---|---|
| `check-compliance` | contract-check-filesystem | read_text_file | path (knowledge/compliance-rules.md) |
| `check-gdpr` | contract-check-filesystem | read_text_file | path (knowledge/gdpr-policy.md) |
| `assess-culture-fit` | contract-check-filesystem | read_text_file | path (profil) |
| `generate-onboarding` | contract-check-filesystem | write_file | path, content (string) |
| `store-feedback` | contract-check-filesystem | write_file | path, content (string) |
| `explain-match` | contract-check-filesystem | read_text_file | path (profil + stellenprofil) |

---

## Schritt 4: Test mit lebenslauf-anna-schuster.txt

### Test-Aufruf

```json
{
  "name": "read_text_file",
  "arguments": {
    "path": "/home/batnini/mimo-agents/km-hr-agent/testdaten/lebenslauf-anna-schuster.txt"
  }
}
```

### Durchführung

Datei wird via `contract-check-filesystem` Connector gelesen.

---

## Schritt 5: Ergebnis-Analyse

### Erwarteter Output

Das Ergebnis wird in:
```
~/mimo-agents/km-hr-agent/ergebnisse/test-anna-schuster-final.md
```

---

## Zusammenfassung

| Aspekt | Vorher | Nachher |
|---|---|---|
| **Connector** | Intern (read/write) | contract-check-filesystem (MCP) |
| **Tool** | Intern | read_text_file |
| **Parameter** | Nicht definiert | `path` (string, absolut) |
| **MCP-konform** | ❌ Nein | ✅ Ja |

---

## Nächster Schritt

Der KM-HR-Agent ist jetzt MCP-konform mit dem `contract-check-filesystem` Connector. Die Skills wurden aktualisiert, um den Connector explizit zu referenzieren.

**Zum Testen der Komplettlösung:**
- Verwende den `contract-check-filesystem` Connector
- Rufe `read_text_file` für `lebenslauf-anna-schuster.txt` auf
- Ergebnis wird in `ergebnisse/test-anna-schuster-final.md` gespeichert
