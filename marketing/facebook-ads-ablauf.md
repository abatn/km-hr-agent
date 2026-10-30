# Facebook-Ads-Ablauf — Konfiguration und Betrieb

**Geltung:** beschreibt den im Code implementierten Live-Pfad für Meta/Facebook.
**Normative Grenzen:** `marketing/ADS_ENTSCHEIDUNG.md` (Entscheidungen) und `marketing/ads-agent.md` (Agent-Regeln).
**Code:** `scripts/meta_ads.py` (`MetaConfig`, `MetaAdsClient.preflight`, `launch`, `activate`, `ensure_video`, `ensure_thumbnail`), `scripts/ads_agent.py` (`--check-meta`, `--live`, `--activate`).

## 1. Grundsatz

1. **PAUSED-first:** `launch()` legt Kampagne, AdSet, Creative und Ad ausschließlich mit `status=PAUSED` an. Es gibt keinen Code-Pfad, der ACTIVE erzeugt.
2. **Aktivierung ist menschlich:** nur `--activate <key> --yes` bei `KMHR_ADS_DAILY_CAP_EUR > 0`. Der Agent entscheidet nie selbst.
3. **Beschäftigungskategorie:** jede Meta-Kampagne trägt `special_ad_categories=["EMPLOYMENT"]`; Targeting ohne Geschlecht, ohne PLZ, ohne Lookalikes/Ausschlüsse.
4. **Kein Personenbezug:** nur Aggregate; keine Bewerber-, Aufgaben- oder Kontaktdaten an Meta.

## 2. Voraussetzungen (einmalig, nur ein Mensch)

1. **Werbekonto** in Meta Business anlegen, Rechtsperson/Rechnungsdaten hinterlegen, **Zahlungsmittel** hinzufügen.
2. **Facebook-Seite** als Anzeigengeber; Rolle „Anzeigen verwalten“ für den handelnden Nutzer.
3. **Token mit `ads_management`** (Graph API Explorer, App `2263359441188320`). Nutzer-Token oder Page-Token der Zielseite. Bei Page-Token liest der Preflight die Scopes per `debug_token`; dafür `META_APP_ID`/`META_APP_SECRET` setzen.
4. **DSA-Begünstigter und -Bezahler** eintragen (Pflicht für Zielgruppe DE/FR/CH).

## 3. Konfiguration (`.env-social`, `chmod 600`)

| Variable | Pflicht | Default | Bedeutung |
|---|---|---|---|
| `META_AD_ACCOUNT_ID` | ja | — | Werbekonto, mit oder ohne Präfix `act_` |
| `META_ADS_ACCESS_TOKEN` | ja | — | Token mit `ads_management` (Fallbacks: `FACEBOOK_ADS_ACCESS_TOKEN`, `FACEBOOK_PAGE_ACCESS_TOKEN`) |
| `FACEBOOK_PAGE_ID` | ja | — | Seite als Anzeigengeber |
| `META_DSA_BENEFICIARY` | ja (EU) | — | DSA-Begünstigter |
| `META_DSA_PAYOR` | ja (EU) | — | DSA-Bezahler |
| `META_GRAPH_VERSION` | nein | `v26.0` | Graph-API-Version |
| `META_ADS_CURRENCY` | nein | `EUR` | Muss zur Kontowährung passen, sonst verweigert der Preflight |
| `META_APP_ID` / `META_APP_SECRET` | bei Page-Token | — | Scope-Prüfung via `debug_token` (Alternativen: `FACEBOOK_APP_ID`/`FACEBOOK_APP_SECRET`) |
| `META_VIDEO_ID` | nein | — | Bereits im Werbekonto vorhandene Video-ID (bevorzugt) |
| `META_VIDEO_URL` | nein | — | Öffentliche Video-URL für `advideos` |
| `META_VIDEO_PATH` | nein | — | Lokale Videodatei für `advideos` |
| `META_VIDEO_THUMBNAIL_PATH` | bei Video | — | Lokales Miniaturbild → `adimages` → `image_hash` |
| `META_VIDEO_THUMBNAIL_URL` | bei Video | — | Alternative öffentliche Thumbnail-URL |
| `KMHR_ADS_CHANNELS` | für Live | `google_ads,microsoft_ads` | Für Meta-Live: `meta_ads` |
| `KMHR_ADS_LIVE_CONFIRM` | für Live | — | Muss `1` sein |
| `KMHR_ADS_DAILY_CAP_EUR` | für Live | `0` | Tagescap in EUR; `0` blockiert Anlage **und** Aktivierung |
| `KMHR_ADS_APPROVAL_FILE` | für Live | — | JSON mit Kampagnen-Freigaben, z. B. `{"campaigns": {"employers_eu": 3.0}}` |

Ohne Videoquelle entsteht eine **Link-Anzeige** (`link_data`), mit Video eine **Video-Anzeige** (`video_data`). Vorlage: `.env-social.example`.

## 4. Objektkette und Pflichtfelder

