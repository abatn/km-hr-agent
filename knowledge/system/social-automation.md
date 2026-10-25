# Social-Automation — autonomer Marketing-Agent

**Stand:** 25.10.2026 · **Status:** implementiert (Dry-Run-Default) · **Agent:** `marketing/social-agent.md` · **Code:** `scripts/social_agent.py`

## Zweck

Der Social-Agent erzeugt aus realen, aggregierten HR-Daten einen wöchentlichen
Redaktionsplan und publiziert ihn auf LinkedIn, Facebook und Instagram. Er ist
**standardmäßig Dry-Run**; Live-Posting erfordert explizite Konfiguration und
Tokens.

## Kanäle und Formate

| Kanal | Primäre Zielgruppe | Formate | API |
|---|---|---|---|
| LinkedIn | Arbeitgeber DE/FR/CH | Text + Link, Single Image, PDF-Dokument | `/rest/posts` |
| Facebook | Kandidaten Nordafrika | Text + Link, Image, Carousel | Graph `/{page-id}/feed` |
| Instagram | visuelle Arbeitgebermarke | 4:5 Image, Carousel, Reels | Graph `/{ig-user-id}/media` + `media_publish` |

Entscheidung und Quellen: `marketing/ENTSCHEIDUNG.md`.

## OAuth-Bootstrap (einmalig, produktiv)

**Wichtig:** LinkedIn verlangt laut offizieller Doku eine **HTTPS**-Redirect-URI.
`http://localhost:8765` ist deshalb **kein** belastbarer Produktionsweg (und
Meta blockiert Localhost im Live-Modus). Der verbindliche Callback ist:

```text
https://jobs.hanibal-ai.com/oauth/callback
```

Diese URI muss in **beiden** Apps exakt registriert sein. Caddy leitet
`/oauth/callback` an den lokalen Helper auf dem VPS weiter
(`127.0.0.1:8765`); der Helper tauscht den Code gegen Tokens und schreibt sie
nur nach `/opt/km-hr-agent/.env-social` (chmod 600, gitignored).

```bash
# 1) .env-social auf den VPS kopieren (enthält Client Secret/App Secret)
scp .env-social root@176.57.189.201:/opt/km-hr-agent/.env-social
ssh root@176.57.189.201 'chmod 600 /opt/km-hr-agent/.env-social'

# 2) Helper auf dem VPS starten (bindet 127.0.0.1:8765; Caddy macht HTTPS)
ssh -t root@176.57.189.201 \
  'cd /opt/km-hr-agent && .venv-streamlit/bin/python scripts/social_oauth.py linkedin --serve --timeout 600'

# 3) Auth-URL im normalen Browser öffnen, LinkedIn/Facebook bestätigen
# 4) Callback geht an https://jobs.hanibal-ai.com/oauth/callback -> Caddy -> Helper
# 5) Tokens landen in /opt/km-hr-agent/.env-social
```

Für Facebook analog `facebook --serve --page-id <PAGE_ID>`; der Helfer liest
`/me/accounts` und schreibt Page-Token, `FACEBOOK_PAGE_ID` sowie – falls
vorhanden – `INSTAGRAM_USER_ID`/`INSTAGRAM_ACCESS_TOKEN`.

**Fehlerquellen:** Die Redirect-URI muss zeichengenau passen (Schema, Host,
Port, Pfad). `--serve` öffnet **keinen** Browser (WSL/Headless: DBus/GCM/WebGL);
die URL wird manuell geöffnet. Ein alter `--serve`-Prozess blockiert Port 8765:
`ss -ltnp | grep :8765`, dann `kill <PID>`. `--timeout` gibt den Port automatisch
frei. `--listen-port` ändert nur den lokalen Helper-Port; die öffentliche URI
bleibt unverändert.

## Ausführung

```bash
# Dry-Run (Default): Outbox + Plan, kein Netz
.venv-streamlit/bin/python3 scripts/social_agent.py --once --dry-run

# Nur Plan
.venv-streamlit/bin/python3 scripts/social_agent.py --plan

# Live: nur mit Auto-Publish + Tokens
KMHR_SOCIAL_MODE=live KMHR_SOCIAL_AUTO_PUBLISH=1 \
  .venv-streamlit/bin/python3 scripts/social_agent.py --once --live
```

**Autonomie:** `kmhr-social.timer` startet den Agenten täglich um 07:15
(`deploy/systemd/kmhr-social.timer`). Der Timer enqueued **nicht** in die
HR-Queue; er startet denselben Dry-Run-/Live-Agenten. Live bleibt an
`KMHR_SOCIAL_AUTO_PUBLISH=1` gebunden.

## Ausnahme von der MCP-Regel

LinkedIn/Meta/Instagram haben in diesem Repo keinen MCP-Connector. Der
Social-Agent spricht die offiziellen APIs deshalb **direkt** an — ausschließlich
in `scripts/social_agent.py`, nie in UI-Callbacks oder Agent-Tools. Das ist eine
bewusste, hier dokumentierte Ausnahme von der Regel „externe Dienste nur über
MCP-Connectoren"; Tokens liegen nur in `.env-social`.

## Datenquellen (PII-frei)

Erlaubt:

- `jobs`: `id`, `titel`, `standort`, `land`, `stellentyp`, `gehaltsrahmen_min/max`, `erstellt_am` bei `status='aktiv'`.
- `applications`: ausschließlich `COUNT(*)` je `status` (Aggregat).

Verboten (nie selektieren/loggen):

