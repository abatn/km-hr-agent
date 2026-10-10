# SKILL: NiceGUI Migration (Phase 0–1)

> **Status:** Phase 0 abgeschlossen, **Phase 1 abgeschlossen (P1.1–P1.3 + P2.1, 20.09.2026)**
> **Spec:** knowledge/ui-design-system.md (Quelle der Wahrheit für UI)
> **Code:** webui/ (16 Dateien, 11.583 Zeilen inkl. 2 × `__init__.py`; gemessen ⓘ09.10.2026, `find webui -name '*.py' | wc -l` / `wc -l`)

---

## Übersicht

Migration des Streamlit-Monoliths (`app.py`, 4040 Zeilen) zu einer modularen NiceGUI-App (`webui/`, 16 Dateien).

**Ziel:** Framework-unabhängige Business-Logik (db.py + logic.py) +NiceGUI-spezifisches UI.

---

## Architektur

```
webui/
├── main.py              # Entry Point, Routing, Boot-Sequenz
├── db.py                # Framework-unabhängiger DB-Layer (16 Tabellen, Stand 24.09.2026)
├── logic.py             # Framework-unabhängige Business-Logik (Scoring, DSGVO, Auth)
├── theme.py             # Design Tokens, CSS, Tailwind-Klassen
├── components.py        # Wiederverwendbare UI-Komponenten (28 `def`, `grep -c '^def '` 24.09.2026)
├── pages/
│   ├── login.py         # Login/Registrierung (5 Tabs)
│   ├── candidate.py     # Candidate-Portal (7 Tabs, _TAB_MAP Stand 02.10.2026)
│   ├── employer.py      # Employer-Portal (11 Pages)
│   └── admin.py         # Admin-Portal (12 Pages)
```

---

## Phase 0: Framework-unabhängige Layer (ABGESCHLOSSEN)

### Was wurde extrahiert?

| Layer | Datei | Funktionen | Quelle app.py |
|-------|-------|-----------|---------------|
| DB | `db.py` | **28 Funktionen** (gemessen ⓘ09.10.2026, `grep -c '^def ' webui/db.py`): `get_conn()`, `set_language_resolver()`, `init_agent_tasks_table()`, `queue_agent_task()`, `apply_to_job()`, `get_invitation_artifacts()`, `get_application_status_history()`, `get_agent_task_status()`, `get_candidate_agent_tasks()`, `get_language_tests()`, `insert_language_test()`, `get_documents()`, `insert_document()`, `delete_document()`, `upsert_employer()`, `insert_job()`, `update_job_status()`, `init_notifications_table()`, `init_mentoring_table()`, `init_compliance_protokoll_table()`, `record_compliance_protokoll()`, `get_active_mentor()`, `assign_mentor()`, `end_mentoring()`, `insert_notification()`, `get_notifications()`, `get_unread_count()`, `mark_notifications_read()` | aus `app.py` extrahiert (Phase 0) |
| Logik | `logic.py` | Scoring (7 Kategorien), DSGVO-Cleanup, Agent-Runner-Autostart, Passwort-Hashing, Rollen-Login, Gewichtungs-Feedback | Zeilen 150–621 |

### Regeln für Phase 0
- `db.py` und `logic.py` haben **KEINE** Streamlit- oder NiceGUI-Imports
- Session-gebundene Funktionen akzeptieren `session` als Parameter (entkoppelt)
- Beide Apps (Streamlit + NiceGUI) können diese Layer nutzen

---

## Phase 1: NiceGUI-UI (IN ARBEIT)

### Skill 0: Login ✅ (19.09.2026 korrigiert)
- 5 Tabs: Login, Registrieren, Arbeitgeber-Login, Arbeitgeber-Registrieren, Admin
- Quelle: `app.py:891-1095`, `knowledge/system/access-control.md:62`
- Korrigiert: Passwort-Mindestlänge 8Z, Employer-Hint, Admin-Seed, sqlite3-Import

### Skill 1: Candidate-Portal ✅ (7 Tabs, `_TAB_MAP` `webui/pages/candidate.py`, Stand 02.10.2026)
- Implementiert: Upload, Mein Profil, Stellenangebote, **Bewerbungen (NEU 20.09.2026)**, Sprachtest, Onboarding
- Quelle: `app.py:3335-3382`, `knowledge/system/access-control.md:74`
- Features: status_badge, timeline (Status-Historie), withdraw-Funktion, VDO.Ninja-Link bei "eingeladen"

### Skill 2: Employer-Portal ✅ (11 Pages, `PAGE_MAP` `webui/pages/employer.py`, gemessen 2791–2803 ⓘ09.10.2026)
- Dashboard, Kandidaten-Suche, Match-Ergebnis, Compliance, Agent-Details, Dokumente, Pre-Screen, Onboarding, Feedback
- Quelle: `app.py:2000-3500`, `knowledge/system/access-control.md:73`

### Skill 3: Admin-Portal ✅ (12 Pages, funktional)
- Dashboard + Agent-Tools 0–5 (jetzt mit queue_agent_task + ui.notify)
- Quelle: `app.py:3500-3900`, `knowledge/system/access-control.md:73`
- Implementiert: Upload, Extract, Match, Compliance, Contact, Culture-Fit

---

## Design-System

Quelle: `knowledge/ui-design-system.md` (425 Zeilen)

### NiceGUI-Features (dokumentiert, nicht alle genutzt)

