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

### 1. Kandidatenquelle bestimmen (19.10.2026)
- **Arbeitgeber-Portal (Regel):** Quelle ist die **Datenbank** — `applications.status = 'eingestellt'`, arbeitgeber-scoped über `JOIN jobs`, **eine Zeile je Kandidat** (letzte eingestellte Bewerbung). Kein Profil-Datei-Zwang.
- **Admin/Demo (Fallback):** `logic.list_profiles()` aus `testdata/profil-*.md` (Parität zu `app.py`).
- **Kandidatendaten (DB):** `candidates.name` + `candidates.lebenslauf_text` (`hard_skills` als Fallback); Linux-/Kubernetes-Zeilen nur, wenn der Text sie enthält.
- **Design-Entscheidung:** Profil-Dateien sind Demo-/Legacy-Quelle; die DB ist für das Arbeitgeber-Portal maßgeblich (`application-status.md`: `eingestellt` = eingestellt).

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

### 4. Ergebnis speichern (lokal, kein Mailversand)
- **Connector**: `filesystem`
- **Tool**: `write_file`
- **Parameter**: `path` = `~/mimo-agents/km-hr-agent/ergebnisse/onboarding-[name]-[datum].md`
  (DB-Modus zusätzlich mit Kandidaten-ID: `onboarding-[name]-[cand_id]-[datum].md` — schützt vor Namenskollisionen)
- **Parameter**: `content` = generierte Checkliste als String
- **Kein Mailversand:** Der Versand läuft ausschließlich über den Runner-Hook `onboarding_release`/`send_onboarding_mail` (`knowledge/system/agent-automation.md`).
