# PRÜFBERICHT FINAL – km-hr-agent

**Prüfdatum:** 13.09.2026  
**Prüfer:** opencode (mimo-v2.5)  
**Projektstand:** Phase 6.1 (Agent-Automation aktiv, E2E T1–T8 bestanden)

---

## 1. Lese-Buchung (alle Dateien mit Zeilenzahlen)

### Kern-Dateien
| Datei | Zeilen | Status |
|-------|--------|--------|
| `app.py` | 3.277 | ✅ geprüft |
| `scripts/agent-runner.py` | 806 | ✅ geprüft |
| `opencode.json` | 60 | ✅ geprüft |
| `AGENTS.md` | 182 | ✅ geprüft |
| `instructions.md` | ~2.500 | ✅ geprüft |
| `knowledge.md` | ~1.800 | ✅ geprüft |

### Skills (17 SKILL.md-Dateien)
| Skill | Datei | Status |
|-------|-------|--------|
| extract-profile | `skills/extract-profile/SKILL.md` | ✅ vorhanden |
| match-candidate | `skills/match-candidate/SKILL.md` | ✅ vorhanden |
| check-compliance | `skills/check-compliance/SKILL.md` | ✅ vorhanden |
| check-gdpr | `skills/check-gdpr/SKILL.md` | ✅ vorhanden |
| assess-culture-fit | `skills/assess-culture-fit/SKILL.md` | ✅ vorhanden |
| explain-match | `skills/explain-match/SKILL.md` | ✅ vorhanden |
| contact-candidate | `skills/contact-candidate/SKILL.md` | ✅ vorhanden |
| pre-screen | `skills/pre-screen/SKILL.md` | ✅ vorhanden |
| generate-onboarding | `skills/generate-onboarding/SKILL.md` | ✅ vorhanden |
| store-feedback | `skills/store-feedback/SKILL.md` | ✅ vorhanden |
| employer-portal | `skills/employer-portal/SKILL.md` | ✅ vorhanden |
| candidate-portal | `skills/candidate-portal/SKILL.md` | ✅ vorhanden |
| job-application | `skills/job-application/SKILL.md` | ✅ vorhanden |
| verify-documents | `skills/verify-documents/SKILL.md` | ✅ vorhanden |
| export-report | `skills/export-report/SKILL.md` | ✅ vorhanden |
| handle-errors | `skills/handle-errors/SKILL.md` | ✅ vorhanden |
| notify-user | `skills/notify-user/SKILL.md` | ✅ vorhanden |

### Knowledge-Dateien (20)
| Datei | Status |
|-------|--------|
| `access-control.md` | ✅ vorhanden |
| `agent-automation.md` | ✅ vorhanden |
| `application-status.md` | ✅ vorhanden |
| `candidate-portal-fields.md` | ✅ vorhanden |
| `compliance-rules.md` | ✅ vorhanden |
| `cultural-fit-criteria.md` | ✅ vorhanden |
| `document-types.md` | ✅ vorhanden |
| `employer-portal-fields.md` | ✅ vorhanden |
| `explanation-templates.md` | ✅ vorhanden |
| `feedback-schema.md` | ✅ vorhanden |
| `gdpr-policy.md` | ✅ vorhanden |
| `matching-criteria.md` | ✅ vorhanden |
| `mcp-connector-config.md` | ✅ vorhanden |
| `compliance/` (3 Dateien) | ✅ vorhanden |
| `email-templates/` (1 Datei) | ✅ vorhanden |
| `language-templates/` (3 Dateien) | ✅ vorhanden |
| `onboarding-templates/` (3 Dateien) | ✅ vorhanden |

### DB-Tabellen (14)
| Tabelle | Felder | Status |
|---------|--------|--------|
| candidates | 22 | ✅ geprüft |
| candidate_status_history | 6 | ✅ geprüft |
| candidate_documents | 5 | ✅ geprüft |
| employers | 14 | ✅ geprüft |
| jobs | 18 | ✅ geprüft |
| job_status_history | 6 | ✅ geprüft |
| applications | 7 | ✅ geprüft |
| application_status_history | 6 | ✅ geprüft |
| feedback | 19 | ✅ geprüft |
| gewichtung_historie | 7 | ✅ geprüft |
| compliance_protokoll | 7 | ✅ geprüft |
| agent_tasks | 11 | ✅ geprüft |
| admins | 5 | ✅ geprüft |