| Feature | Doku | Status im Code |
|---------|------|----------------|
| `ui.add_head_html()` | §10.1 | ✅ Injiziert via `inject_css()` pro @ui.page |
| `ui.tabs()` / `ui.tab_panels()` | §10.3 | ✅ Login (5 Tabs), Candidate (7 Tabs) |
| `ui.card`, `ui.column`, `ui.row` | §10.3 | ✅ Überall genutzt |
| `ui.grid()` | §10.3 | ✅ Dashboard-Layouts |
| `ui.left_drawer()` | §10.3 | ✅ Employer-Sidebar (shell() `components.py:1084`, Drawer `components.py:1142`) |
| `app.storage.user` | §10.5 | ✅ Session-Management |
| `ui.timer()` | §7.1 | ✅ Dashboard 10s (Candidate/Employer), Bewerbungen 15s, Match-View 15s; **kein** Agent-Details-Timer (Ist ⓘ09.10.2026) |
| `ui.animate()` | §7.2 | ❌ existiert in NiceGUI 3.17.1 **nicht** (`'animate' not in dir(ui)`, s. Kommentar `webui/components.py`); Score-Bar animiert per CSS-Keyframe `score-fill` (theme.py) |
| `ui.skeleton()` | §7.4 | ✅ `skeleton_loader()` (`components.py:428`, genutzt in employer.py:19) |
| `ui.notify()` | §10.2 | ✅ Match-Fehler-Feedback (Skill 2) |
| `ui.expansion()` | §10.2 | ✅ Match-Erklärung (Skill 2) |
| `ui.dark_mode()` | §7.6 | ✅ 1× zentral in shell (`components.py:1138`; Seiten haben KEIN eigenes dark_mode) |

### CSS-Animationen (theme.py)

| Animation | Dauer | Quelle |
|-----------|-------|--------|
| Score-Bar (score-fill) | 800ms ease-out | Design-System §9 |
| Badge Pulse | 2s infinite | Design-System §9 |
| Card Hover | 200ms | Design-System §9 |
| Skeleton Shimmer | 1.5s infinite | Design-System §9 |

---

## Inkonsistenzen (Stand 22.09.2026 – Schritt-2-Lauf; zuerst 20.09.2026)

| # | Datei | Zeile | Ist (Code) | Soll (AGENTS.md) | Schwere |
|---|-------|-------|-----------|------------------|---------|
| 1 | AGENTS.md | 63 | "5 tabs" + argon2id (korrekt) | 5 Tabs (login.py) | ✅ behoben 20.09.2026 |
| 2 | AGENTS.md | 73 | "6 pages" (Candidate) | ~~6 Tabs~~ ~~7 Tabs~~ ~~8 Tabs~~ ~~9 Tabs~~ **7 Tabs** (_TAB_MAP `webui/pages/candidate.py`, Stand 02.10.2026 – 📊 Dashboard als 1. Tab, Upload/Dokumente in 👤 Mein Profil; 8 seit P2.1/P2.2) | ✅ behoben (3×: 20.09.2026); Tab-Zahl 8→9 am 01.10.2026, 9→7 am 02.10.2026 |
| 3 | AGENTS.md | 75 | "9 portal pages" | ~~9~~ ~~10~~ **11 portal pages** (employer.py:1649-1660, seit P1.2; 10→11 durch HR-write-Stellen-View 20.09.2026) | ✅ behoben (3×: 20.09.2026) |
| 4 | AGENTS.md | 46 | NiceGUI-Start vorhanden | NiceGUI-Start | ✅ behoben 20.09.2026 |
| 5 | ui-design-system.md | 459 | "Login (5 Tabs)" (korrekt) | 5 Tabs (login.py) | ✅ behoben 20.09.2026 |
| 6 | ui-design-system.md | 372 | "5 Candidate-Seiten" | 5 Tabs (korrekt) | ✅ OK |
| 7 | ui-design-system.md | 373 | "9 Employer-Seiten" | 9 Pages (korrekt) | ✅ OK |
| 8 | ui-design-system.md | 428 | "12 Admin-Seiten" (korrekt) | 12 Pages (admin.py) | ✅ behoben 20.09.2026 |
| 9 | projectweit (10 Dateien) | div. | Code-Wahrheit: Timer 10s/15s (admin: keiner), Visum-Badge da (app.py:2165-2172/3700-3708), Refs `employer.py:1649-1660` / `_TAB_MAP` (`webui/pages/candidate.py`, Codemarke) / `admin.py:753-766`, EMPLOYER 11 Seiten | Alt-Werte bereinigt: `1180-1192`, `745-754`, `660-673`, „kein UI-Badge“, Timer 5s/30s + erfundene Callbacks, `tab_map`→`_TAB_MAP` | ✅ behoben 22.09.2026 |

**Quelle (Schritt-2-Konsistenzlauf):** `ergebnisse/entscheidungen.md` → Eintrag „2026-09-22: Schritt 2 – Konsistenzlauf: stale MD-Werte an den Code angeglichen“ (Z.938–996) – Beweistabelle der 6 Ziele, Sweep der 14 Zusatzvorkommen, Verifikation (Alt-Werte projectweit 0, keine `__TAB_MAP`-Korruption), betroffene 10 Dateien, Zahlenkorrektur 13→10.

---

## Start-Befehle

```bash
# NiceGUI
source .venv-streamlit/bin/activate
python3 -m webui.main  # → http://localhost:8080
# oder
./start-webui.sh
```

---

## Offene Arbeiten

