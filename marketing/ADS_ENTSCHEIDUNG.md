# ADS-ENTSCHEIDUNG — Werbe-Komponente (DSP/DMP-ähnlich)

**Stand:** 27.10.2026 · **Umsetzung:** `scripts/ads_agent.py` · **Agent:** `marketing/ads-agent.md`
**Ergebnis der Recherche:** Werbeausgaben laufen **nicht autonom**. Der Agent plant, prüft und legt
Meta-Kampagnen **PAUSED** an. Ausgaben beginnen erst, wenn ein Mensch die Kampagne aktiviert
(Begründung unten).

## 1. Ist-Analyse: was das System für Targeting hergibt

| Quelle | Inhalt | Für Werbung nutzbar? |
|---|---|---|
| `scripts/social_agent.py::read_aggregates` | aktive Stellen (Titel, Ort, Land, Typ, Gehalt), Zählungen je Status | **Ja**, PII-frei, bereits geprüft |
| `applications` / `candidates` | Personen, Bewerbungstexte, Dokumente | **Nein**, personenbezogen (Art. 6/9 DSGVO) |
| `agent_tasks.payload` | Task-Parameter mit IDs | **Nein** |
| `social_agent` Outbox | veröffentlichte Posts, Plattform-Reaktion nicht gemessen | **Begrenzt**, keine Rückkopplung zu Personen |
| `webui/`, `connectors/` | keine Werbe-API | — |

**Ergebnis:** Targeting-Signale werden nur auf **Stellen- und Aggregatebene** gebildet.
Ein Satz wie „Arbeitgeber, die viele Bewerbungen aus Marokko erhalten haben“ ist **nicht** umsetzbar:
die Herkunft einzelner Kandidaten ist personenbezogen und wird nicht gespeichert, nicht geprüft und nicht an Dritte gegeben.

## 2. Recherche: Plattformen und Regeln

| Thema | Befund | Quelle |
|---|---|---|
| Meta Marketing API | Stellenanzeigen müssen als Kategorie **Beschäftigung** (`EMPLOYMENT`) deklariert werden, sobald Europa (u. a. DE/FR) betroffen ist. Dann gelten: Alter 18–65+, alle Geschlechter, keine PLZ, keine Lookalikes, keine Ausschlüsse; Verstoß = harter Fehler. | Meta Transparency Center („Diskriminierende Praktiken“), Meta Help Center (Special Ad Categories), Marketing-API-Doku |
| DSA / DSGVO | Profilbasierte Werbung mit Art.-9-Daten ist verboten; bei Minderjährigen ebenfalls. Kandidaten-Profiling für Anzeigen ist daher ausgeschlossen. | Kommission, DSA-Leitlinien |
| Google Ads | Offizieller MCP-Server (`googleads/google-ads-mcp`) ist **nur lesend** (Reporting). Schreibende MCP-Server sind Drittanbieter (z. B. `mharnett/mcp-google-ads`, PAUSED-Standard, Freigabe-Workflow). | GitHub-Repos, Google-Entwicklerdoku (Stand 16.10.2026) |
| x402 | In **`~/mimo-agents/flight-agent`** umgesetzt: Verkäufer-Schranke (`attest/x402_gate.py`, Base Mainnet/Testnet) und Käufer-Client (`attest/client.py`, SDK `x402[evm]==2.25.0`). Hier neu: Käufer-Pfad `scripts/ads_x402.py` (nur Testnetz) mit Preisdeckel vor jeder Zahlung. x402-Werbenetzwerke (Instinct, Operon, hive-ad-bid, picoads, AD-402) richten sich an **KI-Agenten**, nicht an Menschen. Meta und Google nehmen x402 nicht an. `AGENTS.md`: Abrechnung nur per Überweisung. |

## 3. Entscheidungen

1. **Keine Verhaltens- oder Personen-Zielgruppen.** Die DMP ist eine **Aggregat-Tabelle** (`ergebnisse/ads/dmp_signals.jsonl`): Datum, Segment, Signalname, Zählwert. Keine IDs, keine Namen, keine Kandidatenbezüge.
2. **Kleinzellen-Schutz:** Zählwerte unter **5** werden als `<5` gespeichert und nicht zur Segmentbildung genutzt.
3. **Segmente** (nur aus Stellendaten bzw. als Platzhalter ohne Messwert):
   - `employers_eu` — Arbeitgeber in DE/FR/CH mit aktiven Stellen (Zählwert aus Stellendaten).
   - `candidates_north_africa` — Kandidaten in Nordafrika. **Größe nicht aus eigenen Daten ableitbar**; Reichweite käme von der Plattform. Wird als `None` geführt, nicht geschätzt.
4. **Targeting-Regel für alle Plattformen:** Behandelt wie Beschäftigungswerbung, also **immer** Alter 18–65+, alle Geschlechter, keine Lookalikes, keine Ausschlüsse, keine PLZ. Diese Konfiguration ist überall rechtlich unkritisch (Empfehlung aus der Recherche).
5. **Budget-Guardrails:**
   - `KMHR_ADS_DAILY_CAP_EUR` ist standardmäßig **0** → kein Euro wird ausgegeben.
   - Eine Kampagne braucht eine **Freigabedatei** (`KMHR_ADS_APPROVAL_FILE`) mit Kampagnen-Schlüssel und Betrag ≤ Cap.
   - Jede angelegte Kampagne ist **PAUSED**.
   - Gebote sind nach oben begrenzt (`max_bid_eur`); der Agent erhöht nie selbst.
