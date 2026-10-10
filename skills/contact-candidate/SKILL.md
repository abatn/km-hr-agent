---
description: Kontaktiert Kandidaten per E-Mail mit Vorlage
tools:
  - filesystem (MCP)
---

## Regime: Vollständig lokal – keine externen E-Mail-APIs

## Verfügbare Tools

| Tool | Typ | Zweck |
|---|---|---|
| `filesystem` | MCP (local) | E-Mail-Vorlage lesen/schreiben |

## Schritte

### 1. Kandidaten-Kontaktdaten abrufen

#### Manuell (aus Lebenslauf/Profil)
- Name: Anna Schuster
- E-Mail: anna.schuster@example.de
- Angesprochener: Senior Cloud/DevOps Engineer

### 2. E-Mail-Vorlage laden

#### Vorlage-Datei (erstellt via write_file)
Pfad: `~/mimo-agents/km-hr-agent/knowledge/templates/email-templates/interview-invitation.md`

Inhalt:
```markdown
# E-Mail-Vorlage: Interview-Einladung

**Von:** HR Team / TechVision GmbH
**An:** {{kandidat_name}}
**Betreff:** Einladung zum Vorstellungsgespräch – {{stelle}}

---

Sehr geehrte(r) {{anredee_kandidat}},

wir freuen uns, Ihnen unser Interesse an Ihrer Bewerbung mitteilen zu können.

Nach der Prüfung Ihres Lebenslaufs haben wir festgestellt, dass Ihre Qualifikationen hervorragend zu unserer Position als {{stelle}} bei {{unternehmen}} passen.

**Wir laden Sie herzlich ein zum:**

- **Datum:** {{datum}}
- **Uhrzeit:** {{uhrzeit}}
- **Format:** {{format}} (Online/Präsenz)
- **Dauer:** ca. 45–60 Minuten (**Design-Entscheidung**, keine externe Quelle; Pre-Screening-Dauer 15–30 Min. kommt aus `prescreen-config`)

**Gesprächspartner:**
{{gespraechspartner}}

**Agenda:**
1. Vorstellung des Unternehmens (5 Min.)
2. Technische Fragen (20 Min.)
3. Kulturelles Fit (10 Min.)
4. Fragen des Kandidaten (10 Min.)

**Vorbereitung:**
Bitte bringen Sie folgende Unterlagen mit:
- Aktuellen Lebenslauf
- Zeugnisse
- Referenzen (falls vorhanden)

Für Rückfragen stehen wir Ihnen gerne zur Verfügung.

Mit freundlichen Grüßen,
HR Team
{{unternehmen}}
{{kontakt}} | {{email}}
```

### 3. E-Mail zusammenstellen

- Platzhalter ersetzen:
  - `{{kandidat_name}}` → Anna Schuster
  - `{{anredee_kandidat}}` → Frau Schuster
  - `{{stelle}}` → Senior Cloud/DevOps Engineer
  - `{{unternehmen}}` → TechVision GmbH
  - `{{datum}}` → Freitag, 15. Oktober 2026
  - `{{uhrzeit}}` → 10:00 Uhr
  - `{{format}}` → Online (Teams)
  - `{{gespraechspartner}}` → Max Mustermann (CTO)
  - `{{kontakt}}` → +49 89 1234567
  - `{{email}}` → jobs@techvision.de

### 4. E-Mail vorbereiten (Draft)

- **Empfänger:** anna.schuster@example.de
- **Betreff:** Einladung zum Vorstellungsgespräch – Senior Cloud/DevOps Engineer
- **Inhalt:** Zusammenstellter Text

### 5. Ergebnis speichern

- **Tool:** `filesystem` → `write_file`
- **Pfad:** `~/mimo-agents/km-hr-agent/ergebnisse/email-draft-{{kandidat}}-{{datum}}.md`

---

## Beispiel: E-Mail an Anna Schuster

**Von:** HR Team / TechVision GmbH  
**An:** anna.schuster@example.de  
**Betreff:** Einladung zum Vorstellungsgespräch – Senior Cloud/DevOps Engineer

---

Sehr geehrte Frau Schuster,

wir freuen uns, Ihnen unser Interesse an Ihrer Bewerbung mitteilen zu können.

Nach der Prüfung Ihres Lebenslaufs haben wir festgestellt, dass Ihre Qualifikationen hervorragend zu unserer Position als Senior Cloud/DevOps Engineer bei TechVision GmbH passen.

**Wir laden Sie herzlich ein zum:**

- **Datum:** Freitag, 15. Oktober 2026
- **Uhrzeit:** 10:00 Uhr
- **Format:** Online (Teams)
- **Dauer:** ca. 45–60 Minuten (**Design-Entscheidung**, keine externe Quelle; Pre-Screening-Dauer 15–30 Min. kommt aus `prescreen-config`)

**Gesprächspartner:**
Max Mustermann (CTO)

**Agenda:**
1. Vorstellung des Unternehmens (5 Min.)
2. Technische Fragen (20 Min.)
3. Kulturelles Fit (10 Min.)
4. Fragen des Kandidaten (10 Min.)

**Vorbereitung:**
Bitte bringen Sie folgende Unterlagen mit:
- Aktuellen Lebenslauf
- Zeugnisse
- Referenzen (falls vorhanden)

Für Rückfragen stehen wir Ihnen gerne zur Verfügung.

Mit freundlichen Grüßen,
HR Team
TechVision GmbH
+49 89 1234567 | jobs@techvision.de
