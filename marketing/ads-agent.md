# ads-agent

**Rolle:** Werbe-Agent (DSP/DMP-ähnlich) für den KM-HR-Agenten.
**Entscheidung und Grenzen:** `marketing/ADS_ENTSCHEIDUNG.md` · **Code:** `scripts/ads_agent.py`, `scripts/meta_ads.py` · **Tests:** `tests/test_ads_agent.py`, `tests/test_meta_ads.py`, `tests/test_ads_channels.py`

## Prinzip: Wahrnehmen → Planen → Handeln → Beobachten

1. **Wahrnehmen:** nur Aggregate über `social_agent.read_aggregates` und eine Länder-Zählung der aktiven Stellen. Keine Personen-, Bewerbungs- oder Task-Daten.
2. **Planen:** zwei Segmente (`employers_eu`, `candidates_north_africa`), Creatives in DE/EN/FR/AR, Targeting nach Beschäftigungsregeln (18–65+, alle Geschlechter, keine Lookalikes, keine Ausschlüsse, keine PLZ).
3. **Handeln:** Dry-Run-Payloads für Google Ads und Microsoft Advertising; **Meta/Facebook live** über die Marketing API – Kampagne, Ad Set, Creative und Ad werden **immer PAUSED** angelegt. Mit `META_VIDEO_ID`/`META_VIDEO_URL`/`META_VIDEO_PATH` entsteht ein **Video-Ad** (`video_data`), ohne Video eine Link-Anzeige (`link_data`). Aktivieren ist ein getrennter, menschlicher Schritt.
4. **Beobachten:** Lauf-Protokoll `ergebnisse/ads/<Datum>/run.json`; DMP-Aggregate `ergebnisse/ads/dmp_signals.jsonl` (Kleinzellen < 5 als `<5`).

## Guardrails

- **Kein Personenbezug:** `assert_no_pii` (aus dem Social-Agenten) läuft auf jede Werbeaussage. Verbotene Versprechen („garantiert“, „DSGVO-konform“, „kostenlos“ u. a.) werden blockiert.
- **Pflichtbestandteile:** Link `jobs.hanibal-ai.com` und KI-Hinweis in jeder Sprache.
- **Budget:** Cap ist ein **Tagesgesamtbudget**. Ohne Freigabe oder bei Cap 0 ist jede Kampagne `blocked`.
- **PAUSED-first:** Es gibt keinen Code-Pfad, der eine Kampagne ACTIVE anlegt. `meta_ads.MetaAdsClient.launch` setzt `status=PAUSED` fest.
- **Aktivierung nur bestätigt:** `--activate <key> --yes` **und** Cap > 0. Der Agent entscheidet nie selbst.
- **Beschäftigungskategorie:** `special_ad_categories=["EMPLOYMENT"]` und Targeting ohne Geschlecht/PLZ/Lookalikes bei jeder Meta-Kampagne.
- **DSA:** `dsa_beneficiary`/`dsa_payor` sind Pflichtfelder für EU-Zielgruppen; ohne sie blockiert der Preflight.

## Aufruf

```bash
# Planungslauf (Dry-Run, Budget 0)
.venv-streamlit/bin/python3 scripts/ads_agent.py --once

# Simulierter Gebotsprozess mit Freigabe (kein Geld fließt)
KMHR_ADS_DAILY_CAP_EUR=5 KMHR_ADS_APPROVAL_FILE=freigabe.json \
  .venv-streamlit/bin/python3 scripts/ads_agent.py --once
# freigabe.json: {"campaigns": {"employers_eu": 3.0, "candidates_north_africa": 2.0}}

# Manuelles Startpaket (funktioniert ohne API-Freigabe)
.venv-streamlit/bin/python3 scripts/ads_agent.py --kit
# -> ergebnisse/ads/<Datum>/launch-kit.md (Copy-&-Paste für den Ads Manager)

# Meta-Vorabprüfung (Token, Konto, Zahlungsmittel, Seite, DSA)
.venv-streamlit/bin/python3 scripts/ads_agent.py --check-meta
```

## Facebook-Anzeigen live schalten

Voraussetzungen, die **ein Mensch** einmalig erledigt (Code kann das nicht):

