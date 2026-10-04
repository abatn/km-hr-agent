# MCP-Connector-Konfiguration für KM-HR-Agent (aktualisiert)

> **Stand:** September 2026  
> **Datei:** `opencode.json` (lokal im Projekt)

---

## Konfiguration für opencode.json

> **⚠️ Hinweis (Phase-E P0, 24.09.2026):** Der folgende JSON-Block ist ein **gekürzter Auszug vom 15.09.2026** und inzwischen veraltet – er fehlt `anysearch`, `hr-benchmark`, `salary-data`, `prescreen-config`, `language-test` sowie die Venv-Präfixe (`.venv-pdf/bin/python3`) und die Mail-Auth über `.env-email`. **Außerdem entfernt (Phase-E Runde 2, 24.09.2026):** `memory`, `mobileid`, `payment`; **`jitsi-meeting` entfernt 27.09.2026** → siehe „Entfernte Connectors" unten. **Maßgeblich:** `opencode.json` direkt (live: **14 Server** = 13 local + 1 remote, Stand 27.09.2026) + die Tabelle „Aktive Connector-Übersicht (14 Server)" unten.

Die folgenden Connector-Einträge sind in der `mcpServers`-Sektion von `opencode.json` aktiv:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest", "--browser", "chromium"],
      "description": "Browser-Automation (Playwright + Chromium)"
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/batnini/mimo-agents/km-hr-agent"],
      "description": "KM-HR-Agent: TXT/MD lesen + schreiben"
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"],
      "description": "HTTP-Fetch (Web-Inhalte laden)"
    },
    "pdf-reader": {
      "command": "python3",
      "args": ["/home/batnini/mimo-agents/km-hr-agent/mcp-pdf-server.py"],
      "description": "KM-HR-Agent: PDF-Text extrahieren (PyMuPDF)"
    },
    "meeting-tools": {
      "command": "python3",
      "args": ["/home/batnini/mimo-agents/km-hr-agent/mcp-meeting-server.py"],
      "description": "KM-HR-Agent: Screening-Fragen + ICS generieren"
    },
    "ansvar-german-law": {
      "command": "npx",
      "args": ["-y", "mcp-remote@0.1.38", "https://gateway.ansvar.eu/mcp"],
      "description": "KM-HR-Agent: DE-Recht (AGG, BDSG, MiLoG, EU AI Act)"
    },
    "ansvar-french-law": {
      "command": "npx",
      "args": ["-y", "mcp-remote@0.1.38", "https://gateway.ansvar.eu/mcp"],
      "description": "KM-HR-Agent: FR-Recht (Code du travail, RGPD)"
    },
    "ansvar-swiss-law": {
      "command": "npx",
      "args": ["-y", "mcp-remote@0.1.38", "https://gateway.ansvar.eu/mcp"],
      "description": "KM-HR-Agent: CH-Recht (OR, ArG, DSG)"
    },
    "email-sender": {
      "command": "python3",
      "args": ["/home/batnini/mimo-agents/km-hr-agent/mcp-email-server.py"],
      "description": "KM-HR-Agent: E-Mails via SMTP senden (Server aus .env-email, seit 24.09.2026 Gmail)"
    },
  }
}
```

---

## Aktive Connector-Übersicht (14 Server, Stand 27.09.2026 = opencode.json; `jitsi-meeting` entfernt, vorher 15)

| Connector | Typ | Auth | Beschreibung | Tools | Status |
|---|---|---|---|---|---|
| `playwright` | local (npx) | Keine | Browser-Automation (Chromium) | 25 (Voll-Liste: ergebnisse/mcp-connector-audit-2026-09-25.md §6.3) | ✅ AKTIV |
| `filesystem` | local (npx) | Keine | Dateisystem-Zugriff für km-hr-agent **(Agenten-Werkzeug; die App greift selbst mit `pathlib`/IO zu — audit §3 S-07)** | 14: read_file, read_text_file, read_media_file, read_multiple_files, write_file, edit_file, create_directory, list_directory, list_directory_with_sizes, directory_tree, move_file, search_files, get_file_info, list_allowed_directories | ✅ FUNKTIONIERT |
| `fetch` | local (uvx) | Keine | HTTP-Fetch (Web-Inhalte laden; **nur Agenten-Aufruf, kein Python — audit §3 S-06**; Ersatz bei anysearch-Ausfall) | 1: fetch *(ungenutzt in Python)* | ✅ AKTIV (Agenten-Werkzeug) |
| `pdf-reader` | local (Python) | Keine | PDF-Text extrahieren (PyMuPDF) | 3: read_pdf_text *(genutzt, Extract-Flow `agent-runner.py:279`)*, get_pdf_info *(ungenutzt — Reserve, audit §3 S-12)*, analyze_pdf_structure *(ungenutzt; Forensik-Pre-Scan = `pdf-verify-mcp`, `agent-runner.py:49`)* | ✅ FUNKTIONIERT |
| `meeting-tools` | local (Python) | Keine | Screening-Fragen + ICS generieren | 3: generate_screening_questions *(genutzt)*, generate_ics_file *(genutzt)*, create_meeting_link *(LEGACY — **ungenutzt seit 25.09.2026**, URL seit 27.09.2026 **VDO.Ninja** statt Jitsi (Punkt e, 0 Aufrufer); Server bleibt, 2/3 aktiv — audit §3 S-11)* | ✅ FUNKTIONIERT |
| `email-sender` | local (Python) | SMTP via `.env-email` (**seit 24.09.2026 Gmail**, davor Yahoo; Code-Default `smtp.mail.yahoo.com`) | E-Mails senden | 3: send_email *(genutzt, `agent-runner.py:495-567`)*, send_interview_invitation *(ungenutzt — Einladung läuft über send_email, audit §3 S-05)*, send_pre_screen_invitation *(genutzt)* | ✅ FUNKTIONIERT |
| ~~`jitsi-meeting`~~ | ~~local (Node.js)~~ | — | ~~Jitsi-Meetings (join/leave/chat/recording)~~ | ~~11 Tools~~ | ❌ **ENTFERNT 27.09.2026** — 0 Aufrufe im Code; VDO.Ninja-Migration (Spec `knowledge/system/vdo-ninja-migration.md`). Raum-URL = String-Bildung im Runner. **Der Ordner `jitsi-mcp-server/` existiert nicht mehr auf Disk** (`ls -d jitsi-mcp-server` → No such file or directory, 01.10.2026) | Frei nutzt nur URL-Erzeugung `agent-runner.py:522`/`:525`, „jitsi-meeting bot optional" (AGENTS.md; audit §3 S-09) |
| `ansvar-german-law` | remote (mcp-remote) | OAuth (Token vorhanden) | Deutsche Gesetze (6.870 Gesetze) | 35: search *(einziger genutzter Tool, `agent-runner.py:973`)*, validate_citation *(ungenutzt)*, get_provision *(ungenutzt)* u.a. (Voll-Liste: ergebnisse/mcp-connector-audit-2026-09-25.md §6.3) — App-Weg = HTTP-Gateway `scripts/ansvar_gateway.py:170` (audit §3 S-02/03/04) | ✅ FUNKTIONIERT |
| `ansvar-french-law` | remote (mcp-remote) | OAuth (Token vorhanden) | Französische Gesetze (3.958 Gesetze) | 35: search *(einziger genutzter Tool, `agent-runner.py:973`)*, validate_citation *(ungenutzt)*, get_provision *(ungenutzt)* u.a. (Voll-Liste: ergebnisse/mcp-connector-audit-2026-09-25.md §6.3) — App-Weg = HTTP-Gateway `scripts/ansvar_gateway.py:170` (audit §3 S-02/03/04) | ✅ FUNKTIONIERT |
| `ansvar-swiss-law` | remote (mcp-remote) | OAuth (Token vorhanden) | Schweizer Gesetze (4.873 Gesetze) | 35: search *(einziger genutzter Tool, `agent-runner.py:973`)*, validate_citation *(ungenutzt)*, get_provision *(ungenutzt)* u.a. (Voll-Liste: ergebnisse/mcp-connector-audit-2026-09-25.md §6.3) — App-Weg = HTTP-Gateway `scripts/ansvar_gateway.py:170` (audit §3 S-02/03/04) | ✅ FUNKTIONIERT |
| `hr-benchmark` | local (Python) | Keine | ZYTHR-Formel: (score/max) × weight | 3: calculate_weighted_score *(ungenutzt — **K4-Doppelwahrheit**: identische Formel in `webui/logic.py:450-452`, App-Rechnung führend — audit §3 S-08)*, get_score_category *(genutzt — **seit 29.09.2026 nur noch im Runner** (`agent-runner.py:1127`); **Webui ruft lokal**: `get_score_category_lokal()` (`logic.py:494-509`) liefert dieselben ZYTHR-Schwellen aus dem Connector-Quelltext (≥80 Strong / ≥60 Consider / sonst Weak) ohne Subprozess — Grund: 82,06 s kalte Match-Seite durch 19 Spawns (M-16, `ergebnisse/m16-timing-20260929.md`; Nutzer-GO 29.09.)*, get_weight_ranges *(ungenutzt — Gewichte kommen aus `gewichtung_historie`)* | ✅ GETESTET (15.09.2026) |
| `salary-data` | local (Python) | Keine | BambooHR-Formel: Min/Mid/Max = 25th/50th/75th | 3: calculate_salary_band *(ungenutzt — Reserve Gehalts-UI, audit §3 S-15)*, calculate_salary_position *(ungenutzt — dasselbe)*, calculate_salary_tolerance *(genutzt, `webui/logic.py:322` gehalt_check)* | ✅ GETESTET (15.09.2026) |
| `prescreen-config` | local (Python) | Keine | CareerPlug: 15-30 Minuten | 3: get_optimal_duration *(genutzt, `agent-runner.py:533`)*, get_screening_questions *(ungenutzt — Fragen kommen aus Skill/MD, audit §3 S-14)*, get_screening_structure *(ungenutzt — dasselbe)* | ✅ GETESTET (15.09.2026) |
| `language-test` | local (Python) | Keine | CEFR-Niveautests (732 Fragen + LLM-Zusatzfragen) | 3: generate_test *(genutzt)*, score_answer *(ungenutzt — **lokale Bewertung ist führend**: `webui/pages/candidate.py:870-894` (Prüfung + `logic.cefr_from_avg`), audit §3 S-10)*, get_cefr_level *(genutzt)* | ✅ GETESTET (16.09.2026), Details unten |
| `anysearch` | remote (URL) | **kein Schlüssel nötig** (anonym; `X-Anysearch-Client` genügt) | Websuche (Heimatland-Suche, Kurse) | 4: batch_search, extract, get_sub_domains, search | ✅ **01.10.2026 (Nutzer-Entscheidung):** `Authorization: Bearer {env:ANYSEARCH_API_KEY}` in `opencode.json` **entfernt**, nur `X-Anysearch-Client: mcp/1.0.0` bleibt → anonym. README anysearch: Key optional, anonym funktional. **Wirksam erst nach OpenCode-Neustart** (G2-5/Nachweis dann `search` ohne Provisionierung). Frühere Stati (P1c 24.09. entfernt, M1/H1 26.09. wieder eingetragen, H9 offen) damit geschlossen. Ersatz bis dahin `fetch` |

---

## Tool-Namen-Pflicht (Connector-Truth, 24.09.2026)

**Regel (verbindlich):** In Code, Specs und Reports **NUR** MCP-Server-Namen aus `opencode.json` verwenden (die **14**: `ansvar-french-law`, `ansvar-german-law`, `ansvar-swiss-law`, `anysearch`, `email-sender`, `fetch`, `filesystem`, `hr-benchmark`, `language-test`, `meeting-tools`, `pdf-reader`, `playwright`, `prescreen-config`, `salary-data`; Stand 27.09.2026, `jitsi-meeting` entfernt). Keine erfundenen Tools (`websearch`/`webfetch` … existieren NICHT in `opencode.json`) und **keine entfernten** (`memory`, `mobileid`, `payment` seit 24.09.2026 raus). Zuordnung: Seitenabruf/HTTP → `fetch` · Websuche → `anysearch` · Browser/Bot-Schutz-Umgehung → `playwright`. Externe URLs in MD sind Zitate für Menschen + immer mit Abruf-Werkzeug (MCP `fetch`/`anysearch`) benannt; in CODE gar keine harten Fremd-URLs — Daten kommen über den Connector.

---

## Neue Connectoren (15.09.2026)

### hr-benchmark
```json
{
  "hr-benchmark": {
    "type": "local",
    "command": ["python3", "connectors/hr-benchmark-server.py"],
    "enabled": true
  }
}
```
**Tools:** `calculate_weighted_score`, `get_score_category`, `get_weight_ranges`  
**Formel:** ZYTHR `(score/max) × weight`  
**Test:** ✅ 15.09.2026

### salary-data
```json
{
  "salary-data": {
    "type": "local",
    "command": ["python3", "connectors/salary-data-server.py"],
    "enabled": true
  }
}
```
**Tools:** `calculate_salary_band`, `calculate_salary_position`, `calculate_salary_tolerance`  
**Formel:** BambooHR `Min=25th, Mid=50th, Max=75th`  
**Test:** ✅ 15.09.2026

### prescreen-config
```json
{
  "prescreen-config": {
    "type": "local",
    "command": ["python3", "connectors/prescreen-config-server.py"],
    "enabled": true
  }
}
```
**Tools:** `get_optimal_duration`, `get_screening_questions`, `get_screening_structure`  
**Logik:** CareerPlug `15-30 Minuten`  
**Test:** ✅ 15.09.2026

### language-test (NEU, 16.09.2026)
```json
{
  "language-test": {
    "type": "local",
    "command": ["python3", "scripts/language-test-server.py"],
    "enabled": true
  }
}
```
**Tools:** `generate_test`, `score_answer`, `get_cefr_level`  
**Logik:** CEFR-Niveautests: 732 Fragen (DE 120, EN 522, FR 90, offiziell) + LLM-generierte Zusatzfragen (hybrid), LLM-Bewertung via NVIDIA API  
**ID-Schema (einheitlich seit 20.09.2026):**

| Namespace | Format | Beispiel | Anzahl |
|---|---|---|---|
| Deutsch (Seed) | `DE-<Level>-NN` (2-stellig) | `DE-A1-20` | 120 |
| Englisch (Seed) | `EN-<Level>-NNN` (3-stellig) | `EN-A2-001` | 522 |
| Französisch (Seed) | `FR-<Level>-NN` (2-stellig) | `FR-B2-05` | 90 |
| LLM-Zusatzfragen | `LLM-<Sprachkürzel>-<Level>-NN` | `LLM-DE-A1-01` | dynamisch |

Quelle: `knowledge/language-tests.md` (Parser `_parse_questions()`, 15 Sektionen). EN-IDs am 20.09.2026 von `cambridge-*-NNN` auf `EN-*` vereinheitlicht (522 umgestellt; Parser/generate_test/score_answer-Regression bestanden).  
**Test:** ✅ 16.09.2026 (py_compile + generate_test + get_cefr_level) · ✅ 20.09.2026 (ID-Rewrite + Regressionstests)

---

## Optionale Connectors (nicht im lokalen opencode.json)

### Öffentliche REST-APIs

| API | URL | Auth | Beschreibung |
|---|---|---|---|
| Arbeitsamt | https://jobsuche.api.bund.dev/ | OAuth | Deutscher Bundes-Jobboard |
| Arbeitnow | https://documenter.getpostman.com/view/18545278/UVJbJdKh | Keine | Europäischer Job-Aggregator |

---

## Entfernte Connectors (nicht mehr vorhanden)

| Alter Connector | Grund der Entfernung |
|---|---|
| `contract-check-filesystem` | Zeigte auf anderes Projekt (contract-check) → filesystem als Ersatz |
| `pdf-connector` (@sylphx/citra) | Citra erwartet Base64 → pdf-reader als Alternative |
| `prismhr-mcp` | Nicht installiert, proprietäre API-Zugangsdaten nötig |
| `breathehr-mcp` | Nicht installiert, API-Key nötig |
| `memory` | **Entfernt 24.09.2026 (Phase-E Runde 2, Nutzerentscheidung P1b)** – 0 Code-Aufrufe (`grep -rn "memory" scripts/ webui/ --include='*.py'` → nur ein Wort in einem Prompt-String); npx-Server `@modelcontextprotocol/server-memory`; Verzeichnis nicht vorhanden |
| `mobileid` | **Entfernt 24.09.2026 (P1b)** – 0 Code-Aufrufe (grep 20.09.2026 + 24.09.2026: 0 Treffer); `mcp-connectors/mobileid-mcp/` bleibt auf Disk liegen |
| `payment` | **Entfernt 24.09.2026 (P1b)** – 0 Code-Aufrufe; `mcp-connectors/payment-mcp/` bleibt auf Disk liegen |

**Wirksamkeit:** Die Änderung wirkt erst nach einem **OpenCode-Neustart** des Nutzers (Config wird beim Start gelesen). Konfiguration geprüft via `python3 -c "import json; len(json.load(open('opencode.json'))['mcp'])"` → 15.

---

## Abhängigkeiten

### Python-Pakete (in .venv-streamlit)

```bash
pip install fastmcp>=4.0.0 pymupdf>=1.23.0 streamlit>=1.30.0
```

### System-Tools

- `uvx` – Für MCP-Filesystem-Server
- `python3` – Für Python MCP-Server (pdf-reader, meeting-tools, email-sender)
- `npx` – Für Ansvar Gateway (mcp-remote)

---

## Test

```bash
# Python MCP-Server testen
source .venv-streamlit/bin/activate
python3 mcp-pdf-server.py --help

