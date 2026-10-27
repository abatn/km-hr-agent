# ADS-ALTERNATIVEN — Kanäle ohne Meta

**Stand:** 28.10.2026 · **Ersetzt:** Meta als Standardkanal in `marketing/ADS_ENTSCHEIDUNG.md` (Meta bleibt Opt-in)
**Umsetzung:** `scripts/ads_agent.py` (`CHANNELS`, `google_ads_payloads`, `microsoft_ads_payload`) · **Tests:** `tests/test_ads_channels.py`

## 1. Analyse: warum Meta als einziger Kanal ein Problem ist

| Problem | Befund |
|---|---|
| **Abhängigkeit von einem Anbieter** | Im Code war der Agent fest auf Meta verdrahtet (`platforms`, Payload-Bau nur für `facebook`). Ein Ausfall, eine Richtlinienänderung oder eine abgelehnte Prüfung hätte die ganze Werbung gestoppt. Das ist mein Entwurfsfehler, nicht eine Eigenschaft von Meta. |
| **x402 ist ein Nebenthema** | Meta akzeptiert x402 nicht. Das betrifft aber nur den Zahlungsweg. Die Kanalwahl hängt davon nicht ab. Ich habe das in meinem Bericht vermischt. |
| **Zielgruppe** | Arbeitgeber in DE/FR/CH suchen Fachkräfte über **Suche und Fachnetzwerke**, nicht über Freundeskreis-Feeds. Kandidaten in Nordafrika suchen Jobs ebenfalls über **Suchmaschinen**. Meta ist dort nur ein Reichweitenkanal ohne Suchabsicht. |
| **Freigabe** | Meta verlangt für `ads_management` ein App Review und eine Beschäftigungskategorie. Die Regeln sind für Stellen eng (Alter, Geschlecht, keine PLZ, keine Lookalikes). |

**Schluss:** Meta bleibt Opt-in. Der Standard sind Kanäle, die **Suchabsicht** bedienen und eine **offene API mit Selbstbedienung** haben.

## 2. Recherche: Kanäle

| Kanal | Zugang | Targeting | Eignung | Quelle |
|---|---|---|---|---|
| **Google Ads (Search)** | Google-Cloud-Projekt, **Explorer-Zugang** automatisch nach Antrag; Developer-Tokens seit 09.09.2026 abgeschafft | Land, Sprache, Suchbegriffe. Beschäftigungs-Einschränkungen gelten laut Google nur für **USA und Kanada** | **hoch**: Suchabsicht in beiden Zielgruppen | developers.google.com/google-ads/api (Access levels, Developer token) |
| **Microsoft Advertising (Bing)** | Developer Portal, **Universal-Entwicklertoken**, OAuth; Sandbox mit öffentlichem Token | Länder inkl. DE, FR, CH, MA, DZ, TN, EG; Sprache | **mittel**: zweiter Suchkanal, geringerer Marktanteil in Nordafrika (nicht gemessen) | learn.microsoft.com/advertising (Get started, Geo-Codes) |
| **LinkedIn** | Marketing API mit App Review | B2B-Berufsdaten | hoch für B2B, aber Review nötig | (bereits in `ENTSCHEIDUNG.md` als Posting-Kanal) |
| **Jobsquare (Marokko)** | Partner-API: Stellen **veröffentlichen** und verwalten | Plattform-intern | mittel, späterer Publikationskanal | api.jobsquare.ma |
| **Jawb.ma, Emploi.ma, Emploitic, Almehan, Optioncarriere, jobs.ly** | nur Lese-Feeds oder Drittanbieter-Wrapper | — | keine Werbefläche per API | Anbieterseiten; Parse-Wrapper sind nicht offiziell |
| **x402-Werbenetzwerke** (Instinct, Operon, hive-ad-bid, picoads, AD-402) | x402-bezahlt | **KI-Agenten**, nicht Menschen | **nicht geeignet** für Arbeitgeber/Kandidaten | x402ads.io, operon.so, github.com/srotzin/hive-ad-bid |

