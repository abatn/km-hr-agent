# Rolle: KM-HR-Agent (Recruiting-Match) – v4.5

> **Version:** 4.5 (v4.3 Mutual-Marketplace → v4.5 Zwei-Ebenen-Modell: Agent-Ebene vs. Portal-Ebene + Matching/Feedback Phase 2–4.6, siehe unten)  
> **Stand:** September 2026

## Funktionierende MCP-Connectoren & Tools — **49 dokumentiert (instructions.md) / 181 live (Handshake 26.09.2026)** (Censusstand 26.09.2026; §G-Nachzug 26.09.2026 ergänzt anysearch 4 + create_meeting_link 1 → vorher 44; Rest-Differenz 132 = undokumentierte Live-Tools, Voll-Liste `ergebnisse/mcp-connector-audit-2026-09-25.md` §6.3)

### Core Connector ( alle funktionieren)

| Connector | Tool | Typ | Status | Verwendung |
|---|---|---|---|---|
| `hr-benchmark` | `calculate_weighted_score`, `get_score_category`, `get_weight_ranges` | MCP (Python) | ✅ FUNKTIONIERT | ZYTHR-Formel: (score/max) × weight |
| `salary-data` | `calculate_salary_band`, `calculate_salary_position`, `calculate_salary_tolerance` | MCP (Python) | ✅ FUNKTIONIERT | BambooHR: Min/Mid/Max = 25th/50th/75th |
| `prescreen-config` | `get_optimal_duration`, `get_screening_questions`, `get_screening_structure` | MCP (Python) | ✅ FUNKTIONIERT | CareerPlug: 15-30 Minuten |
| `language-test` | `generate_test`, `score_answer`, `get_cefr_level` | MCP (Python) | ✅ FUNKTIONIERT | CEFR-Niveautests: 732 Fragen (DE 120, EN 522, FR 90) + LLM-generierte Zusatzfragen (hybrid), LLM-Bewertung via NVIDIA API |
| `filesystem` | `read_text_file` | MCP (local) | ✅ FUNKTIONIERT | TXT/MD-Dateien lesen |
| `filesystem` | `write_file` | MCP (local) | ✅ FUNKTIONIERT | Ergebnisse speichern |
| `filesystem` | `list_directory` | MCP (local) | ✅ FUNKTIONIERT | Verzeichnisse durchsuchen |
| `filesystem` | `search_files` | MCP (local) | ✅ FUNKTIONIERT | Dateien/Muster suchen (26.09.2026 korrigiert: `glob` existiert in `tools/list` nicht mehr — Phantom, Ist `search_files`) |
| `ansvar-german-law` | `search`, `validate_citation`, `get_provision` | MCP (mcp-remote) | ✅ FUNKTIONIERT | DE-Recht (6.870 Gesetze) |
| `ansvar-french-law` | `search`, `validate_citation`, `get_provision` | MCP (mcp-remote) | ✅ FUNKTIONIERT | FR-Recht (3.958 Gesetze) |
| `ansvar-swiss-law` | `search`, `validate_citation`, `get_provision` | MCP (mcp-remote) | ✅ FUNKTIONIERT | CH-Recht (4.873 Gesetze) |
| `pdf-reader` | `read_pdf_text`, `get_pdf_info`, `analyze_pdf_structure` | MCP (Python) | ✅ FUNKTIONIERT | PDF-Text extrahieren |
| `meeting-tools` | `generate_screening_questions`, `generate_ics_file`, `create_meeting_link` | MCP (Python) | ✅ FUNKTIONIERT | Screening-Fragen + ICS generieren (`create_meeting_link` = LEGACY, wird nicht genutzt; URL seit 27.09.2026 VDO.Ninja statt Jitsi) |
| ~~`jitsi-meeting`~~ | — | — | **ENTFERNT 27.09.2026** | 0 Aufrufe im Code; VDO.Ninja-Migration (Spec `knowledge/system/vdo-ninja-migration.md`) | Account) |
| `email-sender` | `send_email`, `send_interview_invitation`, `send_pre_screen_invitation` | MCP (Python) | ✅ FUNKTIONIERT | E-Mails via SMTP (Server aus `.env-email`; **seit 24.09.2026 Gmail** smtp.gmail.com:587 STARTTLS, davor Yahoo) |
| `playwright` | `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_fill_form`, `browser_find`, `browser_close` | MCP (npx) | ✅ FUNKTIONIERT | Browser-Automation (Chromium), Webseiten laden und auslesen |
| `fetch` | `fetch` | MCP (uvx) | ✅ FUNKTIONIERT | HTTP-Fetch (Web-Inhalte laden) |
| `anysearch` | `search`, `extract`, `batch_search`, `get_sub_domains` | MCP (remote) | ✅ **anonym/schlüsselfrei seit 01.10.2026** (nur `X-Anysearch-Client`; die `Authorization`-Zeile wurde am 01.10.2026 aus `opencode.json` **entfernt**, H9 geschlossen; wirksam nach OpenCode-Neustart) | Websuche (Heimatland-Suche, Kurse) |

