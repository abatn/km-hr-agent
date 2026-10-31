# Laufbericht Job-Akquise – 2026-10-31

## Quellen (recherchiert, getestet, belegt)

| Land | Quelle | Auth | Status |
|---|---|---|---|
| **DE** | BA-Jobsuche `pc/v6/jobs` + `pc/v4/jobdetails/{base64}` | `X-API-Key: jobboerse-jobsuche` (öffentlich) | **12 Stellen belegt** |
| **CH** | Job-Room/SECO `POST job-room.ch/jobadservice/api/jobAdvertisements/_search` | keine | **7 Stellen belegt** |
| **FR** | France Travail „Offres d'emploi v2" | OAuth2 | **App ohne API-Abo**: Credentials gültig, aber `invalid_scope` („No scope requested and no default scope configured") |
| **EU** | EURES public jv-search | keine | **17 Stellen belegt** (12 DE/FR gemischt + 5 FR-only) |
| **CH** | Job-Room/SECO | keine | 7 Stellen belegt |

### GitHub-Recherche (3 Agenten)

| Repo | ★ | Quelle | Ohne Credentials? | Verdikt |
|---|---|---|---|---|
| `JoJoLaBagarre/france-travail-mcp` | 1 | FT v2 + ROME | nein | bester FT-MCP, aber Credentials nötig |
| `mohamed-amine-ben-mallessa/francetravail-mcp` | 0 | FT v2 | nein | dependency-frei, unpubliziert |
| `nigifabio/swiss-job-agent` | 0 | jobs.ch/jobup/Job-Room/ATS | Default nein (ToS) | nur mit `PROVIDERS=jobroom;ats` |
| `Stupidoodle/swissdevjobs-cli` | 103 | swissdevjobs + JobCloud | ja | nur IT, JobCloud-Pfad ToS-widrig |
| `lucasnevespereira/swizjobsbot` | 1 | Google Jobs/SerpApi | nein (kostenpflichtig) | nicht nutzbar |
| `slopinger/arbeitsagentur-mcp` | 1 | BA v6/v4 | ja | kein Mehrwert gegenüber direkter API |
| `fabkho/amt` | 3 | BA + ATS | ja | Jobsuchenden-Tool, kein Visa-Filter |
| `wunderfrucht/jobsuche-mcp-server`, `mcp-bajobs` | 3/– | BA **v4-Suche** | ja | **defekt** (v4 → 403 seit 09/2026) |

**Fazit:** Kein fremder MCP war nötig oder besser. Die direkten APIs liefern
dieselben Daten ohne zusätzliche Abhängigkeit; Visa-/Sprachfilter gibt es
nirgends und bleibt eigene Logik.

## Echte Läufe

```sh
# DE (Bundesagentur)
.venv-streamlit/bin/python3 scripts/jobs_api.py --max-jobs 12 --min-jobs 10
# CH (Job-Room)
.venv-streamlit/bin/python3 scripts/jobs_ch.py --max-jobs 8 --max-captures 12
```

| Kennzahl | DE | CH |
|---|---|---|
| Stellen | **12** | **7** |
| Branchen | 3 × Pflege, 3 × LKW, 3 × Handwerk, 3 × Hotellerie | 2 × Pflege, 2 × LKW, 1 × Handwerk, 2 × Hotellerie |
| Belegdateien | 37 | 21 |
| Veröffentlichte Kontaktadressen | 4 | 0 |

**Gesamt: 19 echte Arbeitgeber-Stellen** aus DE und CH, jede mit Screenshot,
HTML-Snapshot, Quell-URL und Abrufdatum.

- Übersicht DE+CH: `jobs/belege/2026-10-31/gesamt.md`
- DE: `jobs/belege/2026-10-31/index.md`
- CH: `jobs/belege/2026-10-31-ch/index.md`
- Entwürfe: `jobs/outbox/2026-10-31/` und `jobs/outbox/2026-10-31-ch/`

## E-Mail-Akquise (produktionsreif)

- `scripts/jobs_mail.py` versendet über `mcp-email-server.py` (MCP-Protokoll).
- **Pflicht:** Abmelde-Option (`Abmelden`/`Unsubscribe`/`Désabonner`) – Mails
  ohne sie werden verworfen (UWG §7).
