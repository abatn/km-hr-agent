# Aufnahme-Einwilligung für Vorstellungsgespräche (Spec)

> **Stand:** 27.09.2026 · **Update 28.09.2026 (Nutzer-GO, Schritt 2):** Gates 8/9/10 umgesetzt (Gast-Link `&record=off`, HR-Prozessregel als UI-Hinweis, Feld `recording: false`); 9/12 offen (Einwilligungsdialog + Löschfrist u. a.)
> **TODO 03.10.2026 (Nutzerauftrag):** Aufnahme-Einwilligung **bei der Registrierung** einholen.
> **IST 09.10.2026 (Code-Angleichung):** Die Kandidaten-**Selbstpräsentation** trägt jetzt
> `https://vdo.ninja/?push=<id>&record=6000` (`webui/pages/candidate.py` (gemessen 10.10.2026)) — die frühere
> Vorgabe „ohne `&record`" ist durch den 04.10.2026-Fix (`vdo-ninja-migration.md` §2.4) überholt.
> **Update 26.10.2026 (umgesetzt):** Die Selbstpräsentation ist jetzt an eine eigene, **nicht vorab
> angehakte** Einwilligungs-Checkbox gebunden. `&record=6000` wird nur nach
> `db.record_consent(..., "recording")` erzeugt; ohne Haken entsteht eine aufnahmefreie `?push=`-URL.
> Der Nachweis liegt in der generischen Tabelle `consents` (`purpose='recording'`), nicht in einer
> separaten `recording_consents`-Tabelle. Die Einwilligung wird **vor der Selbstpräsentation**
> eingeholt, nicht bei der Registrierung — dort entsteht der Zweck noch nicht.
> **Weiter offen:** technische Löschfrist/Datei-Registrierung, HR-Gate 1–7/11–12, DSB-Bestätigung;
> der fertige Einwilligungstext steht in (e3).
> Das 12-Punkte-Gate (d) + (i) Punkt 8 gelten **weiterhin für den HR-Aufnahme-Fall** (Meeting-Raum,
> Director-/Gast-Link).
> **Zweck:** Verbindliche Bedingungen, **unter welchen** ein Aufnahme-Parameter in die Meeting-URL
> geschrieben werden darf. Ohne Erfüllung aller Bedingungen aus (d) bleibt die URL unverändert.
> **Gehört zu:** `knowledge/system/vdo-ninja-migration.md` (Abschnitt 3 verweist hierher) ·
> Skill `pre-screen` · Codemarken `vdo_ninja_url` (Director) / `vdo_ninja_gast_url` (Gast, `&record=off`)
> in `scripts/agent-runner.py`, `prescreen_recruiting_section` in `webui/components.py`,
> `meet_url` / `video_url` in `webui/pages/candidate.py` (alle gemessen 10.10.2026)
> **Geltungsbereich:** Alle Vorstellungsgespräche, die über eine VDO.Ninja-Raum-URL laufen.
> **Status:** **SPEC GESCHRIEBEN, FREIGABE OFFEN.** Diese Datei ist die *Voraussetzung* für
> Aufnahme-*aktivierende* Parameter im **HR-Raumfall** (Meeting-Raum, Director-/Gast-Link) — sie
> **schaltet** nichts frei. **Ist-Zustand (10.10.2026, Code-Angleichung, Nutzer-GO):** im HR-Raumfall
> **kein aktivierender Parameter** in der URL; der Kandidaten-Gast-Link trägt zusätzlich die
> Härtung `&record=off` (Gate 8), der Director-Link bleibt parameterfrei (Codemarken `vdo_ninja_url` /
> `vdo_ninja_gast_url` in `scripts/agent-runner.py`). **Ausgenommen und bewusst anders:** die
> Kandidaten-**Selbstpräsentation** trägt seit 04.10.2026 `&record=6000` (Codemarken `meet_url` /
> `video_url` in `webui/pages/candidate.py`, siehe (i) Punkt 8).
> **Eskalation:** Die ungeklärten Punkte aus (i) sind vor einer Freigabe durch die
> Datenschutzbeauftragte des Arbeitgebers zu bestätigen. Diese Datei ist keine Rechtsberatung.

---

## (a) Worum es geht — und was ausdrücklich nicht

**Gegenstand:** Bild- und/oder Tonaufnahmen des Vorstellungsgesprächs.

**Nicht Gegenstand:** das Gespräch selbst. Der Kandidat **nimmt an einem Live-Gespräch teil**; das ist
der Normalfall und braucht keine Aufnahme-Einwilligung. Diese Spec regelt nur die *Aufzeichnung*.

**Kernaussage der Spec:** Eine Aufnahme ist ein **zusätzlicher, vom Arbeitgeber gewählter
Verarbeitungsschritt**, der für die Durchführung des Gesprächs **nicht erforderlich** ist. Er braucht
deshalb eine **eigene, vorherige, freiwillige, informierte und schriftlich/elektronisch erteilte
Einwilligung** — und darf **nie** so gestellt werden, dass die Teilnahme an der Aufnahme Bedingung für
die Teilnahme am Gespräch oder für die Bearbeitung der Bewerbung wird.

---

## (b) Rechtsgrundlage (Wortlaut geprüft 27.09.2026)

### (b1) Warum überhaupt BDSG und nicht nur DSGVO

**§ 26 Abs. 8 Satz 2 BDSG** — *„Bewerberinnen und Bewerber für ein Beschäftigungsverhältnis sowie
Personen, deren Beschäftigungsverhältnis beendet ist, gelten als Beschäftigte."*

→ Auf Bewerberdaten ist neben der DSGVO die **zweigenehmigte** Norm des § 26 BDSG anzuwenden.

**§ 26 Abs. 2 BDSG** — Anforderungen an die Einwilligung:
> *„Erfolgt die Verarbeitung personenbezogener Daten von Beschäftigten auf der Grundlage einer
> Einwilligung, so sind für die Beurteilung der Freiwilligkeit der Einwilligung insbesondere die im
> Beschäftigungsverhältnis bestehende Abhängigkeit der beschäftigten Person sowie die Umstände, unter
> denen die Einwilligung erteilt worden ist, zu berücksichtigen. […] **Die Einwilligung hat
> schriftlich oder elektronisch zu erfolgen**, soweit nicht wegen besonderer Umstände eine andere Form
> angemessen ist. **Der Arbeitgeber hat die beschäftigte Person über den Zweck der
> Datenverarbeitung und über ihr Widerrufsrecht nach Artikel 7 Absatz 3 der Verordnung (EU) 2016/679
> in Textform aufzuklären.**"*

