# Agent-Automatisierung (Agent-Queue + Hintergrund-Runner)

> **Stand:** September 2026 (v6 – Visum-Workflow: verify_documents + visa_confirmation + Visa-Schritte im Onboarding; **✅ IMPLEMENTIERT 12.09.2026: Runner-Tasks, Hooks an 3 Sites, E2E T1–T8 bestanden, Testdaten entfernt** · **v6.1 (Dokumenten-Tab):** 👤 Candidate Portal → Tab „🗂️ Dokumente" (Typ-Auswahl, Multi-Upload, Art.-17-Löschung, kein Profil-Overwrite) + Tabelle `candidate_documents` als typed Quelle für verify_documents + frist-basierte DSGVO-Löschung der Dateien — **✅ implementiert + E2E T1–T5 bestanden**) (Spec v3 – erstellt 12.09.2026, **✅ IMPLEMENTIERT + GETESTET am 12.09.2026: 8/8 E2E-Checks bestanden, DSGVO-Testdaten entfernt, Server HTTP 200, Runner-Autostart aktiv**)  
> **Zweck:** Der komplette Ablauf (Bewerbung → Agent-Kette → HR-Entscheidung → Einladung/Ablehnung → Onboarding) läuft automatisch. Das Portal schreibt nur **Tasks in eine Queue**; ein **Hintergrund-Runner** führt sie aus – **direkt über die Projekt-MCP-Connectors** (deterministische Tasks) und für LLM-Aufgaben via **direkte NVIDIA-API** (`requests.post` auf `integrate.api.nvidia.com/v1/chat/completions`; Stand 13.09.2026, ersetzt `opencode run`).  
> **Grundregel (Zwei-Ebenen-Modell, access-control.md v3.1):** Das Portal sieht die Agent-Werkzeuge nie. Skills 0️⃣–5️⃣ laufen ausschließlich auf der Agent-Ebene.  
> **User-Entscheidungen (12.09.2026, ergänzt 12.09.2026 v3):** Trigger = **Bewerbung UND CV-Upload** · Ausführung = **Hintergrund-Runner** · E-Mails = **4 Punkte** (Eingang, HR-Info nur bei JA, Einladung, Ablehnung) · **Meetings = Jitsi (KEIN Google Meet)** *(User-Entscheidung 12.09.2026 — ersetzt 27.09.2026 durch VDO.Ninja, siehe `vdo-ninja-migration.md`; Nachtrag ⓘ08.10.2026)* · **JA/NEIN-Regel (Pförtner):** Score ≥ 60 UND Compliance = COMPLIANT → JA → HR-Mail; sonst NEIN → keine Mail, Ergebnisse bleiben für HR sichtbar (Suche/Talentpool) · **Variante A:** Der Agent lädt/lehnt NIE selbst ab – Einladung erst nach HR-Klick `→ eingeladen`, Absage-Mail erst nach HR-Klick `→ abgelehnt` (die Mail wird dann vom Agenten via email-sender gesendet, nie SMTP in app.py) · **v6-Entscheidungen:** Visum-INFO an HR **erst beim JA-Pfad** (in der notify_hr-Mail, NICHT sofort mit dem Badge) · Visum-Relevanz/Inhalt = **ansvar-law-basiert**: Der Agent beschreibt aus den geprüften Dokumenten WAS zu beantragen ist (Visen-/Aufenthaltstitel-Art), WIE (typische Schritte, Unterlagen, Fristen) und WO (zuständige Behörde je Land DE/FR/CH) — agent-generiert via ansvar-german/french/swiss-law, kein Behördenkontakt des Agents

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
   2️⃣ Match-Ergebnis (Anzeige; Einladen/Ablehnen/Einstellen laufen auf der Match-Seite, nicht read-only) · 3️⃣ Compliance-Ergebnis (read-only)
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
                                        -- [Runner-intern, 1] gatekeeper_eval (direktes INSERT, kein Dispatch)
                                        -- Hinweis: handle_errors wird nie gequeued → 18 DISTINCT task_type
                                        -- in agent_tasks (Beweis: sqlite3 COUNT(DISTINCT task_type) = 18,
                                        -- ⓘ09.10.2026; enthält gatekeeper_eval, NICHT handle_errors)
    status TEXT DEFAULT 'pending',      -- pending | running | done | failed | skipped
    payload TEXT NOT NULL,              -- JSON: candidate_id, job_id, application_id, kontext
    result_path TEXT,                   -- ergebnisse/*.md (Agent-Ausgabe)
    result_json TEXT,                   -- Runner-Ausgaben (vdo_ninja_url, ics_path, termin, mail, Gatekeeper-Entscheid, text=vollständiger Berichtstext ungekappt)
    error_text TEXT,                    -- bei failed
    attempts INTEGER DEFAULT 0,         -- Max. 3, dann failed final
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
```

**Erweitertes Schema (Implementierung v3):** `result_json` speichert Runner-Ausgaben (vdo_ninja_url, ics_path, termin, mail, gatekeeper-Entscheid) für die Portal-Sichten. Tabelle wird beim App-Start idempotent angelegt (init_agent_tasks_table()).

**Berichtstext vollständig (Plan-ii, 11.10.2026):** Der Runner legt den **vollständigen** Berichtstext
(Header + Agent-Antwort, **ungekappt**) zusätzlich in `result_json["text"]` ab — additiv zu `result_path`
und `agent_chars`, keine Aufrufer brechen. Die frühere Obergrenze `RESULT_TEXT_MAX = 20000` ist
**entfernt** (Design-Entscheidung, keine externe Quelle). Die HR-Anzeige (🔎 Agent-Details) ist
**DB-primär**: sie liest `result_json["text"]` über `db.get_candidate_agent_tasks`, nicht mehr lokale
`ergebnisse/*.md` (die `ergebnisse/` ist `gitignored` und im CI-Checkout leer). Details §7.1.

**Regeln:**
- App schreibt NUR INSERTs (Events) – nie Agent-Logik im UI-Prozess.
- Ein Task pro Event; abhängige Tasks (Match braucht Extract) plant der Runner: Er setzt `match_candidate` etc. auf `pending` erst, wenn `extract_profile` = `done` (Kette im Runner, nicht in der DB).
- Idempotenz: Vor dem INSERT prüft die App, ob für (task_type, payload.application_id, heutiges Datum) bereits ein Task existiert – verhindert Doppel-Task bei UI-Reruns (NiceGUI-Re-Render; historisch: Streamlit-Reruns).

## 3. Trigger-Matrix (App-Events → Tasks)

| Event (app.py Hook) | Task(s) | Bemerkung |
|---|---|---|
| CV-Upload erfolgreich (Candidate 📤) | `extract_profile` | User-Entscheidung: Agent extrahiert sofort nach Upload |
| Bewerbung erstellt (💼 Bewerben) | `match_candidate`, `check_compliance`, `assess_culture_fit` (+ falls Extract noch offen: auch `extract_profile`) | User-Entscheidung: volle Kette bei Bewerbung |
| `status → eingeladen` (💼 oder 🏢, seit Phase 2 auch 🛡️ Admin-Bewerber-Verwaltung, `trigger: admin_klick`) | `create_invitation` | JA-Pfad: VDO.Ninja-Raum + Fragen + ICS + Einladungs-Mail |
| `status → abgelehnt` (💼 oder 🏢, seit Phase 2 auch 🛡️ Admin) | `send_rejection` | NEIN-Pfad (HR-Entscheid): Agent sendet Absage-Mail **NUR nach HR-Klick** (Variante A) |
| `status → eingestellt` (💼 oder 🏢, seit Phase 2 auch 🛡️ Admin) | `onboarding_release` | bestehender 7️⃣-Mechanismus wird triggerbar; **Spec v6:** Checkliste enthält Visum-Schritte, wenn Visum-relevant. **Phase 2 (20.09.2026):** Übergänge aus der Admin-Bewerber-Verwaltung (webui/pages/admin.py, Muster `webui/pages/employer.py` (gemessen 10.10.2026)) erzeugen dieselben Tasks mit `trigger: admin_klick` — E2E belegt (Task #105 send_rejection, Phase-2-Doku) |
| Bewerbung erstellt (zusätzlich) | `send_confirmation` | Eingangsbestätigung an Kandidaten |
| Bewerbung erstellt (zusätzlich, **Spec v6**) | `verify_documents` | Agent prüft Zeugnisse/Sprachzeugnisse (Herkunft Kandidat) via pdf-reader + Law-Routing DE/FR/CH; HR-Badge erweitert um „Dokumente ✅/⚠️"; **Visum-Auswertung (was/wie/wo, ansvar-law) landet im result_json** und geht **erst beim JA-Pfad** als INFO-Zeilen in die notify_hr-Mail (User-Entscheidung v6) – nur Info, Agent stellt keinen Antrag |
| Bewerbung erstellt (zusätzlich, **Spec v6.2**) | `check_visa` | Agent prüft Visum-Pflicht, Aufenthaltszweck (§18g Blaue Karte EU; §18a/§18b weitere Titel — Korrektur P4 26.09.2026), Blue Card, Anerkennung (BQRF) basierend auf Staatsangehörigkeit + Stellenland; LLM-Task mit compactem Prompt (visa-rules.md-Regeln inline); Ergebnis: ergebnisse/check_visa-kandidat-N-datum.md; HR-Badge im Portal: Streamlit `st.metric „Visum-Status"` + Report-Expander (`app.py` (gemessen 10.10.2026) Agent-Kompass, 3700-3708 Match-Sicht); NiceGUI: Badge-Parsing `_badge_icon` (`webui/pages/employer.py` (Codemarke `def _badge_icon`, gemessen 10.10.2026), C5 22.09.2026) + Visa-Button (`webui/pages/employer.py` (Codemarke `def _badge_icon`, gemessen 10.10.2026)). **✅ LIVE GETESTET 13.09.2026** (Task #50, nemotron-120b via direkte API: tunesischer IT-Admin → Visum ERFORDERLICH, Blue Card möglich, Anerkennung freiwillig; Bericht `ergebnisse/check_visa-kandidat-7-2026-09-13.md`) |
| HR-Klick „📩 Visum-Antrag bestätigen" (**Spec v6**; seit Phase 2 auch aus 🛡️ Admin-Bewerber-Verwaltung; Status-Regel `eingeladen`/`eingestellt` → `knowledge/portal/employer-board.md` §3(b), Codemark `VISA_INFO_STATUS`) | `visa_confirmation` | **NUR nach diesem HR-Klick (Variante A):** Agent sendet dem Kandidaten eine E-Mail mit dem Visum-WAS/WIE/WO aus der verify_documents-Auswertung (agent-generiert via ansvar-law, ohne Behördenkontakt des Agents) |
| Runner-intern: Kette done → JA/NEIN-Auswertung | JA → `notify_hr` · NEIN → **kein Task** | **Pförtner-Regel:** Score ≥ 60 UND Compliance = COMPLIANT → JA (Mail an HR); sonst NEIN (kein Mail, Ergebnisse bleiben für HR sichtbar). **Abfragen exakt + generation-bewusst (R3-1/R3-2, 30.09.2026):** `json_extract(payload,'$.application_id') = ?` statt LIKE-Präfix, Ketten-Zustand mit `ORDER BY id` (neuester Task-Stand gewinnt), `notify_hr` idempotent **je Generation** (`COALESCE(gen,0)`, Altbestand = 0) — Details §3.1 |
| HR-Klick „📄 Vertrags-Check starten" (🏢 Onboarding, **Phase D P8**, 24.09.2026) | `contract_preflight` | **Deterministisch (kein LLM, kein Mailversand):** Gehalt vs. Mindestlohn-Wert **aus** `knowledge/legal/contract-sources.md` (Key `mindestlohn_2026`, 13,90 €/h Stand 2026, **Quellenstatus primär**: MiLoV5 § 1, **BGBl. 2025 I Nr. 268 v. 07.11.2025**, in Kraft 01.01.2026, BMAS; Abruf 25.09.2026), Formfall-Tabelle (§14/§126a/§623), NachwG-Checkliste, Quellen-Tabelle aus dem Link-Katalog (**0 hartkodierte Links in Python**, USER-GO). Variante-A-Guard: `trigger ∈ {hr_onboarding_klick, hr_klick_portal, hr_klick_hr_seite, admin_klick}`. Report: `ergebnisse/contract-preflight-bewerbung-{app_id}.md`, Sicht in Agent-Details. **Kein Signatur-Dienst** (Optionen A–F bleiben User-Wahl, Spec contract-management.md §4) |

> ⚠️ **Design-Entscheidung (15.09.2026):** Die Schwelle Score ≥ 60 als Pförtner hat **keine externe Quelle** (kein Industriestandard, kein Gesetz). **Alternative:** Schwelle aus eigener Datenanalyse ableiten (z.B. Median aller Scores die zu einer Einstellung führten). **Validierung:** Nach 20+ Einstellungsentscheidungen prüfen ob 60 sinnvoll trennt (False-Positive-Rate < 20%).

### 3.1 Pförtner-Abfragen + Generation (R3-1/R3-2, 30.09.2026)

**Abfragen exakt (R3-1).** `_maybe_gatekeeper` (`scripts/agent-runner.py` (Codemarke `def _maybe_gatekeeper`, gemessen 10.10.2026)) liest die Bewerbung in **beiden** Abfragen per `json_extract(payload, '$.application_id') = ?` statt per LIKE-Präfix `%"application_id": N%` — der Präfix-Vergleich traf bei `N=1` auch 10/11/160 (Präfix-Kollision). Umfang: Ketten-Zustand **und** notify_hr-Zählung.

- **Ketten-Zustände** (`scripts/agent-runner.py` (gemessen 10.10.2026)): `json_extract(payload,'$.application_id') = ?` + `COALESCE(json_extract(payload,'$.gen'),0) = ?` + `task_type IN ('match_candidate','check_compliance','assess_culture_fit')` + **`ORDER BY id`**; die Zeilen werden in Abfrage-Reihenfolge eingespeist  → **der letzte Eintrag je task_type gewinnt = neuester Stand** (vorher `dict()` aus unsortierten Zeilen → bei mehreren Tasks desselben Typs gewann zufällig einer).
- **notify_hr-Zählung** : ebenfalls `json_extract … = ?` + Gen-Filter.
- **Notify_hr-Marker** : Payload trägt `"gen": current_gen`.

**Generation (R3-2, Nutzer-GO „A: Generation-Zähler“).** Jedes Bewerbungs-Queue-Payload trägt `gen` (`webui/db.py` (gemessen 10.10.2026)):

| Fall | `gen` | Codestelle |
|---|---|---|
| Erstbewerbung | `0` | `webui/db.py` (gemessen 10.10.2026) |
| Reaktivierung (`zurückgezogen` → „Erneut bewerben“) | `MAX(COALESCE(gen,0)) + 1` über alle Tasks der Application | `webui/db.py` (gemessen 10.10.2026) |

- **Dedupe gen-bewusst:** `queue_agent_task` prüft zusätzlich `AND COALESCE(json_extract(payload,'$.gen'),0) = ?` (`webui/db.py` (Codemarke `def queue_agent_task`, gemessen 10.10.2026), Wert aus `payload.get("gen", 0)`) → dieselbe Kette kann am selben Tag als **neue** Generation gequeued werden; gleicher Tag + Typ + App + **gleiches** `gen` wird weiterhin geduped.
- **notify_hr-Guard gen-bewusst:** `_maybe_gatekeeper` bestimmt `current_gen = MAX(COALESCE(gen,0))` über alle Tasks der Application (`scripts/agent-runner.py` (Codemarke `def notify_hr`, gemessen 10.10.2026)) und filtert Ketten-Zustand **und** notify_hr-Zählung darauf  → ein alter notify_hr-Marker einer früheren Generation blockiert die Auswertung einer neuen Generation **nicht**; zweiter Sweep derselben Generation fügt kein zweites `notify_hr` hinzu (idempotent pro Generation).
- **Altbestand ohne `gen`-Feld:** `COALESCE(…, 0)` liest Bestands-Tasks als Generation 0 → **Verhalten für Bestandsdaten unverändert** (Beleg `tests/test_r32_gatekeeper_gen.py` (Codemarke `def test_altbestand_ohne_gen_wird_als_0_gelesen`, gemessen 10.10.2026)).
- **Design-Entscheidung (30.09.2026, keine externe Quelle):** Die Reaktivierung queue't dieselben Task-Typen wie die Erstbewerbung (eine Codepfad-Quelle, `webui/db.py` (Codemarke `def apply_to_job`, gemessen 10.10.2026)); die erneute Eingangsbestätigung gilt als Bestätigung der Neubewerbung.
- **Tests:** `tests/test_r32_gatekeeper_gen.py` (In-Memory-Beweis für Bewerbungen 1/10/11/160, LIKE-Gegenprobe, notify_hr-Idempotenz je Generation, Dedupe-Grenze, `apply_to_job` gen 0/1/2), Quelltext-Nachweise in `tests/test_application_id_match.py` (gemessen 10.10.2026).

**`gatekeeper_eval` (Inline-Marker, Stand 13.10.2026):** `gatekeeper_eval` ist ein **Inline-Marker**
(Direkt-INSERT mit `status='done'`, kein Runner-Task, `attempts=0`, kein `fetch_pending`); seit
13.10.2026 trägt der Insert `started_at`/`finished_at` und ein minimales `result_json`
(`inline/entscheidung/score/kategorie/signature`) — `done` ist damit nachweisbar.

## 4. Hintergrund-Runner (`scripts/agent-runner.py`) – HYBRID v2

**Kernprinzip v2 (aktualisiert 13.09.2026):** Der Runner ruft die **Projekt-MCP-Connectors direkt** auf (stdio JSON-RPC, handshake-getestet ✅) – ohne LLM, ohne Modell-Abhängigkeit, in Sekunden. Die LLM-Tasks (Extract/Match/Compliance/Culture-Fit + v6/v6.2: verify_documents, check_visa) laufen über die **direkte NVIDIA-API** (`requests.post`, `import requests`, Script `scripts/agent-runner.py` 559–565) — **nicht mehr via `opencode run`** (lieferte nur `step_start`-Events ohne Text, Modell antwortete korrekt → Root-Cause war opencode, nicht das Modell; live verifiziert 13.09.2026).

| Aspekt | Umsetzung |
|---|---|
| Start (**Autostart-Guard, F1, 23.09.2026**) | Beim App-Start geprüft (wie DSGVO-Hook), **3 Fälle in `ensure_agent_runner()` (`webui/logic.py` (Codemarke `def ensure_agent_runner`, gemessen 10.10.2026))**: **(a)** PID-File `data/agent-runner.pid` existiert UND PID lebt (`os.kill(pid, 0)`) UND `/proc/{pid}/cmdline` enthält `agent-runner.py` → **kein Neustart**, Log „vorhandener Runner genutzt"; **(b)** PID tot / File verwaist (stale) → **stale File löschen (`Path.unlink()`), dann neu starten** (`setsid nohup`); **(c)** `KMHR_RUNNER_AUTOSTART=0` → harter Stopp, nie spawnen. Alternativ cron. **Runner-Zählung nie `pgrep -fc`** (zählt den eigenen Bash-Wrapper mit → falsche Hochzählung), sondern `pgrep -fa "agent-runner.py" \| grep -v "bash -c" \| grep -v pgrep`. |
| Loop | Alle 60 s: `SELECT * FROM agent_tasks WHERE status='pending' ORDER BY id LIMIT 5` |
| **Ausführung A – MCP-direct (deterministisch)** | Runner baut JSON-RPC-Requests an die Connector-Server aus `opencode.json` (Subprocess stdio, dasselbe Muster wie der Handshake-Test): `create_invitation` → Raum-URL als String (VDO.Ninja, **kein** Meeting-Tool) + `meeting-tools.generate_screening_questions` + `meeting-tools.generate_ics_file` + `email-sender.send_pre_screen_invitation`; `send_confirmation`/`notify_hr`/`send_rejection` → `email-sender.send_email`. **Kein `opencode run`, kein Modell nötig – 100% deterministisch.** |
| **Ausführung B – LLM-Tasks (v3, Stand 13.09.2026)** | `extract_profile`, `match_candidate`, `check_compliance`, `assess_culture_fit`, `verify_documents`, `check_visa` → **direkte NVIDIA-API**: `requests.post("https://integrate.api.nvidia.com/v1/chat/completions", …)` → `choices[0].message.content` (Templates §5, Key via NVIDIA NIM); zuvor `opencode run` — verworfen, weil nur `step_start` ohne Text zurückkam. Direkte API live getestet (13.09.2026: Mini-Prompt „Say hello" → "Hello!", Visum-Prompt → „Visum-Status: ERFORDERLICH"; Task #50 done, 1 Versuch) |
| Meeting-Raum (Entscheidung 27.09.: VDO.Ninja statt Jitsi vom 12.09.) | Raum-URL = Projektstandard wie `scripts/agent-runner.py` (Codemarke `def create_invitation`, gemessen 10.10.2026) (`def create_invitation`) / ** (die URL selbst)**: `https://vdo.ninja/?director=prescreening{code}` (kostenlos, Peer-to-Peer, kein Account). **Kein** Meeting-Tool-Aufruf — die URL wird als String gebildet; `jitsi-meeting` ist am 27.09.2026 entfernt. **Kein Google Meet** (`create_meeting_link` wird NICHT verwendet) |
| Nachlauf | result_path aus Agent-Ausgabe parsen (oder Standardpfad `ergebnisse/{task_type}-{id}-{datum}.md` erzwingen), `finished_at` setzen, bei Fehler `attempts+1`, ab 3 → `failed` |
| Stabilität | MCP-direct: Timeout 60 s/Tool. LLM-Tasks: max. 10 min (Timeout → failed + Retry). Fehlgeschlagene Connectors → `failed` + Eintrag in `logs/agent-errors.log` (Konvention hr-api-connectors.md §6) |
| **Protokollierung (Stand 13.10.2026)** | `mcp_call` loggt im DRY_RUN eine `[DRY-RUN]`-Zeile. **Live** schreibt es seit 13.10.2026 eine redigierte Nachweiszeile pro Aufruf nach `logs/mcp-calls.log` (Whitelist `to`/`subject`/`language`/`file_path`/`candidate_name`/`position`/`match_score`/`cultural_fit_score`/`date`/`time`/`topic`/`duration_minutes`/`meet_url`, Strings auf 120 Zeichen; **nie** `body`/`cc`/`bcc`/`description` — DSGVO). Logfehler brechen den MCP-Aufruf nie. |
| **Log-Beweissicherung (A, 23.09.2026)** | `/tmp/nicegui.log` = E2E-Beweismittel (Guard-Zeilen „Hintergrund-Runner gestartet" / „stale pidfile" / „vorhandener Runner genutzt", Traceback-Zähler). **Vor JEDEM Server-Neustart sichern:** `cp /tmp/nicegui.log /tmp/nicegui.log.bak-$(date +%Y%m%d-%H%M)` — kein rm, ältere .bak bleiben liegen. **Start NUR mit Append:** `setsid nohup .venv-streamlit/bin/python3 -m webui.main >> /tmp/nicegui.log 2>&1 < /dev/null & disown` — **niemals `>`** (Truncation löscht Guard-Historie). Kill und Spawn IMMER in getrennten Shell-Calls (pkill-Selbstmord-Falle, Pattern `webui/main.py`). Schritt-0 23.09.2026: Truncation-Spawn `>` existiert **nicht** im Repo (`start-webui.sh` (gemessen 10.10.2026) ohne Redirect; Runner-Spawn `webui/logic.py` (gemessen 10.10.2026) → DEVNULL) → A2 „Code-Rotation" entfällt als widerlegt; Log-Birth 2026-09-22 22:21 belegt frühere externe Überschreibung → Regel deshalb bindend. Datei-Backup vor dieser Änderung: `agent-automation.md.bak-20260923-1150`. |
| **send_rejection-Guard (C1/O2, 23.09.2026)** | Spec (jetzt implementierter Code): `send_rejection()` prüft VOR dem Mailversand ZWEIERLEI, Struktur analog `visa_confirmation` (`scripts/agent-runner.py` (Codemarke `def visa_confirmation`, gemessen 10.10.2026)) / `create_invitation` : (1) `payload["trigger"] ∈ {hr_klick_portal, hr_klick_hr_seite, admin_klick}`, sonst `RuntimeError("Variante A verletzt: send_rejection nur nach HR-Klick")`; (2) die zugehörige Bewerbung `payload["application_id"]` hat `applications.status = "abgelehnt"` (alle 5 Trigger-Quellen updaten den Status VOR dem Queue: `app.py` (gemessen 10.10.2026), `webui/pages/employer.py` (gemessen 10.10.2026), `webui/pages/admin.py` (gemessen 10.10.2026)), sonst RuntimeError „nur bei Status 'abgelehnt'". Abbruch = Exception → `process_task` → `finish_task(ok=False)` + Log-Zeile `✓ Task #N FEHLER: …` (`scripts/agent-runner.py` (Codemarke `def log`, gemessen 10.10.2026), Log-Datei `log()`) → **kein Mailversand** (`mcp_call` wird nie erreicht). Quelle: Variante A `AGENTS.md` (user-approved 12.09.2026), Zeilen :87/:123/:125, Runner-Docstring :20-21/:348; C1-Offener-Punkt SKILL:231 + phase2:364 (Task #105 lief ohne Guard durch); Tests `tests/test_send_rejection_guard.py` (NEGATIV/POSITIV, `mcp_call` immer gemockt — nie echter Mailversand). |
| **Match-Dialoge (Ist-Stand, gemessen 15.10.2026; ersetzt die frühere „Identity-Regel NB1+NB4")** | Ist-Stand: Die 3 Match-Dialoge (`webui/pages/employer.py` _page_match: Einladen/Ablehnen/Einstellen) speichern im State die **application_id der gewählten Bewerbung** (`_invite_ctx`/`_reject_ctx`/`_hire_ctx`, Codemark `_page_match`, gemessen 15.10.2026). Jede Aktion wirkt ausschließlich auf diese eine Bewerbung (UPDATE + History per `WHERE id=?`). **Reject:** setzt die gewählte Bewerbung auf `abgelehnt` (Dialog-Label: „Andere Bewerbungen dieses Kandidaten bleiben unveraendert") und queued GENAU EIN `send_rejection`-Task `{application_id, candidate_id, job_id, trigger: hr_klick_portal}` direkt aus dem Dialog-State. **Invite/Hire:** ebenfalls nur die gewählte Bewerbung; Payloads `create_invitation`/`onboarding_release` enthalten zusätzlich `candidate_id` (onboarding_release wertet es für die Visum-Auswertung aus, `scripts/agent-runner.py` (gemessen 10.10.2026)). **Ungültiger Status** (Guard `_legal`, z. B. Bewerbung bereits terminal) → `ui.notify`-Fehler, kein DB-Write, kein Task. **Terminal-Status** (`eingestellt`/`abgelehnt`/`zurückgezogen`) werden von den Dialogen nicht angefasst. Die frühere Identity-Regel (Candidate-ID im State, application_id am Queue-Punkt per SELECT, „flippt ALLE aktiven Apps", `ids[0]`/`LIMIT 1`) ist **nicht** mehr Code-Stand (gemessen 15.10.2026); datierte Historie in `ergebnisse/entscheidungen.md`. |
| **NB1 Payload-Lücke `send_rejection` (doku-only, Entscheidung 23.09.2026; Behavior-Altstand)** | `webui/pages/employer.py` (gemessen 10.10.2026) (alt, Match-Dialog „Ablehnen") queued `send_rejection` NUR mit `{application_id, trigger}` — **OHNE `candidate_id`** (die anderen 4 Queue-Stellen liefern es: `app.py` (gemessen 10.10.2026), `app.py` (gemessen 10.10.2026), `webui/pages/employer.py` (gemessen 10.10.2026), `webui/pages/admin.py` (gemessen 10.10.2026)). Folge: Guard wird bestanden (Status ist `abgelehnt`), danach Candidate-Lookup `cid=None` → RuntimeError „Kandidat #None nicht gefunden" → `finish_task(ok=False)` → **kein Mailversand** (fail-safe, Variante A nicht verletzt), aber: die Absage-Mail wird auf diesem Pfad nie zugestellt. **Umgesetzt (23.09.2026, NB1+NB4+Regelkorrektur):** das `send_rejection`-Payload der Match-Dialoge trägt `candidate_id`; die echte `application_id` wird am Queue-Punkt per SELECT aufgelöst (Identity-Regel, **vorherige** Zeile) — der Backlog-Eintrag aus NB1 („Feature-Freeze hält ihn heraus") ist hiermit **erledigt**. Quelle: entscheidungen.md 23.09.2026 (NB1) + 23.09.2026 (NB1+NB4 Identity-Fix). **Korrektur 15.10.2026:** die oben beschriebene Queue-Punkt-Auflösung (`ids[0]`, JOIN-SELECT, „flippt alle aktiven Apps") ist nicht mehr Code-Stand — application_id/job_id kommen direkt aus dem Dialog-State (`_invite_ctx`/`_reject_ctx`/`_hire_ctx`, gemessen 15.10.2026); siehe Regel „Match-Dialoge (Ist-Stand)". |
| **NB5 (behoben, 23.09.2026): ASCII-Filter `zurueckgezogen` → `zurückgezogen`** | Ursprünglich 5 Altfilter + 3 Nebenstellen verglichen `'zurueckgezogen'` (ohne ü), die DB speichert `'zurückgezogen'` MIT UTF-8-ü (hex-verifiziert, Statuswert App 22) → Filter griffen nie. **Umgesetzt 23.09.2026 (NB5, user-Go):** `'zurückgezogen'` an `webui/pages/employer.py` (gemessen 10.10.2026) (SQL) + Label, `webui/pages/candidate.py` (gemessen 10.10.2026) (History-Check), `webui/pages/admin.py` (gemessen 10.10.2026) (Label), `scripts/agent-runner.py` (gemessen 10.10.2026) (Auto-Refresh), `app.py` (gemessen 10.10.2026) (Parität, archiviert). Sweep: 0 ASCII-Treffer in Projektcode. Verifikation: App 22 korrekt ausgefiltert, Kandidat-1-Auto-Refresh enthält App 22 nicht mehr. |
| **NB6 (behoben, 23.09.2026, Code + Doku): Onboarding-Mail #6** | Ursprünglich doku-only festgestellt: Runner `onboarding_release` schrieb NUR den Freigabe-Report, kein `send_email` (Backlog-Claim aa:115/aa:161 + AGENTS/knowledge/instructions). **Umgesetzt 23.09.2026 (user-Go, Multi-Agent):** neue `send_onboarding_mail()` (`scripts/agent-runner.py` (Codemarke `def send_onboarding_mail`, gemessen 10.10.2026)) mit Variante-A-Guard (`trigger ∈ {hr_klick_portal, hr_klick_hr_seite, admin_klick}`) + Status-Guard (`applications.status = 'eingestellt'`, `candidate_id` aus Lookup statt payload) + E-Mail-Check; Aufgerufen im selben `onboarding_release`-Handler (`scripts/agent-runner.py` (gemessen 10.10.2026)) nach dem Freigabe-Report. Trigger-Payloads unvollständig → behoben: `webui/pages/employer.py` (gemessen 10.10.2026) (+`job_id` via SELECT), `app.py` (gemessen 10.10.2026) (+`trigger: hr_klick_portal`). Test `tests/test_send_onboarding_guard.py` (4 Guards, `mcp_call` immer gemockt); Gesamt pytest **26 passed**. DRY_RUN verifiziert: Task #149 → `[DRY-RUN] mcp-email-server.py::send_email args={"to":"e2e-beweis-phase1@example.com","subject":"Willkommen im Team …"}` + `✓ Task #149 done`, kein echter Versand. Quelle: entscheidungen.md 23.09.2026 (NB6). |
| **Anhang §4 Onboarding (P1-Klassifizierung, 24.09.2026)** | Der Onboarding-Release-Trigger existiert vollständig als `onboarding_release` — Queue `webui/pages/employer.py` (gemessen 10.10.2026) ≙ Streamlit `app.py` (gemessen 10.10.2026), Handler `scripts/agent-runner.py` (gemessen 10.10.2026) inkl. Freigabe-Report und Mail #6. Ein eigener Task-Typ `generate_onboarding` existiert auf keiner Ebene (app.py grep 0; Runner-Dispatch führt ihn nicht, else fängt nur echte Fremd-Typen) — die Checkliste erzeugt der HR-UI-Generator (Skill 7) inline, 1:1-Parität `app.py` (gemessen 10.10.2026) ≙ `webui/components.py` (gemessen 10.10.2026). Damit fällt die ⚠️ in `ergebnisse/phase-d-paritaet-p1-p9.md` als Klasse (b) widerlegt. Quelle: P1-Bericht + entscheidungen.md 24.09.2026 (Phase-D-Runde 1). |

## 5. Task-Prompts (Templates, pro Typ)

Jeder Prompt referenziert die Skills + Wissensdateien (wie scripts/agent-test.sh, aber maschinell):

| task_type | Prompt-Kern |
|---|---|
| `extract_profile` | „Führe Skill extract-profile aus für Kandidat #N (CV: candidates.lebenslauf_pfad). Speichere ergebnisse/profil-kandidat-N-<datum>.md und **schreibe extrahierte Daten in die DB** (hard_skills, soft_skills, berufserfahrung_jahre, abschluss, deutsch, englisch via `_update_candidate_from_extract()`)." |
| `match_candidate` | „Führe Skill match-candidate aus: Kandidat #N vs. Job #M (DB-Felder). Nutze knowledge/lifecycle/matching-criteria.md. Speichere ergebnisse/match-kandidat-N-job-M.md." |
| `check_compliance` | „Führe Skill check-compliance aus (Land: DE/FR/CH aus Kandidat-Standort, + DSGVO). Nutze ansvar-*-law. Speichere ergebnisse/compliance-…md." |
| `assess_culture_fit` | „Führe Skill assess-culture-fit aus (Profil vs. Job/Unternehmen). Speichere ergebnisse/kultur-fit-….md." |
| `create_invitation` | **MCP-direct (kein LLM):** 1) Meeting-Räume: HR/Director `https://vdo.ninja/?director=prescreening{code}` + Kandidaten-Gast `https://vdo.ninja/?room=prescreening{code}&record=off` (seit 28.09.2026, Gates 8/9; Variablen `vdo_ninja_url`/`vdo_ninja_gast_url`; Muster `scripts/agent-runner.py` (gemessen 10.10.2026); **seit 27.09.2026 VDO.Ninja statt Jitsi**, Spec `knowledge/system/vdo-ninja-migration.md`, Jitsi-Aufzeichnung brauchte Jibri auf eigenem Server; Felder im Ergebnis-JSON: `vdo_ninja_url` (seit 27.09.2026) + `vdo_ninja_gast_url`/`recording: false`/`ics_path_hr` (seit 28.09.2026, Gates 8/10), Leser mit Legacy-Fallback auf `jitsi_url`), 2) `meeting-tools.generate_screening_questions` (mit echtem Match-Score aus DB), 3) `meeting-tools.generate_ics_file` (meet_url = GAST-Raum für den Kandidaten, `ics_path`; HR-Director-ICS `ics_path_hr` seit 28.09.2026), 4) `email-sender.send_pre_screen_invitation` (meet_url = GAST-Raum, seit 28.09.2026). `jitsi-meeting.jitsi_join_meeting` **entfernt 27.09.2026** (0 Aufrufe) — es gibt keinen Bot-Pfad mehr. Ablage: ergebnisse/einladung-bewerbung-M.md. **HR-Sicht (seit 12.09.2026):** bei Status `eingeladen` sieht HR an beiden Übergangs-Sites (💼 HR-Modus + 🏢 Portal Tab „👥 Kandidaten“) seit 28.09.2026 seinen eigenen Kalendereintrag mit dem **Director-Link** (`ics_path_hr`; der Kandidat bekommt den Gast-Link) – VDO.Ninja-URL, Termin und ICS-Download (Button „📅 Termin in Kalender speichern (.ics) – HR“, Key `ics_hr_{id}`, Helper `get_invitation_artifacts()` / `render_hr_ics_download()` in app.py). **Termin (seit Feature „HR-Terminauswahl"):** HR wählt Datum/Uhrzeit/Dauer direkt vor dem `→ eingeladen`-Klick (beide Übergangs-Sites); Payload-Felder `termin_datum`/`termin_uhrzeit`/`termin_dauer_min`; Runner validiert (Vergangenheit/Format/Dauer 10–180 Min.) mit Fallback morgen 10:00/30. **NiceGUI-Parität (C1, 22.09.2026):** alle drei `create_invitation`-Queuestellen MÜSSEN `termin_*` mitsenden — `webui/pages/employer.py` `_page_match` Dialog (602-645, Zeilenstand 28.09.2026; war korrekt als 559-589), `_page_stellen` Inline-Inputs wie `app.py` (gemessen 10.10.2026) (Quelle), `webui/pages/admin.py` `_page_stellen` analog (`app.py` (gemessen 10.10.2026)). Ohne `termin_*` fällt der Runner auf Default morgen 10:00/30 zurück. |
| `send_rejection` | „Sende Ablehnungs-Mail (send_email) an Kandidat #N: neutral, dankend, AGG-konform, ohne Begründungspflicht und ohne Diskriminierungsmerkmale (knowledge/legal/gdpr-policy.md). Speichere ergebnisse/ablehnung-bewerbung-M.md." |
| `verify_documents` (**v6**, Quelle seit v6.1) | **LLM-Task:** Prompt = SKILL.md-Regeln (`skills/verify-documents/SKILL.md`) + Dokumenttext (pdf-reader) + Land. **Dokumenten-Quelle v6.1:** Tabelle `candidate_documents` (typed: Typ je Datei, vom Kandidaten im Tab 🗂️ Dokumente gewählt); Fallback: Glob `testdaten/kandidat-N-*`. Ausgabe: Dokument-Tabelle (Typ/Pflichtfelder/Indizien/Status) + Gesamtstatus + **Visum-Auswertung WAS/WIE/WO** (ansvar-law): WAS = Aufenthaltstitel-Art · WIE = Schritte/Unterlagen/Fristen · WO = zuständige Behörde (DE: Ausländerbehörde/Auslandsvertretung · FR: Préfecture · CH: Kantonales Migrationsamt). Ablage: ergebnisse/verify-documents-kandidat-N-datum.md. Kein Visum-Bedarf → „nicht relevant" |
| `visa_confirmation` (**v6**) | **MCP-direct (kein LLM):** liest Visum-WAS/WIE/WO aus verify_documents-result_json und sendet via email-sender.send_email an den Kandidaten (KI-Hinweis EU AI Act Art. 50 inklusive). **NUR nach HR-Klick** (Variante-A-Guard wie create_invitation/send_rejection) |
| `send_confirmation` / `notify_hr` | Einfache send_email-Aufrufe mit Templates (Eingang / Ergebnis bereit) |
| `export_report` | **Deterministisch (kein LLM):** Exportiert Match-Ergebnisse als MD-Datei nach ergebnisse/. Trigger: Nach `store_feedback` (app.py) oder manuell. |
| `handle_errors` | **Deterministisch (kein LLM):** Protokolliert Fehler in logs/agent-errors.log und knowledge/error-statistics.md. Trigger: Manuell (HR meldet Fehler). |
| `contract_preflight` (**Phase D P8**, 24.09.2026) | **Deterministisch (kein LLM):** liest `knowledge/legal/contract-sources.md` (Link-Katalog, 0 Hartkodierung), prüft Gehaltsrahmen vs. Mindestlohn (Wert+URL aus MD), Formfall-Hinweise (§14 Abs.4 / §126a / §623 mit URLs aus Katalog), NachwG-15-Punkte-Checkliste. Report `ergebnisse/contract-preflight-bewerbung-{app_id}.md`. **Trigger: HR-Klick** 📄 „Vertrags-Check starten" (🏢 Onboarding) – Variante-A-Guard. **Kein** Vertrag erstellen, **kein** Signieren (Spec skills/contract-management/SKILL.md). |
| `language_course` | **MCP-Server** (`language-test-server.py`): Niveaus-Tests (generate_test, score_answer, get_cefr_level). Trigger: Manuell (HR oder Kandidat startet Test). |

**Artefakt-Pfade sind tag-genau** (`{task_type}-kandidat-{cid}-{datum}.md`); ein zweiter Lauf
desselben Typs am selben Tag **überschreibt** die Datei (Auto-Refresh `match_candidate`, Codemark
`result_path = str(ERGEBNISSE / …)`). Der Runner protokolliert die Überschreibung; der Altstand
bleibt in `agent_tasks.result_json` (Real-E2E 13.10.2026: 58/100-Lauf durch 71/100-Lauf ersetzt,
Gatekeeper wertet die jüngste Datei aus — by design).

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

### 7.1 Agent-Details (🔎) — DB-primär, Plan-ii (11.10.2026)

- **Berichtstext vollständig:** `agent_tasks.result_json["text"]` trägt Header + Agent-Antwort
  **ungekappt** (kein `RESULT_TEXT_MAX` mehr) → die Anzeige zeigt den Bericht **ohne Verlust**. Die
  Altfelder `result_path`/`agent_chars` bleiben erhalten.
- **Anzeige DB-primär:** `_page_agent_details` (`webui/pages/employer.py`, Codemarke
  `def _page_agent_details`) liest je `task_type` die letzte Task über `db.get_candidate_agent_tasks`
  (`webui/db.py`, Codemarke `def get_candidate_agent_tasks`) — Quelle ist `agent_tasks.result_json`,
  **nicht** mehr der lokale `ergebnisse/*.md`-Glob (der in CI leer ist, `.gitignore`).
- **Badge inhaltsbasiert:** `_badge_icon` (`webui/pages/employer.py`, Codemarke `def _badge_icon`)
  wertet den gespeicherten Text aus (z. B. „AUFFÄLLIG" → 🔴; „COMPLIANT"/„NICHT ERFORDERLICH" → 🟢;
  sonst 🟡). Ein fehlender Text fällt auf das ehrliche **Status-Mapping** zurück (`_legacy_badge_icon`:
  `done`→🟢, `failed`→🔴, sonst 🟡).
- **`notify_user` = Info-Mail:** Der LLM-Task `notify_user` (Liste `notify_user` in §5) ist eine
  **Info-Mail** an den Kandidaten; sein Badge folgt dem **Task-Status** (kein Inhalts-Status), d. h.
  `done`→🟢. Es gibt keine inhaltliche „JA/NEIN"-Auswertung dieses Berichts.
  **Schwelle:** Score ≥90 SOFORT / 80–89 SOFT / <80 keine Benachrichtigung = reine Prompt-Anweisung,
  **kein** Code-Gate (Queue-Payload `apply_to_job` enthält kein `score`-Feld, Codemark `webui/db.py`);
  Design-Entscheidung + Quelle: `skills/notify-user/SKILL.md` §1. Real-E2E 13.10.2026: Score 71 im
  Prompt, LLM antwortete `(keine Ausgabe)` — Verhalten, aber undokumentiert; Task blieb `done`
  (Badge 🟢 folgt Task-Status).
- **Altbestand bleibt (keine Rückübersetzung):** Tasks ohne `result_json["text"]` werden **nicht**
  nachträglich befüllt oder rückübersetzt — sie zeigen den Hinweis „Kein Berichtstext gespeichert
  (Altbestand)" und ein Status-Badge.
- **Quelle:** Nutzer-GO **Plan(ii) 11.10.2026** (keine externe Quelle) → **Design-Entscheidung**.
  Historische Herkunft dieses Designs: `knowledge/system/p8-cloud-datenquellen.md` (⚰️ tot/überholt,
  Cloud entfällt).

## 8. E-Mail-Matrix (alle 6, erweitert Spec v6 12.09.2026)

| # | Anlass | An | Connector/Tool | Inhalt (Kurz) |
|---|---|---|---|---|
| 1 | Bewerbung eingegangen | Kandidat | email-sender · send_email | „Bewerbung eingegangen, Agent prüft Lebenslauf" |
| 2 | Agent-Ergebnis = **JA** (Pförtner-Regel §3) | HR (kontakt_email) | email-sender · send_email | „Ergebnisse für Stelle X / Kandidat #N bereit: Score N/100" – nur bei JA; bei NEIN keine Mail. **v6:** Wenn Visum-relevant (aus verify_documents), enthält diese Mail die Visum-INFO: WAS (Aufenthaltstitel-Art), WIE (Schritte/Unterlagen/Fristen), WO (zuständige Behörde) – agent-generiert via ansvar-law |
| 3 | HR klickt `→ eingeladen` | Kandidat | email-sender · send_pre_screen_invitation | Termin, VDO.Ninja-Link, ICS-Anhang – Agent sendet NUR nach HR-Klick |
| 4 | HR klickt `→ abgelehnt` | Kandidat | email-sender · send_email | Neutrale Absage, AGG-sicher, ohne Begründung – vom Agenten gesendet, NUR nach HR-Klick |
| 5 | HR klickt „📩 Visum-Antrag bestätigen" (**v6**) | Kandidat | email-sender · send_email | Visum-Schritte (agent-generiert via ansvar-law): Behörden-Typ, typische Dokumente, Frist-Hinweise – NUR nach HR-Klick |
| 6 | `status → eingestellt` (**v6**, Mail #6 seit 23.09.2026) | Kandidat | email-sender · send_email (`send_onboarding_mail`, `scripts/agent-runner.py` (Codemarke `def send_onboarding_mail`, gemessen 10.10.2026)) | Onboarding-Begrüßung: Stelle, kompakte Checkliste (Vertrag/IT/Woche 1, aus `knowledge/onboarding-default.md`), optionaler Visum-Abschnitt, Portal-Verweis, `TEMPLATE_KI_HINWEIS` – NUR nach HR/Admin-Klick (Variante-A-Guard) + Status `eingestellt`; davor: Freigabe-Report `ergebnisse/onboarding-freigabe-bewerbung-{app_id}.md` (inkl. Visum-Abschnitt) |

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
4. **Aufräumen** (Test-Task-Rows löschen, Report-Restores) nur nach GO, mit vorheriger DB-Sicherung, danach Baseline-Check (max/pending/failed/fb/hist/apps). Vor jedem Bestandsedit `.bak-YYYYMMDD-HHMM`.