- `candidates` (Name, E-Mail, Telefon, `lebenslauf_text`), `candidate_documents`
- `applications.bewerbungstext`
- `agent_tasks.payload`/`result_json` (enthält `candidate_id`)
- `notifications`, `password_resets`, `language_tests`

Der Guard `assert_no_pii` blockt zusätzlich E-Mail-, Telefon- und
`Kandidat #N`-Muster in gerenderten Posts.

## Planung

- 7-Tage-Plan, ein Post/Tag, Rotation:
  - Mo LinkedIn `new_jobs`
  - Di Facebook `new_jobs`
  - Mi LinkedIn `candidate_tips`
  - Do Facebook `hiring_stats`
  - Fr Instagram `hiring_stats`
  - Sa Facebook `candidate_tips`
  - So LinkedIn `hiring_stats`
- Sprachen: LinkedIn DE, Facebook/Instagram FR; optional `--language de|en|fr|ar`.
- Jeder Post enthält einen KI-Hinweis (EU AI Act Art. 50).

## Konfiguration (`.env-social`, gitignored)

| Variable | Default | Zweck |
|---|---|---|
| `KMHR_SOCIAL_ENABLED` | `1` | Kill-Switch `0` |
| `KMHR_SOCIAL_MODE` | `dry_run` | `dry_run`/`live` |
| `KMHR_SOCIAL_AUTO_PUBLISH` | `0` | Live-Freigabe; `1` nötig |
| `KMHR_SOCIAL_SITE_URL` | `https://jobs.hanibal-ai.com` | Link-Ziel |
| `LINKEDIN_ACCESS_TOKEN` | — | LinkedIn OAuth |
| `LINKEDIN_AUTHOR_URN` | — | `urn:li:person:…` oder `urn:li:organization:…` |
| `LINKEDIN_VERSION` | `202506` | LinkedIn-Version-Header |
| `FACEBOOK_PAGE_ID` / `FACEBOOK_PAGE_ACCESS_TOKEN` | — | Page-Posting |
| `FACEBOOK_SCOPES` | `pages_show_list,pages_manage_posts,pages_read_engagement` | Page-OAuth; Instagram-Scopes erst nach Review |
| `FACEBOOK_FETCH_INSTAGRAM` | `0` | `1` liest `instagram_business_account` aus `/me/accounts` |
| `INSTAGRAM_USER_ID` / `INSTAGRAM_ACCESS_TOKEN` / `INSTAGRAM_IMAGE_URL` | — | IG-Publishing |

Vorlage: `.env-social.example`; Datei mit `chmod 600`. **Nicht** in `.env`,
`.env-runner` oder `.env-email` mischen.

## Outbox und Idempotenz

```text
ergebnisse/social/<YYYY-MM-DD>/
  plan.json
  <plattform>-<thema>.md
  <plattform>-<thema>.json    # Payload/Response/Status
logs/social-agent.log
```

- `post_id` = SHA-256 aus Tag/Plattform/Thema/Text; existiert die JSON-Datei,
  wird der Lauf übersprungen (Ausnahme `--force`).
- Status: `dry_run`, `published`, `failed`, `skipped`, `disabled`.
- Fehler werden mit `error` persistiert; kein `published` ohne `external_id`.

## DSGVO / Recht

- Keine personenbezogenen Daten in Posts, Logs oder Payloads.
- Erfolgsgeschichten nur mit dokumentierter Einwilligung (Art. 6 Abs. 1 lit. a
  DSGVO; §22 KUG bei Porträts). Der MVP postet keine Personenstorys.
- Widerruf → Takedown binnen 7 Tagen; Einwilligungsnachweis separat.
- Post-Assets nach Kampagnenende + 90 Tage löschen; keine Verknüpfung von
  Social-Analytics mit Kandidaten-Datensätzen.
- Plattform-AGB beachten; keine Scraping-/Automatisierungs-Tricks. Facebook-
  Gruppen sind nicht automatisierbar (`publish_to_groups` entfernt).

## Fehlerfälle

| Fall | Verhalten |
|---|---|
| `KMHR_SOCIAL_ENABLED=0` | Lauf `disabled`, rc=0 |
| `KMHR_SOCIAL_MODE=dry_run` | Outbox, kein Netz |
| `mode=live`, Auto-Publish fehlt | Dry-Run mit `reason=approval_required` |
| Token fehlt | `failed` mit Klartext, keine stille Veröffentlichung |
| App Access Token (`app_id\|app_secret`) als Page-Token | `failed` mit Klartext; User-/Page-OAuth nötig |
| HTTP 429/401 | `failed` mit Status/Text; nächster Timer-Lauf |
| Instagram ohne `INSTAGRAM_IMAGE_URL` | `failed` (Instagram braucht Bild) |
| Outbox existiert | `skipped` (idempotent) |

## Tests

```bash
.venv-streamlit/bin/python3 -m pytest tests/test_social_agent.py tests/test_social_oauth.py -q
```

Abgedeckt: 7-Tage-Plan, PII-Guard, Dry-Run ohne Netz, Idempotenz, Live-Gate,
Fake-Adapter, fehlende Tokens, Instagram-Bildpflicht, OAuth-URLs und
`.env-social`-Schreibschutz.

## Quellen

- LinkedIn Posts API: <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api>
- Meta Pages API: <https://developers.facebook.com/docs/pages-api>
- Instagram Content Publishing: <https://developers.facebook.com/docs/instagram-platform/content-publishing>
- DSGVO: <https://eur-lex.europa.eu/eli/reg/2016/679/oj>
