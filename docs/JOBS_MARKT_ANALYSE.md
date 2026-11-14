# Marktanalyse Job-Akquise (DE / FR / CH) – vier Zielbranchen

**Stand:** 13.11.2026 · **Auftrag:** Prüfen, ob die E-Mail-Akquise für
Arbeitgeber in Pflege, LKW, Handwerk und Hotellerie/Gastronomie funktioniert.
**Methode:** Bestehende Docs/Code im Repo gelesen, echte Empfänger- und
Versanddaten ausgewertet, Marktrecherche im Web (Quellen unten, Abruf 13.11.2026).
**Keine erfundenen Zahlen.** Was nicht belegt ist, steht als *(ungeprüft)*.

---

## 1. Wie der aktuelle Prozess funktioniert (Stand aus Docs & Code)

| Schritt | Umsetzung | Quelle im Repo |
|---|---|---|
| Suche | BA-Jobsuche (DE), Job-Room/SECO (CH), EURES, LHR, Journal des Palaces (FR); France-Travail-API ohne Abo | `knowledge/system/jobs-agent.md`, `jobs/ABSCHLUSSBERICHT.md` |
| Filter | `suitability()` (Visum/Anerkennung/Sprache), Aggregator-Filter | `scripts/jobs_agent.py` |
| Beleg | Screenshot + HTML-Snapshot + Wayback-Versuch pro Stelle | `jobs/belege/*/index.md` |
| Empfänger | Nur veröffentlichte Adressen (Seitentext/Impressum), Kontaktsperre pro Firma+Anzeige | `scripts/jobs_recipients.py`, `jobs/ansprache.jsonl` |
| Text | 3 Sprachvorlagen, Betreff „… – kostenlose, unverbindliche Listung“ | `jobs/vorlagen/mail_de.md`, `mail_fr.md`, `mail_en.md` |
| Versand | `scripts/jobs_mail.py` über `mcp-email-server.py` (Mailtrap-SMTP), täglich 08:05 per Timer, Limit 40, Ruhezeit 8–20 Uhr | `scripts/jobs_mail.py`, `jobs/CRON.md` |
| CTA | „Antworten Sie auf diese E-Mail oder nutzen Sie unser Kontaktformular: /kontakt“ | `jobs/vorlagen/mail_de.md` |

**Absender-Konfiguration (`.env-email`, lokal gelesen):**
`KM-HR-Agent <no-reply@hanibal-ai.com>` über `live.smtp.mailtrap.io:587`,
`Reply-To: batniniabdelkader@yahoo.com`.

---

## 2. Wie der DE/FR/CH-Arbeitsmarkt für die Zielbranchen funktioniert

### 2.1 Deutschland

**Lage (Quellen 13.11.2026):**
- ca. **487.000 unbesetzte Stellen**, in der Pflege durchschnittlich **286 Tage Vakanzzeit**
  (personalvermittlungplus.de, „Fachkräftemangel 2026“).
- **369.516 fehlende Fachkräfte**, 157 Engpassberufe laut KOFA
  (candidate-flow.de, 20.10.2026).
- **163+ offizielle Engpassberufe** für die EU-Blauen Karte 2025/26
  (jobbatical.com) – u. a. Pflege, Handwerk.
- Die Bundesagentur bestätigt: Engpassberufe-Quote bleibt hoch, **Einwanderung
  wird immer wichtiger** (arbeitsagentur.de, Pressemitteilung 2026-32).

**Kanäle, die Arbeitgeber dort tatsächlich nutzen:**
| Kanal | Kosten | Rolle |
|---|---|---|
| Bundesagentur für Arbeit (Jobbörse) | **kostenlos** | Standardkanal, zusätzlich Vermittlung über Arbeitgeber-Service/Fachkräfteservice |
| Indeed, LinkedIn | kostenlos (Basis) /ponsored | Reichweite, laut Jobbörse-Vergleich 2026 Testsieger aus Arbeitgebersicht „Jobware“, kostenlose Anzeigen u. a. Indeed, LinkedIn, BA (onapply.de, hire.workwise.io) |
| EURES | kostenlos | EU-weite Ausschreibung, insb. für grenzüberschreitende Suche |
| Personaldienstleister (Zeitarbeit/Vermittlung) | Provision/Zeit | sehr verbreitet, besonders in Pflege |
| Verbände/Kammern, Messen, Empfehlung | variabel | Vertrauenskanäle (Handwerkskammer, IHK, DPK, Hotellerieverbände) |

