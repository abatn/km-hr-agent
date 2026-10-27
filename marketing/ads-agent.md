# ads-agent

**Rolle:** Werbe-Agent (DSP/DMP-ähnlich) für den KM-HR-Agenten.
**Entscheidung und Grenzen:** `marketing/ADS_ENTSCHEIDUNG.md` · **Code:** `scripts/ads_agent.py` · **Tests:** `tests/test_ads_agent.py`

## Prinzip: Wahrnehmen → Planen → Handeln → Beobachten

1. **Wahrnehmen:** nur Aggregate über `social_agent.read_aggregates` und eine Länder-Zählung der aktiven Stellen. Keine Personen-, Bewerbungs- oder Task-Daten.
2. **Planen:** zwei Segmente (`employers_eu`, `candidates_north_africa`), Creatives in DE/EN/FR/AR, Targeting nach Beschäftigungsregeln (18–65+, alle Geschlechter, keine Lookalikes, keine Ausschlüsse, keine PLZ).
3. **Handeln (simuliert):** Budget nur innerhalb von `KMHR_ADS_DAILY_CAP_EUR` (Standard 0) und nur mit Freigabe in `KMHR_ADS_APPROVAL_FILE`. Gebot = Annahme-CPM + 10 %, nie über `max_cpm_eur`. Kampagnen immer PAUSED. Kein Versand an eine Werbeplattform.
4. **Beobachten:** Lauf-Protokoll `ergebnisse/ads/<Datum>/run.json`; DMP-Aggregate `ergebnisse/ads/dmp_signals.jsonl` (Kleinzellen < 5 als `<5`).

## Guardrails

- **Kein Personenbezug:** `assert_no_pii` (aus dem Social-Agenten) läuft auf jede Werbeaussage. Verbotene Versprechen („garantiert“, „DSGVO-konform“, „kostenlos“ u. a.) werden blockiert.
- **Pflichtbestandteile:** Link `jobs.hanibal-ai.com` und KI-Hinweis in jeder Sprache.
- **Budget:** Cap ist ein **Tagesgesamtbudget**. Ohne Freigabe oder bei Cap 0 ist jede Kampagne `blocked`.
- **Live gesperrt:** `--live` bricht mit Status 2 ab. Eine echte Anbindung braucht Werbekonto, Zahlungsmittel und Meta-Freigabe (siehe Entscheidung).

## Aufruf

```bash
# Planungslauf (Dry-Run, Budget 0)
.venv-streamlit/bin/python3 scripts/ads_agent.py --once

# Simulierter Gebotsprozess mit Freigabe (kein Geld fließt)
KMHR_ADS_DAILY_CAP_EUR=5 KMHR_ADS_APPROVAL_FILE=freigabe.json \
  .venv-streamlit/bin/python3 scripts/ads_agent.py --once
# freigabe.json: {"campaigns": {"employers_eu": 3.0, "candidates_north_africa": 2.0}}
```

## Grenzen

- Das Gebotsmodell nutzt **Design-Annahmen** (`assumed_cpm_eur`), keine Marktdaten.
- Die Größe der Kandidatenzielgruppe ist nicht aus eigenen Daten messbar und wird nicht geschätzt.
- Keine Rückkopplung von Klicks oder Bewerbungen auf einzelne Personen.
