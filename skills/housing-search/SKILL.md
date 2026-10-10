---
description: Wohnungssuche-Checkliste + freie Quellen für Zuzug (Onboarding-Report-Abschnitt, kein Scraping, kein neuer Tab)
---

## Funktionierende MCP-Connectors

| Connector | Tool | Zweck |
|---|---|---|
| `filesystem` | `read_text_file` | Spec `knowledge/portal/housing-search.md`, Onboarding-Templates, Kandidatenprofil lesen |
| `filesystem` | `write_file` | Wohnungssuche-Abschnitt in Freigabe-Report ergänzen (analog `_visum_txt`) |
| `fetch` | `fetch` | Freie Info-Quellen verifizieren (BMWSB, Handbook Germany, kommunale Seiten) |
| `anysearch` | `search` | Aktuelle Stadt-/Behörden-Links recherchieren (Link-Liste, **kein** Listing-Scraping) |

**Hinweis (Spec §4):** Feature = **Info-Orchestrierung** (Links + Checkliste + Mietpreis-Kontext aus Open Data). **Kein** neuer MCP-Server, **kein** bezahlter Dienst, **kein** automatisiertes Anzeigens-Scraping. ImmoScout24/Kleinanzeigen: ToS untersagt Crawler → nur Link an Kandidaten (Browser-Nutzung durch den Menschen).

**Externe Quellen (Spec §4, Recherche 24.09.2026):** 8 frei (BMWSB-Ratgeber, Handbook Germany 9 Sprachen, Statistikportal Open Data, kommunale Wohnungsämter, inberlinwohnen.de als Link) · 1 eingeschränkt (Bundesimmobilien, Account) · 4 ToS-klären/untersagt (ImmoScout24, Kleinanzeigen ❌; wg-gesucht/immowelt ⚠️ nur Link) · **0 freie Listing-APIs** → alle Portal-Links = Design-Entscheidung „manuelle Suche durch Kandidaten".

**Status:** **Code implementiert** 24.09.2026 (User-GO): Checklistenpunkt in 4 Templates + `_wohnung_txt` in `onboarding_release` (`scripts/agent-runner.py` (gemessen 10.10.2026)) · **kein DB-Schema**.

---

## Zugriff (v4.5, Zwei-Ebenen-Modell)

| Rolle | Zugriff |
|---|---|
| **CANDIDATE** | ✅ Wohnungssuche-Abschnitt im bestehenden Onboarding-Tab lesen, Checkliste abarbeiten, freie Quellen manuell öffnen |
| **EMPLOYER (HR)** | ✅ Denselben Report im Employer-Onboarding lesen, erledigte Punkte bestätigen (Haken) – **kein** agent-seitiges Einladen/Absagen |
| **ADMIN** | ✅ alle Funktionen |
| **Agent-Ebene** | ✅ Abschnitt in Freigabe-Report schreiben (deterministisch, nach `onboarding_release`), freie Quellen verifizieren/linken – **niemals** Angebote scrapen, nie selbst Mietverträge/-anfragen stellen (Variante A) |

**Anzeige-Ort (Spec §5):** Kein eigener Tab für Housing. Candidate `_TAB_MAP` hat Stand 02.10.2026 **7 Tabs** (📊 Dashboard als 1. Tab; Upload/Dokumente in 👤 Mein Profil, Codemarke `_TAB_MAP`), Employer `PAGE_MAP` bleibt 11 Seiten (Codemarke `PAGE_MAP`, Stand 01.10.2026).

---

## Trigger

- **Auslösung:** HR-Klick `→ eingestellt` (Variante A) → Runner-Task `onboarding_release` (`scripts/agent-runner.py` (gemessen 10.10.2026)) erzeugt Freigabe-Report `ergebnisse/onboarding-freigabe-bewerbung-{app_id}.md`.
- **Abschnitt-Insert:** analog Visum-Block `_visum_txt` (`scripts/agent-runner.py` (gemessen 10.10.2026)) und Mentor-Block `_mentor_txt` (`scripts/agent-runner.py` (gemessen 10.10.2026)) – Wohnungs-Abschnitt als weitere MD-Zeichenkette, **kein** neuer Task-Typ, keine DB.
- **Umgesetzt (24.09.2026, User-GO):** Wohnungs-Abschnitt `_wohnung_txt` (`scripts/agent-runner.py` (gemessen 10.10.2026)), Einfügepunkt nach `_mentor_txt` / vor Report-Write .