1. ~~**Candidate-Bewerbungen-Tab**~~ ✅ (20.09.2026 implementiert)
2. ~~**Match-Ergebnis Live-Score**~~ ✅ (20.09.2026 implementiert)
3. ~~**Admin Agent-Tools**~~ ✅ (20.09.2026 implementiert)
4. ~~**Live-Updates (ui.timer)**~~ ✅ (20.09.2026 implementiert)
5. ~~**Animationen (ui.animate)**~~ ❌ korrigiert (NiceGUI 3.17.1: `ui.animate` existiert nicht, s. `webui/components.py`; Score-Bar animiert per CSS-Keyframe `score-fill` in `theme.py`)
6. ~~**Ladezustaende (ui.skeleton)**~~ ✅ (20.09.2026 implementiert)
7. ~~**Echtzeit-Daten (ui.refreshable)**~~ ✅ (20.09.2026 implementiert)
8. ~~**Dark Mode (ui.dark_mode)**~~ ✅ (20.09.2026 implementiert)
9. ~~**Sprachtest-Flow (P1.1)**~~ ✅ (20.09.2026 portiert: FastMCP async, Scoring, DB-INSERT)
10. ~~**Employer-Portal (P1.2)**~~ ✅ (20.09.2026 portiert: Firmenprofil, Stellen, Status)
11. ~~**eingestellt-Button (P1.3)**~~ ✅ (20.09.2026 portiert: 3 Dialoge, onboarding_release)
12. ~~**Dokumente-Tab (P2.1)**~~ ✅ (20.09.2026 portiert: Upload, Art.17-Loeschung)
13. ~~**Pre-Screen-Tab (P2.2)**~~ ✅ (20.09.2026 portiert: Selbstpräsentation, VDO.Ninja-Raum)
14. ~~**Shell-Navigation (P3.1)**~~ ✅ (20.09.2026 portiert: einheitliche shell() fuer alle 3 Rollen)
15. ~~**Status-Historie (P3.2)**~~ ✅ (20.09.2026 portiert: Timeline im Profil)
16. ~~**Admin Write-Actions (P3.3)**~~ ✅ (20.09.2026 portiert: Stellen-Status, Employer-Details)
17. ~~**GAP-1: extract_profile-Trigger + PDF-Bug**~~ ✅ (20.09.2026: File-Save, extract_pdf_text via pymupdf/.venv-pdf, lebenslauf_datei, Task-Queue; Bug B gefixt: pdfplumber→pymupdf-Subprocess)
18. ~~**GAP-2: Feedback-Write-Pfad + Phase-4-Loop**~~ ✅ (20.09.2026: Formular, idempotente INSERT/UPDATE, adjust_weights, export_report-Trigger)
19. ~~**GAP-3: Visum-Antrag-bestätigen (Employer)**~~ ✅ (20.09.2026: Guard + Button in _page_match pro Job; Bug A gefixt: Payload-LIKE statt application_id-Spalte)
20. ~~**HR-write-Stellen-View (Employer)**~~ ✅ (20.09.2026: _page_stellen mit Bewerber-Status-Verwaltung, 11 Seiten total)
21. ~~**N1+N2: ICS-Download + Termin-Auswahl**~~ ✅ (20.09.2026: Dialog-Felder Datum/Uhrzeit/Dauer → payload termin_* in do_invite; ICS-Button in candidate Bewerbungen + employer Match-HR-Sicht; E2E Task #117 done, HR-Termin übernommen, ICS 468 B; Bonus: ui.download-Argument-Bug in candidate.py gefixt)
22. ~~**N3: Session-Timeout**~~ ✅ FEHLBEFUND widerlegt (20.09.2026): check_login (30-Min-Timeout) läuft über current_role bei jedem Seitenaufruf — Runtime bewiesen; Employer/Admin ohne Timeout = Streamlit-Parität
23. ~~**N4: App-Start-Hooks**~~ ✅ FEHLBEFUND widerlegt (20.09.2026): main.py:24 ruft app_bootstrap() = dsgvo_cleanup_once + init_agent_tasks + ensure_agent_runner (1:1-Port, Runner-PID bewiesen)
24. ~~**Passwort aendern**~~ ✅ (20.09.2026: change_password() in logic.py:659, Expander in 3 Portals (Streamlit + NiceGUI), Design-Entscheidung dokumentiert, E2E 4/4 Cases bestanden)
25. ~~**SPA-Navigation (clientseitiges Routing via ui.sub_pages)**~~ ✅ (21.09.2026: shell() nutzt ui.sub_pages(root_path, routes) fuer clientseitiges Routing; 13 Content-Redirects durch navigate_to() ersetzt (Candidate 3, Employer 3+1 Query-Param, Admin 3); Close-Sidebar-Button (icon=close); 4/4 Haupt-Routen 200; 4/4 Regressionstests bestanden; Sub-Routes /candidate/upload etc. werden clientseitig geroutet (SPA-Verhalten))
26. ~~**P1: Profil-Parität Read-View + navigate_to-Härtung**~~ ✅ (22.09.2026, siehe unten)

---

## P1–P4: Profil-Parität (22.09.2026, ABGESCHLOSSEN)

> **Ziel:** Streamlit-Profil (app.py:2765-2809) und NiceGUI-Profil (candidate.py `_tab_profil`) sind funktionsgleich: 12 Speicher-Felder lesbar + speicherbar, Save-Pfad E2E-bewiesen.

### Migration-Entscheidungen (Lab-Prinzip 4: Transparenz)

| # | Entscheidung | Warum | Quelle |
|---|---|---|---|
| D1 | Read-View zeigt **alle 12 Save-Felder** (nicht nur Name/E-Mail/Status) | Streamlit-Edit-Formular zeigt diese 12 Felder; Parität verlangt dasselbe vor dem Edit-Expander lesbar | `app.py:2779-2806`, `knowledge/portal/candidate-portal-fields.md` §Read-View |
| D2 | `telefon`/`geburtsdatum` **nicht** zur Read-View hinzugefügt | Feature-Freeze: kein Speichern dieser Felder → keine Anzeige (Lab-Prinzip) | AGENTS.md Feature-Freeze |
| D3 | `soft_skills` als `info_row` in Fachkompetenzen | Feld #8 der 12er-Liste; Streamlit zeigt es im Edit, Read-View braucht es | `app.py:2787` |
| D4 | `gehaltsvorstellung` als **eigene Karte** | Zu groß für Info-Row-Grid; `stat_card`-Muster wie Berufserfahrung | `app.py:2795` |
| D5 | `navigate_to` → `try/except` um `run_javascript` | Sidebar-Muster `components.py:692-695` auf navigate_to übertragen; Content-Render darf nie am URL-Update scheitern | `knowledge/ui-design-system.md` §14.4 |
| D6 | Options-Listen visum/abschluss **dynamisch** aus DB (`SELECT DISTINCT`) | Streamlit-Statik-Listen wiesen DB-Werte wie "Visum erforderlich"/"Realschule" nicht aus → None-Save-Risiko | `candidate.py` Edit-Expander |

### E2E-Beweise (22.09.2026)

| Test | Skript | Ergebnis |
|---|---|---|
| P1.3 Read-Only (12 Felder DOM == DB, kein Save) | `tests/e2e_profile_readview.py` | **PASS** |
| P2.3 Regression | `tests/test_drawer_click.py` | **4/4 PASS** |
| P3 Save (Standort/Deutsch ändern → DB-Check → Restore) | `tests/e2e_profile_save.py` | **PASS**, Final DB == Original (Tunisien, B1) |
| Syntax | `py_compile` components.py + candidate.py | OK |

### Geänderte Dateien (P1–P4)

1. `knowledge/portal/candidate-portal-fields.md` — §Read-View Anzeige (12 Felder)
2. `webui/pages/candidate.py` — Read-View erweitert (5 Info-Rows + Soft Skills + Abschluss + Gehalts-Karte)
3. `knowledge/ui-design-system.md` — §14.4 SPA-Navigations-Regel
4. `webui/components.py` — `navigate_to()` pushState in try/except
5. `tests/e2e_profile_readview.py` — NEU (P1.3)
6. `tests/e2e_profile_save.py` — NEU (P3)
7. `skills/nicegui-migration/SKILL.md` — dieser Eintrag (P4.1)
8. `ergebnisse/nicegui-phase-2-rest-portierung.md` — P3-Anhang (P3.2)

---

## C1–C2: Einladungs-Termin + Admin-Navigation (22.09.2026, ABGESCHLOSSEN)

> **Ziel (Paritäts-Inventar C1):** Die Streamlit-Termin-Inputs vor `→ eingeladen` (app.py:3173-3185, Payload `termin_*`) existieren in NiceGUI an allen 3 Queue-Stellen (💼 employer `_page_stellen`, 🛡️ admin `_page_stellen`, Match-Dialog employer.py:603) und landen im `create_invitation`-Payload. **C2:** Admin-Nach-Navigation zeigt eine existierende PAGE_MAP-Seite.

### Migration-Entscheidungen

| # | Entscheidung | Warum | Quelle |
|---|---|---|---|
| D7 | Termin-Widgets = `ui.date_input`/`ui.time_input` (QInput + Picker mit Label) | NiceGUI 3.17: `ui.date`/`ui.time` haben **kein** `label` (nur value/mask/on_change), `ui.input` hat **kein** `mask` → TypeError/500 | offiziell: nicegui.io/documentation/date_input + time_input (seit 3.3), lokale Signatur `inspect.signature` |
| D8 | `ui.caption` → `ui.label(...).classes("text-caption ...")` (7 Stellen) | `ui.caption` existiert in NiceGUI 3.17.1 nicht (`'caption' not in dir(ui)`) → Seite crasht vor jedem Widget | Quasar `text-caption`-Äquivalent; employer.py 343/443/462/466, admin.py 577/597/601 |
| D9 | Termin-Widgets als **Default-Args-Snapshot** an `make_transition` binden | Python-Closure-Late-Binding: `_inv_*` wird in Folge-Cards derselben Loop-Iteration auf None gesetzt → Payload verlor termin_* (im E2E sichtbar) | Fund im P3-Test 22.09.2026; Muster wie `_a_id=a_id` daneben |
| D10 | Runner-Guard akzeptiert `admin_klick` (Tripel) | Spec erlaubt Admin-Übergänge mit `trigger: admin_klick` — Code war enger als MD (Lab-Prinzip 3: Inkonsistenz → hier Code an MD) | `agent-automation.md:86/92` vs `agent-runner.py:349/414` |
| D11 | **C2:** `navigate_to("admin","kandidaten")` → `"stellen"` (2 Zeilen) | `"kandidaten"` existiert nicht im Admin-PAGE_MAP (12 Keys, admin.py:753-766) → Navigation nach Transition ins Leere | admin.py:574+598 |
| D12 | admin `conn.close()` erst nach Archiv-Block | Close Zeile 499 → Visum-Count (586) bediente geschlossene DB → 500 `ProgrammingError` | admin.py:_page_stellen |

### E2E-Beweise (22.09.2026)

| Test | Skript | Ergebnis |
|---|---|---|
| C1.1 Employer-Pfad (Login → stellen → → eingeladen → Payload → Restore) | `tests/e2e_invitation_termin.py` | **PASS** — termin_datum=morgen, uhrzeit=10:00, dauer=30 (≠ Fallback 20), trigger=hr_klick_portal |
| C1.2 Admin-Pfad (Login → /admin/stellen → → eingeladen → Payload → Restore) | `tests/e2e_invitation_termin_admin.py` | **PASS** — termin_* + trigger=admin_klick |
| P2-Regression | `tests/test_drawer_click.py` | **4/4 PASS** |
| Syntax | `py_compile` employer.py + admin.py + agent-runner.py + 2 Tests | OK |
| Restore (beide Tests) | status=eingegangen, upd=2026-09-14 22:05:49, hist-Max=34, 0 Rest-Tasks | verifiziert |

### Offene Punkte (aus C1 mitgenommen)

- ✅ `send_rejection`-Variante-A-Guard **umgesetzt 23.09.2026 (O2/C1)**: trigger-Tripel (`hr_klick_portal`/`hr_klick_hr_seite`/`admin_klick`) + `applications.status='abgelehnt'`-Check vor Mailversand, `scripts/agent-runner.py:377-386`, Spec `knowledge/system/agent-automation.md` §4, Tests `tests/test_send_rejection_guard.py` 4/4 (Mailversand nie echt, `mcp_call` gemockt). *(Ursprünglicher offener Punkt: „hat KEINEN Guard", MD:87.)*
- Test-Limit: q-select Dauer-Optionen via Playwright nicht zuverlässig klickbar; Test akzeptiert Default 30.

### Geänderte Dateien (C1–C2)

1. `knowledge/system/agent-automation.md` — §5 NiceGUI-Parität-Notiz (P1 MD-first)
2. `webui/pages/employer.py` — date_input/time_input + Snapshot-Binding + caption-Fix
3. `webui/pages/admin.py` — dasselbe + C2-Navigation + conn.close + caption-Fix
4. `scripts/agent-runner.py` — Guard erweitert um admin_klick (2 Stellen)
5. `tests/e2e_invitation_termin.py` + `tests/e2e_invitation_termin_admin.py` — NEU
6. `ergebnisse/nicegui-phase-2-rest-portierung.md` — C1/C2-Anhang

---

## C3: Gehalt-Check live im Match-View (22.09.2026, ABGESCHLOSSEN)

> **Ziel (Paritäts-Inventar C3):** `logic.gehalt_check()` (war dead code, 0 Aufrufe) an der Stelle rendern, an der Streamlit ihn zeigt (app.py:3848→3867 `st.metric("Gehalt")`, Employer-Tab-3-Ranking) — Spec `skills/employer-portal/SKILL.md:91` („Gehalt als Kompatibilitätshinweis"). NiceGUI-Entsprechung: `_page_match` Pro-Job-Block.

### Migration-Entscheidungen

| # | Entscheidung | Warum | Quelle |
|---|---|---|---|
| D13 | Einladungs-Dialog: `ui.input(multiline=True)` → `ui.textarea(label=…)` | NiceGUI 3.17.1: `ui.input` hat kein `multiline` → TypeError → **/employer/match lief seit Portierung mit 500** (Dialog-Bau crashte die Seite vor jedem Score) | offiziell: nicegui.io `ui.textarea`; employer.py:599 |
| D14 | `ui.animate(bar,'value',…)` in `score_bar` entfernt | `ui.animate` existiert nicht (`'animate' not in dir(ui)`); CSS-Keyframe `score-fill` (theme.py:429-432) animiert bereits identisch (0.8s ease-out) → Python-Zeile war ungültig UND redundant | lokale Inspektion NiceGUI 3.17.1 + theme.py |
| D15 | `_GEHALT_TOL_CACHE` (key = Midpoint) in `gehalt_check` | Connector-Kalkulation ~2s pro Subprocess; Match-View rief 11× pro Render auf → Event-Loop blockiert ~26s (Browser-Timeout). Ergebnis deterministisch pro Midpoint → Cache = **identische Werte**, warm 0.01s | Messung 22.09.2026: 6 Calls 11.6s → warm 0.01s |
| D16 | `_static_connector_call` für `get_score_category` (3 Stellen: logic:386/462, employer:1295) | Gleicher ~2s-Kostenblock in `berechne_match_score` (10 Scores/Render ≈ 20s). Nur Erfolge cachen → bei Connector-Fehler bleibt Retry + Fallback-Design-Entscheidung erhalten (Lab: Fallback-Werte unverändert) | ZYTHR-Schwellen sind statisch (hr-benchmark, knowledge); Messung Cold 25.7s / Warm 0.01s |

### E2E-Beweise (22.09.2026)

| Test | Skript | Ergebnis |
|---|---|---|
| C3 View-only (Login → /employer/match → 11× „Gehalt:" + 3 Varianten) | `tests/e2e_gehalt_match.py` | **PASS** — passt / außerhalb / unbekannt korrekt gegen DB-Paare (#16, #1, #13) |
| Unit `gehalt_check` 9 Fälle | Inline-Check | PASS |
| P2-Regression | `tests/test_drawer_click.py` | **4/4 PASS** |
| C1-Regressionslauf nach C3-Fixes | `tests/e2e_invitation_termin.py` | **PASS** (termin_* + Restore) |
| Syntax | `py_compile` employer/logic/components | OK |

### Geänderte Dateien (C3)

1. `webui/pages/employer.py` — Gehalt-Label in `_page_match` + textarea-Fix + `_static_connector_call`
2. `webui/logic.py` — `_GEHALT_TOL_CACHE` + `_static_connector_call` (Cache nur bei Erfolg)
3. `webui/components.py` — `ui.animate`-Zeile entfernt (score_bar)
4. `tests/e2e_gehalt_match.py` — NEU
5. `tests/e2e_invitation_termin.py` + `tests/e2e_invitation_termin_admin.py` — Login-Panel-Scope-Fix (Strict-Mode)
6. `ergebnisse/nicegui-phase-2-rest-portierung.md` + dieser Eintrag — P4

---

## C4: Sprachtest-Display + Cat-Map „Schwach" (22.09.2026, ABGESCHLOSSEN)

> **Ziel (Paritäts-Inventar C4):** (1) Sprachtest-Tab 1:1 wie Streamlit (Session-Caption, LIMIT 5, Prozent statt Rohwert); (2) Employer-Feedback-Cat-Map = Employer-Tab-4-Variante „Schwach" (nicht Admin-Variante „Nicht passend").

### Migration-Entscheidungen

| # | Entscheidung | Warum | Quelle |
|---|---|---|---|
| D17 | Sprachtest: Caption + `LIMIT 5`/`test_datum DESC` + Prozent-Formate (`{p*100:.0f}%`) in Historie UND Ergebnis | NiceGUI zeigte ALLE 11 Rows, Rohwert `0.0`, kein Session-Hinweis — Streamlit zeigt 5 + `70%` + Caption | app.py:2925-2926, 2945, 2950, 3044 |
| D18 | Employer-Feedback-Cat-Map → `Weak→"Schwach"`, default `"Schwach"` (3 Strings) | Streamlit hat ZWEI Maps: Employer-Tab-4 (app.py:3943) „Schwach" vs Admin-Tool (app.py:2602) „Nicht passend"; NiceGUI hatte die Admin-Variante an der Employer-Stelle (falsche Quelle) | app.py:3939-3944 + `lab-2-design-entscheidungen.md:82` + `matching-connector-recherche.md:275` |
| D19 | `data_table`-Suche: `ui.input(icon=…)` → `.props('prepend_icon="search"')` | NiceGUI 3.17.1: `ui.input` hat kein `icon`-Kwarg → TypeError → **500 auf jeder Seite mit Daten-Tabelle** (zuerst /employer/feedback mit >0 Rows sichtbar) | lokale Signatur + Quasar QInput `prepend-icon` |
| D20 | `_page_feedback`: Seiten-`conn.close()` nach Build entfernt | Handler-Closures (`save_feedback`/`refresh_cands`/`refresh_list`) liefen nach Close → `sqlite3.ProgrammingError: Cannot operate on a closed database` (im E2E bewiesen); Verbindung lebt wie die Page-Instance (GC schließt) | Fund 22.09.2026 in `tests/e2e_sprachtest_feedback.py` |

### E2E-Beweise (22.09.2026)

| Test | Skript | Ergebnis |
|---|---|---|
| C4 A: /candidate/sprachtest — Caption + **genau 5** Karten + `Score: 0%` | `tests/e2e_sprachtest_feedback.py` | **PASS** |
| C4 B: /employer/feedback Score=30 → `kategorie='Schwach'`, kein Weight-Loop (Ja+30<80), Restore | dasselbe | **PASS** |
| P2-Regression | `tests/test_drawer_click.py` | **4/4 PASS** |
| Syntax | `py_compile` candidate/employer/components | OK |

### Offene Punkte (aus C4 mitgenommen)

- ✅ `Eingeladen?`-Option `"Vorgemerkt"` **umgesetzt 23.09.2026 (O3/C4)**: `webui/pages/employer.py:1252` = `options=["Ja","Nein","Vorgemerkt"], value="Ja"` (Parität `app.py:3924`), Spec `knowledge/lifecycle/feedback-schema.md`, E2E `tests/e2e_vorgemerkt.py` PASS (DB-Beweis `eingeladen='Vorgemerkt'` + Restore). *(Ursprünglicher offener Punkt: „fehlt Option Vorgemerkt — Inventar/Schritt 2".)*

### Geänderte Dateien (C4)

1. `webui/pages/candidate.py` — Caption, LIMIT 5, Prozent-Formate
2. `webui/pages/employer.py` — Cat-Map „Schwach", Quellen-Kommentare, conn.close entfernt
3. `webui/components.py` — data_table Such-Icon via Props
4. `tests/e2e_sprachtest_feedback.py` — NEU
5. `ergebnisse/nicegui-phase-2-rest-portierung.md` + dieser Eintrag — P4

---

## C5: Agent-Details-Ergebnis-Parser (22.09.2026, ABGESCHLOSSEN)

> **Ziel (Paritäts-Inventar C5):** Port des Streamlit 🔍 Agent-Details-Blocks (check_visa-Parser u.a. — 9 Ergebnis-Globs → Badge-Farbe + Expander-Volltext) nach NiceGUI gemäß Spec `ergebnisse/agent-details-doku.md`.

### Migration-Entscheidungen

| # | Entscheidung | Warum | Quelle |
|---|---|---|---|
| D21 | `_page_agent_details` um Spec-Block: Kandidat-Select, ⚡ Badge-Grid (`ui.grid(6)`), `ui.expansion`-Volltexte, ⚪-Captions; Task-Queue als Sektion darunter beibehalten | NiceGUI hatte NUR die DB-Queue — Spec (Badge-Zeile + Expander) fehlte komplett; Queue bleibt als NiceGUI-Ergänzung (Read-Only) | `agent-details-doku.md` + app.py:1969-2026 |
| D22 | Matching-Slug = `kandidat-{id}` (NICHT Name-Slug) | **Fund:** Streamlit matcht Name (`name.lower().replace(" ","-")`, app.py:1974) gegen Runner-Dateien `*-kandidat-{id}-*.md` → 0 Treffer (alle ⚪, Datei-Listing + DB-Namen-Loops bewiesen); Runner-Konvention ist `kandidat-N` | app.py:1974 + agent-automation.md:91 + ergebnisse/Listing |
| D23 | `_badge_icon()`-Keyword-Reihenfolge: AUFFAELLIG → **NICHT ERFORDERLICH → ERFORDERLICH** → PLAUSIBEL/KONFORM | Streamlit-Expander-Variante (app.py:2012-2019) prüft `ERFORDERLICH` vor `NICHT ERFORDERLICH` → Precedence-Bug (🟢 laut MD würde 🔴); Badge-Zeile (1985-1989) + MD-Tabelle sind korrekt — NiceGUI folgt diesen | app.py:1985-1989 + `agent-details-doku.md` (Badge-Farben-Tabelle) |
| D24 | Kandidat-Picker lokal (`ui.select`, ORDER BY name) statt Streamlit-Sidebar | NiceGUI hat keinen Sidebar-Kandidaten-Selektor; Select auf der Page = kürzester Weg mit gleichem Ergebnis | NiceGUI shell()-Architektur |

### E2E-Beweise (22.09.2026)

| Test | Skript | Ergebnis |
|---|---|---|
| Default (id16, 0 Dateien) → 9× ⚪ + Status-Übersicht | `tests/e2e_agent_details.py` | **PASS** |
| Kandidat 17 → 9 Expander; check_visa **🔴** / check_gdpr **🟢** / verify **🟡**; Visa-Volltext „Visum-Status: ERFORDERLICH"; Queue sichtbar | dasselbe | **PASS** |
| C4-Regressionslauf | `tests/e2e_sprachtest_feedback.py` | **PASS** |
| P2 | `py_compile` + `test_drawer_click.py` | OK / 4/4 |

### Offene Punkte (aus C5 mitgenommen — Schritt 2/Backlog)

- ✅ **Randbefund A** — Streamlit app.py:1974 Slug-Bug (dauerhaft ⚪ in Streamlit-Agent-Details) — Referenz-App. **Geprüft 23.09.2026 (F4): Streamlit-only; NiceGUI unbetroffen — `tests/e2e_agent_details.py` PASS (Badges 🔴/🟢/🟡 via eigenem Parser employer.py:926-939), kein NiceGUI-Fehler.**
- ✅ **Randbefund B** — Streamlit app.py:2012-2019 Expander-Precedence („NICHT ERFORDERLICH" → 🔴 statt 🟢). **Geprüft 23.09.2026 (F4): Streamlit-only; NiceGUI C5-E2E beweist korrekte Precedence (Visa 🔴 / GDPR 🟢 / Verify 🟡), kein NiceGUI-Fehler.**
- ✅ **Bewerbung #25** — geprüft, korrekt — kein Fehler (Gatekeeper NEIN, Score 0 Kern = correct).

### Geänderte Dateien (C5)

1. `webui/pages/employer.py` — `_page_agent_details` Spec-Port (Parser + Badge-Grid + Expander)
2. `tests/e2e_agent_details.py` — NEU (view-only)
3. `ergebnisse/agent-details-doku.md` — Status-Zeile
4. `ergebnisse/nicegui-phase-2-rest-portierung.md` + dieser Eintrag — P4

---

## C6: Admin-Tool-Ergebnisse + Downloads (22.09.2026, ABGESCHLOSSEN)

> **Ziel (Paritäts-Inventar C6 / Auflage „12 Downloads"):** Streamlit zeigt auf allen 5 Admin-Tool-Seiten das frisch generierte MD inline + `st.download_button` — NiceGUI hatte nur die Queue-Auslösung, kein Ergebnis, keinen Download.

### Migration-Entscheidungen

| # | Entscheidung | Warum | Quelle |
|---|---|---|---|
| D25 | `tool_result_section(glob, label)` (admin.py): Ergebnis-Karte mit neuestem `ergebnisse/{task}-*.md` — Dateiname, Vorschau-Expander, **Herunterladen**-Button (`ui.download`, Default-Arg-Closure) | Streamlit-Parität: Ergebnis + Download je Tool (app.py:1378/1531/1641/1734/1851); Inhalt = Runner-Artefakt (NiceGUI-Laufzeitmodell), nicht Streamlit-Heuristik-MD | agent-automation.md (Runner schreibt ergebnisse/) |
| D26 | Position: Ergebnis-Karte **nach** `section_header`, **vor** der Queue-Karte; 1 Call-Site je Seite | Early-Returns der Queue-Karten (`if not rows: … return`, z.B. Contact ohne eingeladene Bewerbungen) hätten ein Ergebnis unten übersprungen; Nested-Card im with-Block vermeidbar; Streamlit-Rerun-Ordnung (Aktion→Ergebnis) ist bei persistenter NiceGUI-Seite nicht übertragbar | admin.py:235/291/347/403/462 (Returns) |
| D27 | **KEIN** Port der lokalen Heuristik-Inputs (Länder-Multiselect app.py:1560-1564, Stelle/Unternehmen app.py:1659-1662, testdaten-Datei-Selects) | Streamlit selbst markiert sie als „vereinfacht – in Produktion via LLM" (app.py:1341/1414); echte Ausführung = Agent-Queue (paritaets-matrix-final.md:36 akzeptiert Queue-Seiten als Tool-Parität); tote Inputs wären Embellishment | app.py:1341 + agent-automation.md + matrix:36 |

### Download-12-Mapping (Status nach C6)

#1 ICS ✅ (vor C6) · **#2–6 Admin-Tools ✅ C6** · #7 ps_self_dl ✅ (P2.2) · #8–12 ⏳ C7.

### E2E-Beweise (22.09.2026)

| Test | Skript | Ergebnis |
|---|---|---|
| 5× Ergebnis-Karte + Download-Button + Glob-Dateiname + Vorschau | `tests/e2e_admin_downloads.py` | **PASS** |
| Download-Event | dasselbe | **PASS** (`extract_profile-*.md`) |
| P2 | `py_compile` + `test_drawer_click.py` | OK / 4/4 |

### Geänderte Dateien (C6)

1. `webui/pages/admin.py` — `tool_result_section` + 5 Call-Sites
2. `tests/e2e_admin_downloads.py` — NEU (view-only)
3. `ergebnisse/nicegui-phase-2-rest-portierung.md` + dieser Eintrag — P4

---

## C7: Prescreen/Onboarding/Feedback + Downloads #8–12 (22.09.2026, ABGESCHLOSSEN)

> **Ziel (Paritäts-Inventar C7 / Auflage „12 Downloads" final):** Streamlit Skills 6/7/8 (Pre-Screen Recruiting, Onboarding-Generator, Store Feedback) waren in NiceGUI leere Slot-Stubs; Candidate-Onboarding zeigt die vom Runner freigegebene Checkliste. Letzte 5 Downloads (#8–12) portiert.

### Migration-Entscheidungen

| # | Entscheidung | Warum | Quelle |
|---|---|---|---|
| D28 | **Status-Gate entfällt** in Skills 6/7/8 (Employer + Admin) | Streamlit-Gate war sidebar-gekoppelt und hatte Indent-Bugs: Buttons app.py:2263/2418/2566 rendern **außerhalb** des Gates → Gate schützte nie die Aktion; NiceGUI-Sections sind pfadunabhängig | app.py:2263/2418/2566 (Indent) + D28-Begründung 22.09.2026 |
| D29 | Generator-Inputs = **testdaten** `list_profiles()` (NICHT DB-candidates); Dateinamen `pre-screen-{stem}-{date}.md`, `onboarding-{stem}-{startdatum}.md`, `feedback-{stem}-{date}.md`; Skill-8 `match_id = {stem}-{date}`; export_report `candidate_id` = String-Stem | Streamlit-Parität 1:1 (app.py:124/2351/2505/2641); D29(b): Runner schreibt `onboarding-freigabe-bewerbung-{app_id}.md` (agent-runner.py:1250) — Candidate-Tab globbt **dieses** Muster, Streamlit globbt tote `onboarding-kandidat-*` (app.py:2386 → Streamlit-Gap, Schritt 2) | app.py:82-129/2319-2353/2426-2507/2598-2692 + agent-runner.py:1250 |

### Download-12-Mapping (FINAL 12/12)

#1 ICS ✅ · #2–6 Admin-Tools ✅C6 · #7 ps_self_dl ✅P2.2 · **#8 Einsicht ✅C7 · #9 Pre-Screen ✅C7 · #10 Candidate-Onboarding ✅C7 · #11 Onboarding-Gen ✅C7 · #12 Skill-8 ✅C7**.

> **⚠️ Ist-Korrektur #8 (06.10.2026, MD an Code angeglichen — Lab-Prinzip S3):** „Ansehen" löst **keinen Download** mehr aus, sondern öffnet einen **Dialog mit MD-Vorschau** (`_show_file`, `webui/components.py`, Helfer `prescreen_recruiting_section`; Änderung dokumentiert 30.09.2026 in `ergebnisse/runde4-abschluss.md` S3g). Der Dialog hat **kein Download-Angebot** → Download-Event #8 entfällt (**Design-Entscheidung**, Abdeckungsverlust #8; Code nicht defekt: richtiger Dateiname + Vorschau). Streamlit-Parität `app.py:2250` (`st.download_button "📥 Ansehen"`) bleibt Archiv-Vergleich. E2E `tests/e2e_c7_downloads.py` prüft daher Dialog-Öffnung + Datei + Vorschau.

### E2E-Beweise (22.09.2026)

| Test | Skript | Ergebnis |
|---|---|---|
| #9 Generator + #11 Generator + #12 Skill-8 Downloads (exakte Filenames) | `tests/e2e_c7_downloads.py` | **PASS** (exakte Filenames) |
| #8 Ansehen → Dialog-Öffnung + richtige Datei + Vorschau (kein Download, s. o.) | dasselbe | **PASS** (06.10.2026, ersetzt Download-Assertion) |
| Cat-Map Skill-8: score 30 → `Schwach` (Admin; P9.3 vereinheitlicht, vorher `Nicht passend`), kein Weight-Adjust | dasselbe | **PASS** |
| export_report bei INSERT | dasselbe (Task #126) | **PASS** |
| Employer-Smoke 3 Seiten + Candidate empty_state/Flip/Expansion | dasselbe | **PASS** |
| Restore (app8/hist/gew/fb/tasks + alle neuen Dateien) | dasselbe | **PASS** (identisch Pre) |
| P2 | `py_compile` 5 Dateien + `test_drawer_click.py` | OK / 4/4 |

### Geänderte Dateien (C7)

1. `webui/logic.py` — `read_profile_text` / `save_result` / `list_profiles`
2. `webui/components.py` — `_md_result_card` + 3 Shared-Sections
3. `webui/pages/admin.py` — 3 Slot-Stubs → Sections
4. `webui/pages/employer.py` — 3 Pages + Skill-8 nach Tab4
5. `webui/pages/candidate.py` — `_tab_onboarding` Freigabe-Glob + `ui.warning`→`ui.label`
6. `tests/e2e_c7_downloads.py` — NEU (Write + Restore)
7. `ergebnisse/nicegui-phase-2-rest-portierung.md` + `ergebnisse/entscheidungen.md` + dieser Eintrag — P4

### Klappen-Rollout (23.09.2026, Fix 1 + Fix 3)

1. `webui/pages/employer.py` — `_page_match`: Job-Block → `ui.expansion` + `add_slot("header")` (Parität app.py:3857); `_page_agent_details`: Task-Queue → `ui.expansion(value=False)`; Detaillierte Berichte unverändert (bereits Expansion, employer.py:960)
2. Verifikation: `/tmp/opencode/verify_klappen.py` **18/18 PASS** (P1 Match 11 Klappen, P2 Berichte 9, P3 Task-Queue 1 + Filter) · py_compile OK · HTTP 200 · 1 Runner == pidfile · residue id>146=0
3. Rollback: `/tmp/opencode/rollback/employer.py.bak` (sha256 vorher `e7cb31ee…` → nachher `9ac3fd50…`); Details: entscheidungen.md 2026-09-23 „Klappen/Ausklappen" (Fix 3 = Design-Entscheidung, Fix 1 = Quelle app.py:3857; Doku: nicegui.io/documentation/expansion)

### Schritt 4 – finale Paritäts-Matrix (23.09.2026) ✅ ERLEDIGT

- **Report:** `ergebnisse/paritaets-matrix-final-2026-09-23.md` (212 Z.) — 86 Zeilen = Schritt-0 (7) + C1–C7 + D1–D29 + #1–#9 + Bestands-Matrix A–D (34); Zähler final **67 portiert / 12 D-entschieden / 0 offen / 7 Sonderfälle** (O1-Nachzählung 23.09. + O2/O3: C1 `send_rejection`-Guard `agent-runner.py:377-386` behoben, C4 Option „Vorgemerkt" `employer.py:1252` behoben → Offene-Liste leer; Zählweg + Sonderfälle-Liste im Report; alte Zahlen 72/12/2 unbelegt, O1-Zwischenstand 65/12/2/7). Klassen a/b/c = abgeleitet (Schritt-0-Befund C: Schema nicht im Repo).
- **Quellen:** paritaets-matrix-final.md (20.09.) + C1–C7/D1–D29/#1–#9 (diese Datei) + nicegui-phase-2-rest-portierung.md (E2E) + entscheidungen.md Schritt-2/F1-F3.
- **Beweis-Appendix:** entscheidungen.md „2026-09-23: Schritt 4 – finale Paritäts-Matrix + Nachzügler A/B/C" (Schritt-0-Befundtabelle A/B/C + C2-Abschlusschecks py_compile 11/11, drawer 4/4, HTTP 200×4, Runner==pidfile, ID=1, failed=[20,21,23,39,105], F3=0). Log-Beweissicherung: knowledge/system/agent-automation.md §4 Zeile „Log-Beweissicherung".
