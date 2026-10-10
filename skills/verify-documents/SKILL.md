---
description: Dokumenten-Verifizierung – Zeugnisse, Zertifikate, Pass/Visa-Dokumente extrahieren und auf Echtheit/Plausibilität prüfen
---

## Funktionierende MCP-Connectors

| Connector | Tool | Zweck |
|---|---|---|
| `pdf-reader` | `read_pdf_text` | Text aus PDF-Dokumenten extrahieren (Zeugnis, Zertifikat, Pass, Visa) |
| `filesystem` | `read_text_file` | Knowledge-Dateien (document-types.md, compliance-rules) + TXT-Dokumente lesen |
| `filesystem` | `write_file` | Verifizierungs-Bericht nach `ergebnisse/` schreiben |
| `ansvar-german-law` | `search`, `validate_citation`, `get_provision` | Rechtsrahmen 🇩🇪 DE (AufenthG § 18a/b, BeschV, AGG, BDSG § 26, DSGVO Art. 5/6) |
| `ansvar-french-law` | `search`, `validate_citation`, `get_provision` | Rechtsrahmen 🇫🇷 FR (Code de l'entrée et du séjour des étrangers, Code du travail, RGPD) |
| `ansvar-swiss-law` | `search`, `validate_citation`, `get_provision` | Rechtsrahmen 🇨🇭 CH (AuG/Ausländer- und Integrationsgesetz, ArG, DSG) |

**Länder-Routing (wie Skill 3️⃣ check-compliance):** Der für das Dokument relevante Land wird
im Schritt 2 erkannt und bestimmt den Law-Connector: 🇩🇪 → `ansvar-german-law` ·
🇫🇷 → `ansvar-french-law` · 🇨🇭 → `ansvar-swiss-law`. Visa-/Arbeitserlaubnis-Prüfung nutzt
IMMER den Law-Connector; reine Zeugnis-/Zertifikat-Prüfung nur bei FR/CH-Sachverhalten.

**Hinweis:** Lab-Prinzip – kein eigener Code. Der Skill definiert NUR Workflow, Regeln und Dokumenttypen.
Die Ausführung erfolgt durch den Agenten (opencode + MCP-Connectors) analog zu `check-compliance`.

**Zugriff (v4.5, `knowledge/system/access-control.md` – Zwei-Ebenen-Modell):** Verifizierung ist eine
**Agent-Spezialität** (wie 1️⃣–5️⃣): Sie läuft über opencode + MCP-Connectors und ist im Portal für
CANDIDATE/EMPLOYER/GAST **unsichtbar**. HR/EMPLOYER sieht nur das **Ergebnis** (read-only).
Im UI gibt es **keinen** Verifizierungs-Button – die Auslösung erfolgt als Agent-Task
(`verify_documents` in der `agent_tasks`-Queue, Payload `candidate_id`), z. B. automatisch nach
CV-Upload oder auf HR-Anforderung.

---

## Schritte

### 1. Dokument-Upload (Agent-Ingestion)

**Eingabe:** PDF/TXT-Datei(en) aus `testdaten/` (bereits durch 0️⃣ Upload-Ingestion gespeichert)

**Validierung:**
- Format: PDF (bevorzugt) oder TXT; sonst → Skill `handle-errors`
- Größe: max. 200 MB je Datei (Projektstandard)
- Datei liegt innerhalb `PROJECT_ROOT/testdaten/` (Pfad-Scope des Filesystem-Connectors)

### 2. Dokumenttyp- + Herkunfts-Erkennung

**Vorgehen:** Klassifikation anhand der Signatur-Merkmale aus `knowledge/legal/document-types.md`
(z. B. Schlüsselwörter, Aufbau, Pflichtfelder) – je Typ werden **Herkunft** und **Land** bestimmt:

**Herkunft (wer liefert das Dokument?):**
- **KANDIDAT:** Zeugnisse, Zertifikate, Sprachnachweise – mit der Bewerbung hochgeladen (0️⃣-Ingestion)
- **HR:** Visa-/Aufenthalts-/Arbeitserlaubnis-Dokumente – werden von HR beschafft/vorgelegt
  (Arbeitgeberpflicht) und auf der Agent-Ebene ingested; Prüfschwerpunkt: Arbeitserlaubnis
  nach Landesrecht (immer Law-Connector)

**Land (bestimmt den Law-Connector):** 🇩🇪 / 🇫🇷 / 🇨🇭 – abgeleitet aus Stelle/Kandidat (wie check-compliance Schritt 2)

| Typ | Beispiele | Pflichtfelder (Auszug) |
|---|---|---|
| Arbeitszeugnis | Zwischen-/Endzeugnis | Aussteller, Position, Zeitraum, Datum, Unterschriftszeile |
| Schul-/Studienabschluss | Bachelor/Master-Zeugnis | Institution, Abschlussgrad, Datum, Notenskala |
| Berufszertifikat | AWS, Kubernetes, ITIL … | Aussteller, Zertifikats-ID, Gültigkeit |
| Sprachzertifikat | Goethe, telc, TOEFL | Niveau (GER A1–C2), Prüfungsdatum |
| Pass | Reisepass (nur relevante Angaben) | Staatsangehörigkeit, Gültigkeit – **KEINE Volltextspeicherung sensibler Daten** |
| Visum / Aufenthaltstitel | Aufenthaltserlaubnis, Arbeitserlaubnis | Typ, Gültigkeit, Arbeitserlaubnis-Flag |

Unbekannter Typ → Ergebnis `UNBEKANNT` + Handle-errors-Meldung (kein Abbruch).

### 3. Textextraktion (pdf-reader)

- `pdf-reader.read_pdf_text` auf die Datei
- Extrahierten Text **kürzen**: nur extrahierte Merkmale (Felder oben) in den Bericht –
  keine Kopie des ganzen Dokuments (Datenminimierung, DSGVO Art. 5 Abs. 1 c)
- Bei leeren/verschlüsselten PDFs → Status `UNLESBAR`, handle-errors

### 4. Echtheits-/Plausibilitätsprüfung

⚠️ **Wichtig (EU AI Act + Sorgfaltspflicht):** Der Agent liefert eine **Indizienprüfung**,
keinen behördlichen Echtheitsnachweis. Ergebnis-Skala: `PLAUSIBEL` / `AUFFAELLIG` / `UNBEKANNT`.

**4a. Forensik-Pre-Scan (MCP-subprocess, kein LLM) — seit 16.09.2026:**

Vor der LLM-Prüfung wird das PDF technisch geprüft:
```
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"evaluate_policy","arguments":{"file_path":"<PDF_PFAD>","response_format":"markdown"}}}' | npx @shuji-bonji/pdf-verify-mcp
```

| Tool | Was es liefert | Output |
|---|---|---|
| `evaluate_policy` | Trust-Verdict (4-Wert-Skala) | `trust_and_use` / `use_with_caution` / `human_review_required` / `reject` |
| `verify_integrity` | Revisions-Anzahl, Incremental Updates | Anzahl Revisionen, ob Objekte hinzugefügt wurden |
| `verify_signatur` | Kryptografische Signatur-Verifizierung | `valid` / `invalid` / `indeterminate` (Ist-Code ruft nur `evaluate_policy` + `verify_integrity` auf, s. `scripts/agent-runner.py` (gemessen 10.10.2026) ⓘ09.10.2026) |

**Ergebnis:** Trust-Verdict wird als zusätzliche Variable in den LLM-Prompt übergeben.
`use_with_caution` (kein Signatur) → LLM weiß: " technische Echtheitsprüfung nicht möglich".
`reject` → LLM wird angewiesen, Status `AUFFAELLIG` zu setzen.

**4b. LLM-Indizienprüfung (bestehend):**

**Geprüfte Indizien (je Dokumenttyp, Details: `knowledge/legal/document-types.md`):**
- **Pflichtfelder vollständig?** (fehlend → AUFFAELLIG)
- **Datumslogik:** Ausstellungsdatum ≤ heute; Zeitraum im Zeugnis widerspruchsfrei; Gültigkeit (Pass/Visa/Zertifikat) noch offen?
- **Konsistenz zum Kandidatenprofil:** Name, Position, Zeitraum gegen `profil-{kandidat}.md` abgleichen (Abweichung → AUFFAELLIG)
- **Sprach-/Formatplausibilität:** erwartete Abschnitte/Signaturen vorhanden (Unterschriftszeile „Unterschrift", Firmenstempel-Hinweis)
- **Länder-Rechtsrahmen (Country-Routing, immer bei Visa-/Aufenthaltsdokumenten):**
  🇩🇪 `ansvar-german-law`: AufenthG (§ 4, § 18a/b, § 19c), BeschV – Arbeit ohne Work-Permit erlaubt?
  🇫🇷 `ansvar-french-law`: Code de l'entrée et du séjour (Titre de séjour, autorisation de travail)
  🇨🇭 `ansvar-swiss-law`: AuG (Bewilligung, Kontingente), ArG
  Alle: DSGVO/RGPD/DSG Art. 6-Zulässigkeit der Verarbeitung (Bewerbungsverfahren)
- **Nicht prüfbar vom Agenten:** Sicherheitsmerkmale (Wasserzeichen, Hologramme, QR-Codes), Registerabgleich (Anerkennungsstellen, ZAB, amazoni-check) → Bericht markiert diese als `MANUELLE_PRIEFUNG_ERFORDERLICH`

### 5. Ergebnis speichern

- Bericht: `ergebnisse/verify_documents-kandidat-{N}-{datum}.md` (write_file; Glob im Code: `verify_documents-kandidat-{id}-*.md`, `scripts/agent-runner.py` (gemessen 10.10.2026) ⓘ09.10.2026)
- Struktur wie `check-compliance`-Berichte: Typ · extrahierte Felder · Indizien-Tabelle ·
  Gesamtstatus (`PLAUSIBEL`/`AUFFAELLIG`/`UNBEKANNT`) · manuelle Prüfpunkte · AI-Hinweis (EU AI Act Art. 50)
- **Keine** Dokumentkopien, **keine** Pass-/Visa-Nummern im Bericht (nur Typ + Gültigkeitsjahr)

---

## Regeln

1. **Kein automatisches „echt/falsch"-Urteil** – nur Indizien; finale Beurteilung durch HR (Mensch-in-der-Schleife, wie Variante A in `agent-automation.md`)
2. **Datenminimierung:** nur extrahierte Merkmale, keine Volltexte sensibler Ausweisdokumente
3. **Unlesbar ≠ abgelehnt:** Status `UNLESBAR`/`UNBEKANNT` führt nicht zur Ablehnung – HR entscheidet
4. **Rollen:** Ausführung nur Agent-Ebene; Ergebnis-Sicht nur HR/EMPLOYER (Pseudonym „Kandidat #N")
5. **Berichtspfad-Schema** wie alle Skills: `ergebnisse/verify_documents-kandidat-{N}-{YYYY-MM-DD}.md`
