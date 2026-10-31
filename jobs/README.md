# Job-Akquise-Agent (Jobs.hanibal-ai.com)

Sucht Stellen in DE/FR/CH (Krankenpflege, LKW, Handwerk, Hotellerie), prüft die
Eignung für ausländische Kandidaten, belegt jede Stelle und erzeugt Anschreiben.

## Aufruf

```sh
# Offizielle Quelle DE (Bundesagentur-Jobsuche) – empfohlen
.venv-streamlit/bin/python3 scripts/jobs_api.py --max-jobs 12

# Schweiz (Job-Room/SECO, ohne Key)
.venv-streamlit/bin/python3 scripts/jobs_ch.py --max-jobs 8

# Frankreich (France Travail, OAuth2 – braucht FT_CLIENT_ID/SECRET)
.venv-streamlit/bin/python3 scripts/jobs_fr.py

# Fallback: allgemeine Websuche (anysearch) – liefert oft Job-Boersen
.venv-streamlit/bin/python3 scripts/jobs_agent.py

# Mehr/weniger Stellen, ohne Screenshots, ohne Archivversuch
.venv-streamlit/bin/python3 scripts/jobs_agent.py --max-jobs 15 --per-query 10
.venv-streamlit/bin/python3 scripts/jobs_agent.py --no-screenshots --no-archive
```

Exit-Codes: `0` = mindestens 10 Stellen belegt, `2` = weniger als 10.

## Ausgaben

| Pfad | Inhalt |
|---|---|
| `jobs/belege/<datum>/index.md` | Tabelle: Arbeitgeber, Stelle, Ort, Land, Branche, Eignung, Kontakt, Quelle |
| `jobs/belege/<datum>/<slug>.md` | Einzelbeleg mit URL, Abrufdatum, Archiv-Link, Screenshot, HTML-Snapshot |
| `jobs/belege/<datum>/<slug>.png` | Screenshot der Originalseite (Playwright) |
| `jobs/belege/<datum>/<slug>.html` | HTML-Snapshot der Originalseite |
| `jobs/empfaenger.csv` | Empfängerliste; E-Mail nur, wenn auf der Seite veröffentlicht |
| `jobs/outbox/<datum>/*.eml` | gerenderte Anschreiben (DE/EN/FR) |
| `jobs/belege-web/<datum>/` | archivierter Lauf der allgemeinen Websuche |

## Eignungsprüfung

`scripts/jobs_agent.py::suitability` bewertet den Seitentext deterministisch
(kein LLM): Visum/Arbeitserlaubnis, Anerkennung, Relocation, Sprachlevel,
Internationalität — plus Abzug für Seiten ohne verwertbaren Text. Stellen unter
`--min-score` (Default 45) werden verworfen.

## Grenzen (ehrlich)

- **Kein automatischer Versand.** `--send` ist bewusst nicht implementiert:
  Werbliche E-Mail an Unternehmen ist ohne Einwilligung in DE/FR/CH rechtlich
  riskant (UWG §7, Code de la consommation, UWG CH). Der Agent liefert
  fertige `.eml`-Dateien; der Versand erfolgt nach Prüfung manuell über
  `mcp-email-server.py`.
- **Keine erfundenen Adressen.** Adressen stammen aus dem Seitentext
  (mailto/Impressum) oder aus `jobs/empfaenger.csv`. Die drei vom Nutzer
  benannten Testkontakte (AmeSol, Asklepios, Helios) haben **keine**
  hinterlegte Adresse und erzeugen daher keinen Entwurf.
- **Archiv-Link:** Wayback-Save antwortet derzeit mit HTTP 523; der Agent
  vermerkt das im Beleg und belegt stattdessen mit Screenshot + HTML-Snapshot.
- **Screenshots** können bei Bot-Schutz fehlschlagen; der Beleg nennt dann
  „Beleg fehlgeschlagen“.
