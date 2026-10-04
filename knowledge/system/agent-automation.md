# Agent-Automatisierung (Agent-Queue + Hintergrund-Runner)

> **Stand:** September 2026 (v6 – Visum-Workflow: verify_documents + visa_confirmation + Visa-Schritte im Onboarding; **✅ IMPLEMENTIERT 12.09.2026: Runner-Tasks, Hooks an 3 Sites, E2E T1–T8 bestanden, Testdaten entfernt** · **v6.1 (Dokumenten-Tab):** 👤 Candidate Portal → Tab „🗂️ Dokumente" (Typ-Auswahl, Multi-Upload, Art.-17-Löschung, kein Profil-Overwrite) + Tabelle `candidate_documents` als typed Quelle für verify_documents + frist-basierte DSGVO-Löschung der Dateien — **✅ implementiert + E2E T1–T5 bestanden**) (Spec v3 – erstellt 12.09.2026, **✅ IMPLEMENTIERT + GETESTET am 12.09.2026: 8/8 E2E-Checks bestanden, DSGVO-Testdaten entfernt, Server HTTP 200, Runner-Autostart aktiv**)  
> **Zweck:** Der komplette Ablauf (Bewerbung → Agent-Kette → HR-Entscheidung → Einladung/Ablehnung → Onboarding) läuft automatisch. Das Portal schreibt nur **Tasks in eine Queue**; ein **Hintergrund-Runner** führt sie aus – **direkt über die Projekt-MCP-Connectors** (deterministische Tasks) und für LLM-Aufgaben via **direkte NVIDIA-API** (`requests.post` auf `integrate.api.nvidia.com/v1/chat/completions`; Stand 13.09.2026, ersetzt `opencode run`).  
> **Grundregel (Zwei-Ebenen-Modell, access-control.md v3.1):** Das Portal sieht die Agent-Werkzeuge nie. Skills 0️⃣–5️⃣ laufen ausschließlich auf der Agent-Ebene.  
> **User-Entscheidungen (12.09.2026, ergänzt 12.09.2026 v3):** Trigger = **Bewerbung UND CV-Upload** · Ausführung = **Hintergrund-Runner** · E-Mails = **4 Punkte** (Eingang, HR-Info nur bei JA, Einladung, Ablehnung) · **Meetings = Jitsi (KEIN Google Meet)** · **JA/NEIN-Regel (Pförtner):** Score ≥ 60 UND Compliance = COMPLIANT → JA → HR-Mail; sonst NEIN → keine Mail, Ergebnisse bleiben für HR sichtbar (Suche/Talentpool) · **Variante A:** Der Agent lädt/lehnt NIE selbst ab – Einladung erst nach HR-Klick `→ eingeladen`, Absage-Mail erst nach HR-Klick `→ abgelehnt` (die Mail wird dann vom Agenten via email-sender gesendet, nie SMTP in app.py) · **v6-Entscheidungen:** Visum-INFO an HR **erst beim JA-Pfad** (in der notify_hr-Mail, NICHT sofort mit dem Badge) · Visum-Relevanz/Inhalt = **ansvar-law-basiert**: Der Agent beschreibt aus den geprüften Dokumenten WAS zu beantragen ist (Visen-/Aufenthaltstitel-Art), WIE (typische Schritte, Unterlagen, Fristen) und WO (zuständige Behörde je Land DE/FR/CH) — agent-generiert via ansvar-german/french/swiss-law, kein Behördenkontakt des Agents

---

## 1. Ziel-Ablauf (End-to-End)

```
CANDIDATE: Login → CV-Upload → 6️⃣ Pre-Screen (Selbstpräsentation) → 💼 Bewerben
   │
   ├─[EVENT: cv_uploaded]──────▶ QUEUE: Task "extract_profile"
   └─[EVENT: application_created]▶ QUEUE: Tasks "match_candidate" → "check_compliance"
                                    → "assess_culture_fit"
   ↓ (Runner, Hintergrund)
AGENT: LLM-Tasks via direkte NVIDIA-API (Extract → Match → Compliance → Culture Fit → Documents → Visa),
       deterministische Tasks direkt via MCP-Connectors (Mails, ICS, Fragen, Meeting-Link)
   ├─ ergebnisse/match-*.md, compliance-*.md, kultur-fit-*.md
   ├─ E-Mail an Kandidat: „Bewerbung eingegangen, wird geprüft" (email-sender)
   ├─ JA/NEIN-Auswertung (Runner, Regel §3):
   │    JA  (Score ≥ 60 UND COMPLIANT)  → E-Mail an HR: „Match-Ergebnis bereit (Score N)" (email-sender)
   │    NEIN (Score < 60 ODER nicht COMPLIANT) → KEINE Mail – Ergebnisse bleiben für HR sichtbar (Suche/Talentpool)
   └─ DB: agent_tasks.status = done, result_path gesetzt
   ↓
HR (Portal, nur Ergebnisse):
   2️⃣ Match-Ergebnis (read-only) · 3️⃣ Compliance-Ergebnis (read-only)
   8️⃣ Store Feedback → ENTSCHEIDUNG
   │
   ├─ JA  ─[EVENT: status→eingeladen]─▶ QUEUE: "create_invitation"
   │        Runner (MCP-direct, kein LLM):
   │        Meeting-Raum https://vdo.ninja/?director=prescreening{code} (KEIN Google Meet, KEIN Jitsi)
   │        + Fragen (meeting-tools.generate_screening_questions)
   │        + ICS (meeting-tools.generate_ics_file, meet_url = VDO.Ninja-Raum)
   │        + E-Mail (email-sender.send_pre_screen_invitation)
   │        → Kandidat sieht Termin + VDO.Ninja-Link + ICS in 💼 Tab 2
   │        → nach Gespräch(en): status → eingestellt
   │        └─[EVENT: status→eingestellt]─▶ QUEUE: "onboarding_release"
   │              → 7️⃣ Onboarding-Freigabe an Kandidat (bestehender Mechanismus)
   │
   └─ NEIN ─[EVENT: status→abgelehnt]─▶ QUEUE: "send_rejection"
            Runner (MCP-direct): E-Mail send_email (neutral, AGG-sicher, KEINE
            Diskriminierungsmerkmale)
            → Kandidat sieht Statuswechsel in 💼 Tab 2 (wie bisher) + E-Mail
```

---

## 2. Queue-Tabelle `agent_tasks` (SQLite, data/feedback.db)

```sql
CREATE TABLE IF NOT EXISTS agent_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,            -- 18 Dispatch-Typen (Stand 25.09.2026), 2 Gruppen:
                                        -- [deterministisch, 9] send_confirmation | send_rejection |
                                        -- create_invitation | onboarding_release | visa_confirmation |
                                        -- notify_hr | export_report | handle_errors | contract_preflight
                                        -- [LLM, 9] extract_profile | match_candidate | check_compliance |
                                        -- assess_culture_fit | verify_documents | check_visa | notify_user |
                                        -- check_gdpr | explain_match
                                        -- Hinweis: handle_errors wird nie gequeued → 17 DISTINCT task_type
                                        -- in agent_tasks (Beweis: sqlite3 COUNT(DISTINCT task_type) = 17)
    status TEXT DEFAULT 'pending',      -- pending | running | done | failed | skipped
    payload TEXT NOT NULL,              -- JSON: candidate_id, job_id, application_id, kontext
    result_path TEXT,                   -- ergebnisse/*.md (Agent-Ausgabe)
    result_json TEXT,                   -- Runner-Ausgaben (vdo_ninja_url, ics_path, termin, mail, Gatekeeper-Entscheid)
    error_text TEXT,                    -- bei failed
    attempts INTEGER DEFAULT 0,         -- Max. 3, dann failed final
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
```

**Erweitertes Schema (Implementierung v3):** `result_json` speichert Runner-Ausgaben (vdo_ninja_url, ics_path, termin, mail, gatekeeper-Entscheid) für die Portal-Sichten. Tabelle wird beim App-Start idempotent angelegt (init_agent_tasks_table()).

**Regeln:**
- App schreibt NUR INSERTs (Events) – nie Agent-Logik im UI-Prozess.
- Ein Task pro Event; abhängige Tasks (Match braucht Extract) plant der Runner: Er setzt `match_candidate` etc. auf `pending` erst, wenn `extract_profile` = `done` (Kette im Runner, nicht in der DB).
- Idempotenz: Vor dem INSERT prüft die App, ob für (task_type, payload.application_id, heutiges Datum) bereits ein Task existiert – verhindert Doppel-Task bei Streamlit-Reruns.

## 3. Trigger-Matrix (App-Events → Tasks)

| Event (app.py Hook) | Task(s) | Bemerkung |
|---|---|---|
| CV-Upload erfolgreich (Candidate 📤) | `extract_profile` | User-Entscheidung: Agent extrahiert sofort nach Upload |
| Bewerbung erstellt (💼 Bewerben) | `match_candidate`, `check_compliance`, `assess_culture_fit` (+ falls Extract noch offen: auch `extract_profile`) | User-Entscheidung: volle Kette bei Bewerbung |
| `status → eingeladen` (💼 oder 🏢, seit Phase 2 auch 🛡️ Admin-Bewerber-Verwaltung, `trigger: admin_klick`) | `create_invitation` | JA-Pfad: VDO.Ninja-Raum + Fragen + ICS + Einladungs-Mail |
| `status → abgelehnt` (💼 oder 🏢, seit Phase 2 auch 🛡️ Admin) | `send_rejection` | NEIN-Pfad (HR-Entscheid): Agent sendet Absage-Mail **NUR nach HR-Klick** (Variante A) |
| `status → eingestellt` (💼 oder 🏢, seit Phase 2 auch 🛡️ Admin) | `onboarding_release` | bestehender 7️⃣-Mechanismus wird triggerbar; **Spec v6:** Checkliste enthält Visum-Schritte, wenn Visum-relevant. **Phase 2 (20.09.2026):** Übergänge aus der Admin-Bewerber-Verwaltung (webui/pages/admin.py, Muster employer.py:429–492) erzeugen dieselben Tasks mit `trigger: admin_klick` — E2E belegt (Task #105 send_rejection, Phase-2-Doku) |
| Bewerbung erstellt (zusätzlich) | `send_confirmation` | Eingangsbestätigung an Kandidaten |
| Bewerbung erstellt (zusätzlich, **Spec v6**) | `verify_documents` | Agent prüft Zeugnisse/Sprachzeugnisse (Herkunft Kandidat) via pdf-reader + Law-Routing DE/FR/CH; HR-Badge erweitert um „Dokumente ✅/⚠️"; **Visum-Auswertung (was/wie/wo, ansvar-law) landet im result_json** und geht **erst beim JA-Pfad** als INFO-Zeilen in die notify_hr-Mail (User-Entscheidung v6) – nur Info, Agent stellt keinen Antrag |
| Bewerbung erstellt (zusätzlich, **Spec v6.2**) | `check_visa` | Agent prüft Visum-Pflicht, Aufenthaltszweck (§18g Blaue Karte EU; §18a/§18b weitere Titel — Korrektur P4 26.09.2026), Blue Card, Anerkennung (BQRF) basierend auf Staatsangehörigkeit + Stellenland; LLM-Task mit compactem Prompt (visa-rules.md-Regeln inline); Ergebnis: ergebnisse/check_visa-kandidat-N-datum.md; HR-Badge im Portal: Streamlit `st.metric „Visum-Status"` + Report-Expander (app.py:2165-2172 Agent-Kompass, 3700-3708 Match-Sicht); NiceGUI: Badge-Parsing `_badge_icon` (employer.py:926-939, C5 22.09.2026) + Visa-Button (employer.py:450-467). **✅ LIVE GETESTET 13.09.2026** (Task #50, nemotron-120b via direkte API: tunesischer IT-Admin → Visum ERFORDERLICH, Blue Card möglich, Anerkennung freiwillig; Bericht `ergebnisse/check_visa-kandidat-7-2026-09-13.md`) |
| HR-Klick „📩 Visum-Antrag bestätigen" (**Spec v6**; seit Phase 2 auch aus 🛡️ Admin-Bewerber-Verwaltung bei `eingeladen`) | `visa_confirmation` | **NUR nach diesem HR-Klick (Variante A):** Agent sendet dem Kandidaten eine E-Mail mit dem Visum-WAS/WIE/WO aus der verify_documents-Auswertung (agent-generiert via ansvar-law, ohne Behördenkontakt des Agents) |
| Runner-intern: Kette done → JA/NEIN-Auswertung | JA → `notify_hr` · NEIN → **kein Task** | **Pförtner-Regel:** Score ≥ 60 UND Compliance = COMPLIANT → JA (Mail an HR); sonst NEIN (kein Mail, Ergebnisse bleiben für HR sichtbar). **Abfragen exakt + generation-bewusst (R3-1/R3-2, 30.09.2026):** `json_extract(payload,'$.application_id') = ?` statt LIKE-Präfix, Ketten-Zustand mit `ORDER BY id` (neuester Task-Stand gewinnt), `notify_hr` idempotent **je Generation** (`COALESCE(gen,0)`, Altbestand = 0) — Details §3.1 |
| HR-Klick „📄 Vertrags-Check starten" (🏢 Onboarding, **Phase D P8**, 24.09.2026) | `contract_preflight` | **Deterministisch (kein LLM, kein Mailversand):** Gehalt vs. Mindestlohn-Wert **aus** `knowledge/legal/contract-sources.md` (Key `mindestlohn_2026`, 13,90 €/h Stand 2026, Quellenstatus sekundär), Formfall-Tabelle (§14/§126a/§623), NachwG-Checkliste, Quellen-Tabelle aus dem Link-Katalog (**0 hartkodierte Links in Python**, USER-GO). Variante-A-Guard: `trigger ∈ {hr_onboarding_klick, hr_klick_portal, hr_klick_hr_seite, admin_klick}`. Report: `ergebnisse/contract-preflight-bewerbung-{app_id}.md`, Sicht in Agent-Details. **Kein Signatur-Dienst** (Optionen A–F bleiben User-Wahl, Spec contract-management.md §4) |

> ⚠️ **Design-Entscheidung (15.09.2026):** Die Schwelle Score ≥ 60 als Pförtner hat **keine externe Quelle** (kein Industriestandard, kein Gesetz). **Alternative:** Schwelle aus eigener Datenanalyse ableiten (z.B. Median aller Scores die zu einer Einstellung führten). **Validierung:** Nach 20+ Einstellungsentscheidungen prüfen ob 60 sinnvoll trennt (False-Positive-Rate < 20%).

### 3.1 Pförtner-Abfragen + Generation (R3-1/R3-2, 30.09.2026)

**Abfragen exakt (R3-1).** `_maybe_gatekeeper` (`scripts/agent-runner.py:1143`) liest die Bewerbung in **beiden** Abfragen per `json_extract(payload, '$.application_id') = ?` statt per LIKE-Präfix `%"application_id": N%` — der Präfix-Vergleich traf bei `N=1` auch 10/11/160 (Präfix-Kollision). Umfang: Ketten-Zustand **und** notify_hr-Zählung.

- **Ketten-Zustände** (`agent-runner.py:1167-1173`): `json_extract(payload,'$.application_id') = ?` + `COALESCE(json_extract(payload,'$.gen'),0) = ?` + `task_type IN ('match_candidate','check_compliance','assess_culture_fit')` + **`ORDER BY id`**; die Zeilen werden in Abfrage-Reihenfolge eingespeist (`:1174-1176`) → **der letzte Eintrag je task_type gewinnt = neuester Stand** (vorher `dict()` aus unsortierten Zeilen → bei mehreren Tasks desselben Typs gewann zufällig einer).
- **notify_hr-Zählung** (`:1180-1184`): ebenfalls `json_extract … = ?` + Gen-Filter.
- **Notify_hr-Marker** (`:1193-1196`): Payload trägt `"gen": current_gen`.

**Generation (R3-2, Nutzer-GO „A: Generation-Zähler“).** Jedes Bewerbungs-Queue-Payload trägt `gen` (`webui/db.py:194-195`):

| Fall | `gen` | Codestelle |
|---|---|---|
| Erstbewerbung | `0` | `webui/db.py:191` |
| Reaktivierung (`zurückgezogen` → „Erneut bewerben“) | `MAX(COALESCE(gen,0)) + 1` über alle Tasks der Application | `webui/db.py:170-179` |

- **Dedupe gen-bewusst:** `queue_agent_task` prüft zusätzlich `AND COALESCE(json_extract(payload,'$.gen'),0) = ?` (`webui/db.py:80`, Wert aus `payload.get("gen", 0)` `:71`) → dieselbe Kette kann am selben Tag als **neue** Generation gequeued werden; gleicher Tag + Typ + App + **gleiches** `gen` wird weiterhin geduped.
- **notify_hr-Guard gen-bewusst:** `_maybe_gatekeeper` bestimmt `current_gen = MAX(COALESCE(gen,0))` über alle Tasks der Application (`agent-runner.py:1162-1166`) und filtert Ketten-Zustand **und** notify_hr-Zählung darauf (`:1169`, `:1182`) → ein alter notify_hr-Marker einer früheren Generation blockiert die Auswertung einer neuen Generation **nicht**; zweiter Sweep derselben Generation fügt kein zweites `notify_hr` hinzu (idempotent pro Generation).
- **Altbestand ohne `gen`-Feld:** `COALESCE(…, 0)` liest Bestands-Tasks als Generation 0 → **Verhalten für Bestandsdaten unverändert** (Beleg `tests/test_r32_gatekeeper_gen.py::test_altbestand_ohne_gen_wird_als_0_gelesen`).
- **Design-Entscheidung (30.09.2026, keine externe Quelle):** Die Reaktivierung queue't dieselben Task-Typen wie die Erstbewerbung (eine Codepfad-Quelle, `webui/db.py::apply_to_job`); die erneute Eingangsbestätigung gilt als Bestätigung der Neubewerbung.
- **Tests:** `tests/test_r32_gatekeeper_gen.py` (In-Memory-Beweis für Bewerbungen 1/10/11/160, LIKE-Gegenprobe, notify_hr-Idempotenz je Generation, Dedupe-Grenze, `apply_to_job` gen 0/1/2), Quelltext-Nachweise in `tests/test_application_id_match.py::test_pförtner_quelle_ohne_like_und_mit_neuestem_stand`.

## 4. Hintergrund-Runner (`scripts/agent-runner.py`) – HYBRID v2

**Kernprinzip v2 (aktualisiert 13.09.2026):** Der Runner ruft die **Projekt-MCP-Connectors direkt** auf (stdio JSON-RPC, handshake-getestet ✅) – ohne LLM, ohne Modell-Abhängigkeit, in Sekunden. Die LLM-Tasks (Extract/Match/Compliance/Culture-Fit + v6/v6.2: verify_documents, check_visa) laufen über die **direkte NVIDIA-API** (`requests.post`, `import requests`, Script `scripts/agent-runner.py` 559–565) — **nicht mehr via `opencode run`** (lieferte nur `step_start`-Events ohne Text, Modell antwortete korrekt → Root-Cause war opencode, nicht das Modell; live verifiziert 13.09.2026).

| Aspekt | Umsetzung |
|---|---|
| Start (**Autostart-Guard, F1, 23.09.2026**) | Beim App-Start geprüft (wie DSGVO-Hook), **3 Fälle in `ensure_agent_runner()` (webui/logic.py:572)**: **(a)** PID-File `data/agent-runner.pid` existiert UND PID lebt (`os.kill(pid, 0)`) UND `/proc/{pid}/cmdline` enthält `agent-runner.py` → **kein Neustart**, Log „vorhandener Runner genutzt"; **(b)** PID tot / File verwaist (stale) → **stale File löschen (`Path.unlink()`), dann neu starten** (`setsid nohup`); **(c)** `KMHR_RUNNER_AUTOSTART=0` → harter Stopp, nie spawnen. Alternativ cron. **Runner-Zählung nie `pgrep -fc`** (zählt den eigenen Bash-Wrapper mit → falsche Hochzählung), sondern `pgrep -fa "agent-runner.py" \| grep -v "bash -c" \| grep -v pgrep`. |
| Loop | Alle 60 s: `SELECT * FROM agent_tasks WHERE status='pending' ORDER BY id LIMIT 5` |
| **Ausführung A – MCP-direct (deterministisch)** | Runner baut JSON-RPC-Requests an die Connector-Server aus `opencode.json` (Subprocess stdio, dasselbe Muster wie der Handshake-Test): `create_invitation` → Raum-URL als String (VDO.Ninja, **kein** Meeting-Tool) + `meeting-tools.generate_screening_questions` + `meeting-tools.generate_ics_file` + `email-sender.send_pre_screen_invitation`; `send_confirmation`/`notify_hr`/`send_rejection` → `email-sender.send_email`. **Kein `opencode run`, kein Modell nötig – 100% deterministisch.** |
| **Ausführung B – LLM-Tasks (v3, Stand 13.09.2026)** | `extract_profile`, `match_candidate`, `check_compliance`, `assess_culture_fit`, `verify_documents`, `check_visa` → **direkte NVIDIA-API**: `requests.post("https://integrate.api.nvidia.com/v1/chat/completions", …)` → `choices[0].message.content` (Templates §5, Key via NVIDIA NIM); zuvor `opencode run` — verworfen, weil nur `step_start` ohne Text zurückkam. Direkte API live getestet (13.09.2026: Mini-Prompt „Say hello" → "Hello!", Visum-Prompt → „Visum-Status: ERFORDERLICH"; Task #50 done, 1 Versuch) |
| Meeting-Raum (Entscheidung 27.09.: VDO.Ninja statt Jitsi vom 12.09.) | Raum-URL = Projektstandard wie `agent-runner.py:497` (`def create_invitation`) / **`:518` (die URL selbst)**: `https://vdo.ninja/?director=prescreening{code}` (kostenlos, Peer-to-Peer, kein Account). **Kein** Meeting-Tool-Aufruf — die URL wird als String gebildet; `jitsi-meeting` ist am 27.09.2026 entfernt. **Kein Google Meet** (`create_meeting_link` wird NICHT verwendet) |
| Nachlauf | result_path aus Agent-Ausgabe parsen (oder Standardpfad `ergebnisse/{task_type}-{id}-{datum}.md` erzwingen), `finished_at` setzen, bei Fehler `attempts+1`, ab 3 → `failed` |
| Stabilität | MCP-direct: Timeout 60 s/Tool. LLM-Tasks: max. 10 min (Timeout → failed + Retry). Fehlgeschlagene Connectors → `failed` + Eintrag in `logs/agent-errors.log` (Konvention hr-api-connectors.md §6) |
| **Log-Beweissicherung (A, 23.09.2026)** | `/tmp/nicegui.log` = E2E-Beweismittel (Guard-Zeilen „Hintergrund-Runner gestartet" / „stale pidfile" / „vorhandener Runner genutzt", Traceback-Zähler). **Vor JEDEM Server-Neustart sichern:** `cp /tmp/nicegui.log /tmp/nicegui.log.bak-$(date +%Y%m%d-%H%M)` — kein rm, ältere .bak bleiben liegen. **Start NUR mit Append:** `setsid nohup .venv-streamlit/bin/python3 -m webui.main >> /tmp/nicegui.log 2>&1 < /dev/null & disown` — **niemals `>`** (Truncation löscht Guard-Historie). Kill und Spawn IMMER in getrennten Shell-Calls (pkill-Selbstmord-Falle, Pattern `[w]ebui.main`). Schritt-0 23.09.2026: Truncation-Spawn `>` existiert **nicht** im Repo (`start-webui.sh:7` ohne Redirect; Runner-Spawn `webui/logic.py:607-609` → DEVNULL) → A2 „Code-Rotation" entfällt als widerlegt; Log-Birth 2026-09-22 22:21 belegt frühere externe Überschreibung → Regel deshalb bindend. Datei-Backup vor dieser Änderung: `agent-automation.md.bak-20260923-1150`. |
| **send_rejection-Guard (C1/O2, 23.09.2026)** | Spec (jetzt implementierter Code): `send_rejection()` prüft VOR dem Mailversand ZWEIERLEI, Struktur analog `visa_confirmation` (`agent-runner.py:349`) / `create_invitation` (`:485`): (1) `payload["trigger"] ∈ {hr_klick_portal, hr_klick_hr_seite, admin_klick}`, sonst `RuntimeError("Variante A verletzt: send_rejection nur nach HR-Klick")`; (2) die zugehörige Bewerbung `payload["application_id"]` hat `applications.status = "abgelehnt"` (alle 5 Trigger-Quellen updaten den Status VOR dem Queue: `app.py:3192`/`:3767`, `employer.py:425`/`:648`, `admin.py:594`), sonst RuntimeError „nur bei Status 'abgelehnt'". Abbruch = Exception → `process_task` → `finish_task(ok=False)` + Log-Zeile `✓ Task #N FEHLER: …` (`agent-runner.py:1347`, Log-Datei `log()` `:139-147`) → **kein Mailversand** (`mcp_call` wird nie erreicht). Quelle: Variante A AGENTS.md:81 (user-approved 12.09.2026), Zeilen :87/:123/:125, Runner-Docstring :20-21/:348; C1-Offener-Punkt SKILL:231 + phase2:364 (Task #105 lief ohne Guard durch); Tests `tests/test_send_rejection_guard.py` (NEGATIV/POSITIV, `mcp_call` immer gemockt — nie echter Mailversand). |
| **Identity-Regel Match-Dialoge (NB1+NB4, umgesetzt 23.09.2026)** | Spec: Die 3 Match-Dialoge (`webui/pages/employer.py` _page_match: Einladen/Ablehnen/Einstellen) speichern im State ausschließlich die Candidate-ID (`_invite_cid`/`_reject_cid`/`_hire_cid`, Quelle Button-Lambda `cid=c_id`). Die echte `application_id` wird AM QUEUE-PUNKT per SELECT aufgelöst: `JOIN jobs` auf `employer_id` (Closure `:572`), Aktiv-IN-Liste `('eingegangen','angesehen','eingeladen')`, `ORDER BY a.id DESC`. **Reject:** flippt ALLE aktiven Apps des Kandidaten bei diesem Employer (UPDATE + History je App) und queued GENAU EIN `send_rejection`-Task `{application_id: ids[0], candidate_id: cid, trigger: hr_klick_portal}`. **Invite/Hire:** neueste aktive App (`ids[0]` aus dem Helper, äquivalent zu `LIMIT 1`), nur diese wird geupdatet; Payloads `create_invitation`/`onboarding_release` enthalten zusätzlich `candidate_id` (onboarding_release wertet es für die Visum-Auswertung aus, `agent-runner.py:1301`). **Kein aktiver Treffer** → `ui.notify`-Fehler, kein DB-Write, kein Task. **Terminal-Status** (`eingestellt`/`abgelehnt`/`zurückgezogen`) werden von keinem der 3 Dialogen angefasst (erl-Matrix `employer.py:374`; Regeln (a)-(d) + Korrektur (c) 23.09.2026). |
| **NB1 Payload-Lücke `send_rejection` (doku-only, Entscheidung 23.09.2026; Behavior-Altstand)** | `webui/pages/employer.py:631` (alt, Match-Dialog „Ablehnen") queued `send_rejection` NUR mit `{application_id, trigger}` — **OHNE `candidate_id`** (die anderen 4 Queue-Stellen liefern es: `app.py:3779-3781`, `app.py:3199-3201`, `employer.py:431-433`, `admin.py:600-601`). Folge: Guard wird bestanden (Status ist `abgelehnt`), danach Candidate-Lookup `cid=None` → RuntimeError „Kandidat #None nicht gefunden" → `finish_task(ok=False)` → **kein Mailversand** (fail-safe, Variante A nicht verletzt), aber: die Absage-Mail wird auf diesem Pfad nie zugestellt. **Umgesetzt (23.09.2026, NB1+NB4+Regelkorrektur):** das `send_rejection`-Payload der Match-Dialoge trägt `candidate_id`; die echte `application_id` wird am Queue-Punkt per SELECT aufgelöst (Identity-Regel, **vorherige** Zeile) — der Backlog-Eintrag aus NB1 („Feature-Freeze hält ihn heraus") ist hiermit **erledigt**. Quelle: entscheidungen.md 23.09.2026 (NB1) + 23.09.2026 (NB1+NB4 Identity-Fix). |
| **NB5 (behoben, 23.09.2026): ASCII-Filter `zurueckgezogen` → `zurückgezogen`** | Ursprünglich 5 Altfilter + 3 Nebenstellen verglichen `'zurueckgezogen'` (ohne ü), die DB speichert `'zurückgezogen'` MIT UTF-8-ü (hex-verifiziert, Statuswert App 22) → Filter griffen nie. **Umgesetzt 23.09.2026 (NB5, user-Go):** `'zurückgezogen'` an `webui/pages/employer.py:696/:717/:1220` (SQL) + Label `:469`, `webui/pages/candidate.py:273` (History-Check), `webui/pages/admin.py:639` (Label), `scripts/agent-runner.py:969` (Auto-Refresh), `app.py:1879` (Parität, archiviert). Sweep: 0 ASCII-Treffer in Projektcode. Verifikation: App 22 korrekt ausgefiltert, Kandidat-1-Auto-Refresh enthält App 22 nicht mehr. |
| **NB6 (behoben, 23.09.2026, Code + Doku): Onboarding-Mail #6** | Ursprünglich doku-only festgestellt: Runner `onboarding_release` schrieb NUR den Freigabe-Report, kein `send_email` (Backlog-Claim aa:115/aa:161 + AGENTS/knowledge/instructions). **Umgesetzt 23.09.2026 (user-Go, Multi-Agent):** neue `send_onboarding_mail()` (`agent-runner.py:376-435`) mit Variante-A-Guard (`trigger ∈ {hr_klick_portal, hr_klick_hr_seite, admin_klick}`) + Status-Guard (`applications.status = 'eingestellt'`, `candidate_id` aus Lookup statt payload) + E-Mail-Check; Aufgerufen im selben `onboarding_release`-Handler (`agent-runner.py:1317-1320`) nach dem Freigabe-Report. Trigger-Payloads unvollständig → behoben: `employer.py:680` (+`job_id` via SELECT), `app.py:3783-3785` (+`trigger: hr_klick_portal`). Test `tests/test_send_onboarding_guard.py` (4 Guards, `mcp_call` immer gemockt); Gesamt pytest **26 passed**. DRY_RUN verifiziert: Task #149 → `[DRY-RUN] mcp-email-server.py::send_email args={"to":"e2e-beweis-phase1@example.com","subject":"Willkommen im Team …"}` + `✓ Task #149 done`, kein echter Versand. Quelle: entscheidungen.md 23.09.2026 (NB6). |
| **Anhang §4 Onboarding (P1-Klassifizierung, 24.09.2026)** | Der Onboarding-Release-Trigger existiert vollständig als `onboarding_release` — Queue `webui/pages/employer.py:680-681` ≙ Streamlit `app.py:3782-3785`/`:3198-3205`, Handler `scripts/agent-runner.py:1297-1321` inkl. Freigabe-Report `:1311` und Mail #6 `:1318`. Ein eigener Task-Typ `generate_onboarding` existiert auf keiner Ebene (app.py grep 0; Runner-Dispatch `:1322-1339` führt ihn nicht, else `:1338-1339` fängt nur echte Fremd-Typen) — die Checkliste erzeugt der HR-UI-Generator (Skill 7) inline, 1:1-Parität `app.py:2419-2515` ≙ `webui/components.py:657-797`. Damit fällt die ⚠️ in `ergebnisse/phase-d-paritaet-p1-p9.md:42` als Klasse (b) widerlegt. Quelle: P1-Bericht + entscheidungen.md 24.09.2026 (Phase-D-Runde 1). |

## 5. Task-Prompts (Templates, pro Typ)

Jeder Prompt referenziert die Skills + Wissensdateien (wie scripts/agent-test.sh, aber maschinell):

| task_type | Prompt-Kern |
|---|---|
| `extract_profile` | „Führe Skill extract-profile aus für Kandidat #N (CV: candidates.lebenslauf_pfad). Speichere ergebnisse/profil-kandidat-N-<datum>.md und **schreibe extrahierte Daten in die DB** (hard_skills, soft_skills, berufserfahrung_jahre, abschluss, deutsch, englisch via `_update_candidate_from_extract()`)." |
| `match_candidate` | „Führe Skill match-candidate aus: Kandidat #N vs. Job #M (DB-Felder). Nutze knowledge/lifecycle/matching-criteria.md. Speichere ergebnisse/match-kandidat-N-job-M.md." |
| `check_compliance` | „Führe Skill check-compliance aus (Land: DE/FR/CH aus Kandidat-Standort, + DSGVO). Nutze ansvar-*-law. Speichere ergebnisse/compliance-…md." |
| `assess_culture_fit` | „Führe Skill assess-culture-fit aus (Profil vs. Job/Unternehmen). Speichere ergebnisse/kultur-fit-….md." |
| `create_invitation` | **MCP-direct (kein LLM):** 1) Meeting-Räume: HR/Director `https://vdo.ninja/?director=prescreening{code}` + Kandidaten-Gast `https://vdo.ninja/?room=prescreening{code}&record=off` (seit 28.09.2026, Gates 8/9; Variablen `vdo_ninja_url`/`vdo_ninja_gast_url`; Muster agent-runner.py:497; **seit 27.09.2026 VDO.Ninja statt Jitsi**, Spec `knowledge/system/vdo-ninja-migration.md`, Jitsi-Aufzeichnung brauchte Jibri auf eigenem Server; Felder im Ergebnis-JSON: `vdo_ninja_url` (seit 27.09.2026) + `vdo_ninja_gast_url`/`recording: false`/`ics_path_hr` (seit 28.09.2026, Gates 8/10), Leser mit Legacy-Fallback auf `jitsi_url`), 2) `meeting-tools.generate_screening_questions` (mit echtem Match-Score aus DB), 3) `meeting-tools.generate_ics_file` (meet_url = GAST-Raum für den Kandidaten, `ics_path`; HR-Director-ICS `ics_path_hr` seit 28.09.2026), 4) `email-sender.send_pre_screen_invitation` (meet_url = GAST-Raum, seit 28.09.2026). `jitsi-meeting.jitsi_join_meeting` **entfernt 27.09.2026** (0 Aufrufe) — es gibt keinen Bot-Pfad mehr. Ablage: ergebnisse/einladung-bewerbung-M.md. **HR-Sicht (seit 12.09.2026):** bei Status `eingeladen` sieht HR an beiden Übergangs-Sites (💼 HR-Modus + 🏢 Portal Tab „👥 Kandidaten“) seit 28.09.2026 seinen eigenen Kalendereintrag mit dem **Director-Link** (`ics_path_hr`; der Kandidat bekommt den Gast-Link) – VDO.Ninja-URL, Termin und ICS-Download (Button „📅 Termin in Kalender speichern (.ics) – HR“, Key `ics_hr_{id}`, Helper `get_invitation_artifacts()` / `render_hr_ics_download()` in app.py). **Termin (seit Feature „HR-Terminauswahl"):** HR wählt Datum/Uhrzeit/Dauer direkt vor dem `→ eingeladen`-Klick (beide Übergangs-Sites); Payload-Felder `termin_datum`/`termin_uhrzeit`/`termin_dauer_min`; Runner validiert (Vergangenheit/Format/Dauer 10–180 Min.) mit Fallback morgen 10:00/30. **NiceGUI-Parität (C1, 22.09.2026):** alle drei `create_invitation`-Queuestellen MÜSSEN `termin_*` mitsenden — `webui/pages/employer.py` `_page_match` Dialog (602-645, Zeilenstand 28.09.2026; war korrekt als 559-589), `_page_stellen` Inline-Inputs wie app.py:3173-3185 (Quelle), `webui/pages/admin.py` `_page_stellen` analog (app.py:3173-3185). Ohne `termin_*` fällt der Runner auf Default morgen 10:00/30 zurück. |
| `send_rejection` | „Sende Ablehnungs-Mail (send_email) an Kandidat #N: neutral, dankend, AGG-konform, ohne Begründungspflicht und ohne Diskriminierungsmerkmale (knowledge/legal/gdpr-policy.md). Speichere ergebnisse/ablehnung-bewerbung-M.md." |
| `verify_documents` (**v6**, Quelle seit v6.1) | **LLM-Task:** Prompt = SKILL.md-Regeln (`skills/verify-documents/SKILL.md`) + Dokumenttext (pdf-reader) + Land. **Dokumenten-Quelle v6.1:** Tabelle `candidate_documents` (typed: Typ je Datei, vom Kandidaten im Tab 🗂️ Dokumente gewählt); Fallback: Glob `testdaten/kandidat-N-*`. Ausgabe: Dokument-Tabelle (Typ/Pflichtfelder/Indizien/Status) + Gesamtstatus + **Visum-Auswertung WAS/WIE/WO** (ansvar-law): WAS = Aufenthaltstitel-Art · WIE = Schritte/Unterlagen/Fristen · WO = zuständige Behörde (DE: Ausländerbehörde/Auslandsvertretung · FR: Préfecture · CH: Kantonales Migrationsamt). Ablage: ergebnisse/verify-documents-kandidat-N-datum.md. Kein Visum-Bedarf → „nicht relevant" |
| `visa_confirmation` (**v6**) | **MCP-direct (kein LLM):** liest Visum-WAS/WIE/WO aus verify_documents-result_json und sendet via email-sender.send_email an den Kandidaten (KI-Hinweis EU AI Act Art. 50 inklusive). **NUR nach HR-Klick** (Variante-A-Guard wie create_invitation/send_rejection) |
| `send_confirmation` / `notify_hr` | Einfache send_email-Aufrufe mit Templates (Eingang / Ergebnis bereit) |
| `export_report` | **Deterministisch (kein LLM):** Exportiert Match-Ergebnisse als MD-Datei nach ergebnisse/. Trigger: Nach `store_feedback` (app.py) oder manuell. |
| `handle_errors` | **Deterministisch (kein LLM):** Protokolliert Fehler in logs/agent-errors.log und knowledge/error-statistics.md. Trigger: Manuell (HR meldet Fehler). |
| `contract_preflight` (**Phase D P8**, 24.09.2026) | **Deterministisch (kein LLM):** liest `knowledge/legal/contract-sources.md` (Link-Katalog, 0 Hartkodierung), prüft Gehaltsrahmen vs. Mindestlohn (Wert+URL aus MD), Formfall-Hinweise (§14 Abs.4 / §126a / §623 mit URLs aus Katalog), NachwG-15-Punkte-Checkliste. Report `ergebnisse/contract-preflight-bewerbung-{app_id}.md`. **Trigger: HR-Klick** 📄 „Vertrags-Check starten" (🏢 Onboarding) – Variante-A-Guard. **Kein** Vertrag erstellen, **kein** Signieren (Spec skills/contract-management/SKILL.md). |
| `language_course` | **MCP-Server** (`language-test-server.py`): Niveaus-Tests (generate_test, score_answer, get_cefr_level). Trigger: Manuell (HR oder Kandidat startet Test). |

## 6. Kandidaten-Sicht (Portal, kein Agent sichtbar)

| Ort | Neu |
|---|---|
| 💼 Tab 2 (Meine Bewerbungen) | Bei Status `eingeladen`: VDO.Ninja-Link + ICS-Download (aus agent_tasks.result_path bzw. daraus geparstem JSON) |
| 💼 Tab 2 | Status-Historie wie bisher; zusätzlich optional „Agent-Prüfung läuft/abgeschlossen" (aus agent_tasks-Status, anonymisiert) |
| 7️⃣ Onboarding | wie bisher (read-only nach Freigabe) |

## 7. HR-Sicht (Portal)

| Ort | Neu |
|---|---|
| 💼/🏢 Bewerber-Expander | Badge „🤖 Agent-Ergebnisse: Match ✅ · Compliance ✅ · Culture-Fit ✅" (Verweis auf result_paths, read-only views existieren bereits) |
| 2️⃣/3️⃣ Ergebnis-Sichten | unverändert (lesen ergebnisse/*.md) |
| Übergangs-Buttons | unverändert in der Logik; NUR der Hook nach dem Status-Write erzeugt Tasks (A2-Prinzip: ein Klick, automatische Kette) |

## 8. E-Mail-Matrix (alle 6, erweitert Spec v6 12.09.2026)

| # | Anlass | An | Connector/Tool | Inhalt (Kurz) |
|---|---|---|---|---|
| 1 | Bewerbung eingegangen | Kandidat | email-sender · send_email | „Bewerbung eingegangen, Agent prüft Lebenslauf" |
| 2 | Agent-Ergebnis = **JA** (Pförtner-Regel §3) | HR (kontakt_email) | email-sender · send_email | „Ergebnisse für Stelle X / Kandidat #N bereit: Score N/100" – nur bei JA; bei NEIN keine Mail. **v6:** Wenn Visum-relevant (aus verify_documents), enthält diese Mail die Visum-INFO: WAS (Aufenthaltstitel-Art), WIE (Schritte/Unterlagen/Fristen), WO (zuständige Behörde) – agent-generiert via ansvar-law |
| 3 | HR klickt `→ eingeladen` | Kandidat | email-sender · send_pre_screen_invitation | Termin, VDO.Ninja-Link, ICS-Anhang – Agent sendet NUR nach HR-Klick |
| 4 | HR klickt `→ abgelehnt` | Kandidat | email-sender · send_email | Neutrale Absage, AGG-sicher, ohne Begründung – vom Agenten gesendet, NUR nach HR-Klick |
| 5 | HR klickt „📩 Visum-Antrag bestätigen" (**v6**) | Kandidat | email-sender · send_email | Visum-Schritte (agent-generiert via ansvar-law): Behörden-Typ, typische Dokumente, Frist-Hinweise – NUR nach HR-Klick |
| 6 | `status → eingestellt` (**v6**, Mail #6 seit 23.09.2026) | Kandidat | email-sender · send_email (`send_onboarding_mail`, `agent-runner.py:376`) | Onboarding-Begrüßung: Stelle, kompakte Checkliste (Vertrag/IT/Woche 1, aus `knowledge/onboarding-default.md`), optionaler Visum-Abschnitt, Portal-Verweis, `TEMPLATE_KI_HINWEIS` – NUR nach HR/Admin-Klick (Variante-A-Guard) + Status `eingestellt`; davor: Freigabe-Report `ergebnisse/onboarding-freigabe-bewerbung-{app_id}.md` (inkl. Visum-Abschnitt) |

## 9. DSGVO / Compliance

| Regel | Umsetzung |
|---|---|
| Rechtsgrundlage | Art. 6(1)(b) – Bewerbungsverfahren (wie application-status.md); Einladungs-Mail erst ab Status `eingeladen` (Kontaktfreigabe beidseitig, employer-portal-fields.md) |
| Absage-Mail | KEINE Diskriminierungsmerkmale, keine Pflichtbegründung (application-status.md, AGG §1) |
| Datenminimierung | Queue-Payload enthält nur IDs + nötige Felder, keine CV-Texte |
| Löschung | agent_tasks-Zeilen (payload mit Bewerbungsbezug) werden mit der Bewerbung gelöscht (dsgvo_cleanup-Erweiterung) |
| Protokollierung | Jede Mail-Aktion landet als ergebnisse/*.md (Nachweispflicht, EU AI Act Art. 50: KI-Hinweis im Mail-Template) |
| Mensch-in-der-Schleife (Variante A) | Agent versendet KEINE Einladung und KEINE Absage eigenständig – Einladung/Absage nur nach HR-Klick im Portal (EU AI Act Art. 26: menschliche Aufsicht); Agent-JA/NEIN ist nur eine Vorauswahl, nie eine Entscheidung |

## 10. Konfigurations-Status (v2/v3)

| Punkt | Status | Bemerkung |
|---|---|---|
| `email-sender` in opencode.json | ✅ ERGANZT (12.09.2026) | mcp-email-server.py, .venv-pdf, `.env-email`; Handshake getestet (3 Tools) |
| `jitsi-meeting` in opencode.json | ❌ ENTFERNT (27.09.2026) | 0 Aufrufe im Code; VDO.Ninja-Migration (Spec `knowledge/system/vdo-ninja-migration.md`). Raum-URL = String-Bildung im Runner |
| Jitsi-Server | ❌ nicht mehr genutzt (27.09.2026) | `jitsi-mcp-server/` **existiert nicht mehr auf Disk** (`ls -d jitsi-mcp-server` → No such file or directory, 01.10.2026); Aufzeichnung bräuchte Jibri (github.com/jitsi/jibri) |
| E-Mail-Zugang | ✅ vorhanden | **Gmail SMTP** (smtp.gmail.com:587, STARTTLS) via `.env-email` – Umstieg Yahoo→Gmail 24.09.2026, Beleg M2①+M2③ in entscheidungen.md |
| LLM-Provider | ✅ KONFIGURIERT + LIVE GETESTET (12.09. + **13.09.2026**) | **Ausführung seit 13.09.2026: direkte NVIDIA-API** (`requests.post` auf `integrate.api.nvidia.com/v1/chat/completions`) statt `opencode run` — Root-Cause: opencode lieferte nur `step_start`-Events ohne Text (Modell via API selbst korrekt, Mini-Test "Hello!" + Visum-Prompt OK). **LLM-Modell: `nvidia/nemotron-3-super-120b-a12b`** (live: Task #50 check_visa done, 1 Versuch). Optional stärkeres Reasoning via derselben API: `moonshotai/kimi-k3` (Chat-Completion HTTP 200, ~150 s, gleicher Account-Key). opencode bleibt nur noch als Agent-Interaktions-UI, nicht mehr als LLM-Executor des Runners |

## 11. Implementierung (✅ ABGESCHLOSSEN 12.09.2026)

| # | Schritt | Ort | Status |
|---|---|---|---|
| 1 | agent_tasks-Tabelle (inkl. result_json) + Event-Hooks (CV-Upload, Bewerbung+Confirmation, eingeladen, abgelehnt, eingestellt; beide Übergangs-Sites 💼/HR-Modus, nur echte Entscheid-Status erzeugen Tasks) | app.py | ✅ |
| 2 | Hybrid-Runner + PID-File + App-Start-Autostart (Env-Opt-out KMHR_RUNNER_AUTOSTART=0) | scripts/agent-runner.py | ✅ |
| 3 | Kandidaten-Sicht: Einladungs-Banner + ICS-Download bei eingeladen (💼 Tab 2) | app.py | ✅ |
| 4 | HR-Badge „🤖 Agent-Ergebnisse" (Match/Compliance/Culture-Fit je Task-Status) | app.py 💼 HR-Modus | ✅ |
| 5 | dsgvo_cleanup-Erweiterung (agent_tasks mit Bewerbungsbezug) | app.py | ✅ |
| 6 | opencode.json: email-sender + jitsi-meeting | opencode.json | ✅ (12.09. ergänzt) → **jitsi-meeting 27.09.2026 wieder entfernt** (VDO.Ninja-Migration) |
| 7 | E2E: 8/8 Checks (siehe §12) | AppTest + Runner dry-run | ✅ |

## 12. Test-Ergebnisse (12.09.2026, AppTest + Runner `--once --dry-run`)

1. ✅ Bewerbung (echter UI-Button, Kandidat #2 × Job #1) → 5 Tasks: send_confirmation, extract_profile, match_candidate, check_compliance, assess_culture_fit (alle pending, korrekte Payloads)
2. ✅ HR-Klick `→ angesehen` erzeugt KEINEN Task (Bug im ersten Test gefunden und behoben: Hook-Map statt else-Zweig); `→ eingeladen` → create_invitation mit trigger=hr_klick_hr_seite
3. ✅ Runner (dry-run, --once): Tasks 1–5 done, Pförtner-Regel korrekt (kein Bericht → NEIN → keine HR-Mail); zweiter Durchlauf: Task 6 (onboarding_release) + 7 (create_invitation) done, result_json mit dem Raum-Link + ics_path (damals noch Schlüssel `jitsi_url`, heute `vdo_ninja_url`)
4. ✅ Kandidaten-Sicht bei eingeladen: Meeting-Link-Banner sichtbar; ICS-Download-Button erscheint, sobald die ICS-Datei existiert (dry-run schreibt sie nicht – Live-Run tut es); Warte-Hinweis falls noch nicht fertig
5. ✅ HR-Badge „🤖 Agent-Ergebnisse: Match ✅ · Compliance ✅ · Culture-Fit ✅" am Bewerber-Expander
6. ✅ Idempotenz: App-Rerun mit bestehender Bewerbung → keine neuen Tasks (7 vor/nach)
7. ✅ Variante-A-Guard: create_invitation ohne HR-Trigger → RuntimeError VOR jedem MCP-Call („Variante A verletzt")
8. ✅ DSGVO: Bewerbung final + Frist simuliert → applications + Historie + alle 7 agent_tasks-Zeilen gelöscht; Cleanup-Artefakte entfernt, DB-Baseline wiederhergestellt (0 agent_tasks, 0 applications, 2 candidates)

Hinweis: Die Dry-Run-Tests verifizieren Queue, Hooks, Gatekeeper, Guard und Sichten. **Der LIVE-Run wurde am 12.09.2026 durchgeführt** — Bericht: `ergebnisse/agent-automatisierung-live-run.md` (echte Mails, 3 NVIDIA-LLM-Berichte, Pförtner-NEIN live, Variante A live; **8 Live-Bugs gefunden und behoben**, u. a. opencode-Non-Interaktiv-Permissions, Provider-Timeout 60 s → 300 s, MCP-`notifications/initialized` + stdin-EOF, Tippfehler `SMCP_USERNAME` im email-server, tool-freie LLM-Prompts, Gatekeeper-Parser + Sweep). Der **JA-Pfad** (`→ eingeladen` → Jitsi + ICS + Einladungsmail) wurde ebenfalls live verifiziert (17:36, Task #15: Jitsi-Raum `pre-screening-o57adwqt`, ICS 459 Bytes, Einladungsmail „OK\|Gesendet", Kandidaten-Sicht mit ICS-Download-Button) — NEIN- und JA-Pfad sind damit beide live belegt.

---

*Erstellt am 12.09.2026 für den KM-HR-Agenten (Agent-Automatisierung v3 – implementiert am 12.09.2026; Ausführung über die Projekt-MCP-Connectors, Meetings seit 27.09.2026 ausschließlich VDO.Ninja, JA/NEIN-Pförtner-Regel, Variante A „Mensch entscheidet, Agent sendet").*

## Test-Regeln (24.09.2026, user-bestaetigt – verbindlich)

1. **Nur echte Auslöser.** Mail-/Flow-Tests laufen ausschließlich über die KM-HR-Logik: Portal-Klick HR (`eingeladen`/`abgelehnt`/`eingestellt`/Visum-Bestätigung), `apply_to_job` (Bewerbungskette), Pförtner (`match_candidate`/`check_compliance`/`assess_culture_fit` → `notify_hr`), Candidate-Portal-Aktionen.
2. **Verboten:** handgeschriebene Queue-Payloads (`queue_agent_task`/Direkt-INSERT) mit erfundenen scores/Triggern/`test`-Feldern; selbstverfasste Mail-Inhalte (auch „Selbsttests"). Mail-Texte stammen ausschließlich aus den Handler-Strings in `scripts/agent-runner.py` bzw. den MCP-Tool-Vorlagen (email-sender, meeting-tools).
3. **DB-Änderungen im Test** (inkl. `UPDATE candidates`/Status) nur mit vorherigem Plan + ausdrücklichem User-GO + Doku in `ergebnisse/entscheidungen.md` im selben Zug. Empfänger werden nie per Payload/Update umdefiniert – sie folgen immer `candidates.email` bzw. `employers.kontakt_email`.
4. **Aufräumen** (Test-Task-Rows löschen, Report-Restores) nur nach GO, mit DB-`.backup` vorher, danach Baseline-Check (max/pending/failed/fb/hist/apps). Vor jedem Bestandsedit `.bak-YYYYMMDD-HHMM`.
