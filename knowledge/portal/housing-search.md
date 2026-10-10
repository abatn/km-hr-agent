# Wohnungssuche – Spec (Phase D, Punkt 6)

> **Stand:** 24.09.2026 · **Status:** **Code implementiert** (Templates + `_wohnung_txt` in `onboarding_release`, User-GO 24.09.2026; E2E siehe `ergebnisse/entscheidungen.md`) — **kein DB-Schema**
> **Gegenstück:** `knowledge/templates/onboarding-templates/` · `knowledge/system/agent-automation.md` · `knowledge/portal/candidate-portal-fields.md`
> **Recherche-Report:** `ergebnisse/phase-d-p6-wohnungssuche.md`

---

## 1. Zweck + Bipperz-Abgleich (Punkt 6)

**Zweck:** Neu zugezogene Arbeitnehmer (Fokus DE, Hinweise auch für CH/FR) brauchen nach der Einstellung eine rechtlich saubere, kostenfreie Orientierung bei der Wohnungssuche. Dieser Spec definiert **nur** (a) einen Checklisten-/Quellen-Abschnitt im Onboarding-Report, (b) die beteiligten Datenfelder und (c) welche externen Quellen der Agent nutzen darf. **Kein** automatisiertes Anzeigens-Scraping, keine bezahlten Dienste.