## 3. Entscheidung

**Erster Test: Google Ads (Search) und Microsoft Advertising (Search).**

Begründung:
1. **Suchabsicht** trifft beide Zielgruppen direkt: „Jobs in Deutschland“, „emploi Allemagne“, „وظائف في أوروبا“.
2. **Offene API** mit Selbstbedienung (Explorer-Zugang bzw. Universal-Token), keine Beschäftigungskategorie und kein Alters- oder Geschlechtstargeting nötig.
3. **Beide Kanäle sind Länder-Targeting** für DE, FR, CH, MA, DZ, TN, EG verfügbar. Damit ist das Ziel ohne Personen-Daten erreichbar.
4. **Zwei unabhängige Anbieter** statt einem.

**Nicht zuerst:** LinkedIn (App Review), Jobsquare (Partnerschaft nötig, nur Veröffentlichung), x402-Netzwerke (KI-Agenten).

## 4. Umsetzung (Dry-Run)

- `CHANNELS`: `google_ads` und `microsoft_ads` sind Default, `meta_ads` nur per `KMHR_ADS_CHANNELS=meta_ads`.
- Suchanzeigen mit festen Längen: Headline ≤ 30, Beschreibung ≤ 90 Zeichen, Ziel-URL, KI-Hinweis (geprüft, `check_search_asset`).
- Google Ads: Budget und Kampagne als zwei Schritte, `status PAUSED`, `SEARCH`, Geo- und Sprachkriterien.
- Microsoft Advertising: SOAP-Operation `AddCampaigns`, `Status Paused`, Länder und Sprachen.
- Alle Guardrails unverändert: Cap 0, Freigabedatei, PAUSED, Gebotsobergrenze, Testnetz-Sperre für x402, kein Personenbezug.

## 5. Offene Punkte (vor einer Live-Schaltung)

- **Feldnamen und Kriterien-IDs** (Google `geoTargetConstants`/`languageConstants`, Microsoft `AddCampaigns`) sind im Dry-Run nach bestem Wissen und Doku-Stand gesetzt. Vor jeder Live-Nutzung gegen die aktuelle API-Referenz prüfen.
- **Google Ads:** Explorer-Zugang beantragen; für mehr Volumen Basic (Markenprüfung nötig).
- **Microsoft:** eigenes Universal-Token im Developer Portal anfordern.
- **Marktanteile** Bing/Google in Nordafrika sind nicht gemessen. Vor Budgeterhöhung eine Messung über die Kampagne selbst machen (Klicks, nicht Schätzung).
- **Rechtlich:** Werbeausgaben brauchen ein Zahlungsmittel und eine Rechtsentität (Anwalt; Rechtsseiten sind Entwürfe).
- **Gebote** bleiben Design-Annahmen, bis echte Messwerte vorliegen.

## Quellen

- Google Ads API, Access levels: https://developers.google.com/google-ads/api/docs/api-policy/access-levels
- Google Ads API, Developer token (Sunset 09.09.2026): https://developers.google.com/google-ads/api/docs/api-policy/developer-token
- Google Ads Policy, Employment (USA/Kanada): https://support.google.com/adspolicy/answer/16700442
- Microsoft Advertising, Get started (Universal-Token): https://learn.microsoft.com/en-us/advertising/guides/get-started
- Microsoft Advertising, Geo-Codes (MA, DZ, TN, EG, DE, FR, CH): https://learn.microsoft.com/en-us/advertising/guides/geographical-location-codes
- Jobsquare Partner-API: https://api.jobsquare.ma/
- Jawb.ma Flux-Doku: https://jawb.ma/api-recrutement
- x402-Werbenetzwerke: https://x402ads.io/ · https://operon.so/x402 · https://github.com/srotzin/hive-ad-bid
