# Relocation: Umzug, Behörden, Anmeldung

> **Stand:** 24.09.2026
> **Typ:** MD-first-Spec (Phase D, Punkt 7) — **kein Code, kein Skill-Umfang, keine DB-Änderung**
> **Status:** Spezifikation · Umsetzung erfordert User-Go (Feature-Freeze, siehe `ergebnisse/entscheidungen.md`)
> **Verwendung:** Grundlage für einen künftigen Skill `relocation` (Agent-Ebene) + Checklisten-Ergänzung im Onboarding

---

## 1. Zweck + Bipperz-Abgleich (Punkt 7)

**Zweck:** Relocation fasst die behördenrechtlichen und organisatorischen Schritte zusammen, die auf einen **Zuzug/Umzug** eines Kandidaten folgen — getrennt vom Visums-/Aufenthaltstitel-Check (andere Behörde, andere Rechtsgrundlage):

- **check_visa** = Ausländerbehörde/Auslandsvertretung · AufenthG/AuG/CESEDA → *Darf ich arbeiten/aufhalten?*
- **relocation (diese Spec)** = Meldebehörde (Bürgeramt) · Bundesmeldegesetz (BMG) → *Wo wohne ich offiziell?* — plus die daraus abgeleiteten Folgeschritte (Steuer-ID, Krankenkasse, ELStAM)

**Bipperz-Abgleich (Punkt 7):**

| Beleg | Befund |
|---|---|
| `ergebnisse/bipperz-konkurrenz-analyse.md` | Bipperz hat laut Doku **3 Vorteile** (E-Mail, Video, DE-TN-Kultur-Matching) — **Relocation ist KEIN Bipperz-Vorteil** |
| `ergebnisse/bipperz-konkurrenz-analyse.md` | „Vorteile Bipperz (nicht im KM-HR-Agent)": 3 Zeilen, Relocation nicht enthalten → **kein Wettbewerbs-gap gegenüber Bipperz** |
| `ergebnisse/bipperz-konkurrenz-analyse.md` | Punkt **7** der Tabelle „Vorteile KM-HR-Agent": „17 Skills, 13 DB-Tabellen, DSGVO-6-Monats-Löschung" — **Zitat-Stand 13.09.2026; Abgleich 24.09.2026: 23 Skills, 16 DB-Tabellen** (Zieltext unverändert; Tabellenwert heute **17**, gemessen 21.10.2026) — relocation.md wäre ein Knowledge-/Skill-Beitrag jenseits dieser Liste |
| `ergebnisse/bipperz-konkurrenz-analyse.md` | Punkt 3 (DE-TN-Spezialisierung, ⚠️ offen): Relocation **stärkt indirekt** diesen Punkt — Nicht-EU-Kandidaten (z.B. TN) müssen exakt diese Behördenkette (Meldebehörde → Ausländerbehörde) durchlaufen |

**Lesart „Punkt 7" (Design-Entscheidung):** Der Report-Dateiname `phase-d-p7-relocation.md` positioniert diese Spec als **Phase-D-Arbeitspunkt 7**. Die Phase-D-Entscheidungstabelle (`ergebnisse/entscheidungen.md`) listet Optionen (a)–(d5) — Relocation ta dort **nicht** auf; diese Spec ist ein eigener, noch nicht entschiedener Punkt.

---

## 2. Prozessschritte (DE-Fokus, FR/CH-Hinweise)

