# Verbesserungsvorschlag – aus Anfragen (Ursachen U0–U8)

**Stand:** 13.11.2026 · **Auftrag:** 2–3 Maßnahmen entwerfen, **keine Umsetzung**.
**Grundlage:** `docs/JOBS_MARKT_ANALYSE.md`, `docs/JOBS_URSACHEN.md`.
**Reihenfolge = Empfehlung.** Jede Maßnahme hat Ziel, Schritte, Metriken und
Risiko/Rollback. Keine Zahlen erfunden; erwartete Werte sind als Planwerte
markiert und nicht als Prognose zu lesen.

---

## Übersicht

| # | Maßnahme | Löst | Aufwand | Wirkung |
|---|---|---|---|---|
| **M1** | Messbar machen: Zustellbarkeit + Antwort-Empfang | U0, U1 | klein (1–2 Tage) | Voraussetzung für alles andere |
| **M2** | Angebot drehen: „kostenlose Listung“ → „vorausgewählte Kandidaten“, Zielgruppe segmentieren | U2, U3, U4, U6, U8 | mittel (3–5 Tage) | Kern des Werts |
| **M3** | Kanalwechsel: von Kaltmail zu warm/partnerbasiert (Vermittler als Kunde, BA/EURES, LinkedIn, FR statt DE) | U5, U7, Teil U1 | laufend | einziger skalierbar rechtmäßiger Weg |

**Grundregel:** M1 vor M2 und M3. Ohne Messung ist jede Verbesserung nicht
nachweisbar (Lehre aus U0).

---

## M1 – „Messen & Zustellen“ (Zustellbarkeit + Antwort-Monitoring)

### Ziel
Wissen, ob die Mails überhaupt im Posteingang landen und ob Antworten
eingehen. Heute ist beides unbekannt (U0, U1) – das ist der erste Bremsklotz.

### Schritte
1. **Authentifizierung prüfen** (DNS, nur lesend zuerst):
   - SPF für `hanibal-ai.com` fehlt am Apex → `v=spf1 include:<Mailtrap-SPF> -all`
     beim Provider ergänzen *(Wert aus Mailtrap-Doku, nicht geraten)*.
   - DKIM: den von Mailtrap vergebenen Selector in der Mailtrap-Doku nachschlagen
     und CNAME/TXT anlegen (aktuell kein Record für übliche Selector gefunden).
   - DMARC beibehalten (`p=quarantine`) und `rua`-Reports über 2 Wochen auswerten
     (Reports laufen bereits an `dmarc@reports.mailtrap.io`).
2. **Zustelltest:** 5 Testempfänger (Gmail/Outlook/Corporate) über
   `scripts/jobs_mail.py --to <adresse>` senden und Ordnerlage + Header
   (`spf=`, `dkim=`, `dmarc=`) prüfen.
3. **Antwort-Empfang einrichten:**
   - Option A: Mailtrap-Inbound-Route auf `jobs@`/`no-reply@` einrichten und
     eingehende Antworten abrufen (IMAP-Zugang prüfen – der Bounce-Poller
     `scripts/mail_bounce.py` zeigt, dass `KMHR_IMAP_*` bereits als Muster existiert).
   - Option B: Reply-To von der Yahoo-Adresse auf ein echtes, ausgelesenes
     Postfach der Domain umstellen.
   - Eingänge protokollieren (Datum, Absender, Bezug zu `jobs/ansprache.jsonl`).
4. **`no-reply@` überdenken:** Absender mit antwortbarer Adresse ist für
   B2B-Akquise sinnvoller (Deliverability + UX).
5. **Metrik-Pflege:** wöchentliche Tabelle in `jobs/laufbericht.md`:
   gesendet / zugestellt / Spam / Antworten.