### PDF-Extraktion (CLI, nicht MCP)

| Tool | Typ | Status | Verwendung |
|---|---|---|---|
| `resume-parser-ats` | CLI (npm) | ✅ Installiert | PDF → strukturierte Daten |

### HR-Aggregator / Jobboard-API (optional, nicht aktiv)

| Connector | Tool | Typ | Status | Voraussetzung |
|---|---|---|---|---|
| `arbeitsamt` | Jobsuche-API (Bund-Jobboard) | REST (öffentlich) | ⏳ Configuriert (nicht aktiv) | OAuth (öffentliche APIs) |
| `arbeitnow` | Europe/Remote Job Aggregator | REST (öffentlich) | ⏳ Configuriert (nicht aktiv) | Kein Key nötig |

## Nicht verfügbare Connectors

| Tool | Status | Notiz |
|---|---|---|
| `aspose-pdf-foss-mcp` | Nicht installiert | Nicht benötigt (pdf-reader vorhanden) |
| `excel-mcp` | Nicht installiert | Nicht benötigt |
| `email-mcp` / `slack-mcp` | Nicht installiert | Nicht benötigt (E-Mail-Vorlage vorhanden) |
| `arbeitsamt` | Nicht konfiguriert | OAuth nötig (öffentlich) |
| `arbeitnow` | Nicht konfiguriert | REST-API, kein Key nötig |

## Skills (23 Stück – alle aktiv, Stand 24.09.2026)

