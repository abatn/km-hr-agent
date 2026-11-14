# Ursachenanalyse – warum keine Anfragen/Arbeitgeber-Antworten kommen

**Stand:** 13.11.2026 · **Basis:** Repo-Code, echte Versand-/Empfängerdaten,
Marktrecherche (`docs/JOBS_MARKT_ANALYSE.md`).
**Reihenfolge = Schadenshöhe.** Nicht belegbare Punkte sind als *(ungeprüft)*
markiert – es wird nichts behauptet, was nicht geprüft wurde.

---

## U0 – Wir können Antworten gar nicht messen (Fundament des Problems)

**Befund:** Es gibt **kein Monitoring eingehender Antworten**.

- `scripts/jobs_mail.py` sendet nur; es liest nichts zurück
  (Codemark `def run` – Ende nach `Gesendet: …`).
- Ein IMAP-Poller existiert ausschließlich für **Bounce-Meldungen**
  (`scripts/mail_bounce.py`, an `KMHR_BOUNCE_POLL_*`, Standard aus).
- `jobs/ABSCHLUSSBERICHT.md` sagt es offen: „Antworten: **0** (kein
  Postfach-Monitoring eingerichtet)“ und „Mailtrap Inbound ist noch nicht
  verifiziert“.
- Absender ist `no-reply@hanibal-ai.com`; `Reply-To` zeigt auf eine
  Yahoo-Adresse (`.env-email`). Ob und wie oft dort gelesen wird, steht in
  keinem Repo-Datensatz.

**Folge:** Die Aussage „es kommen keine Anfragen“ ist **nicht messbar
belegt**. Es kann sein, dass Antworten existieren und niemand sie sieht –
genau wie beim Admin-Dashboard-Fall vom 12.11. (dort fehlte die Anzeige, hier
fehlt der Empfang). **Jede weitere Maßnahme ohne Messung ist Blindflug.**

---

## U1 – Die Zustellbarkeit der Mails ist nie geprüft (höchste Wirkung, ungeprüft)

**Befund (DNS-Abfrage 13.11.2026, nur lesend):**
- `hanibal-ai.com` hat **keinen SPF-Eintrag am Apex** (`dig TXT` → leer).
- DMARC existiert: `p=quarantine; pct=100` mit Reports an Mailtrap – ein
  scheiterndes Mail landet also **im Spam-Ordner des Empfängers**, nicht im
  Posteingang.
- Kein DKIM-Record für übliche Selector gefunden (`default`, `google`,
  `mailtrap`, `s1`, `s2`, `k1`) – ein von Mailtap vergebener anderer Selector
  ist *(ungeprüft)*; über Provider-Doku prüfen.
- Versandweg: `live.smtp.mailtrap.io:587`, From `KM-HR-Agent
  <no-reply@hanibal-ai.com>`, Reply-To Yahoo (`.env-email`).
  Ein `no-reply`-From mit abweichender Reply-To-Adresse ist ein bekanntes
  Spam-Signal *(allgemeines Muster, keine Messung für uns)*.

**Folge:** Wenn SPF/DKIM nicht alignen, greift DMARC-Quarantäne → die
„Kaltakquise“ landet im Spam, ungeachtet von Inhalt und Zielgruppe. Das wäre
**die einfachste technische Erklärung für null Antworten** – und ist in 15
Minuten messbar (Mailtrap-Deliverability-Reports, Testempfänger, SPF/DKIM-Check).

---

## U2 – Das Angebot trifft den Bedarf nicht („Listung“ statt Kandidaten)

**Befund:** Betreff und Vorlage verkaufen eine **kostenlose, unverbindliche
Listung** (`jobs/vorlagen/mail_de.md`, `mail_fr.md`).

- Kostenlos listen können Arbeitgeber überall: BA, Indeed, LinkedIn, EURES,
  Job-Room (Belege in `docs/JOBS_MARKT_ANALYSE.md` §2).
- Was Arbeitgeber in Pflege/LKW/Handwerk wirklich brauchen: **vorausgewählte
  Kandidaten** mit Anerkennungs-Status, Sprachniveau, Visum-Pfad – das
  verspricht die Mail nirgends.
- Der Wert dahinter ist (noch) leer: lokale DB **16 Kandidaten / 5 Arbeitgeber /
  6 Stellen**, Produktion **6 Kandidaten** (Sichtung 12.11.2026, read-only).
  Selbst bei Interesse gäbe es für den Arbeitgeber nichts zu sehen.