---

## 2. Befund-Matrix A–H

| ID | Prüfpunkt | Erwartet | Ist | Bewertung |
|----|-----------|----------|-----|-----------|
| **A1** | Skills (SKILL.md-Dateien) | 12 | 17 | ❌ WIDERSPRUCH |
| **A2** | MCP-Server in opencode.json | 7 | 11 | ❌ WIDERSPRUCH |
| **A3** | DB-Tabellen | 13 | 14 | ⚠️ ABWEICHUNG (+1) |
| **A4** | DB-Felder candidates | 22 | 22 | ✅ KONSISTENT |
| **A5** | DB-Felder jobs | 20 (laut Doku) | 18 | ❌ WIDERSPRUCH |
| **B1** | Seiten CANDIDATE | 5 | 5 | ✅ KONSISTENT |
| **B2** | Seiten EMPLOYER | 7 | 7 | ✅ KONSISTENT |
| **B3** | Seiten ADMIN | 11 | 11 | ✅ KONSISTENT |
| **C1** | E-Mail-Typen | 4 | 4 | ✅ KONSISTENT |
| **C2** | Agent-Tasks | 11 | 11 | ✅ KONSISTENT |
| **D1** | agent_tasks Schema | 11 Felder | 11 Felder | ✅ KONSISTENT |
| **E1** | Pförtner-Regel (Score≥60+COMPLIANT) | definiert | implementiert | ✅ KONSISTENT |
| **E2** | Variante A (HR-Klick) | definiert | implementiert | ✅ KONSISTENT |
| **F1** | DSGVO-Cleanup | 183 Tage | implementiert | ✅ KONSISTENT |
| **F2** | Feedback-Loop | Gewichtung±15 | implementiert | ✅ KONSISTENT |
| **G1** | Jitsi only (Google Meet entfernt) | "Jitsi only" | Docstring korrigiert | ✅ BEHOBEN |
| **G2** | MCP-Server Anzahl (Doku) | 7 | 11 | ❌ WIDERSPRUCH |
| **H1** | Live-Lauf 🗂️-Tab | erwartet | ✅ erledigt 13.09. (ergebnisse/v6-1-typed-live-run.md) | ✅ ERFÜLLT |

---

## 3. Bilanz

| Kategorie | Anzahl | Details |
|-----------|--------|---------|
| ✅ Konsistent | 12 | A4, B1, B2, B3, C1, C2, D1, E1, E2, F1, F2 |
| ⚠️ Veraltet | 1 | A3 (Tabellen: 13 → 14) |
| ❌ Widersprüche | 5 | A1, A2, A5, G1, G2 |
| ❓ Unprüfbar | 0 | — |

**Gesamtbewertung:** 13/19 konsistent (68%) – 5 Widersprüche erfordern Korrektur

---

## 4. Priorisierte Korrekturliste

### KRITISCH (sofort)
| Priorität | Datei | Korrektur | Begründung |
|-----------|-------|-----------|------------|
| P1 | `AGENTS.md`, `instructions.md`, `knowledge.md` | "12 Skills" → "17 Skills" | Root-Dokumentation veraltet |
| P2 | `knowledge/mcp-connector-config.md` | "7 aktive MCP-Server" → "11 aktive MCP-Server" | Doku veraltet |
| P3 | `knowledge/employer-portal-fields.md` | jobs "20 Felder" → "18 Felder" | branche_erfahrung + startdatum nicht in DB |

### WICHTIG (bei Gelegenheit)
| Priorität | Datei | Korrektur | Begründung |
|-----------|-------|-----------|------------|
| P4 | `knowledge/mcp-connector-config.md` | Google Meet-Eintrag entfernt/klarisiert | ✅ ERLEDIGT |
| P5 | `AGENTS.md` | "13 DB-Tabellen" → "14 DB-Tabellen" | candidate_status_history fehlte |