| # | Schritt | Quelle (extern, wenn nicht anders vermerkt) |
|---|---|---|
| 1 | **Visum/Aufenthalt prüfen** — läuft bereits als `check_visa` (Skill `check-visa`): Aufenthaltstitel-Art, ZAV, Anerkennung, WAS/WIE/WO der Ausländerbehörde | Quelle im Projekt: `knowledge/legal/visa-rules.md`; Ausführung `scripts/agent-runner.py` (gemessen 10.10.2026) — **AA-Fragenkatalog (P4, Abruf 25.09.2026):** auswaertiges-amt.de Fragenkatalog Arbeitsvisum (606484) = Visum vor der Einreise, Aufenthaltstitel danach bei der Ausländerbehörde · **BA (P4, Abruf 25.09.2026):** arbeitsagentur.de Fachkräfte aus dem Ausland = BA-Zustimmung zum Arbeitsmarkt in den meisten Fällen (Reihenfolge) |
| 2 | **Wohnung suchen/beziehen** — Voraussetzung für alles Weitere; Wohnungssuche selbst **außerhalb** des Agent-Scope | **Design-Entscheidung:** Cross-Ref `knowledge/portal/housing-search.md` **existiert nicht** (glob `**/*housing*` → 0 Treffer). Spec-Ziel: eigene Wissensdatei anlegen oder Schritt als HR-/Kandidaten-Hausaufgabe deklarieren |
| 3 | **Bürgeramt-Anmeldung (Meldebehörde)** — Frist: **innerhalb von 2 Wochen nach Einzug** *(Sekundärbeleg service.berlin.de „14 Tage“; §17-BMG-Volltextwortlaut am 25.09.2026 NICHT extrahierbar = nicht belegt, P4; Quelle: recherche-plan-restpunkte-2026-09-25.md:141)*; Dokumente: Meldeschein + Personalausweis/Pass/Passersatz + **Wohnungsgeberbestätigung** (Mietvertrag ersetzt sie NICHT); Nicht-EU: Meldeanmeldung **vor** Aufenthaltstitel-Beantragung bei der Ausländerbehörde, eAT zusammen mit Nationalpass vorlegen | BMG § 17 Abs. 1 + § 23 Abs. 1 (gesetze-im-internet.de/bmg/__17.html) · service.berlin.de/dienstleistung/120686/ (14 Tage, Unterlagenliste; **Sekundär für die Frist, P4**) · bonn.de Meldegesetz-Seite (Meldevorbehalt Nicht-EU) |
| 4 | **Steuer-ID (IdNr)** — **nur nach** Schritt 3: bei Zuzug aus dem Ausland ist die Anmeldung bei der Meldebehörde **zwingende Voraussetzung** für die IdNr; lebenslang gültig (§ 139a/139b AO). HR-Checkliste sieht „Steuer-ID angefordert" bereits vor | ELSTER-Hilfe „Wie erhält der Arbeitgeber die IdNr." (elster.de) · `knowledge/onboarding-default.md` (Projekt-Template) |
| 5 | **Krankenkasse / Sozialversicherung** — Kandidat wählt GKV-Kasse; **Arbeitgeber** meldet Beschäftigung elektronisch an die Einzugsstelle (in der Regel die Krankenkasse), Frist: mit der **ersten folgenden Entgeltabrechnung, spätestens 6 Wochen** nach Beschäftigungsbeginn (Meldegrund „10") | § 28a SGB IV + DEÜV (verwaltung.bund.de Leistung 99107065104000; zoll.de Sozialversicherung) · CH-Template: `knowledge/templates/onboarding-templates/onboarding-ch.md` („Krankenkasse gemeldet") |
| 6 | **Gehaltsempfänger-Meldung (ELStAM)** — Arbeitgeber meldet Arbeitnehmer beim Betriebsstättenfinanzamt an und ruft ELStAM ab; braucht **IdNr + Geburtsdatum vom Arbeitnehmer** (§ 39e Abs. 4 S. 1 EStG); ohne IdNr → **Steuerklasse VI**, Übergang max. 3 Monate (§ 39c Abs. 1 S. 2 EStG) | BZSt „ELStAM" (bzst.de) · BMF-Merkblatt „Lohnsteuerabzug im ELStAM-Verfahren" (elster.de PDF) · ELSTER-Hilfe Arbeitgeber |

**Reihenfolge ist bindend:** 1 → 2 → **3** (Meldebehörde) → 4/5/6. Schritt 3 ist **Meldevorbehalt** für Schritt 4 (IdNr) und informiert die Anschrift des eAT (Adressaufkleber/Fortschreibung).

