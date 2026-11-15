# Dependency-Pinning (Reproduzierbarkeit) — P7

**Stand:** 08.10.2026 (Ergänzung 15.11.2026: Dev-Dependency `playwright`, siehe unten)
**Zweck:** Verhindern, dass CI/Deploy **andere** Bibliotheksversionen installieren als lokal getestet
(„Dependency-Drift"), die den MCP-Stack still brechen könnten.
**Quelle (S1):** Portierung aus `backup-vor-revert-20261005` (`knowledge/system/dependency-pinning.md`,
05.10.2026), angepasst auf `main` (SQLite-Betrieb, kein Postgres).

---

## Problemstellung

`requirements.txt` nutzte offene Untergrenzen (`nicegui>=3.0.0`, `fastmcp>=4.0.0`). Ein Build kann damit
neuere Minor-Versionen ziehen als die lokal verifizierten. Der MCP-/Agent-Stack (`fastmcp`, `mcp`) ist
davon besonders betroffen (API-Änderungen).

## Wissensgrundlage (Schritt 1) — mit Kennzeichnung

- **Eigene Messung 08.10.2026** (venv, `importlib.metadata`): `nicegui` 3.17.1, `fastmcp` 4.0.11, `mcp` 2.3.0.
- **Frühere Messung (Backup, 05.10.2026):** Render-Build zog `mcp` 2.3.0 / `fastmcp` 4.0.11, lokal war teils 2.2.0/4.0.3 → Drift.
- **Design-Entscheidung:** *dass* und *welche* Pakete exakt fixiert werden (keine externe Norm erzwingt Pinning).

## Lösung (Schritt 2)

`requirements.txt` fixiert die drift-kritischen Pakete **exakt**:

```
nicegui==3.17.1
fastmcp==4.0.11
mcp==2.3.0          # bisher nur transitiv über fastmcp → explizit sichtbar/fixiert
```

**Bewusst NICHT fixiert/aufgenommen:** `psycopg`/`psycopg-pool` — `main` betreibt **SQLite** (Postgres nur
relevant, falls P1/Cloud portiert wird). Übrige Pakete (`babel`, `argon2-cffi`, `requests`, `PyMuPDF`,
`reportlab`, `Pillow`, `python-dateutil`, `streamlit`) bleiben bei `>=` (geringes Drift-Risiko, S5 „nicht alles auf einmal").

## Kennzeichnung (Lab-Prinzip)

| Aspekt | Kennzeichnung |
|---|---|
| Reproduzierbare Builds / Pinning | ❌ Design-Entscheidung (Best Practice, keine zitierbare Vorschrift) |
| Versionen 3.17.1 / 4.0.11 / 2.3.0 | eigene Messung 08.10.2026 |

## Konsistenz (Schritt 3) / Transparenz (Schritt 4)

- Abgleich Spec ↔ `requirements.txt` ↔ installierte Versionen; bei Abweichung zuerst diese Spec korrigieren.
- Log: `ergebnisse/entscheidungen.md` 08.10.2026.

## Verifikation

- Guard-Test `tests/test_requirements_pinned.py`: erzwingt `==` für die drei Pakete (kein Rückfall auf `>=`).
- Installierte Versionen == Pins (Messung 08.10.2026).

---

## Ergänzung 15.11.2026: Dev-Dependency `playwright`

**Problem:** `requirements-dev.txt` enthielt nur `playwright>=1.63.0` (Untergrenze). Der E2E-CI
(`.github/workflows/e2e.yml`) installiert bei jedem Lauf `pip install -r requirements-dev.txt` und
zieht damit die **jeweils neueste** Version — gemessen in den CI-Logs: 1.64.1 (03.–09.11.),
1.65.0 (10./11.11.), 1.65.1 (12./13.11.), 1.65.2 (14./15.11.2026). Damit war jeder E2E-Lauf
nicht reproduzierbar (Genau der Fall „Dependency-Drift", für den diese Spec 08.10. geschrieben wurde —
der Pin deckte aber nur die drei Prod-Pakete ab).

**Lösung:** `requirements-dev.txt` fixiert `playwright==1.65.2` (Stand der CI-Läufe 14./15.11.2026;
Chromium 159.0.8154.6). Damit `playwright install --with-deps chromium` im CI ebenfalls denselben
Browser-Build zieht.

**Kennzeichnung (Lab-Prinzip):** Die Pin-Wahl ist eine Design-Entscheidung (keine externe Norm);
Version 1.65.2 = eigene Messung aus den CI-Logs 14./15.11.2026. **Kein Kausalnachweis**, dass 1.65.2
den E2E-Fehler verursacht (prüfung 15.11.2026: roter Lauf 05.11. unter identischer Version 1.64.1 wie
vier grüne danach) — der Pin sichert Reproduzierbarkeit, nicht die Race-Behandlung (die sitzt in
`tests/e2e_apply_dialog_multi.py`).

**Verifikation:** Guard-Test `test_playwright_dev_exakt_fixiert` in `tests/test_requirements_pinned.py`
erzwingt `playwright==1.65.2` und verbietet `playwright>=` in `requirements-dev.txt`.
Log: `ergebnisse/entscheidungen.md` 15.11.2026.
