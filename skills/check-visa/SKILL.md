---
description: Visum-, Arbeitserlaubnis- und Anerkennungs-Check für internationale Kandidaten (DE/FR/CH)
---

## Funktionierende MCP-Connectors

| Connector | Tool | Zweck |
|---|---|---|
| `filesystem` | `read_text_file` | Knowledge-Dateien (visa-rules.md, compliance-rules.md) + Kandidatenprofile lesen |
| `filesystem` | `write_file` | Visa-Prüfungsbericht nach `ergebnisse/` schreiben |
| `ansvar-german-law` | `search`, `validate_citation`, `get_provision` | 🇩🇪 DE: AufenthG (§ 4, § 18a/b, § 19c, § 20), BeschV, BA/EAS Anerkennung, ZAB |
| `ansvar-french-law` | `search`, `validate_citation`, `get_provision` | 🇫🇷 FR: Code de l'entrée et du séjour (Titre de séjour, autorisation de travail), CEE |
| `ansvar-swiss-law` | `search`, `validate_citation`, `get_provision` | 🇨🇭 CH: AuG/AIG (Bewilligungen, Kontingente), ArG, BQK |

**Länder-Routing (wie Skill 3️⃣ check-compliance):** Das Zielland wird im Schritt 1 erkannt und bestimmt den Law-Connector: 🇩🇪 → `ansvar-german-law` · 🇫🇷 → `ansvar-french-law` · 🇨🇭 → `ansvar-swiss-law`.