---

## Schritte (Umsetzungsreihenfolge, Code-Go 24.09.2026 — umgesetzt)

### 1. ✅ Checklistenpunkt in Templates ergänzt

**Bestehende Muster (unverändert, +1 Punkt):**
- `knowledge/templates/onboarding-templates/onboarding-de.md` (Checkliste HR, **7 Punkte inkl. Wohnungs-Punkt**)
- gleichauf `knowledge/templates/onboarding-templates/onboarding-fr.md` / `knowledge/templates/onboarding-templates/onboarding-ch.md`
- Default-Ersatz `knowledge/onboarding-default.md`

**Eingefügter Punkt (Design-Entscheidung, Wortlaut Spec §2):**
```
- [ ] Wohnungssuche: Zielstadt + Einzugstermin, Bewerbungsmappe (Selbstauskunft, SCHUFA, Einkommensnachweise), Mietpreis-Range prüfen
```
(Hinweis: Der NiceGUI-Generator `webui/components.py` (gemessen 10.10.2026) baut seine MD hardcoded — die Templates sind die dokumentierte Quelle für den Agent-Skill `generate-onboarding`, nicht der UI-Pfad.)

### 2. ✅ Wohnungs-Abschnitt im Freigabe-Report (analog `_visum_txt`)

**Muster:** `scripts/agent-runner.py` (gemessen 10.10.2026) (`onboarding_release` Handler)

```
## 🏠 Wohnungssuche (Checkliste + freie Quellen)

- **Zielstadt/Einzugstermin:** [aus Kandidatenprofil/HR, falls vorhanden]
- **Checkliste:** Bewerbungsmappe → Mietpreis-Range (Open Data) → freie Quellen → Angebote manuell prüfen
- **Freie Quellen:** BMWSB-Ratgeber · Handbook Germany · Statistikportal Open Data · kommunale Wohnungsämter
- **Portale (nur Link, manuell):** ImmoScout24 · Kleinanzeigen · wg-gesucht · immowelt
- Der Agent sucht keine Angebote und stellt keine Mietanfragen.
```

**Einfügepunkt (umgesetzt):** nach `_mentor_txt` / vor Report-Write (`scripts/agent-runner.py` (gemessen 10.10.2026)).

### 3. ✅ Sichtbarkeit (bestehende Mechanismen, unverändert)

- **Candidate:** Tab Onboarding `webui/pages/candidate.py` (gemessen 10.10.2026) globbt `onboarding-freigabe-bewerbung-*.md` (Parität `ergebnisse/entscheidungen.md`).
- **HR:** Employer-Onboarding `webui/pages/employer.py` (Codemarke `def _page_onboarding`, gemessen 10.10.2026) (`_page_onboarding`), Generator + Kandidaten-Status + Mentoring-Section bereits da.

### 4. ✅ E2E (24.09.2026 PASS, `tests/e2e_housing.py`)

Portal-Klick-Test: HR-Klick „Einstellen" (`/employer/match`) → Task `onboarding_release` (#186) → Report `onboarding-freigabe-bewerbung-27.md` enthält Wohnungs-Abschnitt → Candidate-Tab Onboarding zeigt Abschnitt → Employer-Onboarding-Karte sichtbar. Log: `/tmp/e2e_housing_run.log`.

---

## Datenfelder (Spec §3 – MD-only, **kein** DB-Schema)

| Feld | Typ | DSGVO-sensibel? |
|---|---|---|
| `zielstadt` | Text | nein |
| `ziel_region` | Text | nein |
| `einzugstermin` | Datum | nein |
| `budget_kaltmiete_eur` | Zahl | **ja** |
| `wohnungsart` | Auswahl | nein |
| `zimmer_anzahl` | Zahl | nein |
| `wbs_bedarf` | Checkbox | indirekt ja |
| `wohnadresse_zukunft` | Text | **ja** (nicht erheben ohne Speicherzweck) |
| `kandidat_id` | FK intern | **ja** |
| `quellen_links` | MD-Liste | nein |
| `checkliste_erledigt` | MD-Checkboxen | nein |

**Speicherregel:** Felder **nur im MD-Report**, kein INSERT in `candidates`/`applications` (Datenminimierung, `knowledge/legal/document-types.md`).

---

## Regeln