**FR/CH (Design-Entscheidung — gleiche Struktur, andere Behörden):** FR: Mairie (`déclaration de domicile`/CHANGEAD) → numéro fiscal → sécurité sociale/CNAV; CH: Einwohnerkontrolle/Gemeinde (Meldeausweis) → AHV-Nummer → Krankenkasse (siehe `knowledge/templates/onboarding-templates/onboarding-ch.md`). FR/CH-Details sind **nicht** recherchiert → als Design-Entscheidung gekennzeichnet, vor Umsetzung zu belegen.

---

## 3. Verantwortlichkeiten

| Schritt | Kandidat | HR | Agent |
|---|---|---|---|
| 1 Visum/Aufenthalt | Unterlagen liefern (Pass, Abschluss) | Zeitplan (3–6 Monate), ZAV-Antrag | `check_visa` ausführen, Bericht ablegen |
| 2 Wohnung | Sucht/schließt Mietvertrag | Hinweis/Checklisten-Eintrag, ggf. Umzugshilfe klären (z.B. Umzugskostenzuschuss, s. `ergebnisse/onboarding-abdelkader-batnini-2026-10-27.md`) | **keine** Wohnungssuche (außer Scope) |
| 3 Bürgeramt-Anmeldung | **Persönlich** beim Bürgeramt, Frist 14 Tage einhalten (Sekundär: service.berlin.de; §17-BMG-Volltextwortlaut nicht belegt, P4), Wohnungsgeberbestätigung vom Vermieter holen | Terminhinweis + Dokumenten-Checkliste in Onboarding | Checklisten-Punkt vorschlagen; Behörden-Infos via fetch/anysearch liefern (siehe § 5) |
| 4 Steuer-ID | IdNr bei BZSt/FA anfragen, an HR weitergeben | ELStAM-Abruf (ELSTER) | Checklisten-Punkt „Steuer-ID angefordert" (`knowledge/onboarding-default.md`) prüfen/ergänzen |
| 5 Krankenkasse | Kasse wählen, Daten an HR | SV-Anmeldung „10" via Entgeltabrechnung/Einzugsstelle | Checklisten-Punkt (DE fehlt, CH vorhanden) |
| 6 Gehaltsempfänger/ELStAM | IdNr + Geburtsdatum + Haupt-/Nebenjob mitteilen | ELStAM abrufen, in Lohnkonto übernehmen, Steuerklasse anwenden | Checklisten-Punkt; **kein** Steuerdaten-Speichern im Agenten |

**Grundsatz (Variante A, `knowledge/system/agent-automation.md`):** Der Agent **ladet, meldet und beantragt nie** etwas bei einer Behörde — nur Information, Checkliste, E-Mail-Hinweis nach HR-Freigabe.

---

## 4. Bestehende Anbindung (was schon mitspielt)