**Pain Points der Arbeitgeber:** offene Stellen über Monate, Anerkennung
ausländischer Abschlüsse, Sprachniveau B1/B2, hohe Fluktuation, teure
Vermittlungsprovisionen, Betreuungsaufwand bei Visum/Relocation.

### 2.2 Frankreich

- France Travail: **2,3 Mio. Rekrutierungsprojekte 2026**, −6,5 % ggü. 2025
  (vie-publique.fr, 29.04.2026).
- **43,8 % der geplanten Einstellungen gelten als schwer besetzbar** (BMO 2026,
  France Travail); bei qualifizierten Fertigungsberufen bis 80,6 %.
- **65.000 unbesetzte Saisonstellen 2026**, Schwerpunkt Hotellerie-Restauration
  (faire-le-pont.fr, 25.01.2026).

**Kanäle:** France Travail (kostenlose Anzeige), Intérim-Agenturen (sehr stark
in Frankreich), OPCO/Fondations, Mission locale, Fachverbände (UMIH,
Métiers de bouche), direkte Karriereseiten, LinkedIn.

**Pain Points:** Personalengpass in Gesundheit/Handwerk/Tourismus,
Bürokratie bei ausländischen Profilen, Sprache (Französisch-Niveau),
Saisonalität.

### 2.3 Schweiz

- Quoten 2026: maximal **8.500 Drittstaaten-Fachkräfte** und **3.000 L-Permits
  für EU/EFTA** unverändert (vischer.com, fragomen.com, admin.ch – Stand 05.12.2025/04.06.2026).
- **Vorrangregelung:** EU/EFTA-Bewerber gehen vor; Drittstaaten brauchen
  Nachweis, dass kein EU/EFTA-Kandidat verfügbar ist, plus Quote/Kanton.
- Das bedeutet für Nordafrika-Kandidaten: **ohne klaren Permit-Pfad ist das
  Angebot für CH-Arbeitgeber praktisch nicht verwendbar** (Anwerbung läuft
  über Kanton/SECO, nicht über eine „Listung“).

**Kanäle:** Job-Room/SECO (kostenlos), jobup.ch, Swissstaffing (Interims-
verband), kantonale Wirtschaftsdienste, Firmen-Karriereseiten, Mundpropaganda.

**Pain Points:** Vorrangregelung/Quote, Wohnraum, Lohnnebenkosten,
Anerkennung beruflicher Qualifikationen (SECO/BK), Sprache (DE/FR/IT).

### 2.4 Branchenspezifisch

| Branche | typische Rekrutierung | Besonderheit für unser Angebot |
|---|---|---|
| **Pflege** | BA, Vermittler, Anerkennungsverfahren (Pflegefachkraft mit Gleichwertigkeit), Ausbildung | größter Bedarf, aber Anerkennung + Sprache = 2 Hürden; Arbeitgeber brauchen **vorbereitete** Kandidaten, keine Listung |
| **LKW** | Firmenwebsite, BA, Speditionen-Verbände, Zeitarbeit | C1/CCE-Führerschein + Geltungszeit; kaum über generische Mail erreichbar |
| **Handwerk** | IHK/HWK-Netzwerk, Ausbildungsbetriebe, Mundpropaganda | sehr lokal, Vertrauen über Kammer/Meister |
| **Hotellerie/Gastronomie** | Saisonagenturen, Intérim, Direktbewerbung, Messen | hohe Fluktuation, Saisonalität; Luxushotels (unsere FR-Empfänger) arbeiten mit festen Agenturen |

---

## 3. Funktioniert die aktuelle E-Mail-Strategie (Kaltakquise)?

