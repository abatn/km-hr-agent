# Zugriffskontrolle (Access Control) – Rollenmodell v3.1 (Zwei-Ebenen-Modell + ADMIN)

> **Stand:** September 2026 (v3.1 – Agent-Ebene vs. Portal-Ebene + ADMIN-Rolle, **implementiert in app.py und getestet: 18/18 AppTest-Checks bestanden**)
> **Vorgänger:** v2 (Mutual Marketplace, implementiert) – durch Nutzer-Feedback vom 12.09.2026 teilweise verworfen: Der Arbeitgeber hat mit Skills 0️⃣–5️⃣ NICHTS zu tun. Diese sind Agent-Spezialitäten.
> **Diese Datei ist die Source of Truth für Zugriffsfragen.**
> **Vorgabe des Nutzers (12.09.2026):** Ein Arbeitgeber lädt keine Lebensläufe hoch und führt keine Agent-Skills aus. Er sieht ERGEBNISSE und verwaltet Bewerber. Skills 1️⃣–5️⃣ laufen auf der Agent-Ebene – für Portal-Rollen gilt „es läuft, aber niemand sieht diese Werkzeuge".
> **Vorgabe des Nutzers (12.09.2026, v3.1):** Für den **ADMIN** muss die Agent-Ebene **sichtbar** sein – der Betreiber sieht und betreibt die Tools im UI.

---

## 1. Rollen und Ebenen

### 1.1 Rollen (Sessions)

| Rolle | Session-State | Wer |
|---|---|---|
| **CANDIDATE** | `user_logged_in = True`, `user_cand_id` | Jobsuchende/r |
| **EMPLOYER (HR)** | `employer_logged_in = True`, `employer_id` | Arbeitgeber / HR / Recruiting |
| **GAST** | beide `False` | nur Login-Bildschirm |
| **ADMIN** | `admin_logged_in = True` | Betreiber/Administrator – einzige UI-Rolle mit Zugang zur Agent-Ebene (NEU v3.1) |

**Grundregel:** Eine Session = eine Rolle.

### 1.2 Zwei Ebenen (NEU in v3)

| Ebene | Was | Wer nutzt es | Sichtbar im Portal? |
|---|---|---|---|
| **Agent-Ebene** | Skills 0️⃣ Upload (Ingestion), 1️⃣ Extract Profile, 2️⃣ Match Candidate, 3️⃣ Check Compliance, 4️⃣ Contact Candidate, 5️⃣ Assess Culture Fit | Regulär: **KM-HR-Agent** (opencode + MCP-Connectors: pdf-reader, filesystem, ansvar-Law, email-sender, meeting-tools). Manueller Betrieb/Tests: **ADMIN-Session** | ❌ für CANDIDATE/EMPLOYER/GAST – ✅ **nur in der ADMIN-Session sichtbar und ausführbar** (NEU v3.1) |
| **Portal-Ebene** | Ergebnis-Sichten + Interaktions-Seiten (siehe Matrix §2) | CANDIDATE / EMPLOYER (HR) | ✅ Die einzige Sichtbarkeit im Web-UI |

Konsequenz: Die Agent-Ausgaben (`ergebnisse/*.md`, DB-Scores, E-Mail-Entwürfe) sind das Produkt der Agent-Ebene. Das Portal zeigt **Ergebnisse und Zustände** – niemals die Werkzeuge selbst.

---

## 2. Portal-Ebene: Seiten-Sichtbarkeit pro Rolle

### 2.1 EMPLOYER (HR) – 14 Seiten (NiceGUI, Stand 15.10.2026: Sidebar 4 Punkte, Rest unter „Mehr“; vorher 12 seit 13.10.2026: Firmenprofil-Split; vorher 11 seit 20.09.2026 Phase 2; Phase 1: 10, vorher 9)