| Baustein | Datei:Zeile | Beitrag zu relocation |
|---|---|---|
| `check_visa`-Prompt (LLM-Task) | `scripts/agent-runner.py` (gemessen 10.10.2026) | Prüft Aufenthalt/ZAV/Anerkennung; regt „Nächste Schritte Kandidat/HR" an — enthält **keinen** Meldebehörden-Schritt |
| ansvar-Hybrid für `check_visa` | `scripts/agent-runner.py` | 7 DE-Queries (AufenthG/BeschV/ZAV/AnerkG) — **kein** `Bundesmeldegesetz`-Query |
| Task-Queue nach Bewerbung | `webui/db.py` (gemessen 10.10.2026) | `check_visa` = Task 7/10 der Kette |
| Visa-WO-Regel | `knowledge/system/agent-automation.md` | „WO = zuständige Behörde (**DE: Ausländerbehörde/Auslandsvertretung** · FR: Préfecture · CH: Kantonales Migrationsamt)" — Meldebehörde **nicht** enthalten |
| Visum-Schritte-Mail (nach HR-Klick) | `knowledge/system/agent-automation.md` | Variante A: Mail erst nach „Visum-Antrag bestätigen" — relocation könnte analog als **HR-Klick** modelliert werden |
| visa-rules.md HR-Tabelle | `knowledge/legal/visa-rules.md` | „Einreise + Aufenthaltserlaubnis **beim Einwohnermeldeamt**" — ⚠️ **belegte Ungenauigkeit**: Aufenthaltstitel → Ausländerbehörde, nicht Einwohnermeldeamt; als MD-Korrektur-Kandidat markiert (Lab-Prinzip 3, hier **nicht** geändert — STOP vor Änderung ohne Auftrag) |
| Matching-Erklärung | `knowledge/lifecycle/explanation-templates.md` | „Der Kandidat wohnt [X] km entfernt – **Umzug erforderlich**." = Nur-Text im Erklärungstemplate, **kein** Feature |
| generate-onboarding | `skills/generate-onboarding/SKILL.md` | Liest `onboarding-default.md`; Checkliste enthält **keinen** Umzug/Anmeldung-/Bürgeramt-Punkt (nur „Steuer-ID angefordert", `knowledge/onboarding-default.md`) |
| Onboarding-Templates DE/FR/CH | `knowledge/templates/onboarding-templates/onboarding-de.md`, `knowledge/templates/onboarding-templates/onboarding-fr.md`, `knowledge/templates/onboarding-templates/onboarding-ch.md` | DE: Steuer-ID · FR: Numéro fiscal · CH: AHV + Krankenkasse — **0×** Umzug/Bürgeramt/Anmeldung |
| check-visa-Skill | `skills/check-visa/SKILL.md` | „kantonale Behörden" (Anerkennung) / „Behörden-Hinweis" bei Unklarheit — generisch, keine Meldeanmeldung |
| ansvar-german-law (Konfiguration) | `opencode.json` (gemessen 10.10.2026) + `knowledge/system/mcp-connector-config.md` | mcp-remote `gateway.ansvar.eu/mcp`, OAuth, **6.870 DE-Gesetze**, Tools `search/validate_citation/get_provision + 28`; **BMG-Abdeckung ungeprüft** (kein Live-Aufruf laut Aufgabe) → verifizierbar via `search("Bundesmeldegesetz 17")` |
| connectors/README.md | `connectors/README.md` | Enthält **nur** die 3 HR-Connectoren — ansvar hat hier **keinen** eigenen README-Eintrag |

**Onboarding-Template-Befund (Schritt-0, exakte Zitate):** Kein Template-Element mit Umzug/Anmeldung/Bürgeramt. Nachbar-Treffer:
- `knowledge/onboarding-default.md` / `knowledge/templates/onboarding-templates/onboarding-de.md`: „- [ ] Steuer-ID angefordert"
- `knowledge/templates/onboarding-templates/onboarding-ch.md`: „- [ ] Krankenkasse gemeldet"
- `knowledge/templates/onboarding-templates/onboarding-fr.md`: „- [ ] Numéro fiscal demandé"
- Nur in **generiertem** Ergebnis (nicht Template): `ergebnisse/onboarding-abdelkader-batnini-2026-10-27.md`: „| **Umzugskostenzuschuss** | ☐ Prüfen ob anwendbar | Vor Eintritt |"

---

## 5. Lücke: was müsste NEU kommen

1. **Behörden-Infos live & kostenlos (Kernlücke):** Fristen/Öffnungen/Formulare der Bürgerämter ändern sich lokal. **Connector-Vorschlag (kein neuer MCP-Server nötig):** `fetch` + `anysearch` (beide in `opencode.json` konfiguriert; Status ✅ in `ergebnisse/bipperz-konkurrenz-analyse.md`) abfragen, Quellen: `service.de`, `service.berlin.de/dienstleistung/120686/`, `verwaltung.bund.de`, kommunale Portale (z.B. bonn.de). Output: Behörden-Kartei als `knowledge/`-MD (MD-first), **nicht** als Python.
2. **Wissensdatei/Checklisten-Ergänzung:** Abschnitt „Relocation" in `knowledge/onboarding-default.md` + die 3 Land-Templates (Punkte 3–6 aus § 2) — aktuell 0 Treffer.
3. **Skill `relocation` (Agent-Ebene):** Analog `check-visa` (Schritte, Berichtschema `ergebnisse/relocation-kandidat-{N}-{datum}.md`, DSGVO-Regeln, Variante A). **Vor** Code: User-Go (Feature-Freeze, Beleg `ergebnisse/entscheidungen.md`).
4. **ansvar-Query-Test (nur Prüfung):** `search("Bundesmeldegesetz Anmeldung 17")` gegen ansvar-german-law — ob BMG im 6.870-Gesetze-Korpus liegt (ungeprüft, Design-Annahme: ja, da Bundesgesetz).
5. **MD-Korrektur-Kandidat:** `knowledge/legal/visa-rules.md` (Einwohnermeldeamt ≠ Aufenthaltstitel-Stelle) — separate Doku-Pflege-Aufgabe.
6. **Trigger/Task:** relocation-Check analog `check_visa` (nach Bewerbung **oder** erst nach Status `eingestellt`/Onboarding-Freigabe — Reihenfolge 2→3 erst nach Vertragsabschluss sinnvoll) = **Design-Entscheidung, offen**.

---

## 6. DSGVO-Notiz (Meldeadresse sensibel)

- **Meldebestätigung/Meldeschein enthält:** vollständige Wohnanschrift, Geburtsdatum, ggf. Staatsangehörigkeit → **Stammdaten-Kategorie** laut `knowledge/legal/gdpr-policy.md` („Name, Adresse, Telefon, E-Mail | 6 Monate" Löschfrist).
- **Datenminimierung (Art. 5 Abs. 1 c DSGVO):** In Agent-Berichten (relocation-/check_visa-/verify_documents-Output) **nur Status speichern** („Meldebestätigung: ja/nein/Offen", „Wohnungsgeberbestätigung: vorliegend/ja"), **keine** Adresse, **keine** Meldeschein-Nummern, **keine** Pass-/eAT-Nummern (Vorbild: `skills/check-visa/SKILL.md`, `knowledge/legal/document-types.md`).
- **Rechtsgrundlage Bewerbung/Onboarding:** Art. 6 Abs. 1 b DSGVO (Vertragserfüllung) — nur für den **laufenden** Prozess; Zweckbindung Art. 5 Abs. 1 b (`knowledge/legal/document-types.md`).
- **Meldeadresse nie in E-Mails** (email-sender) an Dritte; Kandidaten-Hinweise enthalten nur „Adresse X Wochen nach Einzug anmelden (Frist)", nicht die Adresse selbst.
- Löschung: Stammdaten nach 6 Monaten (`knowledge/legal/gdpr-policy.md`); laufende Bewerbungsdaten über `dsgvo_cleanup()` 183 Tage (`knowledge/legal/gdpr-policy.md`).

---

**Quellenübersicht (extern):** gesetze-im-internet.de (BMG § 17/§ 23) · service.berlin.de (14-Tage-Frist, Unterlagen) · bonn.de (Meldevorbehalt Nicht-EU, eAT+Pass) · verwaltung.bund.de (SV-Meldung Frist 6 Wochen) · zoll.de (§ 28a SGB IV) · elster.de (IdNr bei Zuzug, ELStAM-Arbeitgeber) · bzst.de (ELStAM) · BMF-Merkblatt ELStAM.
**Design-Entscheidungen:** Reihenfolge/Scope-Schritte, FR/CH-Ausbaustufe, housing-search-crossref-Ziel, relocation-Trigger-Zeitpunkt, Bipperz-„Punkt 7"-Lesart.