**Folge:** Die Mail beantwortet eine Frage, die der Arbeitgeber nicht hat
(„Wo stelle ich meine Anzeige kostenlos ein?“) und nicht auf die, die er hat
(„Woher bekomme ich in 4 Wochen eine examinierte Pflegefachkraft mit B2?“).

---

## U3 – Die Zielgruppe ist falsch gemischt

**Befund (`jobs/empfaenger_final.csv`, 36 Zeilen, 13.11.2026 ausgewertet):**

| Kennzahl | Wert |
|---|---|
| Empfänger mit echter E-Mail | **13 von 36** (23 nur Kontaktformular/Website) |
| Davon **Personal-/Vermittlungsfirmen** | **14 von 36** (ARWA ×3, JobImpulse ×2, Permacon ×2, PerZukunft, Personaltaucher, CarePeople, AllcuraMed, persona service ×2, Steffi Richter) |
| Branche | Pflege 28 · Hotellerie 7 · **LKW 1** (Zielbranchen-Anteil LKW also ~3 %) |
| Land | DE 18 · CH 11 · FR 7 |
| Quelle | EURES 14 · Job-Room 11 · BA 4 · LHR 4 · Journal des Palaces 3 |

- **Personalvermittler sind Abnehmer von Kandidaten, keine Empfänger für
  „Ihre Anzeige kostenlos listen“** – die Ansprache ist an sie falsch
  adressiert (und potenziell unbequem: sie sehen uns als Konkurrenz).
- Kliniken/Universitätsspitäler (CH) und Caritas/AWO (DE) laufen über
  zentrale Stellenportale und Ausschreibungsverfahren – Kaltmail erreicht dort
  selten die Entscheidungsebene.
- Luxushotels (FR-Empfänger aus Journal des Palaces) arbeiten mit festen
  Saison-/Intérim-Agenturen.

**Folge:** Selbst bei Zustellung und Interesse spricht die Mail die falsche
Person an; die Empfängerzahl ist für jede Statistik viel zu klein
(13 adressierbare Mails gesamt, Einmalversand).

---

## U4 – Vertrauen/Identität reicht für einen Kaltkontakt nicht aus

**Befund (Rechtsseiten und Mail-Fuß):**
- Anbieter: **Agic Tunisie GmbH, Ben Arous/Tunesien**, Kontakt
  **`batniniabdelkader@yahoo.com`**, Telefon Tunesien/DE gemischt
  (`knowledge/legal/kontakt.md`).
- Absender-Name „KM-HR-Agent“, Domain `jobs.hanibal-ai.com` – ohne
  Referenzen, Kundenlogos, Fallbeispiele, Zahlen oder Impressum-Nachweis im
  Mail-Text (nur Links auf `/impressum`, `/datenschutz`).
- Für einen deutschen/schweizerischen HR-Verantwortlichen ist eine
  Kaltmail mit tunesischem Anbieter + Yahoo-Kontakt + „kostenlos“ **ohne
  Vorab-Bekanntheit** das klassische Spam-/Betrugsmuster – unabhängig davon,
  ob das Unternehmen seriös ist.

**Folge:** Öffnet jemand die Mail trotz Spam-Ordner, fehlt der Grund, zu
glauben, dass dahinter ein reales, nutzbares Angebot steht.

---

## U5 – Rechtsrahmen und Länder-Spezifik machen zwei Drittel des Zielmarkts schwierig

- **DE (18/36 Empfänger):** Kaltmail ohne Einwilligung ist nach UWG § 7
  unzulässig (Quellen in `docs/JOBS_MARKT_ANALYSE.md` §3.1). Risiko: nicht nur
  Unwirksamkeit, sondern auch **Abmahnung** und Spam-Beschwerden, die die
  Domain- Reputation weiter zerstören (Kopplung zu U1).
- **CH (11/36):** Drittstaaten-Kandidaten brauchen Quote + Vorrangregelung
  (8.500 Plätze 2026). Ohne Permit-Pfad im Angebot ist „Listung“ für
  Schweizer Arbeitgeber **fachlich irrelevant** – selbst bei Interesse.
- **FR (7/36):** hier ist Kaltakquise an berufliche Adressen mit Opt-out am
  ehesten zulässig; unser `Désabonner` ist vorhanden – der FR-Teil ist also
  rechtlich der unkritischste, wird aber am wenigsten adressiert (nur 7 Mails,
  davon Luxushotels).