- **Dedupe:** eine Mail pro Empfänger (22 Dateien → 6 eindeutige Adressen).
- **Dry-Run:** `python3 scripts/jobs_mail.py --limit 10` zeigt die Empfänger.
- **Echter Lauf:** `--send --yes --to batniniabdelkader@yahoo.com --limit 3`
  → **3/3 gesendet** (Betreff `[TEST] …`), Log: `jobs/outbox/2026-10-31/versand-223931.md`.
- **Kein Kaltversand an Arbeitgeber.** Echte Adressen nur mit `--allow-real`.

## Harte Grenze: Frankreich

France Travail verlangt OAuth2 mit `client_id`/`client_secret`. Die Registrierung
ist kostenlos, aber ein Konto kann ich nicht für dich anlegen (E-Mail-
Bestätigung). Ohne Credentials liefert die API 401, der Katalog antwortet 403.
Es gibt **keinen** öffentlichen Live-Feed mit Arbeitgeber + Titel (der einzige
key-freie Datensatz ist ein eingefrorener 150-Offer-Snapshot aus Saint-Denis).

**Was du tun musst (verifiziert 31.10.2026):**
1. `https://francetravail.io` → deine Anwendung → **Abonnements** →
   „Offres d'emploi v2" hinzufügen und bestätigen (die App hat aktuell **keine**
   Scopes; ohne Scope antwortet der Token-Endpunkt mit `invalid_scope`).
2. Danach genügen die bereits eingetragenen `FT_CLIENT_ID`/`FT_CLIENT_SECRET`
   in `.env-runner` – keine Codeänderung.
3. `python3 scripts/jobs_fr.py` (Mock-Beweis: `python3 scripts/jobs_fr.py --mock`).

Fehlerhistorie: erste Credentials → `invalid_client` (Secret falsch). Neue
Credentials → `invalid_scope` (App hat kein API-Abo). Der Adapter selbst ist
durch den Mock-Lauf belegt.

## Nächste Schritte

1. FR-Credentials besorgen (siehe oben) → drittes Land anbinden.
2. E-Mail-Adressen der drei Testkontakte in `jobs/empfaenger.csv` eintragen.
3. Versand über `mcp-email-server.py` freigeben (dann `--send` mit Abmeldelogik).


## Frankreich-Lauf ohne France-Travail (31.10.2026)

```sh
python3 scripts/jobs_eures.py --country fr --max-jobs 8 --per-quota 3 --min-jobs 5
```

| Kennzahl | Wert |
|---|---|
| Stellen | **5** (je Branche mind. 1) |
| Belege | `jobs/belege/2026-10-31-eures-fr/` |
| Gefundene Kontaktadressen | 7 (über alle Läufe) |

**Adzuna wurde entfernt** (Free-Tier nur Evaluierung, kommerziell lizenzpflichtig).
**iQuesta** wurde getestet und verworfen: 0 Treffer für Pflege/LKW/Handwerk/
Gastronomie. **Apify** ist technisch möglich, aber kostenpflichtig und die
FT-robots sperren die Keyword-Suche – nicht empfohlen.

### Hotellerie/Gastronomie: LHR angebunden

`lhotellerie-restauration.fr` ist keyfrei, robots erlaubt die Stellenpfade und
die Detailseiten liefern JSON-LD (`hiringOrganization.name`, Ort, Datum).

| Kennzahl | Wert |
|---|---|
| Stellen | **6** (Cuisinier, Serveur, Chef de partie, …) |
| Belege | `jobs/belege/2026-10-31-lhr/` |
| Arbeitgeber | BABEL FOOD, BRASSERIE LAURA, … (echte Namen) |

Frankreich gesamt: **11 Stellen** aus allen vier Branchen (5 EURES + 6 LHR).


## Autonomie-Nachweis (31.10.2026)

