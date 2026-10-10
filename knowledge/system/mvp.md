# MVP-Definition (Phase-E Runde 2 · Schritt P2)

> **Angelegt:** 25.09.2026 · **Art:** MD-only (kein Code, keine DB-Änderung, kein Prozess, keine Mail)
> **Auftrag:** Phase-E Runde 2, Schritt 4 = P2 MVP-Definition · Schritt 5 = P3 Pilot → `ergebnisse/pilot-plan.md`
> **Vorheriger Stand:** Datei existierte **nicht** — Beweis: `test -e knowledge/system/mvp.md` → `NOT_EXISTS` (Exit 1), 25.09.2026 (vor diesem Anlegen)
> **Lab-Prinzip 1 (Quellenpflicht):** Jede Zahl unten hat eine Quelle (Datei:Zeile bzw. Live-Befehl) **oder** ist ausdrücklich als **Design-Entscheidung** gekennzeichnet. Keine erfundenen Zahlen.
> **Wird NICHT hier geändert:** `ergebnisse/entscheidungen.md` (nur gelesen, Zitat §4).

---

## 0. Was „MVP" hier bedeutet

**MVP = das kleinste Gesamtpaket, das den Kernnutzen „Bewerbung → automatisiertes Matching → HR-Entscheidung → Feedback-Loop" ohne Ausfall nachweist** — inklusive der Infrastruktur, die dafür live laufen muss (Portal, Queue, Runner, Connectoren).