Daraus vier **harte** Pflichten: (1) schriftlich/elektronisch, (2) Aufklärung über den **Zweck**,
(3) Aufklärung über das **Widerrufsrecht**, (4) Aufklärung in **Textform**.

### (b2) DSGVO

| Norm | Wortlaut / Inhalt | Folge für die Aufnahme |
|---|---|---|
| **Art. 7 Abs. 1** | *„Beruht die Verarbeitung auf einer Einwilligung, muss der Verantwortliche nachweisen können, dass die betroffene Person in die Verarbeitung ihrer personenbezogenen Daten eingewilligt hat."* | **Nachweispflicht** → Einwilligung muss gespeichert und zuordenbar sein (siehe (e)) |
| **Art. 7 Abs. 3** | *„Die betroffene Person hat das Recht, ihre Einwilligung jederzeit zu widerrufen."* | Widerruf muss jederzeit möglich sein |
| **Art. 7 Abs. 3** (Satz 3) | *„Der Widerruf der Einwilligung muss so einfach wie die Erteilung der Einwilligung sein."* | Widerruf **im selben Kanal** wie Erteilung |
| **Art. 7 Abs. 2** | Erklärung, die „noch andere Sachverhalte" betrifft, muss das Ersuchen so gestalten, *„dass es von den anderen Sachverhalten klar zu unterscheiden ist"* | Einwilligung darf **nicht** in der Einladungs-Mail oder AGB versteckt werden |
| **Art. 7 Abs. 4** | Bei Beurteilung der Freiwilligkeit ist zu berücksichtigen, ob die Vertragserfüllung von der Einwilligung abhängt | siehe (h) |
| **Art. 13 Abs. 1/2** | Informationspflicht: Verantwortlicher, Zwecke, Rechtsgrundlage, Empfänger, Drittlandtransfer, **Speicherdauer**, Betroffenenrechte, **Widerrufsrecht**, Beschwerderecht | Pflichtinhalt des Einwilligungstextes, siehe (e) |
| **Art. 5 Abs. 1 lit. e** | Speicherbegrenzung | Löschfrist, siehe (f) |
| **Erwägungsgrund 32** | *„Stillschweigen, **bereits angekreuzte Kästchen** oder Untätigkeit der betroffenen Person sollten daher **keine Einwilligung** darstellen."* | **Vorab angehakt** = keine Einwilligung |
| **Erwägungsgrund 42** | Freiwillig nur, wenn die Person *„eine echte oder freie Wahl hat und somit in der Lage ist, die Einwilligung zu verweigern oder zurückzuziehen, **ohne Nachteile zu erleiden**"* | siehe (h) — der Nachteil ist der entscheidende Punkt |
| **Erwägungsgrund 43** | Keine Freiwilligkeit, wenn *„zu verschiedenen Verarbeitungsvorgängen […] nicht gesondert eine Einwilligung erteilt werden kann"* | Gesonderte, **eigene** Einwilligung nur für die Aufnahme |

### (b3) Art. 9? — hier in der Regel **nein**, mit einer Ausnahme

Eine gewöhnliche Gesprächsaufnahme ist für sich genommen **keine** besondere Kategorie. Art. 9 Abs. 1
DSGVO erfasst besondere Kategorien u. a. **„biometrische Daten zur eindeutigen Identifizierung einer
natürlichen Person"**.

→ **Grenze:** Sobald die Aufnahme für **Stimmerkennung/Sprecheridentifikation** oder eine
**automatisierte Auswertung** (Transkription mit Personenbezug, Emotion/Sprechmuster-Auswertung)
genutzt wird, kann Art. 9 greifen. Dann gilt zusätzlich **§ 26 Abs. 3 BDSG**: *„[…] die Einwilligung
muss sich dabei **ausdrücklich** auf diese Daten beziehen."*
*Für diese Spec nicht verifiziert und daher nicht entschieden — siehe (i) Punkt 5.*

---

## (c) Technische Parameterlage VDO.Ninja (Anbieter-Doku, 27.09.2026)

| Parameter | Wirkung laut Doku | Ablageort laut Doku | Bewertung |
|---|---|---|---|
| `&record` | erlaubt dem **Gast** die Aufnahme (Bitrate als Wert, z. B. `&record=1500`) | *„The video/audio will be saved in real-time to the **guest's** local download folder."* | Aufnahme beim **Bewerber**, nicht beim Arbeitgeber. WebM, H264/VP8 + OPUS/PCM |
| `&record=false` / `&record=off` | *„Buttons for recording are hidden/deleted and the recording function is disabled"* | — | **Härtung** (siehe (d) Punkt 8) |
| `&autorecord` | *„will record the local and remote videos **automatically on their initial load**"* | nicht ausdrücklich benannt | ❌ **ohne jede Einwilligung** |
| `&autorecordremote` | *„will record the remote video(s) **automatically on their initial load**"* | nicht ausdrücklich benannt | ❌ **ohne jede Einwilligung** |
| `&autorecordlocal` | im Doku-Index als verwandte Variante geführt | — | ❌ **ohne jede Einwilligung** |

### ⚠️ Zwei Befunde, die die ganze Spec tragen

**B1 — Der Parameter ist keine Zusage, dass **nicht** aufgenommen wird.**
`&record`-Doku: *„**The Director of a room can trigger the record function remotely, even if the
`&record` parameter has not been added.**"*
→ **Konsequenz:** Unsere Raum-URL ist ein `?director=`-Link. **Der Arbeitgeber ist der Director.**
Solange der Director den Raum betritt, *kann* er eine Aufnahme auch ohne Parameter starten. „Kein
Parameter in der URL" ist damit **technisch keine Garantie**, sondern nur die Voreinstellung.
Deshalb ist (d) Punkt 8 (Härtung) und Punkt 9 (Prozessregel) **zwingend**, nicht optional.