1. **Werbekonto** in Meta Business anlegen, Rechtsperson und Rechnungsdaten hinterlegen, **Zahlungsmittel** hinzufügen.
2. **Seite** als Anzeigengeber (Facebook-Seite vorhanden, Rolle „Anzeigen verwalten“).
3. **Token mit `ads_management`**: Graph API Explorer, App der App-ID aus `.env-social`, Nutzer muss App-Admin/Entwickler/Tester **und** Werbekonto-Admin sein. In der Entwicklungsumgebung der App funktioniert das ohne App-Review (Review ist nur für fremde Nutzer nötig). Ein Page-Token für die Zielseite funktioniert ebenfalls; der Preflight liest dessen Scopes per `debug_token` (dafür `META_APP_ID`/`META_APP_SECRET` oder `FACEBOOK_APP_ID`/`FACEBOOK_APP_SECRET` setzen).
4. **DSA-Begünstigter/Bezahler** eintragen (Pflicht für DE/FR-Zielgruppe).

Konfiguration in `.env-social` (chmod 600):

```ini
META_AD_ACCOUNT_ID=act_...
META_ADS_ACCESS_TOKEN=EAAG...
FACEBOOK_PAGE_ID=...
META_DSA_BENEFICIARY=Hanibal AI
META_DSA_PAYOR=Hanibal AI
META_GRAPH_VERSION=v26.0
META_ADS_CURRENCY=EUR
# Optional, wenn ein Page-Token statt User-Token genutzt wird:
# META_APP_ID=2263359441188320
# META_APP_SECRET=...
# Video-Ad (optional; ohne Video: Link-Anzeige)
META_VIDEO_PATH=/pfad/zum/reel.mp4
# oder: META_VIDEO_URL=https://.../reel.mp4
# oder: META_VIDEO_ID=<bereits hochgeladene Ad-Video-ID>
META_VIDEO_THUMBNAIL_PATH=/pfad/zum/reel-thumb.jpg
# oder: META_VIDEO_THUMBNAIL_URL=https://.../reel-thumb.jpg
```

**Pflicht bei Video:** Ein Miniaturbild ist laut Meta zwingend. Lokal wird es über
`POST /act_<id>/adimages` hochgeladen und als `image_hash` verwendet; alternativ
kann eine öffentliche `image_url` gesetzt werden.

Ablauf:

```bash
# 1) Prüfen – nennt jeden Blocker im Klartext
.venv-streamlit/bin/python3 scripts/ads_agent.py --check-meta

# 2) PAUSED anlegen (kein Euro fließt, keine Auslieferung)
KMHR_ADS_CHANNELS=meta_ads KMHR_ADS_LIVE_CONFIRM=1 \
KMHR_ADS_DAILY_CAP_EUR=5 KMHR_ADS_APPROVAL_FILE=freigabe.json \
  .venv-streamlit/bin/python3 scripts/ads_agent.py --live

# 3) Im Ads Manager prüfen, dann bewusst scharf schalten
KMHR_ADS_DAILY_CAP_EUR=5 \
  .venv-streamlit/bin/python3 scripts/ads_agent.py --activate employers_eu --yes

# 4) Ausgaben/Aggregate abholen
# meta_ads.MetaAdsClient.insights(campaign_id, since, until)
```

Ergebnis von Schritt 2: `run.json` enthält `mode: "live_paused"`, je Kampagne `meta.campaign_id`, `adset_id`, `creative_id`, `ad_id`, `creative_type` (`video`/`link`), `video_id` und den Status `paused_created`. Bei fehlender Konfiguration bleibt `run.json` als Beweis erhalten und der Lauf endet mit rc=2.

### Video-Ad im Detail

