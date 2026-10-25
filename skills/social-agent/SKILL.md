---
description: Autonomer Social-Media-Agent (LinkedIn/Facebook/Instagram) mit datengetriebenem Redaktionsplan, Dry-Run-Outbox und DSGVO-Guard.
---

# social-agent

**Vollständige Agent-Definition:** `marketing/social-agent.md`
**Normative Spec:** `knowledge/system/social-automation.md`
**Ausführung:** `scripts/social_agent.py`

## Wann einsetzen

- Wöchentlicher Redaktionsplan für neue Stellen, Kandidaten-Tipps und Recruiting-Zahlen.
- Dry-Run-Vorschau für LinkedIn/Facebook/Instagram.
- Live-Posting nur mit `KMHR_SOCIAL_MODE=live`, `KMHR_SOCIAL_AUTO_PUBLISH=1` und gültigen Tokens.

## Schritte

1. DB-Aggregate lesen (nur aktive Stellen + Status-Zahlen; keine Kandidaten-/Bewerbungs-PII).
2. 7-Tage-Plan bauen (`new_jobs`, `candidate_tips`, `hiring_stats`).
3. Post rendern (DE/EN/FR/AR) und `assert_no_pii` ausführen.
4. Dry-Run-Payload in `ergebnisse/social/<Tag>/` schreiben **oder** live publizieren.
5. Status/Outbox prüfen; bei `failed` Ursache im Log, kein stiller Erfolg.

## Output

- `ergebnisse/social/<YYYY-MM-DD>/plan.json`
- `<plattform>-<thema>.md` und `.json` (Outbox)
- `logs/social-agent.log`

## Guardrails

- Keine Namen, E-Mails, Telefonnummern, CVs, Kandidaten-IDs.
- Kein Post ohne Token/Auto-Publish; Default ist Dry-Run.
- Keine Schreiber in `knowledge/**`/`skills/**`.
- Keine erfundenen Zahlen: ausschließlich DB-Aggregate.