**B2 — Der Anbieter nennt die Aufnahmefunktion selbst als unausgereift.**
`&record`-Doku: *„The chunked mode […] is still a maturing feature."* Die Migrations-Spec führt
zusätzlich den Anbieter-Hinweis „experimental" (T4).

---

## (d) Freigabebedingungen — Gate

> **Verbindlich.** Sind auch nur **eine** dieser Bedingungen nicht erfüllt, wird **kein**
> Aufnahme-Parameter in die URL geschrieben. Die URL bleibt `https://vdo.ninja/?director=prescreening{code}`.

| # | Bedingung | Prüfbar durch | Stand |
|---|---|---|---|
| 1 | Einwilligung liegt **vor** dem Gespräch vor, schriftlich oder elektronisch (§ 26 Abs. 2 BDSG) | Datensatz in der Einwilligungsablage (e) | ⬜ offen |
| 2 | Einwilligung ist **eigenständig**, nicht in AGB/Einladungsmail versteckt (Art. 7 Abs. 2, Erwägungsgrund 43) | Text im Portal getrennt von der Terminbestätigung | ⬜ offen |
| 3 | Kandidat wurde über **Zweck** und **Widerrufsrecht** in **Textform** aufgeklärt (§ 26 Abs. 2 BDSG) | Pflichtinhalt (e) | ⬜ offen |
| 4 | Kästchen ist **nicht vorab angehakt** (Erwägungsgrund 32) | UI: `ui.checkbox(value=False)` zwingend | ⬜ offen |
| 5 | **Ablehnung ist folgenlos** — Gespräch findet auch ohne Aufnahme statt, Bewerbung wird normal bearbeitet (Erwägungsgrund 42) | (h) | ⬜ offen |
| 6 | **Widerruf** ist jederzeit möglich und so einfach wie die Erteilung (Art. 7 Abs. 3) | (f) Widerrufsweg | ⬜ offen |
| 7 | **Löschfrist** für die Aufnahme ist festgelegt und technisch umgesetzt (Art. 5 Abs. 1 lit. e) | (f) | ⬜ offen |
| 8 | **Härtung:** Gast-Link enthält `&record=off`, solange keine Einwilligung vorliegt | `scripts/agent-runner.py` → Variable `vdo_ninja_gast_url` (`?room=…&record=off`); Mail/ICS/Kandidaten-Karte nutzen ihn | ✅ umgesetzt 28.09.2026 (Nachweis: entscheidungen.md Schritt 2) |
| 9 | **Prozessregel:** Alle am Raum beteiligten Personen (auch die interviewende HR-Seite) sind angewiesen, **nicht** über die Aufnahmefunktion zu starten. Ohne diese Regel hebt B1 das Gate auf. | HR-Anweisung, (i) Punkt 3 — UI-Hinweis unter dem HR-Director-Link (`webui/pages/employer.py`, Einladungskarte, seit 28.09.2026) | ✅ umgesetzt 28.09.2026 (Nachweis: entscheidungen.md Schritt 2) |
| 10 | `result_json` führt `recording: false` als **explizites** Feld — kein Raten über das Fehlen eines Parameters | `agent-runner.py` Return-Keys `"recording": False` (seit 28.09.2026) | ✅ umgesetzt 28.09.2026 (Nachweis: entscheidungen.md Schritt 2) |
| 11 | Aufnahmedatei, falls sie beim Arbeitgeber eingeht, wird als **Dokument mit Typ** abgelegt — nicht unregistriert in `ergebnisse/` | `webui/db.py` `candidate_documents` | ⬜ offen |
| 12 | DSB des Arbeitgebers hat (i) bestätigt | Bestätigung | ⬜ offen |

**Sperrlogik, wie sie im Code aussehen muss:**
Ein Aufnahme-Parameter darf **nur** gesetzt werden, wenn ein Datensatz „Aufnahme erlaubt" für
`(application_id, sitzung_id)` existiert **und** nicht widerrufen wurde. Fehlt der Datensatz, wird der
Parameter **nicht** gesetzt — auch nicht „vorsorglich". Der Ist-Zustand des Codes entspricht genau dem
(`scripts/agent-runner.py` baut über `vdo_ninja_url` die Director-URL ohne Parameter; `vdo_ninja_gast_url` ist der Gast-Link mit der Härtung `&record=off`, nicht mit einer Aktivierung — Codemarken, Messung 10.10.2026).

---

## (e) Pflichtinhalt der Einwilligung und Nachweisablage

### (e1) Muss im Einwilligungstext stehen (Art. 13 Abs. 1/2 DSGVO + § 26 Abs. 2 BDSG)

1. **Wer** verantwortlich ist (Unternehmen, Anschrift) — Art. 13 Abs. 1 lit. a
2. **Zweck** der Aufnahme — Art. 13 Abs. 1 lit. c **und** § 26 Abs. 2 BDSG
3. **Rechtsgrundlage**: Einwilligung — Art. 13 Abs. 1 lit. c
4. **Empfänger / Kategorien** (wer das Video bekommt) — Art. 13 Abs. 1 lit. e
5. **Speicherdauer** bzw. Löschkriterium — Art. 13 Abs. 2 lit. a
6. **Widerrufsrecht** jederzeit, ohne Angabe von Gründen, ab Zugang der Aufnahme — Art. 7 Abs. 3
7. **Betroffenenrechte**: Auskunft, Berichtigung, Löschung, Einschränkung, Widerspruch,
   Datenübertragbarkeit — Art. 13 Abs. 2 lit. b
8. **Beschwerderecht** bei einer Aufsichtsbehörde — Art. 13 Abs. 2 lit. d
9. **Freiwilligkeit ausdrücklich**: „Sie können die Aufnahme ablehnen, ohne dass dies für Ihr
   Gespräch oder Ihre Bewerbung nachteilig ist." — Erwägungsgrund 42
10. **Hinweis auf Mitwirkende**: Gesprächspartner und ggf. weitere Personen im Raum werden mit erfasst.

> **Sprache (Stand 26.10.2026):** Der Text liegt in **DE/EN/FR/AR** vor (siehe (e3)). Die
> Einwilligungssprache muss **dem Kandidaten verständlich** sein, sonst ist die „informierte"
> Einwilligung angreifbar. Die anwaltliche Prüfung der vier Fassungen steht aus.

