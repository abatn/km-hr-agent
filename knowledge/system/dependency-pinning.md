# Dependency-Pinning (Reproduzierbarkeit) — P7

**Stand:** 08.10.2026
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