6. **Simulation statt Markt:** Das Gebotsmodell nutzt **Design-Annahmen** (Basis-CPM je Segment). Sie sind **nicht gemessen**, nicht als Fakt ausgewiesen und dienen nur dem Ablauftest.
7. **Meta (Facebook) hat einen echten Live-Pfad, PAUSED-first.** `scripts/meta_ads.py` legt Kampagne, Ad Set, Creative und Ad über die Marketing API an – **immer** `status=PAUSED`, **immer** `special_ad_categories=["EMPLOYMENT"]`, Budget in Cent, `dsa_beneficiary`/`dsa_payor` für EU-Zielgruppen. Mit `META_VIDEO_ID`/`META_VIDEO_URL`/`META_VIDEO_PATH` wird das Video über `POST /act_<id>/advideos` hochgeladen und als `video_data`-Creative verwendet; das Pflicht-Thumbnail kommt aus `META_VIDEO_THUMBNAIL_PATH` (Upload via `adimages`) oder `META_VIDEO_THUMBNAIL_URL`. Ohne Video bleibt es ein `link_data`-Creative. Ein Preflight prüft Token, `ads_management`, Werbekonto, Zahlungsmittel, Währung, Seite, Videoquelle/Thumbnail und DSA-Felder und nennt jeden Blocker im Klartext. Meta-2026-Pflichtfelder sind im Live-Pfad gesetzt: `is_adset_budget_sharing_enabled=false` (AdSet-Budget) und `special_ad_category_country` = Targeting-Länder.
8. **Aktivierung bleibt menschlich.** `--activate <key> --yes` setzt Kampagne, Ad Set und Ad gemeinsam auf ACTIVE, nur bei Cap > 0 und nur nach einem `--live`-Lauf. Der Agent schaltet nie selbst scharf. `--live` braucht zusätzlich `KMHR_ADS_LIVE_CONFIRM=1`, eine Freigabedatei und `KMHR_ADS_CHANNELS=meta_ads`.
9. **x402 als Zahlungsschicht, nur Testnetz.** Der Käufer-Pfad `scripts/ads_x402.py` zahlt ein Gebot über HTTP 402 (`x402[evm]`), wie `flight-agent`. Regeln im Code: Mainnet (`eip155:8453`) ist gesperrt; der Preis wird vor der Zahlung gegen den Deckel (geplantes Tagesbudget) geprüft; ohne `KMHR_ADS_X402_URL` und `KMHR_ADS_X402_PRIVATE_KEY` findet keine Zahlung statt; nur freigegebene Kampagnen werden bezahlt; der Schlüssel erscheint nie im Protokoll. Der Schlüssel des `flight-agent` wird **nicht** verwendet. Echte Gebotsbörsen für Menschen gibt es über x402 nicht (siehe Punkt 1 und 2). Die Schicht ist deshalb nur gegen einen Testserver geprüft. |
10. **Google Ads:** später, nur Lesezugriff (offizieller MCP) für Reporting. Kein schreibender Drittanbieter-MCP in dieser Phase.

## 4. Offene Punkte (vor einer echten Schaltung)

- **Menschlich, nicht durch Code lösbar:** Werbekonto mit Zahlungsmittel und Rechtsentität,
  Seitenrolle „Anzeigen verwalten“, Token mit `ads_management`, DSA-Begünstigter/Bezahler.
  Der Preflight (`--check-meta`) meldet jede dieser Lücken als Blocker.
- Meta prüft die Anzeige zusätzlich inhaltlich (Sonderkategorie „Beschäftigung“).
- Native-Review der AR/FR-Texte (laut `i18n.md` offen).
- Rechtliche Freigabe der Datenkategorien für Reichweitenmessung (Anwalt; Rechtsseiten sind Entwürfe).
- Google Ads und Microsoft Advertising bleiben Dry-Run; ihre Feldnamen sind ungeprüft.

## Quellen

- Meta Transparency Center, Diskriminierende Praktiken: https://transparency.meta.com/policies/ad-standards/unacceptable-content/discriminatory-practices
- Meta Marketing API, Special Ad Categories (Stand Okt. 2026, Sekundärauswertung): https://adadvisor.ai/blog/meta-special-ad-categories
- Google Ads MCP (offiziell, lesend): https://github.com/googleads/google-ads-mcp
- Google Ads MCP Entwicklerleitfaden: https://developers.google.com/google-ads/api/docs/developer-toolkit/mcp-server
- x402 Spezifikation: https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md
- DSA / Art. 9 DSGVO Profiling-Verbot: Verordnung (EU) 2022/2065, Verordnung (EU) 2016/679

> **Aktualisierung 28.10.2026:** Meta ist nicht mehr Standardkanal. Standard sind Google Ads und Microsoft Advertising (Suchabsicht, offene API). Begründung: `marketing/ADS_ALTERNATIVEN.md`. Meta läuft nur per Opt-in (`KMHR_ADS_CHANNELS=meta_ads`).
>
> **Aktualisierung 29.10.2026:** Der Live-Blocker aus Punkt 8 ist aufgelöst, soweit er Code betrifft.
> `scripts/meta_ads.py` spricht die Marketing API (Graph v26.0) und legt Kampagnen PAUSED an;
> `--check-meta` prüft Konto, Zahlungsmittel, Token-Rechte, Seite und DSA-Felder. Was bleibt, ist
> menschlich und extern: Zahlungsmittel, Werbekonto-Freigabe, Meta-Prüfung der Anzeige. Wer die API
> nicht freigeben will, nutzt `--kit` und legt die Kampagne im Ads Manager mit denselben Werten an.
> Die Entscheidung „kein autonomes Ausgeben“ bleibt unverändert.