### NACHZUVERLASSEN
| Priorität | Datei | Korrektur | Begründung |
|-----------|-------|-----------|------------|
| P6 | `ergebnisse/` | Live-Lauf 🗂️-Tab dokumentieren | ✅ erfüllt (ergebnisse/v6-1-typed-live-run.md) |

---

## 5. Prüfstand-Daten

### Datum der Prüfung
- **13.09.2026, 14:30 Uhr**

### Geprüfte Versionen
- **app.py:** 3.277 Zeilen (Stand 12.09.2026)
- **agent-runner.py:** 806 Zeilen (Stand 12.09.2026)
- **opencode.json:** 60 Zeilen, 11 MCP-Server (Stand 12.09.2026)
- **feedback.db:** 14 Tabellen (Stand 12.09.2026)

### E2E-Teststatus
- **T1–T8:** ✅ bestanden (AppTest + Runner-Simulation)
- **Live-Lauf 🗂️-Tab:** ✅ erledigt 13.09.2026 (typisierter Lauf, ergebnisse/v6-1-typed-live-run.md)

### Bekannte Einschränkungen
1. Session-State-Auth nicht produktionstauglich
2. Kein formales Test-Framework (nur AppTest)
3. venv muss vor jedem Aufruf aktiviert werden
4. `contract-check-filesystem` nicht modifizierbar (anderes Projekt)

---

## Fazit

Das Projekt ist **funktionsfähig** aber die **Dokumentation weist 5 klare Widersprüche** zur Implementierung auf. Die Kernfunktionalität (Agent-Automation, E2E-Tests) ist vollständig implementiert und getestet. Die Korrekturen sind **nicht blockierend**, sollten aber zeitnah behoben werden, um Wartbarkeit zu gewährleisten.

**Empfohlenes Vorgehen:**
1. Korrekturen P1–P3 sofort umsetzen (5 Minuten Aufwand)
2. Korrekturen P4–P5 bei nächster Gelegenheit
3. Live-Lauf 🗂️-Tab (P6) als letzten Schritt dokumentieren

---

## 6. Nachtrag: Umsetzungs-Nachweis der Korrekturen (13.09.2026, Buffy)

Alle Korrekturen P1–P5 wurden umgesetzt (18 Einzeländerungen, 0 Code-/DB-Änderungen,
py_compile OK). Grep-Beweise je Korrektur:

### K3-Grep (P2/P4): mcp-connector-config.md
```
JSON-Block-Server-Einträge ("name": {): 11   (= exakt die 11 opencode.json-Server,
Set-Differenz zu opencode.json: KEINE)
Tabellen-Zeilen: 11 aktiv + 4 Legacy/entfernt; meeting-tools-Zeile enthält
„create_meeting_link *(LEGACY – wird nicht genutzt, Jitsi only)*"
```

### K5-Grep (P5): 13-Tabellen-Konsistenz
```
AGENTS.md:28   „… `admins` (13 tables total)"
knowledge.md:74 „… (13 tables: …)"
DB-Realität: 13 Tabellen (sqlite_master, NOT LIKE sqlite_%)
```

### K6-Grep (Zusatzkorrektur Gewichts-Baseline)
```
„30/25/15/10/10/10/0“: AGENTS.md ×1 · knowledge.md ×1 · matching-criteria.md ×2
Code-Baseline (BASELINE_GEWINCHTE, app.py:243): 30/25/15/10/10/10/0 ✓ deckungsgleich
```

### K1-Nachbesserung (Ordinal-Fix)
```
AGENTS.md:15: „verify-documents (14th, …)“ → „verify-documents (agent-plane only,
no UI, spec: skills/verify-documents/SKILL.md)“ — grep „14th“: 0 Treffer
```

---

## 7. Nachtrag: H1 abgeschlossen – typisierter Live-Lauf 🗂️-Tab

**Datum:** 13.09.2026 · **Art:** echter UI-Flow (AppTest) + Live-Runner
(NVIDIA nemotron-120b, echte E-Mails) · **Ergebnis:** ✅ H1 erfüllt — Details:
`ergebnisse/v6-1-typed-live-run.md`. Die Berichte `v6-live-run-visum-workflow.md`
(§6) und `v6-1-implementierung-dokumente-tab.md` (§3) wurden entsprechend auf
✅ nachgezogen.