| Skill | Beschreibung | MCP-Connector | Tool |
|---|---|---|---|
| `extract-profile` | Lebenslauf → Strukturiertes Profil | filesystem + pdf-reader | read_text_file + read_pdf_text |
| `match-candidate` | Profil vs. Stelle → Score (0–100) | filesystem | read_text_file |
| `explain-match` | Score → Detaillierte Begründung | filesystem | read_text_file |
| `check-compliance` | Länderspezifische Prüfung | filesystem + ansvar-*-law | read_text_file + validate_citation |
| `check-gdpr` | DSGVO-Compliance | filesystem | read_text_file |
| `assess-culture-fit` | Kultur-Fit-Bewertung | filesystem | read_text_file |
| `generate-onboarding` | Onboarding-Checkliste | filesystem | write_file |
| `store-feedback` | Feedback in MD-Datei | filesystem | write_file |
| `handle-errors` | Fehler protokollieren + Nutzermeldungen | filesystem | write_file |
| `employer-portal` | Arbeitgeber: Registrierung, Stellen ausschreiben, Kandidaten + Bewerber sehen, Feedback | filesystem + SQLite | read_text_file + write_file |
| `job-application` | Kandidat: Stellenangebote ansehen, bewerben, Bewerbungsstatus verfolgen | filesystem + SQLite | read_text_file + write_file |
| `verify-documents` | Dokumente prüfen: Zeugnisse/Zertifikate (Kandidat) + Visa/Arbeitserlaubnis (HR) – Länder-Routing DE/FR/CH + **Forensik-Pre-Scan (pdf-verify-mcp, seit 16.09.2026)** | pdf-reader + ansvar-german/french/swiss-law + filesystem + **pdf-verify-mcp (npx)** | read_pdf_text + validate_citation + write_file + **evaluate_policy + verify_integrity** |
| `check-visa` | Visum-, Arbeitserlaubnis- und Anerkennungs-Check für internationale Kandidaten (DE/FR/CH) | filesystem + ansvar-german/french/swiss-law | read_text_file + validate_citation + write_file |
| `contact-candidate` | Kontaktiert Kandidaten per E-Mail (Interview-Einladung) | filesystem + email-sender | read_text_file + send_email |
| `pre-screen` | Pre-Screening: Fragen + VDO.Ninja-Raum + ICS | filesystem + meeting-tools | read_text_file + generate_screening_questions + generate_ics_file |
| `candidate-portal` | Kandidaten-Portal: Registrierung, Profil, Lebenslauf, Dokumente, Status | filesystem + SQLite | read_text_file + write_file |
| `export-report` | Match-Ergebnisse als PDF/Excel exportieren | filesystem | write_file |
| `notify-user` | Benachrichtigungen bei Top-Matches (E-Mail) | filesystem + email-sender | read_text_file + send_email |
| `language-course` | Sprachkurs-Integration: DE/EN/FR-Kurse finden + Heimatland-Suche (anysearch), Niveaus-Tests, Fortschritt | filesystem + pdf-reader + language-test + anysearch + ansvar-*-law | read_text_file + read_pdf_text + search + generate_test + score_answer + get_cefr_level |
| `nicegui-migration` | Migration Streamlit→NiceGUI: framework-freie Layer (webui/db.py + logic.py) + webui/-App, Phasen-Doku + Inventar-Pflege | filesystem + SQLite | read_text_file + write_file |
| `mentoring` | Mentoring/Patenschaft (Phase D P10, 24.09.2026): HR-Klick-Vergabe, `{MENTOR}`-Befüllung in Report + Mail #6, Lebenszyklus vorschlagen→aktiv→beendet | filesystem + email-sender | read_text_file + write_file + send_email |
| `housing-search` | Wohnungssuche-Checkliste + freie Quellen im Onboarding-Report (Phase D P6, 24.09.2026): Info-Orchestrierung, kein Scraping | filesystem + fetch + anysearch | read_text_file + write_file + fetch + search |
| `contract-management` | Contract Preflight (Phase D P8, 24.09.2026): Gehalt ≥ Mindestlohn (Link-Katalog), Formfall-Hinweise (§14/§126a/§623), NachwG-15-Punkte-Checkliste, Vertragsskelett; Signatur A–F = User-Wahl | filesystem + ansvar-german-law + fetch | read_text_file + write_file + fetch |

## Entfernte Connectors (aus opencode.json gelöscht)

| Alter Connector | Grund der Entfernung |
|---|---|
| `pdf-connector` (@sylphx/citra) | Citra erwartet Base64, kein direkter Pfad → resume-parser-ats als Alternative |
| `prismhr-mcp` | Nicht installiert, proprietäre API-Zugangsdaten nötig → arbeitsamt/arbeitnow als Alternative |
| `breathehr-mcp` | Nicht installiert, API-Key nötig → arbeitnow als Alternative |
| `swagger-mcp` | Kein HR-Fokus, braucht Swagger-URL → nicht benötigt |
| `citycompliance-mcp` | Nicht in npm/Registry vorhanden |
| `france-legal-mcp` | Nicht in npm/Registry vorhanden |
| `swiss-legal-mcp` | Nicht in npm/Registry vorhanden |
| `fallback-config` | Falsche Quelle (SSRN-ID 4893265 existiert nicht) – entfernt 15.09.2026 |
| `gewicht-cap` | Falsche Quelle (Nature-Artikel = AlphaFold 3, nicht HR) – entfernt 15.09.2026 |