Quelle der Felder: `MetaAdsClient.launch()` in `scripts/meta_ads.py`.

**Kampagne** (`POST /act_<id>/campaigns`)

| Feld | Wert | Warum |
|---|---|---|
| `objective` | `OUTCOME_TRAFFIC` | Konstante `OBJECTIVE` |
| `status` | `PAUSED` | PAUSED-first |
| `buying_type` | `AUCTION` | — |
| `special_ad_categories` | `["EMPLOYMENT"]` | Beschäftigungswerbung ist Pflichtkategorie |
| `special_ad_category_country` | Targeting-Länder | **Meta-2026-Pflicht**; fehlt es, blockiert Meta mit Subcode `2909035` |
| `is_adset_budget_sharing_enabled` | `false` | **Meta-2026-Pflicht** bei AdSet-Budget; sonst Subcode `4834011` |

**AdSet** (`POST /act_<id>/adsets`)

| Feld | Wert |
|---|---|
| `daily_budget` | Cap-Anteil in Cent (`cents()`) |
| `billing_event` | `IMPRESSIONS` |
| `optimization_goal` | `LANDING_PAGE_VIEWS` |
| `bid_strategy` | `LOWEST_COST_WITHOUT_CAP` |
| `destination_type` | `WEBSITE` |
| `status` | `PAUSED` |
| `targeting.geo_locations.countries` | `["DE","FR","CH"]` bzw. `["MA","DZ","TN","EG"]` |
| `targeting.age_min` / `age_max` | `18` / `65` |
| `targeting.targeting_automation.advantage_audience` | `0` |
| Geschlecht | **Feld fehlt bewusst** = alle Geschlechter |

**Creative** (`POST /act_<id>/adcreatives`, `object_story_spec`)

- `page_id` = `FACEBOOK_PAGE_ID`
- Video: `video_data` mit `video_id`, `message`, `link_description`, `call_to_action` (`LEARN_MORE` + Link) und **zwingend** `image_hash` (aus `adimages`) oder `image_url`
- Ohne Video: `link_data` mit `message`, `link`, `name` (Headline), `call_to_action`

**Ad** (`POST /act_<id>/ads`)

- `adset_id`, `creative.creative_id`, `status=PAUSED`
- `dsa_beneficiary`, `dsa_payor`

**Reihenfolge:** Video und Thumbnail werden **vor** der Kampagne hochgeladen. Schlägt der Upload fehl, entsteht kein verwaistes Kampagnen-/AdSet-Objekt.

## 5. Segmente und Targeting

Quelle: `SEGMENTS`/`targeting_for()` in `scripts/ads_agent.py`.

| Segment | Label | Länder | Alter |
|---|---|---|---|
| `employers_eu` | Arbeitgeber DE/FR/CH | `DE`, `FR`, `CH` | 18–65, alle Geschlechter |
| `candidates_north_africa` | Kandidaten Nordafrika | `MA`, `DZ`, `TN`, `EG` | 18–65, alle Geschlechter |

Die Zielgruppengröße für Nordafrika wird **nicht geschätzt** (`audience_size` bleibt `None`, siehe `marketing/ADS_ENTSCHEIDUNG.md`).

## 6. Video-Ad im Detail

1. **Upload:** `POST https://graph-video.facebook.com/v26.0/act_<Konto>/advideos` mit `source` (Multipart, lokale Datei) oder `file_url`. Antwort liefert `video_id`.
2. **Thumbnail:** `POST /act_<Konto>/adimages` mit lokaler Datei liefert `image_hash`; alternativ `image_url`. Ohne Miniaturbild keine Video-Ad (Meta-Subcode `1443226`).
3. **Creative:** `video_data` wie oben; **kein** `link_data` bei Video.
4. **Format:** MP4/MOV, H.264/AAC; 9:16 (1080×1920) für Reels/Stories, 4:5 oder 1:1 für den Feed.
5. **Page-Token-Gotcha:** Der Multipart-Upload nach `advideos` kann mit Page-Token an `code=1 — An unknown error has occurred` scheitern, obwohl `ads_management` erteilt ist. Workaround: vorhandene `META_VIDEO_ID` aus dem Werbekonto verwenden (kein Neu-Upload).
6. **Verifikation:** Nach `--live` prüft man im Ads Manager, ob Creative, Thumbnail und Vorschau korrekt sind; erst dann `--activate`.

## 7. Ablauf Schritt für Schritt

```bash
# 0) Konfiguration prüfen (nennt jeden Blocker im Klartext)
.venv-streamlit/bin/python3 scripts/ads_agent.py --check-meta

# 1) Freigabe je Kampagne (Tagesbudget in EUR)
cat > freigabe.json <<'JSON'
{"campaigns": {"employers_eu": 3.0}}
JSON

# 2) PAUSED anlegen (kein Euro fließt, keine Auslieferung)
KMHR_ADS_CHANNELS=meta_ads \
KMHR_ADS_LIVE_CONFIRM=1 \
KMHR_ADS_DAILY_CAP_EUR=3 \
KMHR_ADS_APPROVAL_FILE=freigabe.json \
  .venv-streamlit/bin/python3 scripts/ads_agent.py --live

# 3) Im Ads Manager prüfen
#    https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=<Konto>

# 4) Bewusst scharf schalten (nur dieser Schritt erzeugt ACTIVE)
KMHR_ADS_DAILY_CAP_EUR=3 \
  .venv-streamlit/bin/python3 scripts/ads_agent.py --activate employers_eu --yes

# 5) Ausgaben/Aggregate abholen
#    meta_ads.MetaAdsClient.insights(campaign_id, since, until)
```

