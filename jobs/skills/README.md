# Skill-Lattice (Job-Akquise)

Jeder erfolgreiche Lauf wird zu einem **wiederverwendbaren Skill**: Quelle,
Land, Branchen, Query-Mapping, Nachweis, Transfer-Ziele. Die Lattice liegt
maschinenlesbar als JSON daneben (`*.json`) und wird von
`scripts/jobs_skill.py` geladen.

## Lattice (Stand 2026-10-31)

| Skill | Land | Quelle | Auth | Branchen | Letzter Erfolg | Transfer |
|---|---|---|---|---|---|---|
| `ba-search` | DE | Bundesagentur-Jobsuche v6/v4 | `X-API-Key: jobboerse-jobsuche` | Pflege, LKW, Handwerk, Hotellerie, **Logistik** (gelernt) | 2026-10-31 | CH, FR |
| `jobroom-search` | CH | Job-Room/SECO `_search` | keine | Pflege, LKW, Handwerk, Hotellerie, **Logistik** (gelernt) | 2026-10-31 | DE |
| `france-travail-search` | FR | Offres d'emploi v2 | OAuth2 (FT_CLIENT_ID/SECRET) | Pflege, LKW, Handwerk, Hotellerie | — (Credentials abgelehnt) | DE, CH |
| `eures-search` | * | EURES public jv-search | keine | Pflege, LKW, Handwerk, Hotellerie | 2026-10-31 | DE, FR, CH, AT |
| `arbeitnow-search` | DE/EU | Arbeitnow Job-Board-API | keine | Pflege, LKW, Handwerk, Hotellerie | — (0 Treffer) | AT, CH |
| `websearch-fallback` | * | Anysearch MCP | Header | Pflege, LKW, Handwerk, Hotellerie | 2026-10-31 | DE, FR, CH |

## Transfer-Test (Zero-Shot, gleiche Branche „Krankenpflege")

| Land | Skill | Ergebnis | Treffer | Beispiel |
|---|---|---|---|---|
| DE | `ba-search` | **OK** | 10 | Permacon GmbH |
| CH | `jobroom-search` | **OK** | 50 | Stiftung entero |
| * | `eures-search` | **OK** | 10 | Alloheim Senioren-Residenzen SE |
| FR | `france-travail-search` | FAIL | 0 | Credentials fehlen |
| DE | `arbeitnow-search` | FAIL | 0 | nur Tech-Jobs im Feed |
| * | `websearch-fallback` | FAIL | 0 | API verlangt neuen Key |

**Zero-Shot-Erfolg: 3/6.** Der Pflege-Skill aus DE funktioniert in CH
(Job-Room) ohne Anpassung; FR scheitert nur an fehlenden Credentials, nicht an
der Suchlogik.

## Form-Designer (Lernen durch neue Aufgaben)

`python3 scripts/jobs_skill.py forms` erzeugt Kombinationen (Land × Branche ×
Stadt), prüft sie mit vorhandenen Skills und **erweitert den Skill**, wenn eine
neue Branche erfolgreich war.

| Land | Branche | Stadt | Skill | Ergebnis | Gelernt |
|---|---|---|---|---|---|
| DE | Pflege/LKW/Handwerk/Hotellerie | Berlin | `ba-search` | OK (je 10) | – |
| CH | Pflege/LKW/Handwerk/Hotellerie | Zürich | `jobroom-search` | OK (je 50) | – |
| FR | alle vier | Lyon | `france-travail-search` | FAIL | – (Credentials) |
| DE | **Logistik** | Berlin | `ba-search` | OK (10) | **ja** |
| CH | **Logistik** | Zürich | `jobroom-search` | OK (50) | **ja** |

Bericht: `jobs/belege/skills-2026-10-31/report.md`

## Prinzip

1. **Induktion:** Ein Lauf, der ≥1 Treffer mit Arbeitgeber liefert, wird als
   Skill gespeichert (Quelle, Auth, Query-Mapping, Nachweis).
2. **Transfer:** Neue Länder/Branchen werden zuerst mit vorhandenen Skills
   getestet (Zero-Shot). Erfolg wird gemessen, nicht behauptet.
3. **Lernen:** Scheitert eine Kombination, wird entweder der Skill erweitert
   (neue Branche) oder die Lücke dokumentiert (fehlende Credentials/Quelle).
4. **Ehrlichkeit:** Kein Skill wird als „funktioniert" geführt, wenn der
   Nachweis fehlt (`last_success = null`).

## Aufrufe

```sh
python3 scripts/jobs_skill.py list
python3 scripts/jobs_skill.py probe --skill ba-search --industry Krankenpflege
python3 scripts/jobs_skill.py transfer --industry Krankenpflege
python3 scripts/jobs_skill.py forms
```


## Neue Quellen (geprüft 31.10.2026)

| Quelle | Auth | HTTP | Branchen | Urteil |
|---|---|---|---|---|
| **EURES** `europa.eu/eures/api/.../jv-search/search` | keine | 200 | alle vier, DE/FR/CH/AT | **angebunden** (`eures-search`) |
| **Jobtechdev (SE)** `jobsearch.api.jobtechdev.se/search` | keine | 200 | alle vier | gut, aber nur Schweden |
| Arbeitnow | keine | 200 | 2/600 Pflege, 0 Gastro | unbrauchbar für unsere Branchen |
| jobs.ch `api/v1/public/search` | keine | 200 | alle vier | `robots.txt` verbietet `/api/` → nicht angebunden |
| AMS AT / Job-Room-SPA | Auth | 401/405 | – | nicht nutzbar |


