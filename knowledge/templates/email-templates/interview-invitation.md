# E-Mail-Vorlage: Interview-Einladung

> **Hinweis (12.10.2026):** Die Vorlage ist **sprachparameterisiert**. Das MCP-Tool
> `email-sender.send_interview_invitation` baut Betreff + Body über `tr(..., language)`
> (`webui/i18n_core`, Katalog `webui/locales`) und akzeptiert `language`
> (`de`/`en`/`fr`/`ar`; Default `de` – fehlende/ungültige Werte → `de`).
> Die folgende Fassung ist die **`de`-Variante** (msgid = Identität); die
> Übersetzungen liefern die Kataloge. Die `{{...}}`-Platzhalter entsprechen den
> Tool-Parametern (`{{stelle}}`→`position`, `{{kandidat_email}}`→`to`, `{{datum}}`→`date`,
> `{{uhrzeit}}`→`time`, `{{unternehmen}}`→`company`).

---

**Von:** {{absender_name}} / {{unternehmen}}  
**An:** {{kandidat_email}}  
**Sprache:** {{sprache}} (de/en/fr/ar; Default de)  
**Betreff:** Einladung zum Vorstellungsgespräch – {{stelle}}

---

Sehr geehrte(r) {{anrede_kandidat}},

wir freuen uns, Ihnen unser Interesse an Ihrer Bewerbung mitteilen zu können.

Nach der Prüfung Ihres Lebenslaufs haben wir festgestellt, dass Ihre Qualifikationen hervorragend zu unserer Position als {{stelle}} bei {{unternehmen}} passen.

**Wir laden Sie herzlich ein zum:**

- **Datum:** {{datum}}
- **Uhrzeit:** {{uhrzeit}}
- **Format:** {{format}} (Online/Präsenz)
- **Dauer:** ca. 45–60 Minuten

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
{{absender_name}}
{{unternehmen}}
{{kontakt}} | {{email}}