### 3.1 Rechtliche Lage (Kern des Problems)

- **DE:** Werbliche E-Mail an Unternehmen **ohne vorherige Einwilligung ist
  unzulässig** (UWG § 7). Mehrere aktuelle Quellen bestätigen das für 2025/2026
  (lexware.de 24.07.2026, phocus-direct.de 10.09.2025, revexa.io 27.09.2026).
  Auch Kaltakquise per Telefon ist in DE seit der UWG-Novelle 2022 nur noch mit
  (mutmaßlicher) Einwilligung zulässig – Quellenlage hier uneinheitlich
  *(ungeprüft, vor Nutzung klären)*.
- **FR:** Kaltakquise per E-Mail an **berufliche** Adressen ist unter
  Voraussetzungen zulässig (Opt-out-Pflicht, Art. L.34-5 CPCE) – unser
  `Désabonner`-Hinweis erfüllt den Opt-out-Teil; Identität und Absender müssen
  klar erkennbar sein.
- **CH:** UWG-Einschränkungen ähnlich; Einzelversand an Unternehmen ist enger
  als Massenversand.
- **Konsequenz:** Der Kanal ist in DE der riskanteste der drei – genau dort
  liegen 18 unserer 36 Empfänger.

### 3.2 Praxis der B2B-Leadgenerierung im DACH-Raum 2026

- **LinkedIn ist die wichtigste Quelle für B2B-Kontaktdaten (58 %)**, danach
  Events und persönliche Empfehlungen; 41 % der Unternehmen bevorzugen
  persönlichen Austausch im Lead Engagement (ZHAW-Studie Lead Management
  2023/24, 385 Unternehmen DE/CH).
- Kanäle werden 2026 nach **Cost-per-SQL** sortiert eingesetzt; E-Mail-Kaltakquise
  gilt in DACH als der rechtlich und kulturell schwierigste Kanal
  (hakan-ersu.de 04.02.2026, quotaengine.com 03.09.2026, carpantier-consulting.de 16.01.2026).
- **Antwortraten von Kalt-Mails im DACH-B2B liegen üblicherweise im
  einstelligen Prozentbereich** *(Benchmark-Aussagen einzelner Anbieter,
  keine unabhängige Studie – als grobe Größenordnung lesen, nicht als Zahl
  verwenden)*.

**Fazit:** Kaltmail ist der Kanal mit den größten rechtlichen und
Zustellbarkeits-Hürden – und genau der wird aktuell als einziger genutzt.

### 3.3 Treffen die E-Mails den tatsächlichen Bedarf?

**Nein – drei Befunde aus den echten Daten:**

1. **Das Angebot ist „kostenlose Listung“** (Betreff + Vorlage). Arbeitgeber
   haben kostenlos bereits: BA, Indeed, LinkedIn, EURES, Job-Room. Was ihnen
   fehlt, sind **vorausgewählte, anerkannte, sprachfähige Kandidaten** – das
   verspricht die Mail nicht, weil die Plattform es (noch) nicht liefern kann.
   Der lokale Pool: **16 Kandidaten, 5 Arbeitgeber, 6 Stellen**
   (`data/feedback.local.db`, read-only, 13.11.2026); Produktion: 6 Kandidaten
   (Sichtung 12.11.2026). Eine „Listung“ auf einer Plattform mit 6 Kandidaten
   ist für den Arbeitgeber ohne Wert.
2. **Die Zielgruppe passt nicht:** Von 36 Empfängern sind **14 Personal-/
   Vermittlungsfirmen** (ARWA ×3, JobImpulse ×2, Permacon ×2, PerZukunft,
   Personaltaucher, CarePeople, AllcuraMed, persona service ×2 …) – das sind
   **Abnehmer von Kandidaten und Konkurrenten**, keine End-Arbeitgeber, die
   „ihre Anzeige kostenlos listen“ lassen wollen. 28/36 sind Pflege,
   nur **1/36 LKW**, obwohl LKW eine Zielbranche ist.