# Ansvar Gateway testen
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | npx -y mcp-remote@0.1.38 https://gateway.ansvar.eu/mcp

# Neue Connectoren testen (15.09.2026)
python3 connectors/hr-benchmark-server.py
python3 connectors/salary-data-server.py
python3 connectors/prescreen-config-server.py
```

---

## OAuth-Token (Ansvar Gateway)

**Token-Speicherort:** `/home/batnini/.mcp-auth/mcp-remote-0.1.38/83c240cea87a307a99ab272acd787d05_tokens.json`

**Token-Status:** ✅ Vorhanden (Free-Tier, Bearer-Token)

**Token-Gültigkeit:** Access-Token läuft nach 15 Min ab, Refresh-Token erneuert automatisch

**Scope:** `profile organization email offline_access mcp:tools`

**35 Tools verfügbar:** search, diff, get_changes, get_provision, validate_citation, list_coverage + 29 weitere

---

**Status:** ✅ Aktualisiert (Stand: September 2026)

---

## Ist vs. dokumentiert (§G-Zählwerk-Nachzug, 26.09.2026)

Pflichtformulierung: **49 dokumentiert (instructions.md, nach §G-Nachzug) / 181 live (Handshake 26.09.2026)** — Quelle live: `/tmp/opencode/f1-tools-full.json` (selbst summiert = 181 über **15 Server**; historischer Stand 26.09.2026, **vor** der `jitsi-meeting`-Entfernung am 27.09.2026 → heute 14 Server).

> **Korrektur 26.09.2026 19:22 (K-Zahl):** vorher stand hier „44" — das war der Censusstand **vor** §G. Nach §G-Nachzug (anysearch 4 + create_meeting_link 1) listet `instructions.md` **49** Namen; Differenz zu 181 live = **132**. Frühere Angaben „137"/„138" (audit §6.3) bezogen sich auf denselben alten Stand und sind obsolet.

| Server | dokumentiert (diese Tabelle, nach §G) | live (f1-tools-full.json) | Differenz |
|---|---|---|---|
| playwright | 25 | 25 | 0 |
| filesystem | 14 | 14 | 0 |
| fetch | 1 | 1 | 0 |
| pdf-reader | 3 | 3 | 0 |
| meeting-tools | 3 | 3 | 0 |
| email-sender | 3 | 3 | 0 |
| jitsi-meeting | 11 | 11 | 0 | → **ENTFERNT 27.09.2026** (0 Aufrufe im Code; VDO.Ninja-Migration) |
| ansvar-german-law | 35 | 35 | 0 |
| ansvar-french-law | 35 | 35 | 0 |
| ansvar-swiss-law | 35 | 35 | 0 |
| hr-benchmark | 3 | 3 | 0 |
| salary-data | 3 | 3 | 0 |
| prescreen-config | 3 | 3 | 0 |
| language-test | 3 | 3 | 0 |
| anysearch | 4 | 4 | 0 |
| **Summe** | **181** | **181** | **0** |

Ergänzender Befund (nicht geglättet): `instructions.md` listet nach §G-Nachzug 49 Namen (Censusstand vorher 44) gegenüber 181 live → Differenz 132; die Vollständigkeit der instructions-Liste ist NICHT behauptet. Undokumentierte Live-Tools stehen in `ergebnisse/mcp-connector-audit-2026-09-25.md` §6.3 (A.6-Liste).