| Schritt | Ergebnis |
|---|---|
| Induktion aus Belegen | **47 Belege → 18 Skills** (`jobs/skills/lattice.json`) |
| Zero-Shot-Transfer | **12/12** (4 Branchen × DE/CH/FR) |
| Form-Designer | 12/12 lösbar |
| Autonome Erschließung | `discover --country at --industry Hotellerie` → 10 Treffer → Skill `eures-at` |
| Neue Quelle | Journal des Palaces RSS (`jdp-search`), 4 Stellen belegt |


## FORGE-Formtransfer (31.10.2026)

| Kennzahl | Wert |
|---|---|
| Genom (PayAPI) | 13 Semantiken |
| Bewerbung (nie gesehen) | **10/10 = 100%** |
| Behördenformular | 8/12 = 67% (4 Felder nicht im Genom) |
| Varianten (shuffle/synonyme/decoy) | je 10/10 |
| **Zero-Shot gesamt** | **48/52 = 92%** |

Code: `scripts/forge_forms.py` · Bericht: `jobs/skills/forge_transfer.md`


## E-Mail-Akquise: finale Empfängerliste (31.10.2026)

`python3 scripts/jobs_recipients.py` verbindet alle Beleg-Läufe mit der Akquise.

| Kennzahl | Wert |
|---|---|
| Belegte Stellen (dedupliziert) | **36** |
| Priorität 1 (direkte E-Mail) | **7** |
| Priorität 2 (Kontaktformular/Website) | 29 |
| Personalisierte Entwürfe | 7 (`jobs/outbox/final/`) |

**Priorität 1 – kontaktiert (Dry-Run):**

| Land | Arbeitgeber | E-Mail | Vorlage |
|---|---|---|---|
| CH | iPersonal AG | info@ipersonal.ch | DE |
| DE | ARWA Personaldienstleistungen | pirna@arwa.de | DE |
| DE | BUHL Personal GmbH | bewerbung-berlin.personal@buhl-gruppe.de | DE |
| DE | Permacon GmbH | gerrit.maronde@permacon.de | DE |
| DE | Piening GmbH | muenchen@pieninggmbh.de | DE |
| DE | Younivers GmbH | recruiting@younivers.org | DE |
| FR | Association ALHPI | recrutement@alhpi.com | FR |

**Dry-Run:** `python3 scripts/jobs_mail.py --outbox jobs/outbox/final --limit 20`
→ 7 versandbereit, 0 verworfen (Abmelde-Option in allen Mails).

**Echter Versandnachweis:** 3/3 Mails über `mcp-email-server.py` an die
Testadresse (`[TEST] …`), Log `jobs/outbox/2026-10-31/versand-223931.md`.

**Nicht kontaktiert (ehrlich):** 29 Arbeitgeber ohne veröffentlichte Adresse –
Kontakt nur über Formular/Website. Keine Adresse wurde erfunden.

## Reproduzierbarkeit & Cron (01.11.2026)

Ein Befehl startet den kompletten Ablauf:

```sh
./run_all.sh --quick     # kleiner Beweislauf (55 s)
./run_all.sh             # Standard (12/8/12/6/4 Stellen)
JOBS_ENRICH=1 ./run_all.sh   # + Impressum-/Kontakt-Recherche
```

**Beweislauf 01.11.2026, 00:22:46–00:23:41 (rc=0):**

| Schritt | Ergebnis |
|---|---|
| BA (DE) | 2 Stellen |
| Job-Room (CH) | 1 Stelle |
| EURES | 2 Stellen |
| LHR (FR) | 1 Stelle |
| Journal des Palaces | 1 Stelle |
| Belege neu | 26 Dateien in 5 Läufen |
| Empfängerliste | 36 Zeilen |
| E-Mail-Entwürfe | 14 |
| Transfer | **12/12** |
| Form-Designer | 12/12 |
| Log | `logs/jobs-agent-2026-11-01.log` (7,6 KB) |

**Cron:** `deploy/systemd/kmhr-jobs.timer` (täglich 06:00, `RandomizedDelaySec=300`,
`Persistent=true`) oder `deploy/cron/kmhr-jobs.cron`; Log-Rotation über
`deploy/logrotate/kmhr-jobs` (14 Tage, komprimiert). Versand nur 08:00–20:00
(`jobs_mail.py` verweigert sonst). Details: `jobs/CRON.md`.