**Hinweis:** Lab-Prinzip – kein eigener Code. Der Skill definiert NUR Workflow, Regeln und Rechtsgrundlagen.
Die Ausführung erfolgt durch den Runner-Agenten (**direkte NVIDIA-API + MCP-Connectors**, Stand 13.09.2026 – `opencode run` wird nicht mehr verwendet) analog zu `check-compliance`. **✅ Live getestet 13.09.2026** (Task #50, nemotron-120b): tunesischer IT-Systemadmin → Visum ERFORDERLICH, Blue Card möglich, Anerkennung freiwillig — Bericht: `ergebnisse/check_visa-kandidat-7-2026-09-13.md`.

**Zugriff (v4.5, `knowledge/system/access-control.md`):** Visa-Check ist eine **Agent-Spezialität** (wie 1️⃣–5️⃣):
Sie läuft über opencode + MCP-Connectors und ist im Portal für CANDIDATE/EMPLOYER/GAST **unsichtbar**.
HR/EMPLOYER sieht nur das **Ergebnis** (read-only Badge: „Visa ✅/⚠️/❌").
Im UI gibt es **keinen** Visa-Check-Button – die Auslösung erfolgt als Agent-Task
(`check_visa` in der `agent_tasks`-Queue), z. B. automatisch nach Bewerbung oder auf HR-Anforderung.

---

## Schritte

### 1. Länderkennung + Kandidatenstatus

**Eingabe:** Kandidatenprofil (`profil-{name}.md`) + Stellenprofil (`stellenprofil-{name}.txt`)

**Vorgehen:**
- Erkenne anhand von Kandidatenprofil und Stellenprofil das/die relevanten Länder
- **DE:** Stelle in Deutschland oder Kandidat mit DE-Bezug
- **FR:** Stelle in Frankreich oder Kandidat mit FR-Bezug
- **CH:** Stelle in der Schweiz oder Kandidat mit CH-Bezug
- **Mehrere Länder:** Für jedes Land separate Prüfung (meist DE als Hauptland)

**Kandidatenstatus prüfen:**
- EU-Bürger? → Kein Visum nötig, nur Arbeitsgenehmigung
- Nicht-EU-Bürger? → Visum + Arbeitserlaubnis nötig
- Staatsangehörigkeit aus `knowledge/legal/visa-rules.md` Tabelle 1 ableiten

### 2. Rechtsgrundlagen einlesen

**Connector:** `filesystem` → `read_text_file`
**Pfad:** `knowledge/legal/visa-rules.md`

**Für jedes erkannte Land:**
- 🇩🇪 `ansvar-german-law`: AufenthG § 4 (Aufenthaltszwecke), § 18a (Fachkräfte), § 18b (Hochqualifizierte/Blue Card), § 19c (Selbständige), § 20 (Forscher), BeschV (Mangelberufe)
- 🇫🇷 `ansvar-french-law`: Code de l'entrée et du séjour (Article L311-1 bis L313-27), autorisation de travail, carte compétence et talents
- 🇨🇭 `ansvar-swiss-law`: AuG Art. 10 (Voraussetzungen), Art. 11 (Bewilligungspflicht), Art. 12 (Kontingente), ArG (Arbeitsbewilligung)

### 3. Visum-Check (Landesspezifisch)

**Für DE (häufigster Fall):**

| Prüfpunkt | Gesetz | Tool |
|---|---|---|
| Braucht der Kandidat ein Visum? | AufenthG § 4 + § 6 | `search("AufenthG § 4 Aufenthaltszweck")` |
| Welcher Aufenthaltszweck? | AufenthG § 18a/b/19c/20 | `search("AufenthG 18a")` |
| Arbeitsgenehmigung nötig? | BeschV § 1 | `search("BeschV")` |
| Blue Card möglich? | AufenthG § 18b | `search("AufenthG 18b")` |
| Anerkennung nötig? | BA/EAS § 2 | `search("Anerkennung ausländischer Berufsabschlüsse")` |
| Mangelberuf? | BeschV Anlage 1 | `search("BeschV Mangelberufe")` |

**Für FR:**

| Prüfpunkt | Gesetz | Tool |
|---|---|---|
| Titre de séjour nötig? | CESEDA Art. L311-1 | `search("CESEDA titre séjour")` |
| Autorisation de travail? | CESEDA Art. L521-1 | `search("autorisation travail étranger")` |
| Compétences et talents? | CESEDA Art. L313-20 | `search("carte compétences talents")` |

**Für CH:**

| Prüfpunkt | Gesetz | Tool |
|---|---|---|
| Bewilligungspflicht? | AIG Art. 10 | `search("Bewilligung Ausländer Schweiz")` |
| Kontingent vorhanden? | AIG Art. 12 | `search("Kontingent Ausländer Schweiz")` |
| Arbeitsbewilligung nötig? | ArG Art. 4 | `search("ArG Arbeitsbewilligung Ausländer")` |

### 4. Anerkennungs-Check

**Prüfpunkt:** Muss der Kandidat seinen Abschluss anerkennen lassen?

**Für DE:**
- Reglementierte Berufe (Ärzte, Ingenieure, Lehrer): Anerkennungspflichtig nach AnerkG § 1 (Umsetzung der EU-BQRF)
- IT-Berufe: In der Regel Anerkennungsfrei, aber EQR-Einordnung empfohlen
- `search("AnerkNUNGSGESETZ")`

**Für FR:**
- Enseignement, santé, ingénieurs: Anerkennung durch zuständige Stelle
- `search("reconnaissance diplôme étranger France")`

**Für CH:**
- Reglementierte Berufe: Anerkennung durch kantonale Behörden
- `search("Anerkennung ausländischer Diplome Schweiz")`

### 5. Ergebnis speichern

**Bericht:** `ergebnisse/check-visa-kandidat-{N}-{datum}.md`

**Struktur (4 Abschnitte):**
```markdown
# Visa-/Anerkennungs-Check – Kandidat #{N}

**Datum:** YYYY-MM-DD
**Ziel-Land:** DE/FR/CH
**Kandidatenstatus:** EU/Nicht-EU
**Aufenthaltszweck:** §18a Fachkraft / §18b Blue Card / ...
**Blue-Card-Option:** ja/nein (Gehalt der Stelle vs. Schwelle)
**Anerkennung:** nötig/freiwillig (je Berufsgruppe)
**Timeline:** Gesamtprozess X–Y Monate

## Prüftabelle (nur Rechts-Zeilen)

| Prüfpunkt | Ergebnis | Rechtsgrundlage |
|---|---|---|
| Visumspflicht | JA/NEIN | AufenthG § 4 |
| Aufenthaltszweck | [typ] | AufenthG § 18a/b/... |
| Arbeitsgenehmigung/ZAV | JA/NEIN + Details | BeschV § 1 / §39 AufenthG |
| Blue Card möglich? | JA/NEIN + Gehalt prüfen | AufenthG § 18b |
| Anerkennung nötig? | ja/nein (Pflicht/freiwillig) | AnerkG § 1 |

## Nächste Schritte — Kandidat

1. [konkreter Schritt, z.B. Deutschkurs B2]
2. [konkreter Schritt, z.B. Job-Angebot sichern]
3. [konkreter Schritt, z.B. Visum bei Botschaft beantragen]
...

## Nächste Schritte — HR/Arbeitgeber

1. [konkreter Schritt, z.B. ZAV-Zustimmung beantragen]
2. [konkreter Schritt, z.B. Arbeitsvertrag mit Mindestgehalt vorbereiten]
3. [konkreter Schritt, z.B. Timeline 3–6 Monate einplanen]
...
```

---

## Regeln

1. **Kein automatisches „Visum ja/nein"-Urteil** – nur Rechtsgrundlagen; finale Beurteilung durch HR/Arbeitgeber
2. **Datenminimierung:** nur Staatsangehörigkeit + Berufsabschluss + Zielland im Bericht, keine Passdaten
3. **Unklar = ⚠️** – bei unklarem Status: „MANUELLE PRÜFUNG EMPFOHLEN" + Behörden-Hinweis
4. **Rollen:** Ausführung nur Agent-Ebene; Ergebnis-Sicht nur HR/EMPLOYER (Pseudonym „Kandidat #N")
5. **Berichtspfad-Schema:** `ergebnisse/check-visa-kandidat-{N}-{YYYY-MM-DD}.md`
6. **DSGVO:** Keine Speicherung von Passnummern oder biometrischen Daten