## Entfernte Skills (nicht-funktionierende Connectors)

| Skill | Grund der Entfernung |
|---|---|
| — | (keine, alle 23 Skills aktiv) |

## Jobportal-Prinzip (Zugriffskontrolle)

### Grundprinzip
```
UNREGISTRIERT → NICHTS KANN MACHEN
     ↓
REGISTRIERT → Profil ausfüllen
     ↓
LEBENSLAUF → Matching möglich
     ↓
MATCHING → Ergebnis sehen
```

### Was darf wer? (v4.5 – Zwei-Ebenen-Modell)

| User-Typ | Was kann er tun? |
|---|---|
| **Kein Konto (GAST)** | ❌ NICHTS (nur Login-Bildschirm) |
| **CANDIDATE-Session** | ✅ 📤 Upload (eigener CV) · 6️⃣ Pre-Screen (Selbstpräsentation) · 7️⃣ Onboarding (nur nach Arbeitgeber-Freigabe, read-only) · 👤 Candidate Portal (eigene Daten) · 💼 Stellenangebote (read + write) |
| **EMPLOYER/HR-Session** | ✅ **11 Portal-Seiten** (`PAGE_MAP` in `webui/pages/employer.py`, gemessen 2791–2803 ⓘ09.10.2026): 📊 Dashboard · 🔍 Kandidaten-Suche (Bewerber-Verwaltung + einladen/ablehnen/eingestellt) · 2️⃣ Match-Ergebnis (read-only) · 3️⃣ Compliance-Ergebnis (read-only) · 🔍 Agent-Details · 🗂️ Dokumente (NEU 18.09.2026) · 6️⃣ Pre-Screen (Recruiting-Modus + Kandidaten-Videos) · 7️⃣ Onboarding (erstellen + freigeben) · 8️⃣ Feedback · 💼 Stellenangebote (Bewerber-Status write) · 🏢 Arbeitgeber-Portal |
| **Agent-Ebene (kein UI für Portal-Rollen)** | Skills 0️⃣ Upload-Ingestion · 1️⃣ Extract · 2️⃣ Match-Tool · 3️⃣ Compliance-Tool · 4️⃣ Contact · 5️⃣ Culture Fit – laufen regulär über opencode + MCP-Connectors, für CANDIDATE/EMPLOYER/GAST unsichtbar |
| **ADMIN-Session** | ✅ **12 Seiten (v4.3-Vollansicht + NiceGUI-Dashboard)**: 📊 Dashboard (NEU) + die Agent-Tools 0️⃣–5️⃣ sind **sichtbar und ausführbar** (Betrieb/Kontrolle der Agent-Ebene) + 6️⃣ Pre-Screen (Recruiting) · 7️⃣ Onboarding (HR) · 8️⃣ Feedback · 💼 Stellenangebote (HR-write) · 🏢 Portal. ❌ 👤 Candidate Portal (identitätsgebunden) |
| **Kandidat + Lebenslauf** | ✅ Bewerbung möglich (CV-Pflicht, innerhalb CANDIDATE-Session) |
| **Arbeitgeber + aktive Stelle** | ✅ Bewerber verwalten, freigeben (innerhalb HR-Session) |

**Rollen-Regel (v4.5 – Zwei-Ebenen-Modell):** Eine Session = eine Rolle. Der Arbeitgeber lädt **keine Lebensläufe hoch** und führt **keine Agent-Skills aus** – er sieht **Ergebnisse** (Match/Compliance read-only) und verwaltet Bewerber. Skills 0️⃣–5️⃣ sind Agent-Spezialitäten: „es läuft, aber niemand sieht diese Werkzeuge". Details: `knowledge/system/access-control.md` (v3.1).