> **NiceGUI-Umsetzung** = `webui/pages/employer.py` (Codemarke `PAGE_MAP`, gemessen 10.10.2026) (PAGE_MAP, 14 Einträge seit 15.10.2026, vorher 12 seit 13.10.2026; Zeilenstand 28.09.2026 — war 1492-1503): 📊 Dashboard · 🏢 Firmenprofil (**eigene Seite seit 13.10.2026**, Design-Entscheidung) · 🏢 Stelle ausschreiben (`portal`, **NEU 20.09.2026, P1.2**: Stellen ausschreiben/pausieren/besetzen) · 💼 **Stellenangebote (HR-write, 20.09.2026: Bewerber über alle eigenen Stellen + Archiv)** · 🔍 Kandidaten-Suche (Liste + Suche, **ohne Schreibaktion**; Zeilenauswahl springt auf 📄 Match — Codemarke `_page_kandidaten`, gemessen 15.10.2026) · 📄 Match (Status-Dialoge `do_invite` / `do_reject` / `do_hire`, Codemarke `_page_match`) · ✅ Compliance · 🔎 Agent-Details (17.09.2026) · 🗂️ Dokumente (18.09.2026) · 📞 Pre-Screen · 📋 Onboarding · 💬 Feedback (voll: Formular + Phase-4-Loop, GAP-2 20.09.2026).