- **Upload:** `POST https://graph-video.facebook.com/v26.0/act_<Konto>/advideos` mit `source` (lokale Datei) oder `file_url` (öffentliche URL). Die Antwort liefert `video_id`.
- **Creative:** `object_story_spec.page_id` + `video_data` mit `video_id`, `message`, `link_description`, `call_to_action` und **Pflicht-Thumbnail** (`image_hash` aus `adimages` oder `image_url`). Kein `link_data` bei Video.
- **Unverändert:** Kampagne/AdSet/Ad `PAUSED`, `special_ad_categories=["EMPLOYMENT"]`, Targeting 18–65/alle Geschlechter/keine PLZ, DSA-Felder.
- **Format:** MP4/MOV, H.264/AAC; 9:16 (1080×1920) für Reels/Stories, 4:5 oder 1:1 für den Feed.
- **Meta-2026-Pflichtfelder (live verifiziert):** `is_adset_budget_sharing_enabled=false` bei AdSet-Budget und `special_ad_category_country` = Targeting-Länder. Ohne diese Felder blockiert Meta mit `4834011` bzw. `2909035`.
- **Fehlerfall:** Scheitert der Upload, wird **keine** Kampagne angelegt (kein verwaistes Objekt).

## Was der Live-Pfad bewusst nicht tut

- **Kein ACTIVE beim Anlegen**, keine automatische Budgeterhöhung, kein Retry bei Meta-Fehlern.
- **Kein Video-Zwang:** Ohne Videoquelle bleibt der Link-Ad-Pfad; der Preflight warnt, statt still eine Video-Anzeige vorzutäuschen.
- **Keine Anlage bei fremder Kontowährung** (Cap rechnet in EUR) und nicht, wenn der Konto-Spend-Cap nicht reicht.
- **Keine Google-/Microsoft-Live-Anlage** (weiterhin Dry-Run-Payloads).
- **Keine Personen-Zielgruppen** und keine Kandidatendaten an Meta.

## Grenzen

- Das Gebotsmodell nutzt **Design-Annahmen** (`assumed_cpm_eur`), keine Marktdaten.
- Die Größe der Kandidatenzielgruppe ist nicht aus eigenen Daten messbar und wird nicht geschätzt.
- Keine Rückkopplung von Klicks oder Bewerbungen auf einzelne Personen.
- Meta-Richtlinienprüfung, Identitätsprüfung und Zahlungsabwicklung bleiben extern.

## x402-Zahlungsschicht (nur Testnetz)

Gebote können per x402 bezahlt werden (`scripts/ads_x402.py`, Muster aus `flight-agent/attest/client.py`). Sie läuft nur im Dry-Run, nicht im Meta-Live-Pfad.

```bash
# Testnetz-Schlüssel nur in der Umgebung, nie in Dateien oder Protokollen
KMHR_ADS_X402_URL=https://<boerse>/x402/bid \
KMHR_ADS_X402_PRIVATE_KEY=0x<testnet-schluessel> \
KMHR_ADS_DAILY_CAP_EUR=5 KMHR_ADS_APPROVAL_FILE=freigabe.json \
  .venv-streamlit/bin/python3 scripts/ads_agent.py --once
```

- Zahlung **nur** für Kampagnen mit Status `paused_ready` (Freigabe + Cap).
- Preisdeckel = geplantes Tagesbudget; der Preis wird vor der Zahlung geprüft.
- Mainnet (`eip155:8453`) ist gesperrt.
- Ohne URL oder Schlüssel: `x402.status = nicht_konfiguriert`, keine Zahlung.

Tests: `tests/test_ads_x402.py` läuft mit `.venv-ads` (siehe `requirements-ads.txt`) gegen einen lokalen Mock-Facilitator und eine Test-Börse. Im Projekt-venv werden sie übersprungen.

## Kanäle (ohne Meta als Standard)

Standard: **Google Ads (Search)** und **Microsoft Advertising (Search)**. Begründung und Quellen: `marketing/ADS_ALTERNATIVEN.md`.

```bash
# Default: google_ads,microsoft_ads
.venv-streamlit/bin/python3 scripts/ads_agent.py --once
# Meta nur bewusst zuschalten (Pflicht für --live)
KMHR_ADS_CHANNELS=google_ads,meta_ads .venv-streamlit/bin/python3 scripts/ads_agent.py --once
```

- Suchanzeigen: Headline ≤ 30, Beschreibung ≤ 90 Zeichen, Ziel-URL und KI-Hinweis (`check_search_asset`).
- Alle Such-Payloads sind Dry-Run und PAUSED. Feldnamen vor einer Live-Nutzung gegen die aktuelle API-Referenz prüfen.
- Unbekannte Kanalnamen brechen den Lauf ab.
