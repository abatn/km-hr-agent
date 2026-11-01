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

- **Kein automatischer E-Mail-Versand.** `--send` ist nicht implementiert;
  werbliche Ansprache ohne Einwilligung ist in DE (UWG §7), FR (Code de la
  consommation) und CH (UWG) riskant. Der Agent liefert fertige `.eml`-Dateien,
  der Versand erfolgt nach Prüfung über `mcp-email-server.py`.
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

## Tests

`tests/test_jobs_agent.py` prüft Eignungs-Score (Visum/Anerkennung, kurzer
Text, EU-only), E-Mail-Erkennung ohne Platzhalter, Aggregator-Erkennung,
Arbeitgeber-/Ort-Extraktion, stabile Dateinamen und das Rendern der drei
Sprachvorlagen ohne offene Platzhalter.