1. **Kein Scraping:** ImmoScout24/Kleinanzeigen ToS ❌ untersagt; wg-gesucht/immowelt ⚠️ nur Link, keine Vervielfältigung; Drittanbieter-Scraper ausgeschlossen (bezahlter Dienst + ToS-Widerspruch).
2. **Kein Listing-API-Annahme:** Spec belegt **0 freie Listing-APIs** – Feature bleibt Info-Orchestrierung.
3. **Human-in-the-loop (Variante A):** Agent stellt nie Mietanfragen, nie Bewerbungen auf Portalen, nie Verträge – nur Checkliste + Links.
4. **DSGVO:** `wohnadresse_zukunft`/`budget_kaltmiete_eur` nur wenn zweckgebunden; Adresse = Stammdaten 6 Monate (`knowledge/legal/gdpr-policy.md`); Portal-Angebote werden **nicht** gespeichert.
5. **Design-Entscheidung kennzeichnen:** Checklisten-Wortlaut, Quellen-Auswahl, Einfügepunkt = Design (Spec §4/§5), keine externe Programm-Struktur-Quelle.
6. **Code nur nach User-GO:** Code-Go 24.09.2026 erteilt und umgesetzt (Templates + Runner + MD-Status); weitere Änderungen (z.B. Mail-#6-Hinweis) erneut nur nach GO.

---

## Integration mit anderen Skills

| Skill | Verbindung |
|---|---|
| `generate-onboarding` | Checklistenpunkt + Report-Abschnitt sind Konsum-Punkt (Onboarding-Generator `components.py`, Freigabe-Report) |
| `notify-user` (Mail #6) | `send_onboarding_mail` `scripts/agent-runner.py` (Codemarke `def send_onboarding_mail`, gemessen 10.10.2026) – optionaler Wohnungs-Hinweis in Willkommens-Mail **nicht** umgesetzt (nicht im Code-Go, optional) |
| `export-report` | Freigabe-Report `onboarding-freigabe-bewerbung-{id}.md` = Träger des Abschnitts |
| `check-visa` | Visa-Block `_visum_txt` als Struktur-Muster; Reihenfolge: Visum → Wohnung → Behörden (Spec relocation) |
| `relocation` (Spec, Skill offen) | Wohnung = Voraussetzung für Bürgeramt-Anmeldung (`knowledge/lifecycle/relocation.md` Schritt 2); **P6-Option C (User-GO 25.09.2026):** der Relocation-/Behörden-Abschnitt liegt seitdem **im selben Freigabe-Report** – `_relocation_txt` (`scripts/agent-runner.py` (Codemarke `def _relocation_txt`, gemessen 10.10.2026)), aufgerufen im `onboarding_release`-Zweig (`scripts/agent-runner.py` (Codemarke `def _relocation_txt`, gemessen 10.10.2026)), Nur-Text aus Spec §2/§5/§6. Damit ist die Reihenfolge Visum → Wohnung → Behörden im Report vollständig; der Skill `relocation` selbst bleibt offen (Zählwerk: 23 Skills unverändert, kein neuer Skill; Knowledge-MD 43 Stand 25.09.2026 nach +5 Phase-E-B1-Specs) |
| `employer-portal` | HR-Lesicht: Onboarding-Karte/Timeline (`webui/pages/employer.py` (gemessen 10.10.2026)) – Report-Render dort **nein**; Report-Inhalt via Agent-Details/Datei (Spec §2.5, MD-Korrektur 24.09.2026) |
| `candidate-portal` | Anzeige im bestehenden Onboarding-Tab (kein 9. Tab) |
| `check-gdpr` | Adress-/Budget-Felder an Löschfristen koppeln |

---

**Stand:** 24.09.2026 – MD-Round (doku-first) + **Code-Go umgesetzt** (Templates 4×, `_wohnung_txt` in `scripts/agent-runner.py` (gemessen 10.10.2026)), E2E-Lauf + Ergebnis-Nachtrag in `ergebnisse/entscheidungen.md`. Quellen: `knowledge/portal/housing-search.md` (Spec §1-§7), `ergebnisse/phase-d-p6-wohnungssuche.md` (Schritt-0: 1 feature-irrelevanter Treffer, 8 freie Quellen), `ergebnisse/entscheidungen.md` (Go-Liste); Bipperz Punkt 6 = „Lokal, keine Cloud" (kein expliziter Wohnungssuche-Punkt) → Design-Entscheidung.