### Metriken
- **Zustellquote** (Zustellbestätigung geteilt gesendet) – Ziel: ≥ 95 % *(Planwert)*.
- **Spam-Wertung** der Testpostfächer – Ziel: Posteingang, kein Spam.
- **Antworten/Woche** – heute formal 0 wegen fehlender Messung; erst M1 macht
  jede andere Zahl aussagekräftig.

### Risiko / Rollback
- DNS-Änderungen können bestehende Mails (auch Bounce-Reports) beeinflussen →
  erst dokumentieren, dann ändern, SPF nie doppelt publizieren (Komma-frei),
  `-all` erst nach erfolgreicher Messung (zuerst `~all`).
- **Rollback:** DNS-Eintrag auf den vorherigen Stand zurücksetzen (Werte vorher
  sichern); kein Code-Deploy nötig.

---

## M2 – Angebot drehen: von „Listung“ zu „vorausgewählten Kandidaten“ (+ Segmentierung)

### Ziel
Die Mail muss die Frage des Arbeitgebers beantworten: *„Woher bekomme ich
kurzfristig geeignete Fachkräfte?“* statt *„Wo stelle ich kostenlos eine
Anzeige ein?“* (U2), und bei der richtigen Zielgruppe landen (U3).

### Schritte
1. **Neue Value Proposition** (statt „kostenlose Listung“):
   - Kern: *vorausgewählte Kandidaten mit Anerkennungs-Status, Sprachniveau
     (B1/B2 geprüft), Visum-/Permit-Pfad – als Kurzprofil oder „Shortlist“*.
   - Ehrlichkeitsgrenze: Der Pool ist klein (lokal 16, Produktion 6 Kandidaten,
     Stand 12./13.11.2026). Das Versprechen muss zur tatsächlichen Lieferfähigkeit
     passen – konkreter Vorschlag: **max. 3 Profile in 5 Werktagen** als
     Testpaket, nur wo wir liefern können, sonst „Wir melden uns mit einer
     ehrlichen Einschätzung“.
   - Nachweise statt Floskeln: 1 Zahl, 1 Prozessschritt (Anerkennung/Sprache),
     1 konkreter nächster Schritt (15-Min-Gespräch-Terminlink oder Rückmeldefrist).
2. **Zielgruppe segmentieren** (`jobs/empfaenger_final.csv` als Basis):
   - **Segment A – End-Arbeitgeber** (Kliniken, Pflegeeinrichtungen, Speditionen,
     Hotels): brauchen Kandidaten → Ansprache mit M2-Value-Prop.
   - **Segment B – Personal-/Vermittlungsfirmen** (14 von 36: ARWA, JobImpulse,
     Permacon, persona service …): sind **Abnehmer**, kein „kostenloses Listing“
     nötig → eigene Ansprache: „Kandidatenpool zur Weitervermittlung /
     Kooperation“, statt Jobliste zu listen.
   - **Segment C – ohne E-Mail (23 von 36):** nicht per Mail erreichbar →
     nur über Kontaktformular/Telefon/LinkedIn, eigene Spur.
   - Branche angleichen: LKW aktuell 1/36 – entweder gezielt nachfischen oder
     LKW vorerst als Zielbranche streichen (ehrlicher als 3 % Anteil).
3. **CTA reparieren** (U6):
   - `/kontakt` ist eine statische Rechtsseite – stattdessen **echtes
     Kontaktformular oder Direkt-Antwortweg mit zugesagter Antwortzeit**
     („Antwort innerhalb 2 Werktage“), plus optionale Terminbuchung.
   - Antwortadresse mustergültig (M1) statt `no-reply` + privater Yahoo-Adresse.
4. **Kontextpersonalisierung beibehalten/beenden:** Die Stellenbelege
   (`jobs/belege/`) sind ein echtes Alleinstellungsmerkmal („Ihre Anzeige zu
   ‚Pflegefachkraft Dauernachtwache‘“) – das bleibt, wird aber an das
   Value-Prop gekoppelt: *wegen dieser Stelle melden wir uns mit Profilen*.