## Frankreich ohne France-Travail-Credentials (31.10.2026)

| Lösung | Auth | Test | Ergebnis | Verdikt |
|---|---|---|---|---|
| **EURES** `europa.eu/eures/api/.../jv-search/search` | keine | 200 | **5 FR-Stellen** (Pflege, LKW, Handwerk, Gastro) | **primaer, angebunden** (`eures-search`) |
| iQuesta MCP `mcp.iquesta.com/api/mcp` | keine | initialize OK | **0 Treffer** für alle vier Branchen | untauglich (stage-/IT-lastig) |
| **LHR** `lhotellerie-restauration.fr/emploi-<metier>/france` | keine | 200, JSON-LD | **6 Gastro-Stellen** (Arbeitgeber, Ort, Titel) | **angebunden** (`lhr-search`) |
| **Journal des Palaces RSS** `journaldespalaces.com/carriere/feed/rss.xml` | keine | 200, RSS | 1.899 FR-Items, Luxus-Hotellerie | Option, nicht angebunden |
| Apify France-Travail-Actors | APIFY_TOKEN | 402 ohne Token | ab $0,80/1K, robots sperren Keyword-Suche | **nicht empfohlen** |
| La Bonne Alternance | Key | 401 | – | nicht ohne Key |
| ODS-Portale (Tours, IdF, Seine-Saint-Denis) | keine | 200 | nur Verwaltungsstellen bzw. Snapshot 27.08.2026 | kein Markt-Feed |
| HelloWork/Meteojob/Jobijoba | – | 404/403 | kein offener JSON-Endpunkt | nein |


## Adzuna entfernt (31.10.2026)

Adzuna wurde **vollständig entfernt**: Adapter, Tests, Skill-JSON und alle
Erwähnungen. Grund: Der Free-Tier ist laut ToS nur zur Evaluierung/14 Tage
kommerziell nutzbar – für ein kommerzielles Projekt ungeeignet.


## Automatische Induktion, Transfer und Selbstverbesserung (31.10.2026)

### Induktion (`jobs_induce.py induce`)

Liest alle Beleg-Läufe und leitet generalisierte Skills je (Land, Branche,
Quelle) ab:

- **47 Belege → 18 Skills** (`jobs/skills/lattice.json`)
- Beispiel: `CH Hotellerie jobroom-search n=2`, `FR Hotellerie lhr-search n=6`

### Transfer (`jobs_induce.py transfer`)

| Land | Branche | Skill | Ergebnis |
|---|---|---|---|
| DE | alle vier | `ba-search` | OK (je 10) |
| CH | alle vier | `jobroom-search` | OK (je 50) |
| FR | Pflege/LKW/Handwerk | `eures-search` | OK (je 10, französische Arbeitgeber) |
| FR | Hotellerie | `lhr-search` | OK (20) |

**Zero-Shot-Erfolg: 12/12** – alle vier Branchen in allen drei Ländern.
Details: `jobs/skills/transfer.md`

### Selbstverbesserung (`jobs_induce.py forms`)

Form-Designer prüft Land × Branche × Stadt. Ergebnis: **12/12 lösbar**, keine
Lücke. Für den Nachweis echter Selbstverbesserung wurde eine **neue
Kombination** erschlossen:

```sh
python3 scripts/jobs_induce.py discover --country at --industry Hotellerie
→ 10 Treffer (Beispiel: Mag. Andreas Steinbauer)
→ neuer Skill eures-at automatisch geschrieben
```

Dokumentation: `jobs/skills/self_improvement.md`

### Neue Quelle (selbst gefunden)

**Journal des Palaces RSS** (`journaldespalaces.com/carriere/feed/rss.xml`):
keyfrei, 2.075 Items, 1.899 France – Luxus-/Gastro-Segment. Angebunden als
`jdp-search`, 4 Stellen belegt (`jobs/belege/2026-10-31-jdp/`).


## FORGE-Transfer auf Formulare (31.10.2026)

Dasselbe Prinzip (Genom → Zero-Shot-Transfer → Varianten) auf Formulare:

- **Lernen:** `scripts/forge_forms.py` extrahiert aus dem PayAPI-Checkout
  (`tests/fixtures/forge/payapi.html`) ein Form-Genom mit **13 Semantiken**
  (`jobs/skills/form_genome_payapi.json`).
- **Transfer:** Genom auf nie gesehene Formulare anwenden, ohne Anpassung.

| Zielformular | Felder | korrekt | Quote |
|---|---:|---:|---:|
| Bewerbung (`apply.html`) | 10 | 10 | **100%** |
| Behörde (`behoerde.html`) | 12 | 8 | 67% |
| Variante `shuffle` | 10 | 10 | 100% |
| Variante `synonyme` (FR-Labels) | 10 | 10 | 100% |
| Variante `decoy` | 10 | 10 | 100% |
| **Gesamt** | **52** | **48** | **92%** |

**Ehrliche Lücken (Behörde):** `birthdate`, `nationality`, `passport`,
`purpose` sind im Payment-Genom nicht enthalten und bleiben leer. Das ist die
Grenze des Zero-Shot-Transfers, nicht ein Fehler des Matchers.

Bericht: `jobs/skills/forge_transfer.md` · Tests: `tests/test_forge_forms.py`