3. **Der CTA führt in eine Sackgasse:** „Kontaktformular: /kontakt“ ist eine
   **statische Rechtsseite ohne Formular** (`webui/pages/legal.py` rendert
   `knowledge/legal/kontakt.md`); sie zeigt eine Yahoo-Adresse und eine
   tunesische Telefonnummer. Antworten gehen per `Reply-To` an dieselbe
   Yahoo-Adresse – ob die gelesen wird, ist **nicht eingerichtet/messbar**
   (siehe Ursachen U0).

---

## 4. Bessere Kanäle (Übersicht, keine Umsetzung)

| Kanal | Für wen | Warum besser | Aufwand |
|---|---|---|---|
| **BA-Fachkräfteservice / Arbeitgeber-Service** (DE) | End-Arbeitgeber Pflege/Handwerk | kostenlos, offiziell, bereits etablierte internationale Vermittlung; Vertrauen statt Kaltmail | Partnerschaft/Antrag |
| **EURES-Partnerschaft** | DE/FR/CH grenzüberschreitend | offizieller EU-Kanal, Arbeitgeber aktiv auf Such-Modus | mittel |
| **Personaldienstleister als Kunde** | ARWA, JobImpulse, persona service … | sie **kaufen** Kandidaten, kein „kostenloses Listing“ nötig; unser bestehender Empfänger-Pool ist genau das | niedrig (Angebot ändern) |
| **Verbände/Kammern/Messen** | Handwerk (HWK/IHK), Pflege (DPK/Verbände), Hotellerie (UMIH/HOGA) | Vertrauen, Empfehlung, Zugang zu vielen Betrieben einmalig | mittel |
| **LinkedIn (warm)** | HR/Inhaber von End-Arbeitgebern | dominanter B2B-Kontaktkanal (58 %), kein UWG-Problem, Sichtbarkeit | mittel |
| **Inbound (Content/SEO)** | alle | Bewerber- und Arbeitgeber-Seite zieht Anfragen selbst an; keine Rechtsproblematik | hoch, aber dauerhaft |
| **Kaltmail** | – | in DE rechtswidrig ohne Einwilligung, Zustellbarkeit unbewiesen | – |

---

## 5. Quellen (Abruf 13.11.2026)

- Fachkräftemangel DE: personalvermittlungplus.de/fachkraeftemangel-2026/,
  candidate-flow.de/blog/fachkraeftemangel/ (20.10.2026),
  arbeitsagentur.de (Presse 2026-32), jobbatical.com (EU Blue Card 2025/26),
  mediendienst-integration.de, verdi.de (09.09.2026)
- Jobbörsen/DE: onapply.de/funktion/beste-jobboerse, hire.workwise.io,
  arbeitsagentur.de/faktor-a/mitarbeiter-finden/welche-jobboerse-ist-die-richtige
- FR: vie-publique.fr/en-bref/303023 (29.04.2026), statistiques.francetravail.org (BMO 2026),
  faire-le-pont.fr (25.01.2026), ep-advisory.com
- CH: vischer.com/insights/quotas-for-foreigners-in-switzerland-in-2026 (11.12.2025),
  fragomen.com (20.11.2025), admin.ch (05.12.2025), legal500.com (04.06.2026)
- Recht DE: lexware.de/kaltakquise (24.07.2026), phocus-direct.de (10.09.2025),
  revexa.io (27.09.2026), ihk.de/koeln (Kaltakquise)
- B2B-Kanäle: hakan-ersu.de (04.02.2026), settix.de, quotaengine.com (03.09.2026),
  carpantier-consulting.de (16.10.2026), ZHAW Lead-Management-Studie 2023/24
- Repo-Daten: `jobs/empfaenger_final.csv` (36 Zeilen), `jobs/ansprache.jsonl`,
  `jobs/vorlagen/`, `knowledge/system/jobs-agent.md`, `jobs/ABSCHLUSSBERICHT.md`,
  `.env-email` (nur Schlüssel/Werte gelesen, kein Passwort), DNS-Abfrage
  `hanibal-ai.com` (SPF/DMARC/MX, 13.11.2026)