| # | Seite | Modus | Regel |
|---|---|---|---|
| 1 | **📊 Dashboard** | Übersicht | Statistiken + Agent-Task-Status (NEU, NiceGUI). |
| 2 | **🔍 Kandidaten-Suche** | 🔒 Lesen, keine Schreibaktion | Liste aus `_list_candidates` (Bewerber + passive Matches; Pseudonym „Kandidat #N“ bis Status `eingeladen`). Die Zeilenauswahl ruft `ui.navigate.to` auf `/employer/match?kandidat=<id>` (Codemarke `_page_kandidaten`). Im Funktionskörper von `_page_kandidaten` gibt es kein `UPDATE`, kein `INSERT` und kein `queue_agent_task` (gemessen 15.10.2026). Spec: `knowledge/portal/employer-board.md`. |
| 3 | **📄 Match-Ergebnis** | ✏️ Lesen + Status-Aktionen | Ergebnis-Sicht des Agent-Matchings (Skill 2) für den gewählten Kandidaten: Score-Kategorien, Begründung, gespeicherte Dateien in `ergebnisse/`. Status-Aktionen über Dialoge: `do_invite` (→ `eingeladen`), `do_reject` (→ `abgelehnt`), `do_hire` (→ `eingestellt`), jeweils mit Guard `_legal` gegen `ALLOWED_TRANSITIONS` (Codemarke `_page_match`, gemessen 15.10.2026). Zusätzlich Visum-Bestätigung (`send_visa`). **Kein Ausführen von Matching, keine Dateiauswahl.** |
| — | **📧 Einladungen (geplant, Iteration „Einladungen", Entscheidung 16.10.2026 — noch nicht umgesetzt)** | ✏️ Lesen + Status-Aktionen (dritte Aufrufstelle) | Geplante Seite `/employer/einladen`: oben `eingegangen` (nur „Als angesehen markieren") und `angesehen` (Termin-Defaults in der Karte + „Einladen"), unten Eingeladene mit 📹-Artefakt-Karte; Guard ausschließlich über `ALLOWED_TRANSITIONS`, identische Mail-/Task-Logik wie `do_invite`/`make_transition`. Pseudonym bis `eingeladen` (DSGVO wie Match-Seite). |
| 4 | **✅ Compliance-Ergebnis** | 🔒 Read-only | Ergebnis-Sicht der Compliance-Prüfung (Skill 3) zum Matching-Kandidaten (DE/FR/CH + DSGVO, agent-generiert). **Keine Prüfung auslösbar.** |
| 5 | **🔎 Agent-Details** | 🔒 Read-only | ALLE 9 Agent-Ergebnisse als Badge-Zeile + Expander (NEU 17.09.2026). |
| 6 | **🗂️ Dokumente** | 🔒 Read-only | Zeugnisse/Zertifikate/Visa-Dokumente des eingeladenen Kandidaten (NEU 18.09.2026). |
| 7 | **📞 Pre-Screen** | 🧰 Recruiting-Modus | Screening für Matching-Kandidaten: Fragen + VDO.Ninja + ICS + Einsicht der Selbstpräsentations-Videos (**ohne Status-Gate** — zur Bewertung vor der Übernahme, Nutzer-Entscheidung 28.09.2026, Design-Entscheidung). |
| 8 | **📋 Onboarding** | 🧰 HR-Modus | Checkliste erstellen und für den eingestellten Kandidaten freigeben. |
| 9 | **💬 Feedback** | ✏️ Write | Feedback speichern (Ranking-Picker, Phase 3/4: closed Loop). |

**KEIN Zugang für EMPLOYER:** 📤 Upload, 1️⃣ Extract, das ausführende 2️⃣-Match-Tool, das ausführende 3️⃣-Compliance-Tool, 4️⃣ Contact Candidate, 5️⃣ Culture Fit, 👤 Candidate Portal.

### 2.2 CANDIDATE – 7 Seiten/Tabs (NiceGUI, Stand 02.10.2026: 📊 Dashboard als 1. Tab, Upload/Dokumente in 👤 Mein Profil integriert; Phase 2 20.09.2026: 8; v2: 5, Phase 1: 7)

> **NiceGUI-Umsetzung** = `_TAB_MAP` (`webui/pages/candidate.py`, Codemarke, Stand 02.10.2026) (7 Tabs, gerendert via shell()): 📊 **Dashboard (NEU, 1. Tab)** · 👤 Mein Profil (**enthält seit 02.10.2026 Lebenslauf-Upload + Dokumente als aufklappbare Kästen — die früheren Sidebar-Tabs „Upload"/„Dokumente" entfallen**) · 💼 Stellen · 📨 Bewerbungen · 🗣️ Sprachtest (**P1.1 portiert 20.09.2026**: voller Flow generate_test → Scoring → CEFR via MCP → DB) · 📹 Pre-Screen (**P2.2 portiert 20.09.2026**: eigener VDO.Ninja-Raum seit 27.09.2026 ⓘ08.10.2026 (vorher Jitsi-Raum), Screening-Fragen, MD-Download) · 📋 Onboarding.

> **Entscheidung 01.10.2026, Design-/Nutzerentscheidung — keine externe Quelle:** Der Kandidat landet nach dem Login im **📊 Dashboard** (erster Tab), nicht mehr im 📤 Upload. **02.10.2026:** Upload und Dokumente sind aus der Sidebar entfernt und als aufklappbare Kästen in **👤 Mein Profil** integriert — Tab-Count 9 → **7**.

| # | Seite | Modus | Regel |
|---|---|---|---|
| 1 | 👤 Mein Profil (📤 Lebenslauf-Upload + 🗂️ Dokumente) | eigener CV + Dokumente | Lebenslauf speichert in `candidates.lebenslauf_*` + Statuswechsel; Dokumente (Zeugnis/Zertifikat/Sprachzeugnis/Pass/Visa) mit Art.17-Löschung — **seit 02.10.2026 als aufklappbare Kästen im Profil, keine eigenen Sidebar-Tabs mehr**. |
| 2 | 6️⃣ Pre-Screen | Selbstpräsentation | Eigene Fragen + eigener VDO.Ninja-Raum; Video landet im eigenen Profil (HR sieht es im Recruiting-Modus **ohne Status-Gate — zur Bewertung vor der Übernahme** `eingeladen`, Nutzer-Entscheidung 28.09.2026, Design-Entscheidung; Kontakt-Daten weiterhin erst ab `eingeladen`). |
| 3 | 7️⃣ Generate Onboarding | read-only | Nur nach Arbeitgeber-Freigabe (`eingestellt`): eigene Checkliste. |
| 4 | 👤 Candidate Portal | session-gebunden | Eigene Daten, kein Dropdown. Enthält die Dokumente-Funktion (v6.1, seit 20.09.2026; **seit 02.10.2026 als aufklappbarer Kasten in 👤 Mein Profil, kein eigener Sidebar-Tab mehr**): Zeugnis/Zertifikat/Sprachzeugnis/Pass/Visa-Upload mit Typ-Auswahl, session-gebunden, kein Profil-Overwrite; Kandidat-Löschung = Art. 17 Selbstservice. Seitenzahl jetzt 7 (`_TAB_MAP`, `webui/pages/candidate.py`, Stand 02.10.2026). |
| 5 | 💼 Stellenangebote | read + write | Ansehen, bewerben, zurückziehen, Status verfolgen. |

### 2.3 GAST

Nur Login-Bildschirm (5 Tabs: Login, Registrieren, Arbeitgeber-Login, Arbeitgeber-Registrieren, Admin).

### 2.4 ADMIN – 12 Seiten (v3.1 + NiceGUI-Dashboard, Stand 20.09.2026)

> **NiceGUI-Umsetzung** = `webui/pages/admin.py` (Codemarke `PAGE_MAP`, gemessen 10.10.2026) (PAGE_MAP, 12 Einträge inkl. 📊 Dashboard).

| # | Seite | Modus | Regel |
|---|---|---|---|
| 1 | 📊 Dashboard | Übersicht | Statistiken + Agent-Task-Queue (NEU, NiceGUI). |
| 2 | 📤 Upload | Tool (Ingestion) | Beliebige Lebensläufe/Stellenprofile – Agent-Workflow-Betrieb |
| 3–7 | 1️⃣ Extract · 2️⃣ Match-Tool · 3️⃣ Compliance-Tool · 4️⃣ Contact · 5️⃣ Culture Fit | Tool (ausführbar) | Agent-Ebene-Werkzeuge im UI sichtbar und manuell ausführbar (Betrieb, Tests, Kontrolle) |
| 8–10 | 6️⃣ Pre-Screen (Recruiting) · 7️⃣ Onboarding (HR) · 8️⃣ Feedback | wie EMPLOYER | Vollzugriff auf die Portal-Funktionen |
| 11–12 | 💼 Stellenangebote (HR-write) · 🏢 Arbeitgeber-Portal | wie EMPLOYER | In NiceGUI als PAGE_MAP-Einträge „stellen“/„portal“ vorhanden. |

**ADMIN-Zugang zum 👤 Candidate Portal (Ist-Code, Design-Entscheidung ⓘ09.10.2026):** Der Code lässt die ADMIN-Rolle **durch** — `webui/pages/candidate.py` (gemessen 10.10.2026) (`if role != "candidate" and role != "admin":`) und `webui/main.py` (gemessen 10.10.2026) (`role == page_role or (role == "admin" and page_role in ("candidate", "employer"))`). Die frühere Regel „kein Zugang für ADMIN" ist damit **durch den Ist-Code überholt** (Abweichung vom ursprünglichen Rollenmodell bewusst als Ist dokumentiert = Design-Entscheidung).

### 2.5 Gesamt-Matrix

| Seite | GAST | CANDIDATE | EMPLOYER (HR) | ADMIN | Agent-Ebene |
|---|---|---|---|---|---|
| 📤 Upload (Ingestion) | ❌ | ✅ nur eigener CV | ❌ | ✅ | ✅ (Ingestion) |
| 1️⃣ Extract Profile | ❌ | ❌ | ❌ | ✅ ausführbar | ✅ |
| 2️⃣ Match Candidate (Tool) | ❌ | ❌ | ❌ | ✅ ausführbar | ✅ |
| 2️⃣ Match-Ergebnis (Sicht + Status-Dialoge) | ❌ | ❌ | ✅ Lesen + Einladen/Ablehnen/Einstellen | ✅ | – (Ausgabe) |
| 3️⃣ Check Compliance (Tool) | ❌ | ❌ | ❌ | ✅ ausführbar | ✅ |
| 3️⃣ Compliance-Ergebnis (Sicht) | ❌ | ❌ | ✅ read-only | ✅ | – (Ausgabe) |
| 4️⃣ Contact Candidate | ❌ | ❌ | ❌ | ✅ ausführbar | ✅ (E-Mails agent-generiert) |
| 5️⃣ Assess Culture Fit | ❌ | ❌ | ❌ | ✅ ausführbar | ✅ |
| 6️⃣ Pre-Screen | ❌ | ✅ Selbstmodus | ✅ Recruiting-Modus | ✅ Recruiting-Modus | – |
| 7️⃣ Generate Onboarding | ❌ | ✅ nach Freigabe | ✅ erstellen + freigeben | ✅ erstellen + freigeben | – |
| 8️⃣ Store Feedback | ❌ | ❌ | ✅ | ✅ | – |
| 👤 Candidate Portal | ❌ | ✅ | ❌ | ✅ *(Ist-Code: `webui/pages/candidate.py` (gemessen 10.10.2026) + `webui/main.py` (gemessen 10.10.2026), ⓘ09.10.2026, Design-Entscheidung)* | – |
| 💼 Stellenangebote | ❌ | ✅ read + write | ✅ HR-write | ✅ HR-write | – |
| 🏢 Arbeitgeber-Portal | ❌ | ❌ | ✅ | ✅ | – |

---

## 3. Detailregeln

### 3.1 EMPLOYER (HR)-Rolle (NEU in v3)

| Bereich | Regel |
|---|---|
| Sidebar | 4 Punkte seit 15.10.2026 (Dashboard, Stellenangebote, Hiring-Board, Mehr; Rest unter „Mehr“, `employer-board.md` §6). Vorher: genau 12 Seiten seit 13.10.2026 (vorher 11; +Firmenprofil, Portal-Split). Früher: 11 Seiten (PAGE_MAP `webui/pages/employer.py` (Codemarke `PAGE_MAP`, gemessen 10.10.2026), Stand 28.09.2026; Korrektur: war „Genau 9 Seiten", widersprach §2.1 — 📊 Dashboard und 🔍 Kandidaten-Suche fehlten): 📊 Dashboard · 🔍 Kandidaten-Suche · 2️⃣ Match-Ergebnis · 3️⃣ Compliance-Ergebnis · 🔍 Agent-Details · 🗂️ Dokumente (NEU 18.09.2026) · 6️⃣ Pre-Screen · 7️⃣ Onboarding · 8️⃣ Feedback · 💼 Stellenangebote · 🏢 Portal. **Kein 📤 Upload, kein 1️⃣ Extract, keine Tool-Seiten 4️⃣/5️⃣.** |
| Kandidat-Selector (HR) | HR wählt den Matching-Kandidaten für die Ergebnis-Sichten und Skills 6/7/8. Selector nur auf diesen Seiten, nur in HR-Sessions, Population: Status ≥ `lebenslauf_hochgeladen`. |
| 2️⃣ Match-Ergebnis | Zeigt den agent-generierten Match-Bericht (Kategorien-Scores, Begründung) des gewählten Kandidaten. Quelle: `ergebnisse/` + DB. Kein Rerun, keine Dateiauswahl. Status-Wechsel nur über die Dialoge `do_invite` / `do_reject` / `do_hire` (Codemarke `_page_match`, gemessen 15.10.2026). |
| 3️⃣ Compliance-Ergebnis | Read-only: agent-generierter Compliance-Bericht zum gewählten Kandidaten. Kein Auslösen von Prüfungen. |
| 4️⃣ E-Mails (Contact) | Bleiben vollständig agent-generiert (`ergebnisse/email-*.md`). **Kein Einladungs-/Mail-Button auf dieser E-Mails-Seite** (Seitenkontext!) – Statuswechsel laufen über zwei Pfade: (a) die Dialoge `do_invite` / `do_reject` / `do_hire` auf 📄 Match (Codemarke `_page_match`) und (b) die Status-Buttons `make_transition` auf 💼 Stellenangebote (Codemarke `_page_stellen`; gemessen 15.10.2026, in der Sidebar). 🔍 Kandidaten-Suche und das Hiring-Board (Codemarke `_page_board`) schreiben keinen Status. Der Agent kontaktiert. (Präzisiert 28.09.2026, vorher wortwörtlich „Kein Einladungs-Button im UI" — kollidierte mit dem dokumentierten `_page_match`-Dialog, `knowledge/system/agent-automation.md`.) |
| 6️⃣ Pre-Screen (Recruiting) | Wie v2: Fragen + VDO.Ninja + ICS + Video-Einsicht. |
| 7️⃣ Onboarding (HR) | Wie v2: erstellen + „Onboarding freigeben". |
| 💼 Stellenangebote | Wie v2 (aktive Bewerber + Archiv). |

### 3.2 CANDIDATE-Rolle (unverändert gegenüber v2)

| Bereich | Regel |
|---|---|
| 📤 Upload | Nur eigener Lebenslauf → `candidates.lebenslauf_*` + Status `lebenslauf_hochgeladen`. |
| 👤 Candidate Portal | Session-gebunden auf `user_cand_id`, kein Dropdown, Registrieren-Tab = Hinweis. |
| 💼 Stellenangebote | Ansehen, bewerben (CV-Pflicht), zurückziehen, Status verfolgen. |
| 6️⃣ Pre-Screen | Selbstpräsentations-Modus (eigene Fragen, eigener VDO.Ninja-Raum). |
| 7️⃣ Onboarding | Nur nach Freigabe, read-only. |

### 3.3 Agent-Ebene (NEU in v3)

| Bereich | Regel |
|---|---|
| Skills 0️⃣–5️⃣ im Code | Die Skill-Blöcke bleiben in `app.py` vorhanden (Agent/Automatisierung nutzt dieselbe Logik), werden aber über die Seitenlisten für **jede UI-Session** unsichtbar. Defense-in-Depth: direkte Navigation auf eine nicht freigegebene Seite ist blockiert. |
| Upload als Ingestion | Datei-Upload ist Ingestion für den Agent-Workflow (Kandidaten-CV über das Candidate-Portal, Stellenprofile/Stellendaten über den Agent). Die globale Upload-Seite ist im UI candidate-only (eigener CV). |
| Trigger | Agent-Ausführung erfolgt regulär über opencode + MCP-Connectors (siehe `instructions.md`), nicht über das Web-UI – **einzige UI-Ausnahme: ADMIN-Betrieb (§3.4)** |

### 3.4 ADMIN-Rolle (NEU v3.1)

| Bereich | Regel |
|---|---|
| Admin-Login | Separater, geschützter Zugang (Umsetzungsdetail im Plan, z. B. eigener Login-Tab „🛡️ Admin"). Eine ADMIN-Session ist exklusiv – keine parallele Kandidaten-/Arbeitgeber-Identität. |
| Zweck | Betrieb und Kontrolle der Agent-Ebene im UI: Ingestion, Extract/Match/Compliance/Contact/Culture-Fit manuell ausführen, Ergebnisse prüfen. Der reguläre Ablauf bleibt agent-gesteuert. |
| Sichtbarkeit | ADMIN sieht die Vollansicht (12 Seiten, `webui/pages/admin.py` (gemessen 10.10.2026)) – die v4.3-Seiten + NiceGUI-Dashboard. |
| Abgrenzung | 👤 Candidate Portal **im Ist-Code zugänglich** (nicht ausgeschlossen): Gate `webui/pages/candidate.py` (gemessen 10.10.2026) (`role != "candidate" and role != "admin"`) + `webui/main.py` (gemessen 10.10.2026) erlauben `admin` für `page_role="candidate"` (ⓘ09.10.2026; Abweichung vom ursprünglichen „ausgeschlossen" = **Design-Entscheidung**). Der ADMIN ist kein Arbeitgeber-Account: keine `employers`-Zeile, kein `employer_id`-Kontext. |

### 3.5 Profil-Check bleibt

Der bestehende CV-Status-Check (Skills 6/7/8 + Ergebnis-Sichten nur mit Status ≥ `lebenslauf_hochgeladen`) bleibt unverändert – Datenschutz- und Datenqualitätsregel.

---

## 4. Implementierungsplan (app.py – ✅ IMPLEMENTIERT, 12.09.2026)

| # | Änderung | Ort | Verhalten |
|---|---|---|---|
| 1 | `_seiten_fuer_rolle("employer")` → 9 Seiten: `["2️⃣ Match-Ergebnis", "3️⃣ Compliance-Ergebnis", "🔍 Agent-Details", "🗂️ Dokumente", "6️⃣ Pre-Screen", "7️⃣ Generate Onboarding", "8️⃣ Store Feedback", "💼 Stellenangebote", "🏢 Arbeitgeber-Portal"]` | Sidebar (`app.py` (Codemarke `def _seiten_fuer_rolle`, gemessen 10.10.2026), `_seiten_fuer_rolle`) | Employer-Menü ohne Upload/Extract/Tools 4–5 |
| 2 | Zwei neue Read-only-Seiten | Skill-Blöcke | „2️⃣ Match-Ergebnis" / „3️⃣ Compliance-Ergebnis": anzeigen agent-generierte Berichte zum gewählten Kandidaten (Datei in `ergebnisse/` via Score-Kandidaten-Mapping oder zuletzt erzeugter Bericht), **ohne Button/Selector zum Ausführen** |
| 3 | Candidate-Liste | Sidebar | 7 Tabs (NiceGUI, `_TAB_MAP` `webui/pages/candidate.py`, Stand 02.10.2026) |
| 4 | Kandidat-Selector-Navigation | Sidebar | Selector erscheint auf: Match-Ergebnis, Compliance-Ergebnis, 6/7/8 (nicht mehr auf Upload/Extract) |
| 5 | Defense-in-Depth | alle Skill-Blöcke | Blöcke 0️⃣–5️⃣ (Tool-Varianten) mit Rollen-Gate: nur Agent-Kontext (kein Browser-Session-Zugriff); Seiten außerhalb der Rollenliste → Blockierungsmeldung |
| 6 | ADMIN-Rolle: `current_role()` → `"admin"`, geschützter Admin-Login, `_seiten_fuer_rolle("admin")` → 12 Seiten (v4.3-Liste + Dashboard, inkl. Tools 0–5) | Login + Sidebar | Betreiber betreibt die Agent-Ebene im UI |
| 7 | Doku-Flags | alle `*_PENDING`-Marker | Nach Umsetzung → ✅ + E2E-Ergebnis |

**Nicht geändert werden:** DB-Schema, Matching-Logik (Tab-3-Ranking nutzt DB-Scores, unabhängig vom Skill-2-Datei-Tool), Bewerbungs-Flow, Feedback-Loop (Phase 3/4), DSGVO-Cleanup, Pre-Screen-/Onboarding-Modi, Skill-Code selbst (nur Sichtbarkeit/Gates).

---

## 5. Test-Szenarien (E2E – ✅ 18/18 bestanden, AppTest 12.09.2026; Candidate-Szenarien via Session-Injection, da AppTest keine echten Logins der Kandidaten-Accounts treiben kann)

| # | Szenario | Erwartung |
|---|---|---|
| 1 | EMPLOYER-Login | Sidebar: 4 Punkte seit 15.10.2026 (Dashboard, Stellenangebote, Hiring-Board, Mehr); vorher genau 12 Seiten seit 13.10.2026 (Dashboard, Firmenprofil, Stelle ausschreiben, Stellenangebote HR-write, Kandidaten-Suche, Match-Ergebnis, Compliance-Ergebnis, Agent-Details, Dokumente, Pre-Screen, Onboarding, Feedback – `webui/pages/employer.py` (gemessen 10.10.2026), Zeilenstand 28.09.2026`) – **kein Upload, kein Extract, kein 4️⃣/5️⃣** |
| 2 | EMPLOYER öffnet 2️⃣ Match-Ergebnis | Ansicht des agent-Berichts; kein Matching-Ausführ-Button. Status-Aktionen nur über die Dialoge `do_invite` / `do_reject` / `do_hire` |
| 3 | EMPLOYER öffnet 3️⃣ Compliance-Ergebnis | Read-only Ansicht; keine Prüf-Aktion |
| 4 | EMPLOYER-Vollflow | Bewerber verwalten (💼) → Pre-Screen (Recruiting) → Onboarding freigeben → Feedback speichern – ohne Skills 1–5 erreichbar |
| 5 | CANDIDATE-Login | 7 Tabs (NiceGUI, `_TAB_MAP` `webui/pages/candidate.py`, Stand 02.10.2026) — Landing: 📊 Dashboard (Nutzerentscheidung 01.10.2026) |
| 6 | CANDIDATE Upload | Eigener CV, Statuswechsel, Bewerben freigeschaltet |
| 7 | GAST | Nur Login-Bildschirm |
| 8 | Direkter Navigationssversuch auf entfernte Seite (manipulierte Session) | Defense-in-Depth-Blockierung |
| 9 | Agent-Workflow | Skills 0–5 laufen regulär über opencode/MCP; im UI nur durch ADMIN ausführbar |
| 10 | ADMIN-Login | Sidebar: 12 Seiten inkl. Tools 0–5; Tools ausführbar |
| 11 | ADMIN öffnet 👤 Candidate Portal (direkt) | **Erlaubt** (Ist-Code: `webui/pages/candidate.py` (gemessen 10.10.2026) + `webui/main.py` (gemessen 10.10.2026), ⓘ09.10.2026, Design-Entscheidung — frühere Erwartung „blockiert" überholt) |

---

## 6. Auswirkungen auf Dokumente (✅ aktualisiert 12.09.2026)

- `instructions.md` → v4.5: Matrix auf Zwei-Ebenen-Modell umgestellt, Umsetzungsstatus ✅ implementiert (12.09.2026).
- `skills/README.md`, `knowledge.md`, `AGENTS.md`, `README.md` → Verweis auf v3 mit ✅ implementiert (12.09.2026) für die Sidebar-Änderung.
- `skills/employer-portal/SKILL.md` → Hinweis ergänzen: Portal zeigt Ergebnisse, Tools bleiben agent-only (nach Code-Umsetzung ✅).

---

*Erstellt am 12.09.2026 für den KM-HR-Agenten (Access-Control v3.1 – Zwei-Ebenen-Modell: Agent-Ebene vs. Portal-Ebene + ADMIN-Rolle).*
