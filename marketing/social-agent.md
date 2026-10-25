# social-agent

**Rolle:** Autonomer Social-Media-Marketing-Agent für den KM-HR-Agenten.
**Spec:** `knowledge/system/social-automation.md` · **Entscheidung:** `marketing/ENTSCHEIDUNG.md`
**Ausführung:** `scripts/social_agent.py`

## Prinzip: Wahrnehmen → Planen → Handeln → Beobachten

1. **Wahrnehmen**
   - Liest ausschließlich PII-freie Daten aus der HR-DB: aktive Stellen (Titel, Ort, Land, Typ, Gehaltsband) und aggregierte Bewerbungs-/Einstellungszahlen.
   - Verboten: `candidates`, `candidate_documents`, `applications.bewerbungstext`, `agent_tasks.payload`, Kontaktdaten, CV-Texte.
2. **Planen**
   - Erzeugt einen 7-Tage-Redaktionsplan mit Plattform, Thema, Sprache und Format.
   - Themen: `new_jobs`, `candidate_tips`, `hiring_stats`; Sprachen: DE/EN/FR/AR (Standard je Plattform: LinkedIn DE, Facebook/Instagram FR).
3. **Handeln**
   - Rendert Titel, Text, Link, optional Bild-URL und KI-Hinweis.
   - Publiziert über LinkedIn, Facebook oder Instagram — **nur** wenn `KMHR_SOCIAL_MODE=live`, `KMHR_SOCIAL_AUTO_PUBLISH=1` und der Plattform-Token gesetzt sind.
   - Sonst Dry-Run: der exakte API-Payload landet in der Outbox, ohne Netzwerkaufruf.
4. **Beobachten**
   - Schreibt Plan, Post, Payload, Status und Log nach `ergebnisse/social/<YYYY-MM-DD>/`.
   - Statuswerte: `dry_run`, `published`, `failed`, `skipped`, `disabled`.
   - Idempotent über `post_id`; vorhandene Outbox wird ohne `--force` nicht überschrieben.

## Inputs

- DB: `KMHR_DB_PATH` oder `data/feedback.db` (read-only).
- Env: `.env-social` (gitignored) oder Prozessumgebung.
- Konfiguration: `KMHR_SOCIAL_ENABLED`, `KMHR_SOCIAL_MODE`, `KMHR_SOCIAL_AUTO_PUBLISH`, `KMHR_SOCIAL_SITE_URL`.
- Tokens: `LINKEDIN_ACCESS_TOKEN`/`LINKEDIN_AUTHOR_URN`, `FACEBOOK_PAGE_ID`/`FACEBOOK_PAGE_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`/`INSTAGRAM_ACCESS_TOKEN`/`INSTAGRAM_IMAGE_URL`.

## Outputs

```text
ergebnisse/social/<YYYY-MM-DD>/
  plan.json                     # 7-Tage-Plan
  <plattform>-<thema>.md        # gerenderter Post
  <plattform>-<thema>.json      # Outbox: Payload/Response/Status
logs/social-agent.log           # append-only Lauf-Log
```

## Guardrails

- **DSGVO:** `assert_no_pii` blockt E-Mail, Telefon, `Kandidat #N`, interne IDs. Keine Personenstorys ohne Einwilligung.
- **Keine Erfolgsversprechen:** API-Fehler werden als `failed` persistiert; kein `published` ohne externe ID.
- **Rate-Limits:** max. 1 Post/Plattform/Tag; LinkedIn/Meta 429 wird als Fehler gespeichert, kein hektischer Retry.
- **Kill-Switch:** `KMHR_SOCIAL_ENABLED=0` beendet den Lauf mit `disabled`.
- **Kein Schreiben** in `knowledge/**` oder `skills/**`; Laufzeit-Artefakte nur `ergebnisse/` und `logs/`.

## Aufruf

```bash
# Wochenplan + heutigen Post als Dry-Run
.venv-streamlit/bin/python3 scripts/social_agent.py --once --dry-run

# Nur Plan
.venv-streamlit/bin/python3 scripts/social_agent.py --plan

# Live (nur mit Auto-Publish + Tokens)
KMHR_SOCIAL_MODE=live KMHR_SOCIAL_AUTO_PUBLISH=1 \
  .venv-streamlit/bin/python3 scripts/social_agent.py --once --live
```