---

## U6 – Der CTA endet im Nichts

**Befund:**
- „Nutzen Sie unser Kontaktformular: /kontakt“ → `/kontakt` rendert
  **statischen Markdown-Text ohne jedes Formular** (`webui/pages/legal.py`,
  `knowledge/legal/kontakt.md`). Es gibt nichts auszufüllen, nichts zu senden,
  keine Bestätigung.
- „Antworten Sie einfach auf diese E-Mail“ → Absender `no-reply@…`,
  Reply-To eine private Yahoo-Adresse; ob sie gelesen wird: siehe U0.
- Kein Termin-Link, kein Telefon-Call-to-Action in der Mail, kein konkreter
  nächster Schritt („3 Profile in 5 Tagen“, „15-Min-Gespräch“), keine Antwort-
  Erwartung („Rückmeldung bis …“).

**Folge:** Der einzige Weg, uns zu erreichen, führt über eine Rechtsseite –
das ist der höchste Reibungsverlust im gesamten Funnel.

---

## U7 – Volumen, Einmalversand, keine Nachfassung

**Befund:**
- Empfänger-Datei: **36 Zeilen**, davon **13 mit E-Mail**; Kontaktsperre
  (`jobs/ansprache.jsonl`) verhindert Wiederholung pro Firma+Anzeige – ein
  Arbeitgeber bekommt also **genau eine Mail, nie wieder** (außer neuer Anzeige).
- Versandlimit 40/Tag, aber real nur kleine Läufe (Journal-Sichtung 12.11.2026:
  6 gesendet am 11.11., 6 am 10.11., 2 am 09.11., 0 am 12.11.; lokal nur
  Dry-Run-Logs vorhanden).
- **Keine Sequenz, kein Follow-up, keine LinkedIn-/Telefon-Nachfassung, kein
  zweiter Kontakt nach 7 Tagen.** B2B-Entscheidungen brauchen mehrere
  Kontaktpunkte (vgl. Kanal-Recherche, `docs/JOBS_MARKT_ANALYSE.md` §3.2).

**Folge:** Selbst bei 1–2 % Antwortquote wäre bei ~13 Mails das erwartbare
Ergebnis **0–1 Antworten** – die Kampagne war rechnerisch zu klein, um
überhaupt ein Signal zu liefern.

---

## U8 – Kein Differenzierungsnachweis

Es gibt in der Mail keine einzige Zahl, kein Fallbeispiel, keine
Referenz, keine nennbare Leistung („X Kandidaten in Y Wochen“, „Anerkennung
in Ø Z Monaten“, „Sprachniveau B2 geprüft“). Ohne Nachweis ist „kostenlos und
unverbindlich“ das Einzige, was übrigbleibt – und das ist bei den vielen
kostenlosen Börsen kein Argument.

---

## Ehrliche Bilanz – was wir wissen und was nicht

| Aussage | Status |
|---|---|
| Es sind Antworten/Anfragen eingegangen und wurden übersehen | **ungeprüft** (kein Inbound-Monitoring, U0) |
| Mails landeten im Spam statt im Posteingang | **ungeprüft, aber technisch wahrscheinlich** (U1: kein SPF, DMARC-Quarantäne) |
| Das Angebot „kostenlose Listung“ trifft den Bedarf nicht | **belegt** (Vorlage + Marktdaten + leerer Kandidatenpool, U2) |
| Die Zielgruppe ist falsch gemischt | **belegt** (14/36 Vermittler, 13/36 mit Mail, U3) |
| Der CTA ist eine Sackgasse | **belegt** (`/kontakt` ohne Formular, U6) |
| Das Volumen reicht statistisch nicht | **belegt** (13 adressierbare Mails, Einmalversand, U7) |
| Vertrauen/Identität reicht nicht | **plausibel, nicht messbar** (U4) |
| Rechtliche Lage in DE blockiert den Kanal | **belegt** (UWG § 7, Quellen) |

**Kurz:** Die drei hart belegten Ursachen sind **falsches Angebot (U2),
falsche Zielgruppe (U3) und tote CTA (U6)** – dazu kommen als noch nicht
gemessene Bremsen **Zustellbarkeit (U1)** und **fehlende Antwort-Messung (U0)**
sowie das zu kleine Volumen (U7).