### (e2) Nachweis (Art. 7 Abs. 1 DSGVO — Nachweispflicht)

Der Arbeitgeber muss **belegen** können, dass eingewilligt wurde. Das ist eine
**Nachweispflicht**, keine Absichtserklärung.

| Feld | Inhalt | Quelle der Pflicht |
|---|---|---|
| `application_id` | Bezug zur Bewerbung | Projekt |
| `sitzung_id` / Termin | welcher Termin | Projekt |
| `erteilt_am` | Zeitpunkt | Art. 7 Abs. 1 |
| `form` | `schriftlich` \| `elektronisch` | § 26 Abs. 2 BDSG |
| `text_version` | **Version des gezeigten Einwilligungstextes** | Art. 7 Abs. 1 (nur so ist später beweisbar, was stand) |
| `widerrufen_am` | nullable | Art. 7 Abs. 3 |
| `beleg_dokument_id` | Verweis auf die Datei | Projekt (Vorschlag, **Design-Entscheidung**) |

> **Umsetzung 26.10.2026 (Design-Entscheidung):** Der Nachweis liegt in der generischen Tabelle
> `consents` (`subject_type='candidate'`, `purpose='recording'`, `text_version`, `granted_at`,
> `withdrawn_at`). Eine separate `recording_consents`-Tabelle ist nicht nötig; die generische Tabelle
> ist versioniert und widerrufsfähig. Die Datei-/Sitzungszuordnung (`application_id`, `sitzung_id`)
> wird im `evidence_json` geführt.

### (e3) Fertiger Einwilligungstext (DE/EN/FR/AR) — Vorlage, anwaltlich zu prüfen

> **Status:** Entwurf 26.10.2026. Der Text deckt die Pflichtinhalte aus (e1) ab (Zweck, Empfänger,
> Speicherdauer, Widerruf, Freiwilligkeit, Mitwirkende, Rechte). Er ist **kein Rechtsrat** und
> ersetzt **keine** anwaltliche/DSB-Freigabe (Gate 12). Die **Rollenabgrenzung** zwischen Anbieter
> und Arbeitgeber (wer ist Verantwortlicher der Aufnahme?) ist vor dem ersten Einsatz festzulegen —
> sie hängt davon ab, wessen System die Datei empfängt ((i) Punkt 4).

**Einbauregeln (gelten für alle vier Sprachen):**

- Nur **eine** Erklärung pro Aufnahme, **getrennt** von AGB, Einladungsmail und Terminbestätigung
  (Art. 7 Abs. 2 DSGVO).
- Kästchen **nicht vorab angehakt** (Erwägungsgrund 32); Pflichtfeld `value=False` (Gate 4).
- **Ablehnung ist folgenlos** (Gate 5, (h)); der Text sagt das ausdrücklich.
- Version und Datum des Textes werden beim Nachweis gespeichert (Feld `text_version`, (e2)).
- Sprache: die dem Kandidaten verständliche Fassung; DE/EN/FR/AR liegen vor ((i) Punkt 1).

#### Deutsch (verbindliche Fassung)

**Einwilligung in die Aufzeichnung des Video-Vorstellungsgesprächs**

Verantwortlich für die Aufzeichnung ist der Arbeitgeber, der sie veranlasst; die technische
Bereitstellung erfolgt durch die Agic Tunisie GmbH, 13 rue des Usines, ZI Sidi Rezig, 2033 Ben
Arous, Tunesien, E-Mail batniniabdelkader@yahoo.com, Telefon +216 52 369 325. Die Rollenabgrenzung
wird vor dem Einsatz bestätigt.

1. **Zweck.** Die Bild- und Tonaufzeichnung dient ausschließlich dazu, den Gesprächsverlauf für die
   Auswahlentscheidung nachvollziehbar zu machen. Sie ist für die Durchführung des Gesprächs nicht
   erforderlich.
2. **Empfänger.** Die Aufzeichnung erhalten ausschließlich die interviewenden Personen und die für
   die Auswahl zuständige Personalabteilung des jeweiligen Arbeitgebers. Eine Weitergabe darüber
   hinaus erfolgt nicht. Speicherort und Übermittlungsweg: [zu ergänzen].
3. **Speicherdauer.** Die Aufzeichnung wird **6 Monate nach Ende des Verfahrens** gelöscht. Der
   Nachweis über diese Einwilligung wird **36 Monate** aufbewahrt.
4. **Widerruf.** Sie können diese Einwilligung **jederzeit ohne Angabe von Gründen** widerrufen,
   per E-Mail an batniniabdelkader@yahoo.com. Nach dem Widerruf wird die Aufzeichnung gelöscht,
   soweit sie noch vorhanden ist. Der Widerruf ist so einfach wie die Erteilung.
5. **Freiwilligkeit.** Die Einwilligung ist **freiwillig**. Wenn Sie sie nicht erteilen oder später
   widerrufen, findet das Gespräch **statt** und Ihre Bewerbung wird **genau so** bearbeitet wie bei
   allen anderen. Es entstehen Ihnen **keine Nachteile**.
6. **Mitwirkende.** Gesprächspartner und weitere Personen im Raum werden mit aufgezeichnet. Alle
   Teilnehmenden werden vor dem Gespräch darüber informiert.
7. **Ihre Rechte.** Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung,
   Datenübertragbarkeit und Widerspruch (Art. 15–22 DSGVO) sowie auf Beschwerde bei einer
   Aufsichtsbehörde (Art. 77 DSGVO). Ein Datenschutzbeauftragter ist nicht bestellt; Anfragen
   richten Sie an die oben genannte E-Mail-Adresse.

☐ **Ich willige in die Aufzeichnung des Gesprächs zu den oben genannten Bedingungen ein.**
(Ich kann diese Einwilligung jederzeit ohne Nachteile widerrufen.)

Ort, Datum, Name, Unterschrift bzw. elektronische Bestätigung: ______________________
Textversion: 26.10.2026

#### English (translation; the German version prevails)

**Consent to the recording of the video interview**

The controller of the recording is the employer who arranges it; the technical provision is made by
Agic Tunisie GmbH, 13 rue des Usines, ZI Sidi Rezig, 2033 Ben Arous, Tunisia, email
batniniabdelkader@yahoo.com, phone +216 52 369 325. The allocation of roles will be confirmed before
use.

