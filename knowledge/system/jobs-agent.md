# Jobs-Akquise-Agent (Jobs.hanibal-ai.com)

**Status:** umgesetzt 31.10.2026 · **Code:** `scripts/jobs_agent.py` ·
**Test:** `tests/test_jobs_agent.py` · **Betrieb:** `jobs/README.md`

## Zweck

Findet aktuelle Stellen in Deutschland, Frankreich und der Schweiz in vier
Branchen (Krankenhaus/Krankenpflege, LKW, Handwerk, Hotellerie/Gastronomie),
prüft die Eignung für ausländische Kandidaten (insbesondere Nordafrika) und
erzeugt belegte Anschreiben an die Arbeitgeber.

## Ablauf

1. **Suche** über den MCP-Server `anysearch` (remote JSON-RPC, `tools/call`
   mit `search`). 18 Query-Kombinationen (Land × Branche, plus
   Visum-/Anerkennungs-Fokus), je bis zu 10 Treffer. Nach jeder Suche wird
   `score` als Feedback aufgerufen (Anysearch-Vorgabe).
2. **Filter:** `is_aggregator()` verwirft Job-Börsen (indeed, stepstone,
   linkedin, jobs.ch, …), Listen-Seiten („Jobs in …") und Seiten ohne
   verwertbaren Text.
3. **Eignung:** `suitability()` bewertet deterministisch (kein LLM) das
   Vorkommen von Visum/Arbeitserlaubnis, Anerkennung, Relocation,
   Sprachlevel und Internationalität; Abzug bei „nur EU-Bürger" und bei
   dünnem Text. Schwellwert `--min-score` (Default 40).
4. **Beleg:** Playwright öffnet die Originalseite, erzeugt Screenshot (PNG)
   und HTML-Snapshot. Zusätzlich wird ein Wayback-Save versucht; das Ergebnis
   (Link oder Fehlercode) steht im Beleg.
5. **Ausgabe:** Tabelle `jobs/belege/<datum>/index.md`, Einzelbelege
   `<slug>.md`, Empfängerliste `jobs/empfaenger.csv`, Anschreiben
   `jobs/outbox/<datum>/*.eml` in DE/EN/FR.

## Beleg-Pflicht

Jeder Einzelbeleg enthält: Quelle (URL), Abrufdatum, Archiv-Status,
Screenshot-Pfad, HTML-Snapshot, veröffentlichte Kontaktadresse (falls
vorhanden) und die Eignungsbegründung. Die Tabelle nennt Arbeitgeber, Stelle,
Ort, Land, Branche, Eignung, Kontakt und Quelle.

## Datenquellen (recherchiert und getestet 31.10.2026)

| Land | Quelle | Auth | Status | Ergebnis |
|---|---|---|---|---|
| **DE** | Bundesagentur Jobsuche, `rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs` + `/pc/v4/jobdetails/{base64(refnr)}` | Header `X-API-Key: jobboerse-jobsuche` (öffentlich, keine Registrierung) | **funktioniert** | strukturierte Treffer: Titel, Firma, Ort, Referenznummer, Volltext, teils `externeURL` |
| **FR** | France Travail „Offres d'emploi v2", `api.francetravail.io/partenaire/offresdemploi/v2/offres/search` | OAuth2 `client_credentials` (kostenlos, aber Antrag) | **blockiert** | ohne Token 401; Katalogseite 403 („l'accès à cette API vous est interdit"); Zugang nur über Antrag |
| **CH** | jobs.ch / jobup.ch `api/v1/public/search` | keine | **200, aber unzulässig** | `robots.txt` sperrt `/api/`; JobCloud-ToS untersagt Scraper → nicht produktiv nutzbar |
| **CH** | JobCloud-Affiliate-Feed (XML/JSON) | Freigabe per E-Mail an `affiliates@jobcloud.ch` | **Antrag nötig** | liefert Titel, Firma, Ort, Link |
| **CH** | Job-Room `api.job-room.ch/jobAdvertisements/v1` | HTTP Basic (SECO-Freigabe) | **401** | Publikations-API für eigene Inserate, keine Marktsuche |
| **CH** | swissdevjobs RSS `swissdevjobs.ch/rss` | keine | **200** | nur Tech-Jobs, kein strukturiertes Orts-/Kontaktfeld |

**Umsetzung:** `scripts/jobs_api.py` nutzt die BA-Quelle (DE) und belegt jede
Stelle mit Screenshot der BA-Detailseite. FR/CH sind bewusst nicht angebunden,
solange kein Zugang bzw. keine Freigabe vorliegt – siehe Grenzen.

## Grenzen (bewusst, dokumentiert)

- **Kein automatischer Versand im Suchlauf.** `run_all.sh` erzeugt nur
  `.eml`-Entwürfe. Ein separater, bewusster Versand ist
  `scripts/jobs_mail.py --send --yes` (bzw. `kmhr-jobs-send.timer`);
  werbliche Ansprache ohne Einwilligung ist in DE (UWG §7), FR (Code de la
  consommation) und CH (UWG) riskant und vorher zu prüfen.
- **Keine erfundenen Adressen.** Adressen stammen ausschließlich aus dem
  Seitentext (mailto/Impressum) oder aus `jobs/empfaenger.csv`. Die vom Nutzer
  benannten Testkontakte (AmeSol Akademie, Asklepios, Helios) haben keine
  hinterlegte Adresse und erzeugen keinen Entwurf.
- **Wayback** antwortet derzeit mit HTTP 523; der Agent dokumentiert das und
  belegt mit Screenshot + HTML-Snapshot.
- **Bot-Schutz** kann Screenshots verhindern; der Beleg vermerkt
  „Beleg fehlgeschlagen" statt zu täuschen.

## Aufruf

```sh
.venv-streamlit/bin/python3 scripts/jobs_agent.py                 # Dry-Run
.venv-streamlit/bin/python3 scripts/jobs_agent.py --max-jobs 12 --per-query 10
.venv-streamlit/bin/python3 scripts/jobs_agent.py --no-screenshots --no-archive
```

Exit `0` = mindestens 10 belegte Stellen, `2` = weniger.

## Arbeitgeber-Mail-Inhalt (02.11.2026)

- **Quelle** wird genannt (`{{QUELLE}}`: Bundesagentur für Arbeit, EURES,
  Job-Room) — aus `jobs/belege/*/index.md` über `jobs_recipients.py`.
- **Ort** nur bei echtem Ortsnamen; BA-Regionalcodes (`DE252`, `DEG03`,
  `DEF0F`) werden verworfen (`jobs_api.py::ort`, `render_mail`).
- **Betreff:** `Ihre Stellenanzeige „…“ – kostenlose, unverbindliche Listung`;
  Stellentitel auf 80 Zeichen an Wortgrenzen gekürzt.
- **Absender:** Mohamed Alarbi Nakti, Geschäftsführer; **Anbieter** Agic
  Tunisie GmbH, Ben Arous; **EU-Vertreter** Batnini Abdelkader.
- **Transparenz:** kostenlose Listung, kein Abo, keine Laufzeitbindung; Daten
  aus öffentlicher Ausschreibung, nur für diese Anfrage; Link `/datenschutz`;
  Opt-out („Abmelden“/„Désabonner“/„Unsubscribe“).
- **Lokaler Test:** `KMHR_PUBLIC_BASE_URL=http://127.0.0.1:8080 python3
  scripts/jobs_recipients.py`; danach `jobs_mail.py --outbox …` als Dry-Run.

## Outbox-Lebensdauer und Kontaktsperre (04.11.2026)

- **Outbox pro Lauf:** `jobs_recipients.py` verschiebt vorhandene
  `jobs/outbox/final/*.eml` nach `jobs/outbox/backup-<YYYYMMDD-HHMMSS>/` und
  leert damit die Outbox; `versand-*.md` bleibt erhalten. Backups älter als
  24 h löscht `rotate_backups()`. `--prepare-only` sichert und leert **nicht**.
- **Sperre auf Firma + Anzeige:** `scripts/jobs_keys.py` bildet
  `firma_key()` (Rechtsform/ASCII normalisiert) und `anzeige_keys()`
  (Anzeigen-ID aus der URL, zusätzlich Titel-Hash). `jobs_recipients.py`
  überspringt gesperrte Kombinationen; `jobs_mail.py` schreibt den Datensatz
  **nur nach erfolgreichem Versand** nach `jobs/ansprache.jsonl` (nicht bei
  Dry-Run oder `--to`).
- **Wirkung:** gleiche Firma + gleiche Anzeige → nie wieder; neue Anzeige
  derselben Firma → erneut. Entwürfe tragen `X-KMHR-Firma` und `X-KMHR-Keys`.
- **Tests:** `tests/test_jobs_keys.py`, `tests/test_jobs_recipients.py`
  (Outbox/Rotation/Sperre), `tests/test_jobs_mail.py` (Sperr-Datensatz).

## Tests

`tests/test_jobs_agent.py` prüft Eignungs-Score (Visum/Anerkennung, kurzer
Text, EU-only), E-Mail-Erkennung ohne Platzhalter, Aggregator-Erkennung,
Arbeitgeber-/Ort-Extraktion, stabile Dateinamen und das Rendern der drei
Sprachvorlagen ohne offene Platzhalter.
