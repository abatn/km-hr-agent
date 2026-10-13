# Mitwirken am KM-HR-Agent

Danke für dein Interesse! Dieses Projekt folgt einem strengen, quellenbasierten Arbeitsstil.
**Die Lab-Prinzipien sind bindend — keine Ausnahme.**

---

## 1. Die Lab-Prinzipien (Gesetz)

> Gilt ab 15.09.2026 · Für jede Aufgabe verbindlich.

### Schritt 1 — Quelle finden
Bevor du eine Zahl, eine Regel oder einen Wert verwendest, **musst** du eine externe Quelle finden:
- Gesetz (z. B. `ansvar-german-law`, gesetze-im-internet.de)
- Studie (z. B. SHRM, LinkedIn)
- Offizielle Dokumentation (z. B. Bipperz, docs.vdo.ninja)

Findest du keine Quelle: **sage es klar** und kennzeichne den Wert als **„Design-Entscheidung"**.

### Schritt 2 — MD-first
Schreibe die Logik in `skills/*/SKILL.md` und `knowledge/` — **nicht** in Python.
Nur wenn MD nicht ausreicht (UI, DB, API), darf Python genutzt werden.

### Schritt 3 — Konsistenz prüfen
Vergleiche `SKILL.md` und Code. Wenn sie nicht übereinstimmen: **korrigiere das MD** — nicht den Code.

### Schritt 4 — Transparenz
Dokumentiere jede Entscheidung in `ergebnisse/entscheidungen.md`:
- **Was** wurde geändert?
- **Warum?**
- **Welche Quelle?**

### Schritt 5 — Iteration
Arbeite **einen Skill nach dem anderen** ab. Nicht alles auf einmal.

### Regeln (verbindlich)
- Keine Erfindungen — jede Zahl hat eine Quelle oder wird als „Design-Entscheidung" gekennzeichnet.
- Kein Code, wo MD reicht.
- Keine Inkonsistenz zwischen MD und Code.
- Keine Behauptung ohne Beweis.

---

## 2. Entwicklungsumgebung

```bash
# 1) venv
python3 -m venv .venv-streamlit
source .venv-streamlit/bin/activate
pip install -r requirements.txt

# 2) Secrets (NICHT committen — .gitignore deckt .env* ab)
cp .env.example .env
#   KMHR_STORAGE_SECRET und KMHR_ADMIN_SEED_PASSWORD setzen

# 3) Starten
./start-webui.sh              # http://localhost:8080
KMHR_DEV=1 ./start-webui.sh   # Entwicklung ohne Secrets (nur lokal)
```

Direkter Start `python3 -m webui.main` braucht dieselben Secrets, sonst Abbruch (R3-4).

## 3. Tests

```bash
pytest -q                       # Unit/Integration (Zahlen + CI-Parität: siehe AGENTS.md, Abschnitt „Tests" — hier keine eigenen Zahlen, „ein Fakt ein Ort")
python3 tests/e2e_isolation.py  # E2E (Playwright) — ISOLIERT, nie gegen die Live-App
```

**Regeln:**
- E2E **nur** über `tests/e2e_isolation.py` (der Harness bricht ohne `KMHR_E2E_BASE` ab, R6-0).
- Vor `--port N` prüfen, dass **N frei** ist (`ss -ltn | grep :N`) — sonst läuft der Test gegen einen Alt-Server.
- **Live-DB** (`data/feedback.db`) nie direkt schreiben; Tests nutzen den Spiegel (`tests/conftest.py`).
- Nach Änderungen: `pytest -q` grün, Live-DB-sha256 unverändert.

## 4. Code-Konventionen

- **NiceGUI-App** (`webui/`), frameworkfreie Layer `db.py`/`logic.py`, **deutsche UI**.
- Externe Dienste **nur** über die MCP-Connectoren aus `opencode.json` (kein direkter `requests`-Aufruf an Fremd-APIs außer der dokumentierten NVIDIA-API im Runner).
- **i18n:** kein f-String in `_()` → `_("…{0}…").format(x=…)` (Ruff INT001); Modul-Konstanten mit UI-Strings erst zur **Renderzeit** übersetzen.
- **Zeilenangaben:** `Datei:Zeile` ist kein stabiler Verweis → Zitate mit **Codemarke** (`PAGE_MAP`, `_TAB_MAP`) und/oder Messdatum.
- **`.bak`-Retention:** nur die letzten 2 Kalendertage behalten.

## 5. Pull-Request-Ablauf

1. **Plan zuerst** — beschreibe Was/Warum/Quelle (Lab Schritt 1+4). Ohne Plan keine Modifikation.
2. **MD-first** — Spec/knowledge zuerst, dann Code.
3. **Konsistenz** — MD ↔ Code abgleichen.
4. **Verifikation** — Tests + (bei UI) isolierter Browser-Nachweis mit Screenshot.
5. **Doku** — Eintrag in `ergebnisse/entscheidungen.md`; relevante `AGENTS.md`-Zeile aktualisieren.
6. **Commit** — aussagekräftig, ein Thema pro Commit.

## 6. Commit-Nachrichten

Kurz, imperativ, mit Bezug zur Spec:

```
VDO: Raumname alphanumerisch (prescreening{code}) statt pre-screening-{code}

- Quelle: docs.vdo.ninja &room (aLphaNumEric)
- agent-runner.py + components.py + mcp-meeting-server.py
- Test tests/test_vdo_raumname.py; pytest 434 passed (Stand 10.10.2026)
- Doku: vdo-ninja-migration.md §2.5, entscheidungen.md
```

## 7. Sicherheit

- **Niemals Secrets committen** (`.env*`, `github.key`, Tokens, Schlüssel). `.gitignore` deckt `.env*` und `*.bak-*` ab.
- Keine personenbezogenen Daten (CVs, Bewerbungen, Reports) in das Repo — die Laufzeit-Ordner für Testdaten, Reports und Datenbank sind über `.gitignore` ausgeschlossen.
- Zugangsdaten nur über Umgebungsvariablen / `.env` (lokal).

## 8. Wo finde ich was?

| Thema | Datei |
|---|---|
| Projektwissen + Lab-Prinzipien | `AGENTS.md` |
| Skills-Übersicht | `instructions.md`, `skills/README.md` |
| Wissensbasis | `knowledge/` (legal/, lifecycle/, portal/, system/) |
| Entscheidungen/Transparenz | `ergebnisse/entscheidungen.md` |
| Agent-Automatisierung | `knowledge/system/agent-automation.md` |
| Zugriffskontrolle | `knowledge/system/access-control.md` |
| Meeting-Provider | `knowledge/system/vdo-ninja-migration.md` |
| i18n | `knowledge/system/i18n.md` |

---

*Fragen? Issue eröffnen. Keine Rechtsberatung — Rechtsfragen sind anwaltlich zu prüfen.*
