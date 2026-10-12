# E2E-Spec: Agent-Runner + MCP über DE/EN/FR/AR (Sprach-Matrix)

> **Status:** Spec 07.10.2026 (Nutzer-GO „Volle Runner-Kette je Sprache", Runner-Simulation + DRY_RUN).
> **Test:** `tests/e2e_i18n_runner_chain.py` · **Beleg:** `ergebnisse/entscheidungen.md` 07.10.2026.
> **Bindend für:** alle agent-erzeugten, nutzersichtbaren Texte der Kette.

## 1. Ziel
**Soll (12.10.2026, Nutzer-Entscheidung):** Die nutzersichtbare Ausgabe folgt der **UI-Sprache des
handelnden Nutzers** (`app.storage.user["language"]`, transportiert als `language` im Task-Payload
bzw. gelesen über `_lang(payload)`) — **die Auslöser-UI-Sprache führt**. Nachweis: die
nutzersichtbare Agent-Kette (Runner + MCP) wird in **jeder Sprache** (DE/EN/FR/AR) mit E2E-Beweis je
Sprache bedient — ohne externe Nebenwirkung (kein echter Mail-Versand, kein LLM-/Netz-Call).

**Dokumentierte Ausnahmen zum Soll:**
- **(a) LLM-Berichts-Bodies = best-effort:** Prompt-Anweisung + Sprach-Nachkontrolle
  (`_body_sprache_ok`) mit **max. 1 Retry** und Warn-Log (§7.1 Punkt 5) — **keine** harte Garantie.
- **(b) Gespeicherte Artefakte/Altbestand werden NICHT rückübersetzt:** es gilt die
  **Erzeugungssprache** (§7.1 Punkt 4). Garantiert ist die Sprache für die **deterministischen
  `tr()`-Pfade** (Mails #1–#6, die deterministischen Reports, die `>`-Header-Prosa) — **je Sprache**.

## 2. Was ist sprachabhängig? (Ist-Analyse, Codemarken ⓘ07.10.2026)
| Artefakt | Sprache | Quelle | Abweichung zum Soll |
|---|---|---|---|
| Toasts (z. B. „Profil gespeichert!", „Lebenslauf hochgeladen …", „Bewerbung gesendet! …") | **Session-Sprache** | `webui/pages/candidate.py` (`ui.notify(_(...))`) | — |
| `notifications`-Zeilen (`Neue Bewerbung`, `{0} hat sich beworben: {1}`) | **Erzeugungs-Sprache** (Kandidaten-Session beim Trigger) | `webui/pages/candidate.py` (Codemarke `def _notify_neue_bewerbung`, gemessen 10.10.2026) → `db.insert_notification(..., _(...))` | cross-person: Empfänger ≠ Auslöser (Kandidaten-Sprache beim Trigger) |
| Statische UI (Tabs, Labels, Status über `status_label`) | **Session-Sprache** | `webui/i18n.py` (gemessen 10.10.2026) | — |
| Portal-erzeugte MD (Onboarding-Checkliste, Pre-Screen-MD, Feedback-MD) | **Erzeugungs-Sprache** | P9.4, `knowledge/system/i18n.md` Klasse E | — |
| **Runner-erzeugte Artefakte** (Mails #1–#6, `ergebnisse/einladung-*.md`, `ergebnisse/onboarding-freigabe-*.md`, `ergebnisse/contract-preflight-*.md`, `ergebnisse/export-kandidat-*.md`) | **Payload-Sprache** (Session-Sprache des Auslösers) | `scripts/agent-runner.py` — `_lang(payload)` + `tr()` aus `webui/i18n_core.py` (P2/P3, 07.10.2026); `language` im Task-Payload via `webui/db.py`-Resolver | Runner-intern ohne UI-Akteur: erbt Sprache der auslösenden Kette (`_lang(payload)`, §7) |
| **LLM-Berichts-Body** (`extract_profile-*`, `match_candidate-*`, `check_compliance-*`, `assess_culture_fit-*`, `verify_documents-*`, `check_visa-*`, `explain_match-*`, `notify_user-*.md` in `ergebnisse/`) | **Payload-Sprache** (Prompt-Anweisung `Antworte in <Klarname>.`, §7.1 Punkt 5) — Altbestand **vor** 07.10.2026 bleibt deutsch (Punkt 4), z. B. `extract_profile-kandidat-13-2026-09-24.md` | `scripts/agent-runner.py`, Codemarke `Antworte in` (Prompt-Bau); Anzeige in 🏢 🔎 Agent-Details via `logic.ERGEBNISSE.glob(_glob)` (neueste Datei je Task) | best-effort (Prompt + `_body_sprache_ok`, max 1 Retry, §7.1 P5); Altbestand nicht rückübersetzt (P4) |
| **LLM-Berichts-Header** (`# Extract Profile – Kandidat #13 / Stelle #6` + `> Agent-Task (Phase 5, live …), Modell: …`) | **Prosa-Zeile in Payload-Sprache; Titel-Marker sprachstabil (deutsch)** — nur die `>`-Zeile `(> Agent-Task (Phase 5, live …), Modell: …)` läuft über `tr()`; der **Task-Titel bleibt englisch** (Identifier, entspricht Dateiname-Prefix und Badge-Key) und die **Titel-Struktur-Marker `Kandidat #<id>` / `Stelle #<id>` bleiben IMMER deutsch** (sprachstabile, maschinell geparste Identifier) — **P9.5b, Nutzer-GO 07.10.2026 „Mitübersetzen", korrigiert 09.10.2026 (parse-kritische Marker)**; Altbestand vor 07.10. bleibt deutsch (Punkt 4, GO „Liegen lassen") | `scripts/agent-runner.py`, Codemarke `llm_report_header` (früher `header =`); Parser: `webui/pages/employer.py` Codemarke `_BERICHT_STELLE` (`Stelle #(\d+)`) + `tests/test_r33_compliance_reports.py` (`Stelle #\d+`); Beweise `tests/test_runner_i18n.py` (Codemarke `def test_p9_5b_header_de_byteidentisch`, gemessen 10.10.2026) (de byte-identisch → `e2e_admin_downloads` rc=0) + `test_p9_5b_header_payload_sprache`; Dateisuche unberührt (Dateiname-Muster, Codemarke `_find_agent_report`) | parse-kritische Marker `Kandidat #`/`Stelle #` immer deutsch = gebundene Soll-Ausnahme (§7.1 P5) |

**Design-Entscheidung (keine externe Quelle):** Runner-Artefakte liefen bis P1 fix Deutsch (kein
Session-Kontext). Seit **P2/P3 (07.10.2026, Variante B)** tragen die Tasks `language` im Payload
(`webui/db.py` (Codemarke `def queue_agent_task`, gemessen 10.10.2026) + Resolver-Hook) und der Runner übersetzt Mails #1–#6 + die 3
deterministischen Reports über `tr()` aus der **framework-freien** Kernschicht `webui/i18n_core.py`
(kein NiceGUI-Import). Alt-Tasks ohne `language` → `de` (keine Rück-Übersetzung bestehender Dateien).

## 3. Methode (R6-0, deterministisch, offline)
- **Nur isoliert:** `tests/e2e_isolation.py --port <frei> --only e2e_i18n_runner_chain`
  (`KMHR_E2E_BASE` + Spiegel-DB `KMHR_DB_PATH`); Abbruch, wenn DB == Live-DB.
  **Grenze (ehrlich, Verifizierer-Befund 07.10.2026):** isoliert ist die **DB** (Spiegel).
  Der Test legt seine CV-Testdateien projekt-lokal in `testdaten/` ab (im `finally` gelöscht)
  und der Runner schreibt seine DRY-RUN-Zeilen in `logs/agent-errors.log` (projekt-lokal, keine DB) —
  beides liegt außerhalb des Live-DB-Hash-Nachweises, verändert aber keine Live-Daten.
- **Runner-Simulation statt Hintergrund-Runner** (`KMHR_RUNNER_AUTOSTART=0`): das Testmodul lädt
  `scripts/agent-runner.py`, setzt `DB_PATH` auf die Spiegel-DB und `DRY_RUN=True`, dann
  `process_task()` für alle `pending`-Tasks (id > pre_max), bis die Queue leer ist
  (Gatekeeper kann `notify_hr` nachlegen).
- **Offline-Patches (Pflicht, sonst Seiteneffekte im DRY_RUN):** `_pdf_forensic_pre_scan` (sonst
  `npx`-Subprozess) und `ansvar_search` (sonst ansvar-HTTP) werden durch Stubs ersetzt —
  beide laufen im Runner **vor** dem `DRY_RUN`-Guard.
- **`mcp_call`** ist DRY_RUN-sicher (return „DRY-RUN"); `run_llm_task` bricht im DRY_RUN vor dem
  NVIDIA-Aufruf ab (`[DRY-RUN] NVIDIA API direct`).

## 4. Sprach-Matrix (je Sprache L ∈ {de,en,fr,ar})
1. **Sprachwechsel:** Kandidat-Login → Header-Button `LABELS[L]` (`webui/i18n.py`) → Reload;
   Nachweis `document.documentElement.lang == L`.
2. **CV-Kette:** CV-Upload (cand16) → Toast == msgstr(L, „Lebenslauf hochgeladen ({0} Zeichen).")
   + `candidates.status='lebenslauf_hochgeladen'` + Task `extract_profile` queued.
3. **Profil:** Speichern → Toast == msgstr(L, „Profil gespeichert!").
4. **Bewerbungs-Kette:** Bewerben → Toast == msgstr(L, „Bewerbung gesendet! …") + 10 Tasks queued
   (`send_confirmation`, `extract_profile`, `match_candidate`, `check_compliance`,
   `assess_culture_fit`, `verify_documents`, `check_visa`, `explain_match`, `check_gdpr`,
   `notify_user`) + `notifications`-Zeile in Sprache L (Titel/Nachricht).
5. **Runner-Drain (DRY_RUN):** alle Tasks der Kette → `done`; keine `failed`.
6. **Restore:** cand16-Zeile, neue `applications`/`application_status_history`/`agent_tasks`/
   `notifications`/`candidate_documents` + Testdateien werden zurückgesetzt; F3 `Test-Reste=0`.

**Erwartete msgstr (Quelle: `webui/locales/*/messages.po`, ⓘ07.10.2026):**
| msgid | en | fr | ar |
|---|---|---|---|
| Profil gespeichert! | Profile saved! | Profil enregistré ! | تم حفظ الملف الشخصي! |
| Lebenslauf hochgeladen ({0} Zeichen). | CV uploaded ({0} characters). | CV téléchargé ({0} caractères). | تم تحميل السيرة الذاتية ({0} حرفًا). |
| Bewerbung gesendet! Der Agent prueft Ihren Lebenslauf. | Application submitted! The agent is checking your CV. | Candidature envoyée ! L'agent vérifie votre CV. | تم إرسال الطلب! يتحقق الوكيل من سيرتك الذاتية. |
| Neue Bewerbung | New application | Nouvelle candidature | طلب جديد |
| {0} hat sich beworben: {1} | {0} has applied: {1} | {0} a postulé : {1} | {0} قدّم طلبًا: {1} |

## 5. HR-Seite (Agent-Kette, sprachneutral)
Die HR-ausgelösten Task-Typen (`create_invitation`, `send_rejection`, `onboarding_release` +
`send_onboarding_mail`, `visa_confirmation`, `notify_hr`) werden mindestens in **DE** über echte
Portal-Klicks ausgelöst und via Runner-Simulation bis `done` gefahren; ihre Artefakte folgen
seit P2/P3 (07.10.2026) der **Auslöser-Sprache** (HR-Session, §7). ~~**Design-Entscheidung:** keine
4-fache Wiederholung der status-verändernden HR-Flows (einladen/ablehnen/einstellen) je Sprache —
die Statusflüsse sind bereits durch `e2e_invitation_termin`, `e2e_transition_guard`,
`e2e_contract_preflight` belegt.~~ **Abgelöst 07.10.2026 (Nutzer-Auftrag „kompletter E2E über
alle Punkte … mit alle 4 Sprachen", GO via question-Tool):** die reine DE-Belegung der
Statusflüsse genügt nicht mehr — **Pflicht ist jetzt der vollständige Gesamtlauf je Sprache**
(CV-Upload → Bewerben → Kette → HR-Session in Sprache L → Einladen → Einladungs-Artefakte)
in `tests/e2e_i18n_full_chain.py` (Schleife über `LANGS`, Kandidat #13 aus Tunesien, Helfer 1:1
aus `e2e_i18n_runner_chain` + `e2e_invitation_termin`, DRY_RUN/Offline-Patches, Restore +
Residue-Check je Sprache). Die DE-Regressionsskripte `e2e_invitation_termin`,
`e2e_transition_guard`, `e2e_contract_preflight` bleiben **unverändert** bestehen (Status-Whitelist,
Payload-Keys, ICS/VDO-Karte). **Design-Entscheidung (keine externe Quelle), Invite-Weg:** das
Einladen läuft über den **Dialog der Match-Seite** (`_open_invite`/`do_invite` in
`webui/pages/employer.py`, derselbe Handler `queue_agent_task("create_invitation", …,
trigger="hr_klick_portal")` wie die Stellen-Seite), **nicht** über einen `goto` auf
`/employer/stellen`: diese Navigation ließ den Playwright-Node-Driver in der WSL-Umgebung nach
dem „angesehen"-Klick reproduzierbar verhungern (EPIPE/blockierender `count()`; 6 Läufe belegt,
ergebnisse/entscheidungen.md 07.10.2026), obwohl dieselbe Seite isoliert stabil war. Die
Stellen-Seite selbst bleibt durch das grüne `e2e_invitation_termin.py` (DE) abgedeckt. **Design-
Entscheidung:** pro Sprache **zwei getrennte Playwright-Sessions** (Kandidat / Arbeitgeber,
frischer Node-Driver je Phase) + Polling auf die `create_invitation`-Zeile (Race: der Klick-
Handler schreibt sie erst nach dem Status-UPDATE). **Design-Entscheidung:** Sprachumschaltung im
Skript = Umschalter-Button `DE/EN/FR/AR` + 3 s Reload + Assertion auf `documentElement.lang`
(Muster `switch_lang`, locator-basiert statt `page.evaluate`, das keinen Timeout hat), RTL-
Assertion bei `ar` (Muster `e2e_rtl_drawer`). **E2E-Nachweis 07.10.2026:** isolierter Lauf
Port 8085, `rc=0`, 186,7 s, alle 4 Sprachen `rc=0`, Live-DB-sha256 unverändert.

## 6. Offene Punkte
- ~~**Klasse F (neu):** Runner-/MCP-erzeugte Artefakte ohne i18n~~ → **geschlossen P2/P3
  (07.10.2026):** Mails #1–#6 + die deterministischen Reports (`einladung-*`,
  `onboarding-freigabe-*`, `contract-preflight-*`) laufen über `tr()`/`_lang()`
  (Spec §7.1); LLM-Prompts tragen die Anweisung `Antworte in <Sprache>.` (Punkt 5).
  **P4c (07.10.2026):** auch der Report-Generator `export_report` (`export-kandidat-*.md`)
  ist vollständig übersetzt.
  **Grenze (war Restgrenze, geschlossen in P2b 07.10.2026):** Die vom `email-sender`/
  `meeting-tools`-MCP **selbst erzeugten** Mailtexte (`send_pre_screen_invitation`) und
  Screening-Fragen (`generate_screening_questions`) laufen jetzt ebenfalls über `tr(..., language)`;
  der Runner übergibt `"language": lang` an beide Calls (P2b, `tests/test_runner_i18n.py` (gemessen 10.10.2026)).
- ~~**M1–M3 (Rest-Lücken aus unabhängiger Verifikation):**~~ → **behoben 07.10.2026 (P2c):**
  `notify_hr` Body-Zeile `"Compliance: COMPLIANT"` → `tr("Compliance: {0}", lang).format("COMPLIANT")`
  (Label übersetzt, technischer Token bleibt Platzhalterwert); `create_invitation` übergibt
  `strengths`/`gaps` = `tr("siehe Match-Bericht", lang)` (diese Werte landen **wörtlich** im
  Kandidaten-Pre-Screen-Mail-Body); `contract_preflight` Report-Fallbacks „Kandidat #{0}" und
  „(Katalog-Key {0} ohne URL)" über `tr(...)` (reine **Anzeige** — **kein** Parser-/Persistenz-Marker;
  der geschützte `"Kandidat #"`-Parser betrifft nur `feedback.kandidat_name`/`_feedback_klarname`,
  nicht den Contract-Report). Katalog 969 → **972** (+3).
- **Legacy-MCP-Tools (0 Aufrufer, seit 12.10.2026 sprachparameterisiert):** `mcp-email-server.py`
  (Codemarke `def send_interview_invitation`) und `mcp-meeting-server.py` (Codemarken
  `def create_meeting_link`, `def generate_ics_file`) akzeptieren jetzt `language: str = "de"`
  und bauen ihre Texte (Betreff/Body, Meeting-Labels inkl. Wochentage, ICS-Default-`DESCRIPTION`)
  über `tr(..., language)`; fehlendes/ungültiges `language` → `de` (Altverhalten, DE-Ausgabe
  byte-identisch). Die zugehörigen msgids laufen über den Katalog `webui/locales`; DE = Identität,
  EN/FR/AR = Design-Entscheidung (Native-Review offen).
- Native-Review der EN/FR/AR-Erstfassungen (steht projektweit offen).

## 7. Umsetzung Variante B (Nutzer-GO 07.10.2026)
**Entscheidung (Nutzer):** Sprache = **Session-Sprache des Auslösers**, transportiert als `language`
im Task-Payload. **Keine** `candidates.language`-Spalte (Variante A verworfen).
**Bekannte Grenze — präzisiert 12.10.2026 (kein Verstoß, sondern Soll-konform):** HR-ausgelöste
Kandidaten-Mails (Einladung/Absage/Visum/Onboarding) laufen in der **HR-Sprache** — nach dem Soll
„Auslöser-UI-Sprache führt" ist das **konform** (Akteur = HR). **Offener Rest** ist allein die
**Empfänger-Sprache** (Kandidat): die Mail folgt nicht der Sprache des Kandidaten. Der explizite,
offene Pfad dafür bleibt **Variante A** (Kandidaten-Sprache, später möglich, additiv).

**Weitere Abweichungsklasse (dokumentierte Grenze, kein Bug):** Runner-interne Events **ohne
UI-Akteur** (`notify_hr`, Auto-Refresh `match_candidate`, Sweep) haben im Runner **keine
HR-Session**; sie erben die Sprache der **auslösenden Kette** über `_lang(payload)` (Payload-Feld
`language`). Ohne UI-Akteur ist das die einzig verfügbare Sprache — dokumentiert, nicht als Fehler
zu werten.

### 7.1 Bausteine
1. **`webui/i18n_core.py` (neu, framework-frei):** pures `gettext` + `lru_cache`,
   `tr(msgid, lang, **fmt)` (Fallback: Original; `de` = Identität). **Eine Katalogquelle**
   `webui/locales`. `webui/i18n.py` (gemessen 10.10.2026) delegiert an `i18n_core` (NiceGUI-Session bleibt dort).
   Der Runner importiert **nur** `webui/i18n_core.py` (kein NiceGUI) → löst die Prozess-Trennung.
2. **Transport `language`:** `webui/db.py` (Codemarke `def queue_agent_task`, gemessen 10.10.2026) injiziert
   `payload.setdefault("language", <Resolver>)` über einen **Resolver-Hook**
   `db.set_language_resolver(fn)`; registriert in `webui/i18n.py` (`db.set_language_resolver(get_language)`).
   Damit sind **alle 28 Aufrufer** zentral abgedeckt (candidate/employer/admin/components), ohne sie
   einzeln zu ändern. **Dedupe-Schutz:** im Zweig ohne `application_id` wird `language` aus dem
   Payload-Vergleich ausgenommen (sonst würde ein altes Task-Payload ohne `language` das neue mit
   `language` nicht matchen → Duplikat). Der `application_id`-Zweig nutzt `json_extract` → unberührt.
   **Pflicht für Runner-interne Direkt-INSERTs (F1, 12.10.2026):** schreibt `scripts/agent-runner.py`
   selbst `agent_tasks`-Zeilen (**nicht** über `queue_agent_task` — Auto-Refresh `match_candidate`,
   `gatekeeper_eval`, `notify_hr`), MUSS das Payload `"language": _lang(payload)` tragen
   (Codemarke `_lang(payload)` in `scripts/agent-runner.py`); sonst greift kein Resolver und die
   Folge-Task fällt **still** auf `de` zurück.
3. **Runner:** `_lang(payload) = payload["language"] if in SUPPORTED else "de"`; alle **6 Mails**
   (`send_confirmation`, `notify_hr`, `visa_confirmation`, `send_onboarding_mail`, `send_rejection`,
   `create_invitation` inkl. ICS-Titel) und die **4 deterministischen Reports** (`einladung-*`,
   `onboarding-freigabe-*`, `contract-preflight-*`, `export-kandidat-*`) über `tr(...)`.
4. **Fallback / Altbestand:** Tasks ohne `language` (bereits in der Queue) → `de`; keine
   Rück-Übersetzung bestehender Mails/Reports **und LLM-Berichte** (P9.4-Regel „Erzeugungssprache";
   Praxis-Fall 07.10.2026: Agent-Details zeigt Alt-Dateien vom 24.09.2026 → deutsch = **Abweichung
   zum Soll, GO Liegenlassen 07.10.2026**).
5. **LLM-Tasks:** Prompt erhält die Anweisung, in der Payload-Sprache zu antworten (HR-Sichtbar);
   als Design-Entscheidung dokumentiert. **Berichts-Header seit P9.5b (07.10.2026, Nutzer-GO
   „Mitübersetzen"):** `llm_report_header(task_type, cid, jid, datum, lang)` baut den Header über
   `tr()` in der Payload-Sprache (Prosa-Zeile „Agent-Task (Phase 5, live …), Modell: …"); der
   **Task-Titel bleibt englisch** (`task_type.title()` = Identifier, entspricht Dateiname-Prefix und
   Badge-Key — Design-Entscheidung). **Korrektur P9.5b für parse-kritische Marker (Design-Entscheidung,
   09.10.2026) = gebundene Soll-Ausnahme (parse-kritisch):** die Titel-Struktur-Marker `Kandidat #<id>` / `Stelle #<id>` sind **sprachstabile
   Identifier** und werden **immer deutsch** geschrieben (nicht mehr über `tr()`) — Grund: sie werden
   maschinell geparst von `webui/pages/employer.py` (Codemarke `_BERICHT_STELLE = _re.compile(r"Stelle
   #(\d+)")`, HR-Compliance-Seite) und von `tests/test_r33_compliance_reports.py` (`Stelle #\d+`);
   die frühere FR-Titelzeile `Candidat #1 / Poste #9` brach das Schema (`job_id=None`). Nur die
   `>`-Prosa-Zeile bleibt übersetzt. Bei `de` byte-identisch mit dem Altbestand
   (Beweis `tests/test_runner_i18n.py` (Codemarke `def test_p9_5b_header_de_byteidentisch`, gemessen 10.10.2026); E2E
   `e2e_admin_downloads` rc=0). **Badge-Härtung (Nutzer-GO „Prompt-Härtung"):** hinter dem
   Sprach-Suffix `Antworte in …` folgt eine feste deutschsprachige Prompt-Regel, dass die
   Status-Tokens (`COMPLIANT`/`NICHT_COMPLIANT`/`KONFORM`/`NICHT_KONFORM`/`PLAUSIBEL`/`AUFFAELLIG`/
   `UNBEKANNT`/`UNGEWISS`/`ERFORDERLICH`/`NICHT ERFORDERLICH`) IMMER unverändert ausgegeben werden
   → `_badge_icon` (employer.py) bleibt auch bei FR/AR-Berichten funktionsfähig; interne Regel wie
   `Antworte in <Klarname>`, **keine** msgid (nicht nutzersichtbar, kein Katalogeintrag).
   Beweis `tests/test_runner_i18n.py` (Codemarke `def test_p9_5b_prompt_token_haertung`, gemessen 10.10.2026). **Altbestand** (Dateien vor
   07.10.2026, z. B. `extract_profile-kandidat-13-2026-09-24.md`) bleibt deutsch (Punkt 4,
   Nutzer-GO „Liegen lassen" — keine Rück-Übersetzung).
   **Struktur-Labels in der Payload-Sprache (O1, Nutzer-GO „O1" 11.10.2026, Design-Entscheidung):**
   die **Struktur-Labels** des LLM-Prompts — die **Sektionsliste** (`Profil`, `Kernkompetenzen`,
   `Berufserfahrung`, `Bildung`, `Sprache`, `Standort`), die **7 Gewichts-Labels**
   (`kern`/`erfahrung`/`bildung`/`standort`/`branche`/`soft`/`sprache`) und das `Kategorie`-Label —
   werden über `tr(msgid, payload.language)` in der **Payload-Sprache** erzeugt
   (`scripts/agent-runner.py`, Codemarken `_gewichts_prompt_zeile(lang)` + `tr('Kategorie', lang)`
   in `run_llm_task` sowie die Sektionsliste im `extract_profile`-Prompt, gemessen 11.10.2026);
   der **freie Fließtext** bleibt bewusst in der **Generierungssprache** (Design-Entscheidung — kein
   `tr()` auf Prosa); der **Altbestand** (**199** Berichte = `result_json["text"]`, DB-Stichprobe
   11.10.2026) wird **nicht** rückübersetzt (Punkt 4). Katalog-Auswirkung: **+7** Gewichts-msgids
   (**993 → 1000** je Sprache); die Sektions-/`Kategorie`-Labels waren bereits katalogisiert.
   Quelle: **Design-Entscheidung** (keine externe Quelle); die EN/FR/AR-Erstfassungen der 7 Labels
   sind eigene Übersetzung (Native-Review offen, Muster Punkt 6).
   **Sprach-Nachkontrolle des LLM-Bodys (F2, 12.10.2026):** nach dem LLM-Call prüft
   `_body_sprache_ok(text, lang)` (billige Heuristik; Default `True` bei Unsicherheit) den Body
   (Codemarke `_body_sprache_ok(text, lang)` in `scripts/agent-runner.py`); bei Abweichung **genau
   ein** Retry mit gehärteter Instruktion („Antworte ausschliesslich in <Klarname>. Uebersetze auch
   alle Fachbegriffe."); schlägt auch dieser fehl, **Warn-Log** und Originaltext beibehalten —
   **nie blockierend**; die Status-Tokens (`COMPLIANT`/`NICHT_COMPLIANT`/… s. o.) und die Marker
   `Kandidat #`/`Stelle #` bleiben unverändert.
6. **MCP-Server-Texte (P2b, 07.10.2026):** `mcp-email-server.py` (Codemarke `def send_pre_screen_invitation`, gemessen 10.10.2026)
   und `mcp-meeting-server.py` (Codemarke `def generate_screening_questions`, gemessen 10.10.2026) erhalten den Parameter
   `language: str = "de"` und bauen `subject`/`body` bzw. Kategorien/Fragetemplates/Kopf+Fuß
   über `tr(..., language)`; `scripts/agent-runner.py` (Codemarke `def create_invitation`, gemessen 10.10.2026) übergibt `"language": lang`.
   Fehlendes/ungültiges `language` → `de` (Altverhalten). Neuer Katalog-Bestand: **+42 msgids**
   (927 → **969**; Übersetzungen EN/FR/AR = **Design-Entscheidung**, eigene Erstfassung,
   Native-Review offen). **Legacy-Tools (12.10.2026):** auch `send_interview_invitation`
   (`mcp-email-server.py`, Codemarke `def send_interview_invitation`) sowie `create_meeting_link`
   und `generate_ics_file` (`mcp-meeting-server.py`) sind sprachparameterisiert
   (`language: str = "de"`, Texte über `tr(..., language)`, fehlend/ungültig → `de`); die
   DE-Ausgabe ist byte-identisch zu vorher (backward compatible). Die zugehörigen msgids laufen
   über den Katalog `webui/locales`; DE = Identität, EN/FR/AR = Design-Entscheidung
   (Native-Review offen).

### 7.2 Nachweis
- Unit: `tests/test_runner_i18n.py` (`tr()` je Sprache, Fallback, `_lang`-Priorität, Dedupe ignoriert
  `language`, Alt-Payload → `de`; P2b: `test_p2b_*` prüft Katalog-Vollständigkeit, Übersetzungen
  sowie den Direktaufruf von `send_pre_screen_invitation`/`generate_screening_questions` je Sprache
  ohne echten Versand).
- Katalog-Vollständigkeit: jeder neue Runner-msgid in allen 4 `.po` (Test analog `test_i18n.py`).
- E2E: `tests/e2e_i18n_runner_chain.py` prüft zusätzlich **je Sprache** den DRY-RUN-Mail-Betreff
  (Log `[DRY-RUN] MCP …send_email … "subject": …`) gegen die Zielsprache; Klasse-F-Gap-Abschnitt
  entfällt dann (Klasse F wird geschlossen).

### 7.3 Nachtrag P2c/M1–M3 (07.10.2026)
Drei von der unabhängigen Verifikation gefundene Rest-Lücken sind geschlossen (Details §6):
M1 `notify_hr` „Compliance: {0}", M2 `create_invitation` `strengths`/`gaps` „siehe Match-Bericht"
(kandidensichtbar), M3 `contract_preflight` Report-Fallbacks (reine Anzeige). Katalog **969 → 972**.
**Nachtrag Legacy-Tools (12.10.2026):** die zuvor ausgenommenen Legacy-Tools
`send_interview_invitation` (`mcp-email-server.py`) sowie `create_meeting_link` und
`generate_ics_file` (`mcp-meeting-server.py`) sind jetzt sprachparameterisiert
(`language: str = "de"`, Texte über `tr(..., language)`, fehlend/ungültig → `de`); die DE-Ausgabe
ist byte-identisch zu vorher (backward compatible). Die zugehörigen msgids laufen über den Katalog
`webui/locales`; DE = Identität, EN/FR/AR = Design-Entscheidung (Native-Review offen).

### 7.4 Nachtrag P4c (07.10.2026) — `export_report`
Der als letzte Rest-Lücke gefundene deterministische Report-Generator **`export_report`** (Skill 16,
`ergebnisse/export-kandidat-<cid>-job-<jid>-<datum>.md`, im HR-Portal sichtbar) baut seinen `bericht`
jetzt vollständig über `tr("<msgid>", lang, **fmt)` (`lang = _lang(payload)`). Betroffen: Titelzeile,
`**Datum:**`, `**Score:** …`, `**Compliance:** …` (Label übersetzt, technische Tokens
`COMPLIANT`/`NICHT COMPLIANT` bleiben Platzhalterwert), `**Kultur-Fit:** …` (vorhandener msgid
`**Kultur-Fit:** {cultural_fit_score}/100` wiederverwendet), `## Kategorien`, Tabellenkopf,
die 7 Kategorie-Zeilen (Kategorienamen übersetzt, „siehe Match-Bericht" = vorhandener msgid) und die
Fußzeile. **Nicht geändert:** Dateiname `export-kandidat-…`, technische Marker, `handle_errors`
(Logs = technisch). Katalog **972 → 980** (+8; 2 der Zielstrings `**Datum:** {0}` und
`**Score:** {0}/100 ({1})` waren bereits vorhanden). Beweis: `tests/test_runner_i18n.py` (P4c).
**Ist-Stand 09.10.2026 (Korrektur):** Katalog je Sprache = **993** msgids (`grep -c '^msgid ' webui/locales/de/LC_MESSAGES/messages.po` = 993, de/en/fr/ar gleich); die 980/991 sind datierte Zwischenstände.
Übersetzungen EN/FR/AR = **Design-Entscheidung** (eigene Erstfassung, Native-Review offen).