**Schritt-0-Befund (eigener grep, 24.09.2026):** `wohnung|unterkunft|accommodation|immo` in `knowledge/`, `skills/`, `webui/` → **exakt 1 Treffer**, und zwar `knowledge/language-tests.md` (EN-B2-087, Sprachtest-Frage „look for a flat" – kein Feature). `skills/` und `webui/` = **0 Treffer**. Wohnungssuche ist im gesamten Code-/Skill-Bestand also **neu**.

**Bipperz-Abgleich (Punkt 6):** In `ergebnisse/bipperz-konkurrenz-analyse.md` existiert **kein** „Punkt 6 = Wohnungssuche" (0 Treffer für `Wohnung` dort). Punkt 6 der Tabelle „Vorteile KM-HR-Agent" (`ergebnisse/bipperz-konkurrenz-analyse.md`) lautet „Lokal, keine Cloud-Abhängigkeit". Der einzige thematische Anknüpfungspunkt ist der offene Bipperz-Vorteil **DE-TN-Spezialisierung** (`ergebnisse/bipperz-konkurrenz-analyse.md`, Fazit) – Wohnungssuche bei Zuzug fällt unter diese Nische. **Kennzeichnung: Design-Entscheidung** (keine externe Quelle, die Wohnungssuche als Bipperz-Punkt 6 belegt).

---

## 2. Nutzerreihenfolge (Schritt-für-Schritt)

**Hauptnutzer: CANDIDATE** (Voraussetzung: Status `eingestellt`, Freigabe-Bericht vorhanden):

1. HR klickt `→ eingestellt` (Variante A) → Runner-Task `onboarding_release` erzeugt Freigabe-Report `ergebnisse/onboarding-freigabe-bewerbung-{app_id}.md` (`scripts/agent-runner.py` (gemessen 10.10.2026)).
2. Der Report enthält künftig einen Abschnitt **„🏠 Wohnungssuche (Checkliste + freie Quellen)"** – nach dem Muster des Visum-Abschnitts (`scripts/agent-runner.py` (gemessen 10.10.2026)).
3. Kandidat öffnet Tab **Onboarding** im Candidate Portal (`webui/pages/candidate.py` (gemessen 10.10.2026)) und liest den Report (bestehender Glob-Mechanismus, unverändert).
4. Kandidat arbeitet die Checkliste ab: Zielstadt + Einzugstermin festlegen → Bewerbungsmappe (Selbstauskunft, SCHUFA, Einkommensnachweise) → Mietpreis-Range via Open-Data-Mietspiegel prüfen → freie Info-Quellen (BMWSB-Ratgeber, Handbook Germany) nutzen → Angebote **manuell** auf Portalen (Browser, kein API-Zugriff) ansehen.
5. **HR-Lesicht** (`webui/pages/employer.py` `_page_onboarding`, Code-Abgleich 24.09.2026): Employer-Onboarding zeigt Kandidaten-Karte + Status-Timeline + Mentoring-Section, **rendert aber den Freigabe-Report nicht** – den Report-Inhalt sieht HR als Task-Ergebnis (`onboarding_release`, Agent-Details) bzw. in der Datei `ergebnisse/onboarding-freigabe-bewerbung-{app_id}.md`. **Kein** agent-seitiges Einladen/Absagen (Variant-A-Guard gilt weiter). *(Korrektur der früheren Spec-Zeile „sieht denselben Report im Employer-Onboarding" – MD an Code angeglichen, Lab-Prinzip 3.)*

**Nebennutzer: EMPLOYER/HR** – nur Lese-/Haken-Function im bestehenden Onboarding-Report. **Kein** neuer Tab, **keine** Statusänderung ausgelöst.

---

## 3. Datenfelder

> ⚠️ Nur Spec-Liste – **kein DB-Schema in dieser Phase** (Hausregel: STOP vor Code).

| Feld | Typ | Pflicht? | DSGVO-sensibel? |
|---|---|---|---|
| `zielstadt` | Text | ja | nein (Ortsangabe, keine Adresse) |
| `ziel_region` | Text | nein | nein |
| `einzugstermin` | Datum | nein | nein |
| `budget_kaltmiete_eur` | Zahl | nein | **ja** (finanzielle Angabe, bei Kandidaten-Verknüpfung personenbezogen) |
| `wohnungsart` | Auswahl (WG / 1-Zimmer / Wohnung / Haus) | ja | nein |
| `zimmer_anzahl` | Zahl | nein | nein |
| `wbs_bedarf` | Checkbox | nein | indirekt ja (WBS setzt Einkommensnachweis voraus) |
| `wohnadresse_zukunft` | Text | nein | **ja** (Zukunfts-Wohnadresse = Stammdaten i.S.d. `knowledge/legal/gdpr-policy.md`) |
| `kandidat_id` | Zahl (FK, intern) | ja | **ja** (Verknüpfung mit Person) |
| `quellen_links` | Liste (MD-Output, agent-generiert) | ja (Ausgabe) | nein (Öffentlich-Links) |
| `checkliste_erledigt` | Checkbox-Liste (MD, keine DB) | nein | nein |

**Speicherregel (Design-Entscheidung):** Die Felder leben **nur im MD-Report** (`onboarding-freigabe-*.md`). Kein INSERT in `candidates`/`applications`. `wohnadresse_zukunft` darf gar nicht erst erhoben werden, solange kein spezifizierter Speicherzweck existiert (Datenminimierung, `knowledge/legal/document-types.md`).

---

## 4. Quellen-Connector-Vorschlag (kostenlos, mit Rechtscheck-Status)

**Empfohlener Connector: `fetch` + `anysearch` (beide bereits in `opencode.json`, kostenlos, getestet)** – reine Info-Weitergabe per Link/Zusammenfassung. **Kein** neuer MCP-Server, **kein** bezahlter Dienst.

| Quelle | Typ | Rechtscheck-Status | Nutzung im Feature |
|---|---|---|---|
| BMWSB-Ratgeber „Auf Wohnungssuche in Deutschland" (PDF, DE/EN, Bundesregierung) | Öffentliche Info | ✅ **frei** (kostenlos, Regierungsbroschüre) | Link + Kern-Tipps zitieren |
| Handbook Germany (`handbookgermany.de`, 9 Sprachen inkl. AR/FR) | Öffentliche Info | ✅ **frei** (kostenlos, mehrsprachig) | Linkliste, v. a. für tunesischen Hintergrund |
| Statistikportal.de / Destatis **Open Data** (GENESIS-API, CSV/Excel, Mikrozensus Wohnen, Mietspiegel-Makrodaten) | Offene API / Open Data | ✅ **frei** (ausgewiesenes Open Data-Angebot) | Mietpreis-Range als Kontextwert |
| Kommunale Wohnungsamt-/Beratungsseiten (z.B. Integreat LK München, Willkommenszentrum Berlin) | Öffentliche Info | ✅ **frei** (Behördenseiten) | Stadt-bezogene Linkliste |
| `inberlinwohnen.de` Wohnungsfinder (landeseigene Gesellschaften) | Öffentliches Portal | ✅ **frei zum Aufruf**, aber **kein öffentliches API belegt** → nur Link/manuelles Suchen | Link, kein Datenabruf |
| Bundesimmobilien „Wohnungsfürsorge" (`bundesimmobilien.de`) | Eingeschränkt | ⚠️ **eingeschränkt** – Account „meine BImA" + Nutzungsbedingungen, nur Bundesbedienstete | nicht vorgesehen |
| ImmoScout24 (`immobilienscout24.de`) | Kommerziell-Portal | ❌ **untersagt**: Verbraucher-AGB §8.3 – „Eine automatisierte Abfrage durch Skripte, Bots, Crawler o.ä. … sind nicht gestattet" | nur **Link** an Kandidaten (Browser-Nutzung durch den Menschen) |
| Kleinanzeigen / eBay Kleinanzeigen | Kommerziell-Portal | ❌ **untersagt**: Nutzungsbedingungen – Crawler/Spider/Scraper ohne ausdrückliche schriftliche Zustimmung | nur Link |
| wg-gesucht.de | Kommerziell-Portal | ⚠️ **ToS-klären**: AGB §7 (Stand 10/2025) – „Eine Vervielfältigung der Angebote … nur mit vorheriger Zustimmung gestattet"; Bot-Captcha aktiv | nur Link, **keine** Vervielfältigung |
| immowelt.de | Kommerziell-Portal | ⚠️ **ToS-klären**: robots.txt mit Disallows; Scraping-Klausel in AGB nicht belegt | nur Link |
| Drittanbieter-Scraper-APIs (z.B. Apify, kleinanzeigen-agent.de) | Bezahlt | ❌ **ausgeschlossen** (Hausregel: keine bezahlten Dienste; zudem ToS-Widerspruch der Portalbetreiber) | nicht nutzbar |

**Ergebnis:** Es existiert **kein frei nutzbares öffentliches Listing-API** für konkrete Wohnungangebote (belegt: ImmoScout24/IS24-Partnerzugang kommerziell, BImA nur für Bundesbedienstete, keine kommunale bundesweite API gefunden). Feature = **Info-Orchestrierung (Links + Checkliste + Mietpreis-Kontext aus Open Data)**, keine Angebotsdatenbeschaffung.

---

## 5. Anbindung an den Onboarding-Report

Bestehende Muster (unverändert, nur um einen Abschnitt ergänzt):

- **Checklisten-Vorlagen:** `knowledge/templates/onboarding-templates/onboarding-de.md` („Checkliste HR" – **7 Punkte inkl. Wohnungs-Punkt**, umgesetzt 24.09.2026) · gleichauf `onboarding-fr.md` / `onboarding-ch.md` · Default-Ersatz `knowledge/onboarding-default.md`.
- **Runner-Handler:** `scripts/agent-runner.py` (Codemarke `def send_onboarding_mail`, gemessen 10.10.2026) (`task_type == "onboarding_release"`) schreibt `ergebnisse/onboarding-freigabe-bewerbung-{app_id}.md`  und sendet Mail #6 (`send_onboarding_mail`, Aufruf).
- **Abschnitt-Muster:** Visum-Block `_visum_txt` (`scripts/agent-runner.py` (gemessen 10.10.2026)) zeigt exakt die gewünschte Struktur (WAS/WIE/WO + Quellen) – der **Wohnungs-Abschnitt wird analog** als reine MD-Zeichenkette angehängt (kein neuer Task-Typ, keine DB).
- **Sichtbarkeit Candidate:** Tab Onboarding `webui/pages/candidate.py` (gemessen 10.10.2026) globbt `onboarding-freigabe-bewerbung-*.md` (Parität-Beleg: `ergebnisse/entscheidungen.md`).
- **Sichtbarkeit HR:** `webui/pages/employer.py` `_page_onboarding` (`PAGE_MAP`, Function) – Karte/Timeline/Mentoring, **kein** Report-Render (siehe §2.5).

**Umsetzungsreihenfolge (Code-Go 24.09.2026, umgesetzt):** (1) ✅ MD-Templates um Checklistenpunkt „Wohnungssuche" ergänzt → (2) ✅ `_visum_txt`-Analog (`_wohnung_txt`) in `agent-runner.py` → (3) E2E (Portal-Klicks, siehe `ergebnisse/entscheidungen.md`-Nachtrag).

---

## 6. DSGVO-Notiz

- **Wohnadresse = personenbezogenes Datum** der Kategorie „Stammdaten … Adresse" mit Speicherdauer 6 Monate (`knowledge/legal/gdpr-policy.md`). Rechtsgrundlage im Bewerbungskontext Art. 6 Abs. 1 b (`knowledge/legal/gdpr-policy.md`).
- **Datenminimierung:** nur erheben, was zweckgebunden ist – „keine Volltext-/Nummern-Speicherung"-Prinzip analog `knowledge/legal/document-types.md`, Kategorie-Zuordnung.
- **Betroffenenrechte** (Auskunft/Berichtigung/Löschung) gelten für alle gespeicherten Adressangaben (`knowledge/legal/gdpr-policy.md`); Löschpflicht nach 6 Monaten technisch via `dsgvo_cleanup()` (`knowledge/legal/gdpr-policy.md`).
- **Portal-Daten (Wohnungsangebote)** sind **keine** Daten des Kandidaten und werden **nicht** gespeichert – es werden nur öffentliche Links weitergegeben. Bei Dritt-Portalen (ImmoScout24 & Co.) gilt deren eigene Datenschutzerklärung für die dortige Nutzung durch den Kandidaten selbst.
- **Design-Entscheidung:** Kein Art.-9-Sonderdaten-Flag für Adresse (Art. 9 ist in `gdpr-policy.md` nicht einschlägig gelistet) – trotzdem als **sensibel behandeln**, weil Wohnungssuche + Budget Rückschlüsse auf Lebenssituation zulassen.

---

## 7. Verweise auf bestehende Muster

| Muster | Beweis (Datei:Zeile) | Bezug |
|---|---|---|
| Candidate-Portal `_TAB_MAP` (7 Tabs, Stand 02.10.2026; `dashboard` erster, `onboarding` letzter Eintrag; Upload/Dokumente in 👤 Mein Profil) | `_TAB_MAP` (`webui/pages/candidate.py`, Stand 02.10.2026) | Anzeige-Ort ohne neuen Tab |
| Employer `PAGE_MAP` (11 Seiten, `onboarding`) | `webui/pages/employer.py` (Codemarke `PAGE_MAP`, gemessen 10.10.2026) (onboarding) | HR-Lesicht |
| Candidate-Portal-Fielder-Doku (NiceGUI-Referenz) | `knowledge/portal/candidate-portal-fields.md` | Parität-Nachweis der 7 Tabs |
| Onboarding-Checkliste (DE) | `knowledge/templates/onboarding-templates/onboarding-de.md` | einzufügender Checklistenpunkt |
| Freigabe-Report + Visum-Abschnitt | `scripts/agent-runner.py` (gemessen 10.10.2026) | Muster für Wohnungs-Abschnitt |
| Variant-A-Guard (HR-Klick Pflicht) | `scripts/agent-runner.py` (gemessen 10.10.2026) | kein agent-seitiges Handeln |
| Bipperz-Analyse (offener DE-TN-Punkt) | `ergebnisse/bipperz-konkurrenz-analyse.md` | thematische Verortung |
| DSGVO Stammdaten | `knowledge/legal/gdpr-policy.md` | Adresse = 6 Monate |
