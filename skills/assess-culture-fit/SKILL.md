---
description: Bewertet Kultur-Fit eines Kandidaten basierend auf Profil und Teamdaten
connector: filesystem
---

## Funktionierende MCP-Connector

| Connector | Tool | Parameter | Zweck |
|---|---|---|---|
| `filesystem` | `read_text_file` | `path` (string) | Teamdaten und Profile lesen |

### Konfiguration (opencode.json)
```json
"filesystem": {
  "command": "uvx",
  "args": ["mcp-server-filesystem", "/home/batnini/mimo-agents/km-hr-agent"],
  "description": "KM-HR-Agent: TXT/MD lesen + schreiben"
}
```

## Schritte

### 1. Kandidatenprofil einlesen
- **Connector**: `filesystem`
- **Tool**: `read_text_file`
- **Parameter**: `path` = Kandidatenprofil-Pfad

### 2. Teamdaten einlesen (falls vorhanden)
- **Connector**: `filesystem`
- **Tool**: `read_text_file`
- **Parameter**: `path` = `~/mimo-agents/km-hr-agent/knowledge/team-profile.md` (optional)

### 3. Kultur-Fit bewerten
- Kommunikationsstil
- Arbeitsweise (Remote, Hybrid, Onsite)
- Wertschätzung für Feedbackkultur
- Sprachkenntnisse

### 4. Ergebnis speichern
- **Tool**: `write_file` (internal)
- **Pfad**: `~/mimo-agents/km-hr-agent/ergebnisse/culture-fit-[name].md`

## DE-TN-Spezialisierung

- **Pointer (Quelle der vollen Spec):** `knowledge/lifecycle/cultural-fit-criteria.md`,
  Abschnitt **„DE-TN-Spezialisierung (Phase-E Runde 2, 24.09.2026)"** (dort: Arbeitsstil, Kommunikation,
  Rechtsrahmen, Erwartungshaltung, je mit Quelle oder Kennzeichnung).
- **P5-Disclaimer (§H-18, 26.09.2026):** Alle DE-TN-Aussagen sind **Design-Entscheidung** (Quellenlage
  0/0: recherche-plan-restpunkte-2026-09-25.md:182-197 — GLOBE ohne TN, Hofstede-TN nachgerechnet,
  Omrane/Khan deskriptiv). Nicht als empirisch belegt zitieren.
- **Kurzfassung:**
  - Arbeitsstil: DE = Prozess/Struktur zuerst, TN = Beziehungsaufbau vor Fachthema → übernimmt die
    Punkte-Skalen der Abschnitte „Arbeitsstil" (0–25) und „Kulturelle Passung" (0–30) unverändert.
  - Kommunikation: DE sachlich-direkt (Wert Zeile 75), TN höflich-indirekt (Wert Zeile 87) – HR übersetzt
    beide Richtungen (Übersetzungsbrücke).
  - Rechtsrahmen (nur Kontext, **kein** Kultur-Punktwert): §18a/§18b AufenthG, ZAV-Zustimmung §39 AufenthG
    4–8 Wochen, Blue Card 50.700 €/45.934 € (Stand 2026), Anerkennung IT freiwillig, Gesamtprozess 3–6 Monate.
  - Erwartungshaltung: Deutsch B2 empfohlen, realistischer Start 3–6 Monate, Score = Indiz (Variant A).
- **Kennzeichnung Quelle/Design:**
  - Rechtsrahmen-Zeilen: interne Quelle `knowledge/legal/visa-rules.md` (Zeilen 131, 133, 141-143, 157, 160).
  - Alle kulturellen/erwartungshaltenden Aussagen: **Design-Entscheidung** – Recherche am 24.09.2026 mit
    MCP-Connector `fetch` (bamf.de HTTP 200 ohne TN-Inhalt, daad.de studiengaenge HTTP 404,
    bamf.de ZuzugBeruf HTTP 404, bamf.de migrationaufenthalt HTTP 200 ohne TN-Inhalt) lieferte **0 externe
    TN-Quellen**.
  - Score-Gewichte und Kategorisierungsschwellen bleiben unverändert (**Design-Entscheidung**).