1. **Purpose.** The video and audio recording serves exclusively to make the course of the interview
   comprehensible for the selection decision. It is not required to conduct the interview.
2. **Recipients.** The recording is received only by the interviewing persons and the HR department
   responsible for selection at the respective employer. It is not passed on beyond that. Storage
   location and transmission path: [to be added].
3. **Storage period.** The recording is deleted **6 months after the process ends**. The record of
   this consent is kept for **36 months**.
4. **Withdrawal.** You may withdraw this consent **at any time without giving reasons** by email to
   batniniabdelkader@yahoo.com. After withdrawal the recording is deleted insofar as it still
   exists. Withdrawal is as easy as giving consent.
5. **Voluntariness.** Consent is **voluntary**. If you do not give it or withdraw it later, the
   interview **takes place** and your application is processed **in exactly the same way** as for
   everyone else. You suffer **no disadvantages**.
6. **Participants.** Interviewers and other persons in the room are recorded as well. All
   participants are informed before the interview.
7. **Your rights.** You have the right to access, rectification, erasure, restriction, data
   portability and objection (Art. 15–22 GDPR) and to lodge a complaint with a supervisory
   authority (Art. 77 GDPR). No Data Protection Officer has been appointed; please address requests
   to the email address above.

☐ **I consent to the recording of the interview under the conditions stated above.**
(I may withdraw this consent at any time without disadvantages.)

Place, date, name, signature or electronic confirmation: ______________________
Text version: 26.10.2026

#### Français (traduction ; la version allemande prévaut)

**Consentement à l'enregistrement de l'entretien vidéo**

Le responsable de l'enregistrement est l'employeur qui le demande ; la mise à disposition technique
est assurée par Agic Tunisie GmbH, 13 rue des Usines, ZI Sidi Rezig, 2033 Ben Arous, Tunisie,
e-mail batniniabdelkader@yahoo.com, téléphone +216 52 369 325. La répartition des rôles sera
confirmée avant utilisation.

1. **Finalité.** L'enregistrement audio-vidéo sert exclusivement à rendre le déroulement de
   l'entretien compréhensible pour la décision de sélection. Il n'est pas nécessaire à la tenue de
   l'entretien.
2. **Destinataires.** L'enregistrement est reçu uniquement par les personnes qui mènent l'entretien
   et le service RH chargé de la sélection chez l'employeur concerné. Aucune transmission
   supplémentaire n'a lieu. Lieu de stockage et voie de transmission : [à compléter].
3. **Durée de conservation.** L'enregistrement est supprimé **6 mois après la fin de la procédure**.
   La preuve de ce consentement est conservée **36 mois**.
4. **Retrait.** Vous pouvez retirer ce consentement **à tout moment et sans motif**, par e-mail à
   batniniabdelkader@yahoo.com. Après le retrait, l'enregistrement est supprimé dans la mesure où il
   existe encore. Le retrait est aussi simple que le consentement.
5. **Liberté.** Le consentement est **libre**. Si vous ne le donnez pas ou le retirez plus tard,
   l'entretien **a lieu** et votre candidature est traitée **exactement comme** celle de toutes les
   autres personnes. Vous ne subissez **aucun désavantage**.
6. **Participants.** Les interlocuteurs et d'autres personnes présentes dans la salle sont également
   enregistrés. Tous les participants en sont informés avant l'entretien.
7. **Vos droits.** Vous disposez des droits d'accès, de rectification, d'effacement, de limitation,
   de portabilité et d'opposition (art. 15–22 RGPD) ainsi que du droit d'introduire une réclamation
   auprès d'une autorité de contrôle (art. 77 RGPD). Aucun délégué à la protection des données n'est
   désigné ; adressez vos demandes à l'adresse e-mail ci-dessus.

☐ **Je consens à l'enregistrement de l'entretien aux conditions indiquées ci-dessus.**
(Je peux retirer ce consentement à tout moment sans désavantage.)

Lieu, date, nom, signature ou confirmation électronique : ______________________
Version du texte : 26.10.2026

#### العربية (ترجمة؛ النسخة الألمانية هي المعتمدة)

**الموافقة على تسجيل مقابلة الفيديو**

الجهة المسؤولة عن التسجيل هي صاحب العمل الذي يطلبه؛ ويتم التوفير التقني من قبل
Agic Tunisie GmbH، 13 rue des Usines, ZI Sidi Rezig, 2033 Ben Arous، تونس،
البريد الإلكتروني batniniabdelkader@yahoo.com، الهاتف +216 52 369 325. وسيتم تأكيد توزيع الأدوار
قبل الاستخدام.

1. **الغرض.** يُستخدم التسجيل الصوتي والمرئي حصريًا لجعل سير المقابلة مفهومًا لقرار الاختيار. وهو
   ليس ضروريًا لإجراء المقابلة.
2. **الجهات المستلمة.** لا يتلقى التسجيل إلا الأشخاص الذين يجروون المقابلة وإدارة الموارد البشرية
   المسؤولة عن الاختيار لدى صاحب العمل المعني. ولا يتم نقلها إلى أبعد من ذلك. مكان التخزين ومسار
   النقل: [يُستكمل].
3. **مدة التخزين.** يُحذف التسجيل **بعد 6 أشهر من انتهاء العملية**. ويُحفظ إثبات هذه الموافقة
   **36 شهرًا**.
4. **السحب.** يمكنك سحب هذه الموافقة **في أي وقت ودون ذكر أسباب** عبر البريد الإلكتروني
   batniniabdelkader@yahoo.com. وبعد السحب يُحذف التسجيل إن كان لا يزال موجودًا. وسحب الموافقة
   بسيط مثل منحها.
5. **الطوعية.** الموافقة **طوعية**. وإذا لم تمنحها أو سحبتها لاحقًا، فستُجرى المقابلة **وستتم
   معالجة طلبك بالطريقة نفسها تمامًا** كجميع الآخرين. ولن تتعرض **لأي أضرار**.
6. **المشاركون.** يُسجَّل أيضًا المحاورون والأشخاص الآخرون الموجودون في الغرفة. ويُبلَّغ جميع
   المشاركين بذلك قبل المقابلة.