5. **Konkurrenz-Frage klären:** Wenn wir Vermittlern (Segment B) schreiben,
   braucht die Mail eine klare Kooperationsrolle, sonst wird sie als
   Konkurrenzangriff abgewiesen (U3).

### Metriken
- **Antwortquote je Segment** (A vs. B) – Steuerungsgröße für M3.
- **Antwort pro Kontaktpunkt** (nicht pro Mail) – Ziel: spürbar über dem
  heutigen formalen 0/13 *(Planwert, erst nach M1 messbar)*.
- **Anteil End-Arbeitgeber** in `empfaenger_final.csv` – Ziel: klar über 50 %.
- **CTA-Klicks/Formular-Absenden** – braucht M2-Schritt 3 + Analytics-Zählpunkt.

### Risiko / Rollback
- Zu großes Versprechen bei kleinem Pool → „3 Profile in 5 Tagen“ nur, wo
  lieferbar; sonst ehrliche Vorabinformation (sonst Vertrauensschaden, U4).
- Segmentierung verkleinert die Menge weiter (heute schon nur 13 Mails) –
  das ist Absicht: **weniger, aber richtige Mails**; Volumen erst über M3.
- **Rollback:** Altvorlagen bleiben in `jobs/vorlagen/` liegen; Betreff/Text
  je Sprache umschaltbar, kein Schema-Bruch nötig.

---

## M3 – Kanalwechsel: von Kaltmail zu warm, partnerbasiert und rechtkonform

### Ziel
Den rechtlich riskanten und wenig wirksamen Einzelkanal Kaltmail (DE: UWG § 7,
U5; Zustellrisiko U1; Volumen U7) durch Kanäle ersetzen, die im DACH-Raum
tatsächlich funktionieren (Belege: `docs/JOBS_MARKT_ANALYSE.md` §3.2, §4).

### Schritte (Reihenfolge nach erwartbarem Nutzen je Aufwand)
1. **FR vor DE priorisieren:** In Frankreich ist Kaltakquise an berufliche
   Adressen mit Opt-out am ehesten zulässig (Art. L.34-5 CPCE); unser
   `Désabonner` existiert. Nur 7 von 36 Empfängern sind FR – Umverteilung
   der Kampagne Richtung FR senkt Rechtsrisiko sofort, ohne neue Kanäle.
2. **Vermittler (Segment B) als Kundensegment ernst nehmen:** Sie kaufen
   Kandidaten, sie brauchen kein Listing. Kooperations-Mail/Partnerschaft statt
   „kostenlose Listung“ – der vorhandene Empfänger-Pool (14 Firmen) ist genau
   dafür geeignet.
3. **Offizielle, kostenlose Kanäle bespielen statt umverteilen zu wollen:**
   BA-Arbeitgeber-/Fachkräfteservice (DE), EURES-Partnerkanal, Job-Room (CH) –
   dort stehen Arbeitgeber bereits im Such-Modus; Anträge/Kooperation statt
   Kaltmail (Mittel: einmaliger Aufwand, dauerhafter Zugang).
4. **LinkedIn statt Kaltmail (DE/CH):** dominanter B2B-Kontaktkanal (58 % der
   B2B-Kontaktdatenquelle, ZHAW-Studie), kein UWG-Problem, gleichzeitig
   Sichtbarkeit/Vertrauen (U4). Ansprache warm: Profil + Content + InMail
   statt Massenmail.
5. **Verbände/Kammern/Messen** (HWK/IHK, DPK/Pflegeverbände, UMIH/HOGA):
   einmaliger Zugang zu vielen Betrieben, Vertrauensvorsprung – Aufwand
   mittel, Wirkung multiplikativ.
