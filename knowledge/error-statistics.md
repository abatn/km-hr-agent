# Error-Statistik

Quelle: `logs/agent-errors.log` + eigene API-Tests (16.09.2026)

## NVIDIA API 503 – Fehleranalyse

| Datum | Task-Typ | Fehler | Häufigkeit | Status |
|---|---|---|---|---|
| 15.09.2026 00:08 | check_visa | HTTP 503 Service overloaded | 1/3 Versuche | ✅ Versuch 2 OK |
| 15.09.2026 23:59 | assess_culture_fit | HTTP 503 Service overloaded | 2/3 Versuche | ❌ Alle fehlgeschlagen |
| 16.09.2026 00:00 | extract_profile | HTTP 503 Service overloaded | 1/3 Versuche | ✅ Versuch 3 OK |
| 16.09.2026 00:00 | check_compliance | HTTP 503 Service overloaded | 1/3 Versuche | ✅ Versuch 3 OK |
| 16.09.2026 00:02 | extract_profile | HTTP 503 Service overloaded | 1/3 Versuche | ✅ Versuch 3 OK |
| 16.09.2026 00:02 | match_candidate | HTTP 503 Service overloaded | 1/3 Versuche | ✅ Versuch 3 OK |
| 16.09.2026 00:02 | check_compliance | HTTP 503 Service overloaded | 1/3 Versuche | ✅ Versuch 3 OK |

**Gesamt:** 7 Events, 6× erfolgreich nach Retry, 1× endgültig fehlgeschlagen
**Erholungszeit:** 8–118 Sekunden (Median ~68s)
**Zeitlicher Cluster:** 00:00–00:03 Uhr (Nacht)

## API-Tests (16.09.2026)

| Test | Modell | Ergebnis |
|---|---|---|
| 20 parallele Requests | nemotron-120b | 16/20 OK (20% 503) |
| 20 parallele Requests | lightning-30b | 19/20 OK (0% 503, 1x Timeout) |
| Retry mit 5s Backoff | nemotron-120b | 100% Erholung |
| kimi-k3 Fallback | moonshotai/kimi-k3 | Timeout (>30s) |

**Umgesetzt (nicht nur Empfehlung):** Exponential Backoff (5→10→20s, `wait=[5,10,20]`) + lightning-30b als Fallback — Implementierung 16.09.2026 in `scripts/agent-runner.py` (gemessen 10.10.2026), Modellkette; verifiziert 24.09.2026 (Phase-E P0)

## NVIDIA Free-Tier Limit

| Quelle | Wert | Datum |
|---|---|---|
| NVIDIA Developer Forum | 40 RPM (Requests pro Minute) | 25.06.2026 |
| Eigener Test | 20 parallele Requests → 4 503er (20%) | 16.09.2026 |

**Bewertung:** 20 parallele Requests = 20 RPM (unter Limit). 503er kommen von NVIDIA-seitiger Überlastung, nicht von unserem Usage.

## pdf-verify-mcp Test (16.09.2026)

| Test | Ergebnis | Quelle |
|---|---|---|
| `npx @shuji-bonji/pdf-verify-mcp` | ✅ 7 Tools gelistet | Eigener Aufruf |
| `evaluate_policy` auf CV-sirine-ilahi.pdf | `use_with_caution` (kein Signatur, 2 Revisions) | Eigener Test |
| `verify_integrity` auf CV-sirine-ilahi.pdf | 2 Revisions, 1 Incremental Update | Eigener Test |
| npm Registry | Version 0.26.0 | `registry.npmjs.org` |
| **Keine pip-Installation nötig** | Funktioniert via npx | Bewiesen |