7. **حقوقك.** لك الحق في الوصول والتصحيح والمحو والتقييد ونقل البيانات والاعتراض (المواد 15–22
   GDPR)، وفي تقديم شكوى إلى جهة رقابية (المادة 77 GDPR). لا يوجد مسؤول حماية بيانات معيّن؛
   يُرجى توجيه الطلبات إلى البريد الإلكتروني أعلاه.

☐ **أوافق على تسجيل المقابلة وفق الشروط المذكورة أعلاه.**
(يمكنني سحب هذه الموافقة في أي وقت دون أضرار.)

المكان والتاريخ والاسم والتوقيع أو التأكيد الإلكتروني: ______________________
نسخة النص: 26.10.2026

#### Umsetzungsstand und Lücke (26.10.2026)

| Punkt | Ist-Zustand | Bewertung |
|---|---|---|
| Einwilligungs-Checkbox vor Selbstpräsentation | **umgesetzt 26.10.2026** (`_recording_consent_ui`, nicht vorab angehakt) | erfüllt Gate 1–4 für die Selbstpräsentation |
| Nachweis `consents` (`purpose='recording'`) | **umgesetzt 26.10.2026** | erfüllt Art. 7 Abs. 1 (Version/Zeitpunkt/Widerruf) |
| Selbstpräsentation `?push=…&record=6000` | **nur nach Haken**; ohne Haken `?push=` ohne Aufnahme | entspricht Gate 1–4 |
| HR-Raumfall | kein aktivierender Parameter; Gast-Link `&record=off` | entspricht Gate 8 |
| Löschfrist technisch | **nicht umgesetzt** | Lücke zu Gate 7 / (f) |
| Aufnahme-Ablage beim Arbeitgeber | **nicht definiert** | Lücke zu (i) Punkt 4 / Gate 11 |

> **Klartext:** Die Selbstpräsentation ist jetzt ohne dokumentierte Einwilligung nicht mehr
> aufnahmefähig; der Aufnahme-Parameter wird nur im Consent-Zweig erzeugt. Offen bleiben die
> technische Löschfrist, die Datei-Registrierung und die HR-Gate-Punkte 1–7/11–12.

---

## (f) Löschfristen