### Zugriffskontrolle pro Seite (Zwei-Ebenen-Modell, v4.5)

| Seite | GAST | CANDIDATE | EMPLOYER (HR) | ADMIN | Agent-Ebene |
|---|---|---|---|---|---|
| 📤 Upload (Ingestion) | ❌ | ✅ (nur eigener CV) | ❌ | ✅ | ✅ |
| 1️⃣ Extract Profile | ❌ | ❌ | ❌ | ✅ ausführbar | ✅ |
| 2️⃣ Match-Ergebnis (Sicht) | ❌ | ❌ | ✅ read-only | ✅ | – (Ausgabe) |
| 3️⃣ Compliance-Ergebnis (Sicht) | ❌ | ❌ | ✅ read-only | ✅ | – (Ausgabe) |
| 4️⃣ Contact Candidate | ❌ | ❌ | ❌ | ✅ ausführbar | ✅ (E-Mails agent-generiert) |
| 5️⃣ Assess Culture Fit | ❌ | ❌ | ❌ | ✅ ausführbar | ✅ |
| 6️⃣ Pre-Screen | ❌ | ✅ (Selbstpräsentations-Modus) | ✅ (Recruiting-Modus + Video-Einsicht) | ✅ (Recruiting-Modus) | – |
| 7️⃣ Generate Onboarding | ❌ | ✅ (nur nach Freigabe, read-only) | ✅ (erstellen + freigeben) | ✅ (erstellen + freigeben) | – |
| 8️⃣ Store Feedback | ❌ | ❌ | ✅ (updaten) | ✅ | – |
| 👤 Candidate Portal | ❌ | ✅ (session-gebunden) | ❌ | ❌ | – |
| 💼 Stellenangebote | ❌ | ✅ (read + write: bewerben/zurückziehen) | ✅ (update/write: Bewerber-Status) | ✅ (HR-write) | – |
| 🏢 Arbeitgeber-Portal | ❌ | ❌ | ✅ | ✅ | – |

**Hinweis ADMIN (v3.1):** Die Agent-Tool-Seiten (0️⃣–5️⃣ inkl. 2️⃣/3️⃣-Tool-Varianten) sind ausschließlich in der ADMIN-Session sichtbar und ausführbar; EMPLOYER sieht nur die read-only Ergebnis-Sichten von 2️⃣/3️⃣. Admin-Login: separater geschützter Zugang (Umsetzungsdetail, siehe `knowledge/system/access-control.md` §3.4).

**Umsetzungsstatus:** ✅ **Implementiert (12.09.2026)** – Arbeitgeber-Menü auf 7 Portal-Seiten reduziert, 2 read-only Ergebnis-Sichten (Match/Compliance) neu, **ADMIN-Rolle mit geschütztem Login (admins-Tabelle; Stand 12.09.2026: 11 Seiten, Agent-Tools sichtbar/ausführbar)**. Getestet: 18/18 AppTest-Checks bestanden, Server HTTP 200. Vorheriger Stand: v4.3 (11 Seiten für Arbeitgeber). **Stand 20.09.2026 (NiceGUI, `webui/pages/`, Phase 2): EMPLOYER 11 Seiten (`PAGE_MAP` in `webui/pages/employer.py`, gemessen 2791–2803 ⓘ09.10.2026, inkl. 💼 HR-write-Stellen-View), CANDIDATE 7 Tabs (`_TAB_MAP` `webui/pages/candidate.py`, Stand 02.10.2026, 📊 Dashboard als 1. Tab, Upload/Dokumente in 👤 Mein Profil), ADMIN 12 Seiten (`PAGE_MAP` in `webui/pages/admin.py`).**

### Matching & Feedback (Phase 2–4.6, alle implementiert)