Diese Abgrenzung selbst ist eine **Design-Entscheidung**: vor dieser Datei war kein MVP im Repo definiert (Beleg: `ergebnisse/entscheidungen.md`, Zitat in §4; „0 Treffer für MVP" dort ebenfalls als Befund notiert).

---

## 1. MVP-Abgrenzung

### 1.1 In-Scope (live umgesetzt)

| # | Bestandteil | Beleg (Datei:Zeile bzw. Report) |
|---|---|---|
| 1 | **Phase 1** – Bewerbungs-Workflow (`applications` + Status-Lebenszyklus, Spec 7 Status) | `knowledge/lifecycle/application-status.md` (Spec, existiert verifiziert 25.09.2026) |
| 2 | **Phase 2** – Scoring/Matching (Baseline-Gewichte + Normalisierung) | `knowledge/lifecycle/matching-criteria.md` („Implementierung: ✅ Phase 2 … + Phase 4") |
| 3 | **Phase 3** – Feedback-Integrität (UNIQUE `match_id`, idempotentes Speichern) | `knowledge.md` „Feedback integrity (Phase 3)" · Report `ergebnisse/phase-3-feedback-integritaet.md` |
| 4 | **Phase 4** – geschlossener Feedback-Loop (`adjust_weights_from_feedback()`) | `knowledge/lifecycle/matching-criteria.md` („geschlossener Feedback-Loop (Phase 4)") |
| 5 | **Phase 4.5** – DSGVO-Autolöschung (183 Tage nach Prozessende) | `knowledge/lifecycle/application-status.md` („6 Monate (183 Tage)"), Report `ergebnisse/phase-4-5-dsgvo-loeschung.md` |
| 6 | **Phase 4.6** – Branchenscore (IT/IT-nah/fremd-Matrix) | `knowledge/lifecycle/matching-criteria.md`, Report `ergebnisse/phase-4-6-branchen-score.md` |
| 7 | **Phase 5** – Agent-Automatisierung (Queue + Hybrid-Runner, Pförtner-Regel, Variante A) | `knowledge/system/agent-automation.md` (60-s-Loop, LIMIT 5), Live-Run `ergebnisse/agent-automatisierung-live-run.md` |
| 8 | **Zwei-Ebenen-Zugriff + ADMIN** (Candidate 7 Tabs / Employer 11 Seiten / Admin 12 Seiten) | `knowledge/system/access-control.md` (v3.1), Seitenzahlen zitiert in `knowledge.md` |
| 9 | **6 E-Mail-Vorlagen + VDO.Ninja-only** (kein Google Meet, kein Jitsi) | `knowledge.md` „E-Mails \| 6 implementiert" · Spec `knowledge/system/vdo-ninja-migration.md` (Nutzer-Entscheidung 27.09.2026, ersetzt die Jitsi-Entscheidung vom 12.09.2026) |
| 10 | **15 MCP-Server** (Stand 24.09.2026; Zählwerk bestätigt §G 26.09.2026: 49 dokumentiert (instructions.md, nach §G) / 181 live (Handshake 26.09.2026)) | `knowledge/system/mcp-connector-config.md` + Live-Befehl §2 |
| 11 | **Kandidaten-Dokumenten-Tab (v6.1)** `candidate_documents` + getippte Uploads | `knowledge.md` „v6.1: Dokumenten-Tab … ✅ implementiert (E2E T1–T5)" |
| 12 | **23 Skills / 16 DB-Tabellen** als Umfang des Laufzeitsystems | Live-Befehle §2 |

### 1.2 Out-of-Scope (nicht Teil des MVP)

| Punkt | Befund | Quelle (Datei:Zeile bzw. Live-Befehl) |
|---|---|---|
| **Partnernetzwerk-Betrieb** | Kein Partner-/Supplier-Feature: `supplier` existiert im Projekt weder als Tabelle noch als Spec; für ein echtes Feature wären neue Spec + Tabelle + UI-Page + Matching-Regeln nötig („außerhalb dieses Freeze-Auftrags"). Ob „Lieferant" = „Arbeitgeber" ist, bleibt **Design-Entscheidung**. Freigabe „Partnern/Pilot" wartet auf User-Entscheidung. | `ergebnisse/supplier-abgleich-2026-09-24.md` (supplier existiert nicht) (Design-Entscheidung + außerhalb Freeze), `ergebnisse/entscheidungen.md` („Partnern/Pilot-Freigabe" als offener Punkt) |
| **Bezahlung / Zahlungsverkehr** | Kein Zahlungs-Feature spezifiziert; der Connector `payment` wurde **24.09.2026 entfernt** (0 Code-Aufrufe), `payment-mcp/` liegt nur noch auf Disk. | `knowledge/system/mcp-connector-config.md` („Entfernt 24.09.2026 (P1b) – 0 Code-Aufrufe") |
| **Mobile App (nativ/PWA)** | Im Repo **0 Treffer** für „mobile app / mobile-app / smartphone app / ios-app / android-app" in `knowledge/`, `skills/`, `instructions.md`, `AGENTS.md`, `knowledge.md`, `ergebnisse/` (ohne `.bak`). Es gibt nur ein responsives Web-Grid. | Live-Befehl: `grep -rni "mobile app\|mobile-app\|smartphone app\|ios-app\|android-app" --include="*.md" knowledge/ skills/ instructions.md AGENTS.md knowledge.md ergebnisse/ \| grep -v "\.bak" \| wc -l` → **0**; Layout: `knowledge/ui-design-system.md` („Responsive Grid") |
| **Signatur / E-Signatur (Vertragsabschluss)** | Ausdrücklich „Nicht in diesem GO"; Signatur-Optionen A–F bleiben User-Wahl; grep nach `e-sign\|esign\|…signatur` (Design gefiltert) = **0 Treffer** → „kein Feature". | `knowledge/legal/contract-management.md` („Nicht in diesem GO: Signatur-Dienst-Einbindung") (grep 2b = 0) |
| **Vertrags-Status-Tracking-DB** | Ebenfalls „Nicht in diesem GO"; `contract_preflight` liefert nur einen MD-Report. | `knowledge/legal/contract-management.md` · `knowledge/system/agent-automation.md` („Kein Signatur-Dienst") |
| **Wohnungssuche als Datenquelle** | Kein frei nutzbares öffentliches Listing-API gefunden → Feature ist Info-Orchestrierung, keine Angebotsbeschaffung. | `knowledge/portal/housing-search.md` |
| **Echte Dritt-Partner-Anbindung** (0 Teilnehmer) | Siehe P3-Konzept `ergebnisse/pilot-plan.md` §(b). | `ergebnisse/supplier-abgleich-2026-09-24.md` (kein Partner-Feature), DB-Stand §2 |

**Nicht entschieden (bewusst offen, = Design-Entscheidung):** Score-Schwellen 60/70/80/90, Gewichtung 30/25/15/10/10/10/0 und Gehalts-Toleranz 0.8/1.1 bleiben Design-Entscheidungen ohne externe Quelle (`AGENTS.md` „Hardcoded-Werte (15.09.2026)" — Matching 30/25/… = „Keine / ❌ Design-Entscheidung"; Schwelle ≥60 = `knowledge/system/agent-automation.md` „keine externe Quelle").

---

## 2. Anbindung an den verifizierten Live-Stand

> **Basislinie: live verifiziert 24.09.2026** (durch einen anderen Agenten; als Stand zitiert, nicht neu erfunden).
> **Wiederholungsmessung: 25.09.2026** (durch diesen Auftrag, read-only, identische Werte — Befehl pro Zeile).

| Kennzahl | Wert | Befehl (ausführbar, read-only) | Status |
|---|---|---|---|
| Unit-Tests | **26 passed** | `.venv-streamlit/bin/python3 -m pytest -q` → `26 passed, 1 warning in 0.55s` | 24.09. ✅ · 25.09. ✅ identisch |
| HTTP-Status (4 Routen) | **200** auf `/login`, `/candidate`, `/employer`, `/admin` | `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/<route>` | 24.09. ✅ · 25.09. ✅ identisch (4×200) |
| Agent-Runner | **exakt 1** Prozess | `cat data/agent-runner.pid` → `6194`; `ps -p 6194 -o pid,cmd` → `python3 scripts/agent-runner.py` | 24.09. ✅ · 25.09. ✅ (1 Prozess) |
| Failed Task-IDs | `[20, 21, 23, 39, 105]` (Anzahl **5**) | `sqlite3 data/feedback.db "SELECT id FROM agent_tasks WHERE status='failed' ORDER BY id;"` | 24.09. ✅ · 25.09. ✅ identisch |
| Agent-Tasks gesamt | done **118** / failed **5** | `sqlite3 data/feedback.db "SELECT status, COUNT(*) FROM agent_tasks GROUP BY status;"` | 25.09. (ergänzende Messung) |
| Feedback-Zeilen | **8** | `sqlite3 data/feedback.db "SELECT COUNT(*) FROM feedback;"` | 24.09. ✅ · 25.09. ✅ identisch |
| DB-Tabellen | **16** | `sqlite3 data/feedback.db "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"` | 24.09. ✅ · 25.09. ✅ identisch |
| Skills | **23** | `ls skills/*/SKILL.md \| wc -l` | 24.09. ✅ · 25.09. ✅ identisch |
| Knowledge-MD (ohne `.bak`) | **37** (vor Anlegen) → **38** nach Anlegen dieser Datei | `find knowledge -name '*.md' -not -name '*.bak*' \| wc -l` | 24.09. = 37 ✅ · 25.09. vor Anlegen = 37 ✅; **+1 durch `knowledge/system/mvp.md` → 38** (Zähler-Nachtrag, keine Doku-Fälschung) |
| MCP-Server | **14** (13 local + 1 remote, seit 27.09.2026 ohne `jitsi-meeting`) | `python3 -c "import json;print(len(json.load(open('opencode.json'))['mcp']))"` | 27.09.2026 gemessen: 14 |
| `gewichtung_historie` | **4** Zeilen | `sqlite3 data/feedback.db "SELECT COUNT(*) FROM gewichtung_historie;"` | 24.09. ✅ · 25.09. ✅ identisch |

**Weitere Kontrollzähler 25.09.2026 (read-only, für Pilot-Plan relevant):** `candidates` **9** · `employers` **1** · `applications` **13** · `jobs` **3** · `admins` **1** — Befehl je Zeile: `sqlite3 data/feedback.db "SELECT COUNT(*) FROM <tabelle>;"`.

---

## 3. Erfolgskriterien (Schwellen = Design-Entscheidung)

> **Alle Schwellen unten sind Design-Entscheidungen** — es gibt keine externe Quelle für „26 Tests reichen" o. Ä. (Lab-Prinzip 1). Die **Messwerte** selbst sind belegt (§2).

| # | Erfolgskriterium | Schwelle | Messung | Herkunft der Schwelle |
|---|---|---|---|---|
| E1 | Unit-Tests grün | `pytest -q` ≥ **26 passed** und **0 failed** | `.venv-streamlit/bin/python3 -m pytest -q` | **Design-Entscheidung** (Anzahl = aktueller Bestand, §2) |
| E2 | Portal erreichbar | HTTP **200** auf `/login`, `/candidate`, `/employer`, `/admin` | `curl -o /dev/null -w "%{http_code}" …` | **Design-Entscheidung** (200 = Standard-HTTP-Erfolg, Schwelle 200 festgelegt) |
| E3 | Runner-Kardinalität | **exakt 1** `agent-runner.py`-Prozess (kein Doppelstarter) | `cat data/agent-runner.pid` + `ps -p <pid>` | **Design-Entscheidung** (pidfile-Konvention, `knowledge.md` „PID-File `data/agent-runner.pid`") |
| E4 | Queue-Gesundheit | failed-Tasks ≤ **5** (Baseline) und keine *neuen* Fehler-IDs außerhalb `[20,21,23,39,105]` | `SELECT id FROM agent_tasks WHERE status='failed' ORDER BY id;` | **Design-Entscheidung** (Baseline-Wert 24.09.2026 als Limit gewählt) |
| E5 | Connector-Bestand | **15** MCP-Server in `opencode.json` (kein stiller Verlust) | `python3 -c "import json;…['mcp'])"` | **Design-Entscheidung** (Sollwert = Stand 24.09.2026) |
| E6 | Skill-/Tabellenbestand | **23** Skills, **16** DB-Tabellen | `ls skills/*/SKILL.md \| wc -l` · `sqlite_master`-COUNT | **Design-Entscheidung** (Sollwert = Stand 24.09.2026) |
| E7 | Datenhaltung DSGVO | Feedback-Löschpfad greift weiterhin (183 Tage, `dsgvo_cleanup()` definiert) | `knowledge/lifecycle/application-status.md` | **Design-Entscheidung** (Zahl 183 = Umsetzung von „6 Monate", Quelle in `AGENTS.md` „DSGVO 183 Tage · Art. 17 DSGVO" als offiziell markiert) |
| E8 | Score-Validierung (NICHT MVP-Kriterium) | erfordert **20+ Einstellungsentscheidungen** — belegte Hürde, erst danach Aussage zur Schwelle 60 | `knowledge/system/agent-automation.md` | **belegte Hürde** (Zahl mit Quelle, kein Entwurf) — bewusst NICHT als MVP-Gate gesetzt |

**Geltung:** Ein MVP-Lauf gilt als bestanden, wenn **E1–E6** gleichzeitig erfüllt sind. E7 ist Daueranforderung, E8 ist ausdrücklich kein MVP-Blocker (sonst wäre das MVP nie erreichbar — Begründung: belegte Hürde, siehe E8).

---

## 4. Bezug: Schließung des offenen Punkts „MVP undefiniert"

**Quelle (nur gelesen, nicht verändert):** `ergebnisse/entscheidungen.md`, **Zeile 1382** (verifiziert 25.09.2026 via `sed -n '1382p'` bzw. `awk 'NR==1382'`, Datei = 1841 Zeilen):

> `| **(c) MVP-Echttest mit echten Nutzern** | Produkt-Validierung mit realen Bewerbern/HR; ohne ihn bleibt alles technischer Live-Test | **Nicht belegt** — weder Aufwand noch Status in Doku; Konzept existiert nirgends | Reale Nutzer (Bewerber/HR) — belegte Hürde: 20+ Einstellungsentscheidungen für Score-Schwelle 60 (`knowledge/system/agent-automation.md`) | **0 Treffer** für MVP/Echttest/Testpersonen in AGENTS.md/instructions.md/knowledge/ergebnisse (nur technische Live-Tests, `ergebnisse/agent-automatisierung-live-run.md`) — Konzept NICHT dokumentiert |`

**Ergänzende Fundstellen (ebenfalls nur gelesen):**
- `ergebnisse/entscheidungen.md` — „MVP-Prinzip (0 Treffer)".
- `ergebnisse/entscheidungen.md` — „**(c) MVP** ist als Konzept undokumentiert — nur wählen wenn reale Nutzer-Pilot bewusst gewollt ist; vorher sind 20+ Einstellungsentscheidungen die belegte Hürde."
- `ergebnisse/entscheidungen.md` — Reihenfolge der Folgeschritte: „Danach **P2 MVP-Spec → P3 Pilot** → P5 UI-Polish-Nachweis → P6 Relocation-Check → P7 Verifikation."

**Wirkung dieser Datei:** Der offene Punkt „MVP undefiniert / Konzept existiert nirgends" ist für die **Scope-Definition** geschlossen (§1–§3). **Offen bleibt** die Produkt-Validierung mit echten Dritt-Nutzern — die gehört zu P3 und ist in `ergebnisse/pilot-plan.md` §(a) als Pilot mit Messgrößen und Stop-Bedingungen spezifiziert. Die belegte Hürde „20+ Einstellungsentscheidungen" (E8) bleibt unverändert bestehen und ist hier **nicht** umgangen, sondern als separates Kriterium geführt.

**Status-Änderung ist bewusst eine MD-Änderung:** Der Offen-Status in `entscheidungen.md` selbst wird **nicht** angefasst (Auftragsregel: diese Datei nur lesen); diese Sektion ist der dokumentierte Bezug.

---

## 5. Nicht Teil dieses Dokuments

- **Pilot-Durchführung, Messgrößen, Stop-Bedingungen, Partner-Konzept** → `ergebnisse/pilot-plan.md` (P3).
- **Entscheidungsprotokoll** → `ergebnisse/entscheidungen.md` (unverändert, schreibgeschützt für diesen Auftrag).
- **Code/DB/Prozesse/Mails** → verboten in dieser Runde (Lab-Prinzip 2: MD-first; hier reicht MD).

---

*Erstellt 25.09.2026 (Phase-E Runde 2, Schritt P2) · MD-only · Alle Zahlen mit Quelle oder als Design-Entscheidung gekennzeichnet.*