**Ergebnis von Schritt 2:** `ergebnisse/ads/<Datum>/run.json` mit `mode: "live_paused"`, je Kampagne `meta.campaign_id`, `adset_id`, `creative_id`, `ad_id`, `creative_type` (`video`/`link`), `video_id` und Status `paused_created`. Bei fehlender Konfiguration bleibt `run.json` als Beweis erhalten, der Lauf endet mit `rc=2`.

## 8. Vorabprüfung (`--check-meta`) — was geprüft wird

Quelle: `MetaAdsClient.preflight()`.

- Pflichtvariablen vorhanden (`ad_account_id`, `token`, `page_id`)
- Token-Typ (`/me`): User- oder Page-Token; bei Page-Token Scopes via `debug_token`
- `ads_management` erteilt (sonst Blocker); `pages_read_engagement` (Warnung)
- Konto: `account_status` (blockierende Status `2,3,7,100,101`), `disable_reason`, `funding_source_details`, Währung = `META_ADS_CURRENCY`
- Seite lesbar (Page-Rolle)
- DSA-Felder gesetzt
- Video: Datei/Thumbnail existiert; Video ohne Thumbnail = Blocker
- Ergebnis: `blockers`, `warnings`, `next_steps`, `ok`

## 9. Fehlerbilder und Gegenmaßnahmen

| Symptom / Subcode | Ursache | Lösung |
|---|---|---|
| `4834011` | `is_adset_budget_sharing_enabled` fehlt bei AdSet-Budget | Code setzt `false`; nicht entfernen |
| `2909035` | `special_ad_category_country` fehlt/uneinheitlich | Länderliste = AdSet-Länder setzen |
| `1443226` | Video-Ad ohne Miniaturbild | `META_VIDEO_THUMBNAIL_PATH`/`_URL` setzen |
| `code=1 — An unknown error` bei `advideos` | Page-Token + Multipart-Upload | vorhandene `META_VIDEO_ID` nutzen |
| „Kontowährung ≠ EUR“ | Konto nicht in EUR | Preflight blockiert; Cap rechnet in EUR |
| „Konto-Spend-Cap reicht nicht“ | `spend_cap - amount_spent < Budget` | Cap erhöhen oder Budget senken |
| `ads_management` fehlt | Token ohne Werbezugriff | Token neu erzeugen (App-Admin/Tester) |
| Seite nicht lesbar | fehlende Page-Rolle | Rolle „Anzeigen verwalten“ vergeben |

## 10. Guardrails (gelten auch für Meta)

- **Verbotene Aussagen** (`FORBIDDEN_CLAIMS` in `scripts/ads_agent.py`): `garantiert`, `dsgvo-konform`, `100 %`, `kostenlos`, `visum garantiert`, `sofort eingestellt`, `guaranteed`, `garanti`, `gratuit`, `مضمون`.
- **Pflichtbestandteile:** Link `jobs.hanibal-ai.com` und KI-Hinweis in jeder Sprache.
- **Kein PII:** `assert_no_pii` läuft auf jede Werbeaussage.
- **Budget:** Tagesgesamtcap; ohne Freigabe oder bei Cap 0 ist jede Kampagne `blocked`.
- **Kein ACTIVE beim Anlegen**, keine automatische Budgeterhöhung, kein Retry bei Meta-Fehlern.
- **Keine Google-/Microsoft-Live-Anlage** (weiterhin Dry-Run-Payloads).

## 11. Quellen

- `scripts/meta_ads.py`: `MetaConfig.from_env`, `MetaAdsClient.preflight`, `launch`, `activate`, `ensure_video`, `ensure_thumbnail`, Konstanten `OBJECTIVE`, `BILLING_EVENT`, `OPTIMIZATION_GOAL`, `BID_STRATEGY`
- `scripts/ads_agent.py`: `SEGMENTS`, `CREATIVES`, `SEARCH_ASSETS`, `FORBIDDEN_CLAIMS`, `--check-meta`, `--live`, `activate_campaign`
- `marketing/ADS_ENTSCHEIDUNG.md` (Entscheidungen, offene Punkte), `marketing/ads-agent.md` (Agent-Regeln), `knowledge/system/configuration-secrets.md` (Secret-Dateien)
- Meta-2026-Pflichtfelder und Subcodes: live verifiziert am 30.10.2026 (siehe `marketing/ads-agent.md`, Abschnitt „Video-Ad im Detail“)
