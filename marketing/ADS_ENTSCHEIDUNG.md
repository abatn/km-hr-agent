# ADS-ENTSCHEIDUNG — Werbe-Komponente (DSP/DMP-ähnlich)

**Stand:** 27.10.2026 · **Umsetzung:** `scripts/ads_agent.py` · **Agent:** `marketing/ads-agent.md`
**Ergebnis der Recherche:** Werbeausgaben laufen **nicht autonom**. Der Agent plant, prüft und simuliert.
Echte Ausgaben sind bewusst nicht implementiert (Begründung unten).

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
| x402 | Krypto-Zahlungsprotokoll (HTTP 402, USDC auf Blockchain). **Im Repo nicht vorhanden.** Meta und Google akzeptieren es nicht als Zahlungsweg. `AGENTS.md`: Abrechnung **nur per Banküberweisung**, kein Online-Zahlungsdienst. | x402-Spezifikation, Cloudflare-Doku |

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
7. **Erste Plattform-Anbindung: Meta (Facebook/Instagram) als Dry-Run-Payload.** Die vorhandene Meta-App und die Seiten-Tokens (`.env-social`) bleiben unverändert; Werbekonto-Zugriff (`ads_management`) ist ein separater Review- und Zahlungsschritt.
8. **Keine Live-Anbindung in diesem Schritt.** Begründung: echte Ausgaben, ungeklärtes Werbekonto mit Zahlungsmittel, Meta-Review für `ads_management`, und die Abrechnung läuft laut `AGENTS.md` nur per Überweisung. `--live` bricht deshalb ab.
9. **x402 wird nicht eingebaut.** Es gibt keinen bestehenden x402-Mechanismus, und die Werbeplattformen akzeptieren ihn nicht. Eine Übernahme würde eine Krypto-Zahlungsschicht ohne Gegenstück einführen.
10. **Google Ads:** später, nur Lesezugriff (offizieller MCP) für Reporting. Kein schreibender Drittanbieter-MCP in dieser Phase.

## 4. Offene Punkte (vor einer echten Schaltung)

- Werbekonto mit Zahlungsmittel und Rechtsentität; Freigabe von `ads_management` in der Meta-App.
- Prüfung der Anzeigen auf Beschäftigungs-Konformität durch Meta (Sonderkategorie-Auswahl im Werbemanager).
- Native-Review der AR/FR-Texte (laut `i18n.md` offen).
- Rechtliche Freigabe der Datenkategorien für Reichweitenmessung (Anwalt; Rechtsseiten sind Entwürfe).

## Quellen

- Meta Transparency Center, Diskriminierende Praktiken: https://transparency.meta.com/policies/ad-standards/unacceptable-content/discriminatory-practices
- Meta Marketing API, Special Ad Categories (Stand Okt. 2026, Sekundärauswertung): https://adadvisor.ai/blog/meta-special-ad-categories
- Google Ads MCP (offiziell, lesend): https://github.com/googleads/google-ads-mcp
- Google Ads MCP Entwicklerleitfaden: https://developers.google.com/google-ads/api/docs/developer-toolkit/mcp-server
- x402 Spezifikation: https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md
- DSA / Art. 9 DSGVO Profiling-Verbot: Verordnung (EU) 2022/2065, Verordnung (EU) 2016/679
