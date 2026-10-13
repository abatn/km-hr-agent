# HR-API-Connectors – Integration in Personio, SAP SuccessFactors, Workday

> **Stand:** September 2026  
> **Zweck:** Automatischer Import/Export von Kandidaten- und Stellendaten

---

## 1. Personio

### API-Endpunkte

| Endpoint | Methode | Beschreibung |
|---|---|---|
| `/api/v1/candidates` | GET | Alle Kandidaten abrufen |
| `/api/v1/candidates/{id}` | GET | Einzelnen Kandidaten abrufen |
| `/api/v1/candidates` | POST | Kandidaten anlegen |
| `/api/v1/candidates/{id}` | PUT | Kandidaten aktualisieren |
| `/api/v1/jobs` | GET | Alle Stellen abrufen |
| `/api/v1/jobs/{id}` | GET | Einzelne Stelle abrufen |
| `/api/v1/applications` | GET | Alle Bewerbungen abrufen |
| `/api/v1/applications/{id}` | GET | Einzelne Bewerbung abrufen |

### Authentifizierung
```json
{
  "type": "bearer",
  "header": "Authorization",
  "prefix": "Bearer ",
  "token_url": "https://api.personio.de/v1/auth",
  "credentials": {
    "client_id": "DEINE_CLIENT_ID",
    "client_secret": "DEIN_CLIENT_SECRET"
  }
}
```

### MCP-Connector-Konfiguration
```json
{
  "personio-mcp": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "personio-mcp-server"],
    "env": {
      "PERSONIO_CLIENT_ID": "DEINE_CLIENT_ID",
      "PERSONIO_CLIENT_SECRET": "DEIN_CLIENT_SECRET"
    },
    "enabled": true
  }
}
```

### Import-Mapping (Personio → Agent)

| Personio-Feld | Agent-Feld | Typ |
|---|---|---|
| `first_name` + `last_name` | `name` | string |
| `email` | `kontakt.email` | string |
| `phone` | `kontakt.telefon` | string |
| `address` | `standort.aktuell` | string |
| `work_experience` | `berufserfahrung` | array |
| `education` | `bildung` | array |
| `skills` | `hard_skills` | array |

---

## 2. SAP SuccessFactors

### API-Endpunkte

| Endpoint | Methode | Beschreibung |
|---|---|---|
| `/odata/v2/Candidate` | GET | Alle Kandidaten abrufen |
| `/odata/v2/Candidate('{id}')` | GET | Einzelnen Kandidaten abrufen |
| `/odata/v2/JobRequisition` | GET | Alle Stellen abrufen |
| `/odata/v2/JobRequisition('{id}')` | GET | Einzelne Stelle abrufen |
| `/odata/v2/CandidateApplication` | GET | Alle Bewerbungen abrufen |

### Authentifizierung
```json
{
  "type": "oauth2",
  "flow": "client_credentials",
  "token_url": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
  "scopes": ["odata.metadata", "odata.read"],
  "credentials": {
    "client_id": "DEINE_CLIENT_ID",
    "client_secret": "DEIN_CLIENT_SECRET"
  }
}
```

### MCP-Connector-Konfiguration
```json
{
  "successfactors-mcp": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "successfactors-mcp-server"],
    "env": {
      "SF_CLIENT_ID": "DEINE_CLIENT_ID",
      "SF_CLIENT_SECRET": "DEIN_CLIENT_SECRET",
      "SF_COMPANY_ID": "DEINE_FIRMEN_ID",
      "SF_BASE_URL": "https://api.successfactors.eu"
    },
    "enabled": true
  }
}
```

### Import-Mapping (SuccessFactors → Agent)

| SuccessFactors-Feld | Agent-Feld | Typ |
|---|---|---|
| `firstName` + `lastName` | `name` | string |
| `email` | `kontakt.email` | string |
| `phone` | `kontakt.telefon` | string |
| `location` | `standort.aktuell` | string |
| `employmentHistory` | `berufserfahrung` | array |
| `education` | `bildung` | array |
| `competencies` | `hard_skills` | array |