| Phase | Inhalt | Spec |
|---|---|---|
| **2** | Scoring nach Doc-Gewichtung: Synonym-Matching (k8s↔Kubernetes), Gehaltscheck (`max=0` = offen, unbekannt = ❓), 7 Kategorien, Englisch zählt | `knowledge/lifecycle/matching-criteria.md` |
| **3** | Feedback-Integrität: `feedback.match_id` UNIQUE, idempotentes Speichern (gleicher Tag = UPDATE, nächster Tag = neuer Datensatz), Tab-4-Kandidaten-Picker aus dem tatsächlichen Ranking | `knowledge/lifecycle/feedback-schema.md` |
| **4** | Geschlossener Feedback-Loop: jedes NEUE Feedback (beide Trigger: Tab 4 + Skill 8) → `adjust_weights_from_feedback()` (Erfolg → Berufserfahrung +5, Misserfolg → Sprache +10, Cap Baseline+15); Scoring liest ausschließlich `get_current_weights()` (Historie → Normalisierung auf 100); Baseline 30/25/15/10/10/10/0 | `knowledge/lifecycle/matching-criteria.md` |
| **4.5** | DSGVO-6-Monats-Löschung: `dsgvo_cleanup()` beim App-Start (fehlersicher) löscht `applications` + Historie + `agent_tasks` + `candidate_documents` (4 Tabellen, Messung ⓘ08.10.2026) 183 Tage nach Prozessende (finaler Status); aktive Bewerbungen nie | `knowledge/lifecycle/application-status.md`, `knowledge/legal/gdpr-policy.md` |
| **4.6** | Branchen-Score: `score_branche()` vergleicht `employers.branche` (IT/IT-nah/fremd) mit Kandidaten-CV; Job-Kontext trägt `branche` (JOIN in Tab 3 + Feedback-Picker); NULL → bisherige Heuristik als Fallback | `knowledge/lifecycle/matching-criteria.md` |
| **5 (Spec v3)** | **Agent-Automatisierung**: Agent-Queue (`agent_tasks`) + Hybrid-Runner – deterministische Tasks (Mails, ICS, Fragen, VDO.Ninja-Raum) direkt über die Projekt-MCP-Connectors, LLM-Tasks (Extract/Match/Compliance/Culture-Fit + verify_documents + check_visa) via **direkte NVIDIA-API** (Stand 13.09.2026, statt `opencode run` — lieferte nur `step_start` ohne Text; NVIDIA, live getestet); Trigger: CV-Upload + Bewerbung → Agent-Kette automatisch; **Pförtner-Regel: Score ≥ 60 UND COMPLIANT → JA → HR-Mail (dann warten) · sonst NEIN → keine Mail, Ergebnisse bleiben für HR sichtbar**; **Variante A: Agent lädt/lehnt nie selbst ab** – HR-Klick `→ eingeladen` → Einladung (VDO.Ninja, + ICS + Mail), HR-Klick `→ abgelehnt` → Absage-Mail (vom Agenten gesendet); eingestellt → Onboarding-Freigabe. **Spec v6 (✅ IMPLEMENTIERT 12.09.2026):** Bewerbung → zusätzlich `verify_documents` (Zeugnisse/Sprachzeugnisse via pdf-reader + Law-Routing DE/FR/CH, HR-Badge „Dokumente ✅/⚠️", Visum-Bedarfs-INFO an HR) · HR-Klick „📩 Visum-Antrag bestätigen“ → Agent mailt dem Kandidaten die Visum-Schritte (Variante A) · eingestellt → Onboarding-Freigabe-Report `ergebnisse/onboarding-freigabe-bewerbung-{app_id}.md` (inkl. Visum-Abschnitt) · **Onboarding-Mail #6 `send_onboarding_mail` ✅ implementiert 23.09.2026** (NB6 geschlossen, Variante-A-Guard + DRY_RUN Task #149). **Spec v6.2 (✅ IMPLEMENTIERT + LIVE GETESTET 13.09.2026):** Bewerbung → zusätzlich `check_visa` (Visum-Pflicht §18a/b, Blue Card, Anerkennung BQRF; Agent-Ebene, HR-Badge im Portal vorhanden (app.py:2165-2172 + 3700-3708: `st.metric „Visum-Status"` + Report-Expander; NiceGUI: Badge-Parsing `_badge_icon` (`webui/pages/employer.py`), C5 22.09.2026); erster Live-Run: tunesischer IT-Admin → Visum ERFORDERLICH — Bericht `ergebnisse/check_visa-kandidat-7-2026-09-13.md`). **v6.1:** 👤 Candidate Portal → Tab „🗂️ Dokumente" (Zeugnis/Zertifikat/Sprachzeugnis/Pass/Visa mit Typ-Auswahl, `candidate_documents`, kein CV-Overwrite, Kandidaten-Löschung Art. 17, DSGVO-Datei-Löschung frist-basiert) → typed Quelle für verify_documents | `knowledge/system/agent-automation.md` |

> **✅ Konfiguration vollständig (v2, 12.09.2026; LLM-Ausführung aktualisiert 13.09.2026; `jitsi-meeting` entfernt 27.09.2026):** `email-sender` in `opencode.json` ergänzt und per JSON-RPC-Handshake getestet; LLM läuft seit 13.09.2026 über die **direkte NVIDIA-API** (`requests.post` auf integrate.api.nvidia.com — `opencode run` verworfen: nur `step_start`-Events ohne Text, Modell via API selbst korrekt). **Modell: `nvidia/nemotron-3-super-120b-a12b`** (live: Task #50 check_visa done); optional Reasoning: `moonshotai/kimi-k3` (HTTP 200, gleicher Key). (Details: `agent-automation.md` §10).

### Umsetzung in app.py (Streamlit-Ära — ARCHIVIERT 23.09.2026)

> ⚠️ **Hinweis ⓘ08.10.2026:** Streamlit `app.py` ist seit **23.09.2026 abgeschaltet** (Streamlit-Retirement; `start.sh` verweigert den Start). Die **laufende UI ist NiceGUI** (`webui/`, Start via `./start-webui.sh` bzw. `python3 -m webui.main`). Der Code unten ist historische Referenz des Streamlit-Login-Schutzes (Parität), nicht der laufenden UI.

```python
# Login-Schutz (Session State)
if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False

# Login-Bildschirm
if not check_login():
    # Login + Registrierung anzeigen
    st.stop()  # ← App stoppt für unregistrierte User

# Eingeloggt: Alle Skills anzeigen
st.title("🤖 KM-HR-Agent – Prototyp")
st.caption(f"Eingeloggt als: {st.session_state.user_name}")

# Logout-Button
if st.sidebar.button("🚪 Abmelden"):
    logout_user()
    st.rerun()
```

---

## Profil-Check (Skills 2-8)

**Regel:** Matching (Skill 2) und alle darauf aufbauenden Skills (3-8) nur wenn Kandidat `lebenslauf_hochgeladen` oder besser hat.

```sql
SELECT status FROM candidates WHERE id = ?;
-- Erlaubt: lebenslauf_hochgeladen, profil_geprueft, match_berechnet, eingeladen
-- Verboten: registriert, profil_vollstaendig
```

**Fehlermeldung wenn nicht erfüllt:**
"❌ Kandidat muss Lebenslauf hochladen bevor Matching möglich ist. Aktueller Status: [status]"

**Betroffene Skills:** 2 (Match), 3 (Compliance), 4 (Contact), 5 (Culture Fit), 6 (Pre-Screen), 7 (Onboarding), 8 (Feedback)

---

## Workflow (MCP-konform)

### Standard-Workflow (ohne HR-Integration)

1. **Lebenslauf lesen** → `filesystem` → `read_text_file` (TXT/MD)
2. **PDF parsen (falls PDF)** → `pdf-reader` → `read_pdf_text` (Python MCP)
3. **Profil extrahieren** → `extract-profile` Skill (MCP-konform)
4. **Compliance prüfen** → `check-compliance` Skill (`read_text_file` + ansvar-*-law)
5. **DSGVO prüfen** → `check-gdpr` Skill (`read_text_file` + knowledge/)
6. **Kultur-Fit bewerten** → `assess-culture-fit` Skill (`read_text_file` + Logik)
7. **Match berechnen** → `match-candidate` Skill (`read_text_file` + LLM)
8. **Pre-Screening** → `meeting-tools` → `generate_screening_questions` (Python MCP)
9. **Screening-Fragen** → `meeting-tools` → `generate_screening_questions`
10. **Onboarding generieren** → `generate-onboarding` Skill (`write_file`)
11. **Feedback speichern** → `store-feedback` Skill (`write_file`)
12. **Ergebnis speichern** → `write_file` in ergebnisse/

### Optional: Mit öffentlichen Job-APIs

1. **Job-API auswählen** → arbeitnow (kein Key) oder arbeitsamt (OAuth)
2. **API-Aufruf** → HTTP GET (REST)
3. **Stellen abrufen** → Jobs aus dem API-Feed
4. **Daten speichern** → write_file → knowledge/jobs/
5. **Profil erstellen** → extract-profile (aus Lebenslauf)
6. **Matching** → match-candidate (Profil vs. Stelle)
7. **Ergebnis speichern** → write_file → ergebnisse/

### Automatisiert: Agent-Queue + Hybrid-Runner (Spec v3, ✅ IMPLEMENTIERT 12.09.2026, 8/8 E2E-Checks – Details: `knowledge/system/agent-automation.md` §11–12)

1. **Event im Portal** → die laufende App (NiceGUI `webui/`, bis 23.09.2026 Streamlit `app.py`) schreibt Task in `agent_tasks` (CV-Upload, Bewerbung, JA/NEIN-Entscheid, Einstellung)
2. **Runner** (`scripts/agent-runner.py`) pickt pending Tasks (60-s-Loop, PID-File, max. 3 Versuche)
3. **Ausführung (Hybrid v2):**
   - **MCP-direct (deterministisch, kein LLM):** Einladung (VDO.Ninja-Raum `https://vdo.ninja/?director=prescreening{code}` – seit 27.09.2026, KEIN Google Meet, KEIN Jitsi, + Fragen + ICS + Mail), Eingangs-/Absage-/HR-Mails via `email-sender`, ICS via `meeting-tools`
   - **LLM-Tasks via direkte NVIDIA-API (Stand 13.09.2026, statt `opencode run`):** Extract, Match, Compliance, Culture-Fit + **verify_documents (v6)** + **check_visa (v6.2, ✅ live getestet 13.09.2026)** – `requests.post` auf integrate.api.nvidia.com; opencode lieferte nur `step_start` ohne Text
4. **Ergebnisse** → ergebnisse/*.md + DB-Status; E-Mails an Kandidat/HR gemäß E-Mail-Matrix (`agent-automation.md` §8)
5. **Voraussetzung:** email-sender ✅ in opencode.json (handshake-getestet; `jitsi-meeting` 27.09.2026 entfernt — Raum-URL = VDO.Ninja); LLM ✅ live getestet (NVIDIA NIM: nemotron-120b via direkte API; kimi-k3 optional, HTTP 200)


## Speicherorte

| Inhalt | Pfad |
|---|---|
| Testdaten | `testdaten/` |
| Knowledge | `knowledge/` |
| Ergebnisse | `ergebnisse/` |
| Feedback | SQLite `feedback`-Tabelle in `data/feedback.db` (**Datei `data/feedback.md` existiert nicht** — frühere Angabe falsch; Claude-Altlog unter `ergebnisse/feedback-log.md`) |
| SQLite (Kandidaten, Arbeitgeber, Stellen, **Bewerbungen**, Feedback) | `data/feedback.db` |
| Error-Log | `logs/agent-errors.log` |