| Daten | Frist | Quelle |
|---|---|---|
| Aufnahmedatei (Bild/Ton) | **6 Monate nach Prozessende** — Vorschlag, **parallel** zur Bewerbungsdaten-Frist | **Design-Entscheidung**; orientiert an `knowledge/legal/gdpr-policy.md` (Bewerbungsdaten = 6 Monate). **Nicht aus einem Gesetz abgeleitet** — DSB-Bestätigung nötig |
| Einwilligungsnachweis selbst | **36 Monate** | `knowledge/legal/gdpr-policy.md` („Compliance-Daten \| DSGVO-Report, Einwilligung \| 36 Monate (Pflicht)") — Projektwert, **nicht** gesetzlich abgeleitet |

⚠️ **Spannung, die nicht aufgelöst ist:** Art. 7 Abs. 1 verlangt den Nachweis, Art. 5 Abs. 1 lit. e
verlangt die Begrenzung. Deshalb ist „Aufnahme löschen, Nachweis behalten" die einzige konsistente
Kombination — der Nachweis enthält aber weiterhin **Metadaten** (wer, wann, welcher Termin), keine
Bild-/Tondaten. Auch das ist personenbezogen und fällt unter die Frist.

**Widerrufsweg (Art. 7 Abs. 3):** Widerruf per Antwort auf dieselbe Mail, über die die Einwilligung
erteilt wurde, oder über einen Kandidaten-Kontaktkanal. **So einfach wie die Erteilung** — keine
Formularpflicht, kein Grund.

---

## (g) Unzulässige Konfigurationen (harte Verbotsliste)

| # | Verboten | Grundlage |
|---|---|---|
| 1 | `&autorecord` / `&autorecordremote` / `&autorecordlocal` **ohne** vorherige Einwilligung | Aufnahme „automatically on their initial load" = ohne jede Kenntnis; Erwägungsgrund 32/42 |
| 2 | Einwilligung als **vorab angehaktes** Kästchen | Erwägungsgrund 32 (wörtlich) |
| 3 | Einwilligung versteckt in AGB, Link-Fußzeile oder Einladungsmail | Art. 7 Abs. 2; Erwägungsgrund 43 |
| 4 | Aufnahme als **Bedingung** für Einladung/Gespräch/Bewerbungsbearbeitung | Erwägungsgrund 42 („ohne Nachteile zu erleiden"), Art. 7 Abs. 4 |
| 5 | Stillschweigen oder Untätigkeit als Einwilligung werten | Erwägungsgrund 32 |
| 6 | Aufnahme **nur** mündlich, ohne schriftlichen/elektronischen Beleg | § 26 Abs. 2 BDSG |
| 7 | Einwilligung mit **anderen Erklärungen** verknüpfen | Art. 7 Abs. 2 |
| 8 | Aufnahme starten, obwohl Einwilligung **widerrufen** | Art. 7 Abs. 3 |
| 9 | Aufnahmedatei unregistriert in `ergebnisse/` ablegen | Art. 5 Abs. 1 lit. c/f, Art. 32 |
| 10 | Aufnahme für **Stimmerkennung/automatisierte Auswertung** ohne ausdrückliche Einwilligung | § 26 Abs. 3 BDSG / Art. 9 Abs. 1 DSGVO — siehe (b3) und (i) Punkt 5 |

---

## (h) Einladung ≠ Aufnahme — Ablehnung muss folgenlos sein

Das ist der **inhaltlich wichtigste** Punkt der Spec und der Grund, warum Erwägungsgrund 42 hier
schwerer wiegt als bei gewöhnlichen Online-Einwilligungen:

Ein Bewerber steht in einem **Abhängigkeitsverhältnis** (§ 26 Abs. 2 Satz 1 BDSG nennt die
Abhängigkeit ausdrücklich als Prüfmaßstab der Freiwilligkeit). Wer die Aufnahme ablehnt, fürchtet
Nachteile für das Gespräch oder die Bewerbung. Erwägungsgrund 42 verlangt aber, dass die Person
in der Lage ist, abzulehnen *„ohne Nachteile zu erleiden"*.

**Daraus folgt zwingend:**
1. Die Einladung wird **ohne** Aufnahmeparameter versendet. Die Aufnahme ist ein **späterer**,
   gesonderter Schritt.
2. Die Einwilligung wird **vor** dem Termin eingeholt, mit ausdrücklichem Hinweis, dass die
   Ablehnung folgenlos ist.
3. **Ablehnung ändert nichts** an Termin, Gesprächsführung und Bewerbungsbearbeitung. Im Zweifel
   dokumentieren HR-Notizen: „Aufnahme abgelehnt, Gespräch normal geführt."
4. Wer ablehnt, bekommt **denselben** Gesprächsablauf — keine „dann eben ohne Kamera"-Sonderbehandlung
   im Portal.

> **Ehrlich offen:** Ob die Freiwilligkeit im konkreten Einzelfall gegeben ist, hängt von der
> **Kommunikation des Arbeitgebers** ab, nicht nur vom Formular. Diese Spec kann die Gestaltung
> nicht ersetzen — sie kann nur verhindern, dass die Technik die Gestaltung unterläuft.

---

## (i) Offene Punkte — vor jeder Freigabe zu klären

1. **Sprache der Einwilligung** — **gelöst durch (e3):** vier Fassungen (DE/EN/FR/AR) liegen vor;
   offen ist nur die anwaltliche Prüfung. Ohne für den Kandidaten verständlichen Text ist
   „informiert" nicht erfüllt.
2. **DSB-Bestätigung** der Löschfristen (6 / 36 Monate) und des Aufbewahrungsorts der Aufnahme.
3. **Hosting-Frage VDO.Ninja:** fremder Dienst (fremde TURN-Server) oder selbst gehostet — betrifft
   Art. 13 Abs. 1 lit. e (Drittlandtransfer) und Art. 44 ff. Offen seit
   `ergebnisse/browser-recording-plan-2026-09-27.md`.
4. **Ablageweg der Aufnahme:** Wie kommt die Datei vom Bewerber-Rechner zum Arbeitgeber? Ohne
   definierten Weg („Kandidat lädt hoch" / „HR lädt vom eigenen Recording herunter") ist der Prozess
   nicht umsetzbar — und genau hier entstehen die unkontrollierten Kopien.
5. **Art. 9:** Wird die Aufnahme je für Sprecheridentifikation oder automatisierte Auswertung genutzt?
   Falls ja: eigene Einwilligung nach § 26 Abs. 3 BDSG.
6. **Kollektivvereinbarung (§ 26 Abs. 4 BDSG):** Ob für **externe** Bewerber eine
   Kollektivvereinbarung überhauptabschließbar ist, wurde hier **nicht verifiziert** (BetrVG gilt nur
   für Arbeitnehmer des Unternehmens). **Nicht als gegeben angenommen** — falls sie nicht möglich ist,
   bleibt die Einwilligung der **einzige** Weg. Von der DSB zu klären.
7. **Mitwirkende:** Gesprächspartner und Dritte (z. B. Angehörige im Raum) sind mit erfasst. Für die
   eigenen Beschäftigten gelten die allgemeinen Regeln; die Aufklärung gegenüber Mitwirkenden ist zu
   klären.
8. **TODO (03.10.2026, Nutzerauftrag; Ist-Stand 09.10.2026) — Aufnahme-Einwilligung bei der
   REGISTRIERUNG einholen.**
   Die Einwilligung zur Aufnahme muss **im Registrierungs-Flow** des Kandidaten eingeholt und
   nachgewiesen werden (nicht erst im Gespräch). **Ist-Code (09.10.2026):**
   - Der Kandidaten-Link zur **Selbstpräsentation** ist **`https://vdo.ninja/?push=<id>&record=6000`**
     (Solo-Sender + Aufnahme-Knopf) — Code-Stellen `webui/pages/candidate.py` (gemessen 10.10.2026); der
     04.10.2026-Fix hat `&record=6000` ergänzt (`vdo-ninja-migration.md` §2.4). Die Aufnahme landet
     lokal im Download-Ordner des Kandidaten.
   - Offizielle VDO-Doku (Abruf 03.10.2026): Solo-Selbstpräsentation = **`&push`**, **nicht**
     `&director`; Aufnahme via `&record=6000`.
   - **Dieses Gate (i) Punkt 8 gilt weiterhin für den HR-Aufnahme-Fall** (Meeting-Raum,
     Director-Link `?director=` bzw. Gast-Link `?room=…&record=off`) — dort bleibt ein
     Aufnahme-*aktivierender* Parameter bis zur dokumentierten Einwilligung aus (Gates (d) 8–10).

---

## (j) Quelle je Zahl / Regel

| Regel / Wert | Quelle | Art |
|---|---|---|
| Bewerber = Beschäftigte | § 26 Abs. 8 Satz 2 BDSG, gesetze-im-internet.de/bdsg_2018/__26.html, abgerufen 27.09.2026 | Gesetz, **im Wortlaut geprüft** |
| Einwilligung schriftlich/elektronisch; Aufklärung über Zweck + Widerrufsrecht in Textform | § 26 Abs. 2 BDSG, ebd. | Gesetz, **im Wortlaut geprüft** |
| Einwilligung bei besonderen Kategorien muss sich ausdrücklich darauf beziehen | § 26 Abs. 3 BDSG, ebd. | Gesetz, **im Wortlaut geprüft** |
| Kollektivvereinbarungen als Grundlage | § 26 Abs. 4 BDSG, ebd. | Gesetz, **im Wortlaut geprüft** |
| Nachweispflicht des Verantwortlichen | Art. 7 Abs. 1 DSGVO | Verordnung |
| Widerruf jederzeit / so einfach wie Erteilung | Art. 7 Abs. 3 DSGVO | Verordnung |
| Einwilligung von anderen Erklärungen abzugrenzen | Art. 7 Abs. 2 DSGVO | Verordnung |
| Einwilligung nicht von Vertragserfüllung abhängig | Art. 7 Abs. 4 DSGVO | Verordnung |
| Informationspflicht-Inhalte | Art. 13 Abs. 1/2 DSGVO | Verordnung |
| Speicherbegrenzung | Art. 5 Abs. 1 lit. e DSGVO; Erwägungsgrund 39 | Verordnung |
| Biometrische Daten zur eindeutigen Identifizierung = besondere Kategorie | Art. 9 Abs. 1 DSGVO | Verordnung |
| „Stillschweigen, bereits angekreuzte Kästchen oder Untätigkeit … keine Einwilligung" | Erwägungsgrund 32 DSGVO (EUR-Lex, CELEX:32016R0679, Amtsblatt L 119/1 vom 4.5.2016) | Verordnung, **im Wortlaut geprüft** |
| „echte oder freie Wahl … verweigern oder zurückzuziehen, ohne Nachteile zu erleiden" | Erwägungsgrund 42 DSGVO, ebd. | Verordnung, **im Wortlaut geprüft** |
| Keine gesonderte Einwilligung / Vertragserfüllung ≠ Zwang | Erwägungsgrund 43 DSGVO, ebd. | Verordnung, **im Wortlaut geprüft** |
| Löschfrist Aufnahme **6 Monate** | **Design-Entscheidung** — orientiert an `knowledge/legal/gdpr-policy.md`; **kein Gesetz abgeleitet** | Projekt |
| Einwilligungsnachweis **36 Monate** | `knowledge/legal/gdpr-policy.md` (Projektwert „Compliance-Daten"), **nicht** gesetzlich abgeleitet | Projekt |
| `&record` speichert beim **Gast** in lokaler Download-Ordner | docs.vdo.ninja/advanced-settings/recording-parameters/and-record, abgerufen 27.09.2026 | Anbieter-Doku, **im Wortlaut geprüft** |
| `&record=off`/`false` deaktiviert die Aufnahmefunktion | ebd. | Anbieter-Doku |
| **Director kann ferngesteuert aufnehmen, auch ohne `&record`** | ebd. | Anbieter-Doku |
| `&autorecord` nimmt lokale **und** entfernte Videos automatisch beim Laden auf | docs.vdo.ninja/…/and-autorecord | Anbieter-Doku |
| `&autorecordremote` nimmt entfernte Videos automatisch beim Laden auf | docs.vdo.ninja/…/and-autorecordremote | Anbieter-Doku |
| Aufnahmefunktion „experimental" / „maturing" | `knowledge/system/vdo-ninja-migration.md` §3 (T4) + `&record`-Doku | Anbieter-Doku |
| **HR-Raumfall: kein aktivierender Parameter; Gast-Link mit `&record=off` (Härtung, seit 28.09.2026)** · **Kandidaten-Selbstpräsentation: `?push=…&record=6000` (seit 04.10.2026, Nutzerauftrag)** | Codemarken `vdo_ninja_url`/`vdo_ninja_gast_url` in `scripts/agent-runner.py` bzw. `meet_url`/`video_url` in `webui/pages/candidate.py` (Code-Messung 10.10.2026) | Code-Messung |
| Tabelle `consents` (`purpose='recording'`) | **umgesetzt 26.10.2026** (`webui/db.py`, `record_consent`/`withdraw_consent`) | Code + Tests |
| Einwilligungstext DE/EN/FR/AR (e3) | **Design-Entscheidung** (Entwurf 26.10.2026, Pflichtinhalte aus (e1)); anwaltlich zu prüfen | Projekt |
| Selbstpräsentation `&record=6000` **nur nach** Consent | **umgesetzt 26.10.2026** (`webui/pages/candidate.py`, `_recording_consent_ui`; Test `test_consent_ui.py`) | Code + Test |
| Härtung `&record=off` als Bedingung 8 | **Design-Entscheidung** (aus Anbieter-Doku abgeleitet, dort nicht als Empfehlung ausgewiesen) | Projekt |

---

## (k) Was diese Spec **nicht** freigibt

- **Code-Änderung 28.09.2026 (Nutzer-GO, Schritt 2):** Härtung + Rollentrennung — Gast-Link `vdo_ninja_gast_url` = `?room=…&record=off`, Director-Link `vdo_ninja_url` ohne Parameter; **im HR-Raumfall** gibt es weiterhin keine Aufnahme-*Aktivierung*. **Ausnahme (Nutzerauftrag 04.10.2026, Codemarken `meet_url`/`video_url` in `webui/pages/candidate.py`):** die Kandidaten-Selbstpräsentation trägt `?push=…&record=6000` — Aufnahme landet lokal im Download-Ordner des Kandidaten.
- **Kein Aufnahme-Parameter wurde im HR-Raum aktiviert.** Das Gate (d) ist zu 12/12 offen; es betrifft Director-/Gast-Links des Arbeitgebers, **nicht** die Kandidaten-Selbstpräsentation.
- **Keine Löschfrist wurde technisch umgesetzt.** § 12 (d) Punkt 7 bleibt offen.
- **Einwilligungs-Tabelle ist angelegt** (`consents`, generisch) und wird für
  `purpose='recording'` genutzt; die frühere 12-Punkte-Gate-Liste (d) gilt weiter für den HR-Raumfall.
- **Selbstpräsentation (26.10.2026):** `&record=6000` wird nur nach der separaten Checkbox und
  `record_consent(..., 'recording')` erzeugt; ohne Haken bleibt die URL aufnahmefrei. Offen sind
  Löschfrist, Datei-Registrierung und die HR-Gate-Punkte 1–7/11–12. Übersicht: (e3)
  „Umsetzungsstand und Lücke".
- Es wurde **kein** Vertragstext erstellt; der Einwilligungstext ist als **Pflichtinhalt**
  beschrieben (e1), nicht als juristisch fertiges Formular. Fertigung durch Rechtsabteilung/DSB.

---

## (l) Verbindlichkeit

Diese Datei ist **Source of Truth** für die Frage „darf ein Aufnahme-Parameter in die URL?".
Wird sie geändert, ist `knowledge/system/vdo-ninja-migration.md` Abschnitt 3 mitzuziehen.
Die Bedingungen aus (d) sind **keine Empfehlung**, sondern Voraussetzung — ohne vollständige
Erfüllung bleibt der Ist-Zustand: **URL ohne Aufnahme-Parameter**.

---

*Erstellt am 27.09.2026 für den KM-HR-Agenten. Rechtsgrundlagen am 27.09.2026 im Wortlaut geprüft.
Keine Rechtsberatung — Freigabe nur durch Datenschutzbeauftragte des Arbeitgebers.*