---

## 3. Workday

### API-Endpunkte

| Endpoint | Methode | Beschreibung |
|---|---|---|
| `/api/v1/workers` | GET | Alle Mitarbeiter/Kandidaten abrufen |
| `/api/v1/workers/{id}` | GET | Einzelnen Eintrag abrufen |
| `/api/v1/job_requisitions` | GET | Alle Stellen abrufen |
| `/api/v1/job_requisitions/{id}` | GET | Einzelne Stelle abrufen |
| `/api/v1/candidate_profiles` | GET | Alle Kandidaten-Profile abrufen |

### Authentifizierung
```json
{
  "type": "basic",
  "username": "DEIN_WORKDAY用户名",
  "password": "DEIN_WORKDAY_PASSWORT",
  "header": "Authorization",
  "prefix": "Basic "
}
```

### MCP-Connector-Konfiguration
```json
{
  "workday-mcp": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "workday-mcp-server"],
    "env": {
      "WORKDAY_USERNAME": "DEIN_USERNAME",
      "WORKDAY_PASSWORD": "DEIN_PASSWORT",
      "WORKDAY_TENANT": "DEIN_TENANT",
      "WORKDAY_BASE_URL": "https://www.workday.com"
    },
    "enabled": true
  }
}
```

### Import-Mapping (Workday → Agent)

| Workday-Feld | Agent-Feld | Typ |
|---|---|---|
| `name` | `name` | string |
| `email` | `kontakt.email` | string |
| `phone` | `kontakt.telefon` | string |
| `location` | `standort.aktuell` | string |
| `workHistory` | `berufserfahrung` | array |
| `education` | `bildung` | array |
| `skills` | `hard_skills` | array |

---

## 4. Unified Connector-Konfiguration

### In opencode.json ergänzen:
```json
{
  "mcp": {
    "personio-mcp": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "personio-mcp-server"],
      "enabled": false,
      "_comment": "Personio API – bei Bedarf aktivieren"
    },
    "successfactors-mcp": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "successfactors-mcp-server"],
      "enabled": false,
      "_comment": "SAP SuccessFactors – bei Bedarf aktivieren"
    },
    "workday-mcp": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "workday-mcp-server"],
      "enabled": false,
      "_comment": "Workday – bei Bedarf aktivieren"
    }
  }
}
```

---

## 5. Import-Workflow

```
HR-System (Personio/SF/Workday)
  ↓ API-Call
HR-API-Connector (MCP)
  ↓ Rohdaten
extract-profile (Skill)
  ↓ Strukturiertes Profil
match-candidate (Skill)
  ↓ Score
export-report (Skill)
  ↓ PDF/Excel
Filesystem-Connector
  ↓ Speichern
Ergebnis-Datei
```

---

## 6. Fehlerbehandlung

| Fehler | Ursache | Lösung |
|---|---|---|
| 401 Unauthorized | Token abgelaufen | Token aktualisieren |
| 403 Forbidden | Keine Berechtigung | Berechtigungen prüfen |
| 404 Not Found | Endpoint falsch | URL prüfen |
| 429 Rate Limit | Zu viele Anfragen | Retry nach 60s |
| 500 Server Error | Server-Problem | Später erneut versuchen |

---

## 7. Datenschutz (DSGVO)

- **Einwilligung:** Kandidaten müssen der Datenübermittlung zugestimmt haben
- **Speicherort:** API-Aufrufe nur an EU/CH-Server
- **Protokollierung:** Fehlgeschlagene HR-REST-Connectoren landen in `logs/agent-errors.log`. Der Runner-MCP-Call (`mcp_call`) schreibt **live** seit 13.10.2026 eine redigierte Zeile nach `logs/mcp-calls.log` (Regel: `knowledge/system/agent-automation.md`, Abschnitt Protokollierung).
- **Löschung:** Kandidaten können Löschung in allen Systemen verlangen

---

*Erstellt am 10.09.2026 für den KM-HR-Agenten.*