6. **Nachfass-Sequenz einführen (nur wo zulässig):** 2–3 Kontaktpunkte über
   verschiedene Kanäle (Mail → LinkedIn → Telefon), statt Einmal-Versand mit
   ewiger Kontaktsperre (`ansprache.jsonl`) – in DE nur mit Einwilligung/
   bestehendem Kontakt, in FR mit Opt-out.
7. **Inbound als Dauerlösung:** Landingpage-Arbeitgeber-Seite mit echtem
   Nutzen (Shortlist-Vorschau, Fallzahlen) + SEO/Content; Anfragen kommen dann
   zu uns (kein Rechtsproblem, keine Zustellfrage). Höchster Aufwand, aber der
   einzige Skalierungsweg ohne Kanalrisiko.

### Metriken
- **Antworten je Kanal und Kosten pro Antwort** (Zeit statt Geld) – Steuerung.
- **Anteil DE-Akquise** – Ziel: sinken, solange Kaltmail in DE unbeantwortet
  rechtlich problematisch bleibt (U5).
- **Wiederverwendbare Kanäle** (BA/EURES/LinkedIn/Verbände): Anzahl
  etablierter Zugänge – Ziel: ≥ 2 laufende Kanäle unabhängig von Kaltmail.
- **Inbound-Anfragen/Monat** (Formular/CTA aus M2) – Ziel: erste echten
  Anfragen sichtbar, statt interner Versandzahlen zu tracken.

### Risiko / Rollback
- Weniger Volumen am Anfang (M3.1/M3.2 priorisieren) → kurzfristig weniger
  „rausgeschickte Mails“, aber höherer Nutzen je Mail – Metrik umstellen
  (Antworten statt gesendet).
- LinkedIn/Verbände brauchen menschliche Präsenz und echte Profile – wenn der
  Pool dünn ist, zuerst M2-Nachweise schaffen, sonst Wiederholung von U4.
- **Rollback:** Kaltmail-Vorlagen bleiben bestehen und können in FR weiterlaufen;
  kein Umbau nötig, nur Verteilung der Kampagne verschieben.

---

## Vorgeschlagene Reihenfolge (kein Auftrag zur Umsetzung)

1. **M1** – SPF/DKIM prüfen, Zustelltest, Antwort-Empfang einrichten. *(1–2 Tage)*
2. **M2** – Value-Prop und Segmente A/B/C, CTA reparieren, ehrliche Lieferfähigkeit. *(3–5 Tage)*
3. **M3** – FR priorisieren, Vermittler als Kooperation, BA/EURES/LinkedIn
   parallel aufbauen, Inbound als Zielzustand. *(laufend)*

**Was bewusst nicht vorgeschlagen wird:**
- Mehr Volumen im selben Kaltmail-Kanal (vergrößert nur U1/U5-Risiko).
- Zusätzliche Zielbranchen, bevor LKW (1/36) und Handwerk (0 Empfänger) überhaupt
  adressiert werden – zuerst ehrlich fokussieren.
- Neues Tracking/Feature-Gebäude, bevor M1 existiert – ohne Messung keine
  Verbesserungsnachweisbarkeit.

---

## Ehrliche Einschränkungen dieses Vorschlags

- **Antwortqoten sind unbekannt** (U0): Alle Zielwerte sind Planwerte, keine
  Prognosen. Erst M1 liefert echte Baseline.
- **Zustellbarkeit ist ungeprüft** (U1): Falls die Mails im Spam landen, ist
  das sofortige Top-Priorität – dann dominiert M1 alle anderen Maßnahmen.
- **Kleiner Kandidatenpool:** M2-Messenger sind nur so gut wie die Lieferfähigkeit
  (6 Produktion-Kandidaten, 12./13.11.2026). Ohne Pool-Wachstum ist jedes
  Versprechen Gefahr für das Vertrauen (U4) – Pool-Ausbau ist damit implizit
  Teil des Pfads, aber hier nicht als Maßnahme ausgeführt.
- Keine Umsetzung in diesem Dokument; Umsetzung erst nach explizitem Go.
