# Mentoring / Patenschaft (Spec – PHASE D, Punkt 10)

> **Stand:** 24.09.2026
> **Status:** ✅ **USER-GO erteilt 24.09.2026** – §2 Option A (HR-Klick) + §3 Option C (separate Tabelle `mentoring`) + §4 Ende per HR-Klick (manuell) + Anzeige im bestehenden Candidate-Onboarding-Tab **implementiert**. Feature-Freeze aufgehoben. Option B (Score-Vorschlag) und Frist-Automatik weiterhin optional/offen.
> **Zweck:** Mentoring (Patenschaft) als Lebenszyklus-Feature spezieren – von der HR-Vergabe bis zum Befüllen des toten `{MENTOR}`-Platzhalters in den Sprachtemplates
> **Gehört zu:** Lifecycle-Reihe (`knowledge/lifecycle/`), Anknüpfung an `onboarding_release` (Phase 5) und Sprachtemplates (`knowledge/templates/language-templates/`)
> **Beweisbasis:** Schritt-0-Greps, dokumentiert in `ergebnisse/phase-d-p10-mentoring.md`; Implementierung: `ergebnisse/entscheidungen.md` (24.09.2026, USER-GO-Eintrag)

---

## 1. Zweck + Bipperz-Status ❌ (Punkt 10)

**Zweck:** Eine Patenschaft begleitet den Kandidaten nach der Einstellung (`eingestellt`) durch die ersten Wochen – fester Ansprechpartner, Einarbeitung, Rückfragen. Der Platzhalter existiert bereits in den Sprachtemplates, wird aber von keinem Feature befüllt (Schritt-0-Befund, siehe Report).

**Bipperz-Status ❌ (Punkt 10):**
- Externe Bipperz-Quelle für Mentoring/Patenschaft: **im Projekt NICHT vorhanden.** Einzige Bipperz-Erwähnung im ganzen Wissensbestand ist `knowledge/lifecycle/matching-criteria.md` („keine externe Quelle (… kein Bipperz-Dokument)" – dort allerdings zu den Matching-Gewichten, nicht zu Mentoring).
- Schritt-0-Befund im Code: **KEIN Mentoring-Feature implementiert.** Was existiert, sind:
  - `{MENTOR}`-Platzhalter in `knowledge/templates/language-templates/templates-de.md`, `knowledge/templates/language-templates/templates-en.md`, `knowledge/templates/language-templates/templates-fr.md` – toter Platzhalter, kein Befüll-Code (kein `MENTOR`-Treffer in `scripts/agent-runner.py` oder `webui/`).
  - Soft-Skill-/Bonus-Punkte-Keywords: `webui/logic.py` (gemessen 10.10.2026), `webui/components.py` (gemessen 10.10.2026), `knowledge/lifecycle/matching-criteria.md`.
  - Sprachtest-Frage EN-C1-038: `knowledge/language-tests.md`.
- **Konsequenz (Lab-Prinzip 1):** Jeder hier spezifizierte Wert ohne Quelle ist ausdrücklich als **Design-Entscheidung** gekennzeichnet. Punkt 10 („Mentoring") der externen Checkliste bleibt ❌ bis eine echte Quelle gefunden wird – wir erfinden keine.

---

## 2. Wer vergibt Mentoren? (Optionen – Entscheidung User)

| # | Option | Mechanismus | Vor-/Nachteil | Quelle/Beweis |
|---|---|---|---|---|
| **A** | **HR-Klick auf Employer-Seite** (empfohlen als Basis) | HR wählt im Employer-Portal (Onboarding- oder Kandidaten-Verwaltung) einen Mentor und setzt die Zuordnung – analog zum bestehenden `→ eingestellt`-Klick | ✅ Human-in-the-loop-konform (Variante A: Agent lädt/lehnt nie selbst ein – User-Entscheidung 12.09.2026); ✅ nutzt bestehendes Muster `db.queue_agent_task(..., trigger="hr_klick_portal")` (`webui/pages/employer.py` (Codemarke `def do_hire`, gemessen 10.10.2026)); ❌ manueller Aufwand | Muster: `webui/pages/employer.py` (Codemarke `def do_hire`, gemessen 10.10.2026) (`do_hire`) |
| **B** | **Auto-Vorschlag über bestehendes Scoring** | `berechne_match_score()` (`webui/logic.py` (Codemarke `def berechne_match_score`, gemessen 10.10.2026)) liefert einen Vorschlag (z.B. Kandidaten mit `+3 Pkt: Teamführung/Mentoring`, `knowledge/lifecycle/matching-criteria.md`, erkannt via Keyword `webui/logic.py` (Codemarke `def berechne_match_score`, gemessen 10.10.2026)) – **nur Vorschlag, KEINE automatische Zuweisung** | ✅ wiederverwendet bestehendes Score ohne neue Connector; ❌ Score misst Kandidaten-Passing, nicht Mentor-Qualität – daher nur Vorschlag (Design-Entscheidung: Schwelle/Top-N offen) | `webui/logic.py` (Codemarke `def berechne_match_score`, gemessen 10.10.2026), `knowledge/lifecycle/matching-criteria.md` |

**Entscheidung:** offen – **User Go erforderlich**. Spezifikation hier: beide Optionen, Vergabe bleibt grundsätzlich menschlich (Variante A), B nur als Vorschlags-UX.

---

## 3. Datenfeld: Mentor-Zuordnung – wo speichern?

| # | Option | Vorteil | Nachteil | Bestehendes Muster |
|---|---|---|---|---|
| **A** | Spalte in `candidates`-Tabelle (z.B. `mentor_name TEXT`) | ✅ einfachster JOIN für `{MENTOR}`-Ersatz | ❌ nur EINE Patenschaft gleichzeitig, keine Historie, keine Laufzeit (Start/Ende) | `candidates`-Schema `app.py` (Codemarke `Start`, gemessen 10.10.2026) |
| **B** | Feld im Onboarding-Report (`onboarding-freigabe-bewerbung-{id}.md`) | ✅ kein DB-Schema-Change, Report ist schon der Einstiegspunkt | ❌ MD-Text, kein strukturierter Wert, schwer auswertbar/DSGVO-Löschung nicht anbindbar | `scripts/agent-runner.py` (gemessen 10.10.2026) (Report-Schreibweise) |
| **C** | **Separate Tabelle `mentoring` (Vorschlag)** | ✅ Historie + Status + Laufzeit (Start/Aktiv/Ende) in einer Tabelle; ✅ Vorbild `candidate_status_history` (`app.py` (Codemarke `Start`, gemessen 10.10.2026): `candidate_id`, `status`, `changed_by`, `notizen`, `changed_at`, FK) und `application_status_history` (protokolliert jeden Übergang, `knowledge/lifecycle/application-status.md`); ✅ eigene DSGVO-Löschung koppelbar | ❌ neue Tabelle = Schema-Migration nötig (bei Go) | `app.py` (Codemarke `Start`, gemessen 10.10.2026), `knowledge/lifecycle/application-status.md` |

**Empfehlung (Design-Entscheidung, User-Go):** Option C als Lebenszyklus-Modell + (optional) Materialisierung von `{MENTOR}` in den generierten Onboarding-Artefakten (Report/Mail) – analog dazu, wie `onboarding_release` den Freigabe-Report schreibt.

---

## 4. Lebenszyklus

Reihenfolge (Vorbild: Status-Tabellen mit History-Protokoll):

```
(nach Status 'eingestellt')
   ──▶ vorgeschlagen (optional, Agent-Vorschlag B)
   ──▶ aktiv (HR-Klick A)          [Start: changed_at, changed_by='arbeitgeber']
   ──▶ beendet (HR-Klick / Frist)  [Ende: changed_at, changed_by]
```

| Übergang | Auslöser | Wer | Beweis-Muster |
|---|---|---|---|
| Vorschlag → aktiv | **HR-Klick** (Variante A) | Arbeitgeber | `webui/pages/employer.py` (Codemarke `def do_hire`, gemessen 10.10.2026) (`do_hire`, trigger `hr_klick_portal`) |
| aktiv → beendet | **Optionen (Design-Entscheidung, User wählt):** (1) HR-Klick manuell, (2) Frist (z.B. X Wochen nach Start – Wert offen, keine Quelle), (3) automatisch bei Status-Ende/Kündigung – **KEINE automatische Beendigung ohne User-Go spezifiziert** | Arbeitgeber | History-Protokoll wie `application_status_history` (`knowledge/lifecycle/application-status.md`) |

**Regel:** Jede Änderung wird historisiert (wie `candidate_status_history`, `app.py` (gemessen 10.10.2026)). Kein Trigger, kein Code vor User-Go.

---

## 5. Anbindung an bestehende Templates: `{MENTOR}` endlich befüllen (natürlicher Einstieg)

Der `{MENTOR}`-Platzhalter ist das natürliche Einstiegsfeld – er verhält sich wie jede andere Template-Variable (Exchange-Feld):

| Datei | Zeile | Exakter Inhalt |
|---|---|---|
| `knowledge/templates/language-templates/templates-de.md` | 54 | `Dein Ansprechpartner: {MENTOR}` |
| `knowledge/templates/language-templates/templates-en.md` | 54 | `Your point of contact: {MENTOR}` |
| `knowledge/templates/language-templates/templates-fr.md` | 54 | `Votre contact: {MENTOR}` |

**Wie andere Felder aktuell befüllt werden (Bestandsmuster):**
- **Onboarding-Generator (UI):** `onboarding_generator_section()` in `webui/components.py` (Codemarke `def onboarding_generator_section`, gemessen 10.10.2026) baut die MD 1:1 nach `app.py` (gemessen 10.10.2026) auf und ersetzt Felder per f-String: Name/Stelle/Startdatum in `webui/components.py` (gemessen 10.10.2026), Willkommens-E-Mail-Abschnitt `webui/components.py` (gemessen 10.10.2026) – **Mentor-Zeile ist vorhanden** (Zeile „Dein Ansprechpartner: {0}"); Lookup **per `candidate_id`** im Arbeitgeber-Modus (DB-Quelle, 19.10.2026), im Demo-/Admin-Modus weiterhin **per Name** (`mentoring JOIN candidates`).
- **Agent (Mail #6):** `send_onboarding_mail()` in `scripts/agent-runner.py` (Codemarke `def send_onboarding_mail`, gemessen 10.10.2026) setzt `name`, `titel` (`scripts/agent-runner.py` (Codemarke `def send_onboarding_mail`, gemessen 10.10.2026)) und optionalen Visum-Block (`scripts/agent-runner.py` (gemessen 10.10.2026), 426) per String-Ersatz in den Body – gleiche Mechanik für Mentor (Feld aus DB nachladen, wie `cd.email, cd.name, j.titel` JOIN `scripts/agent-runner.py` (gemessen 10.10.2026)).
- **Freigabe-Report:** `onboarding_release` schreibt `onboarding-freigabe-bewerbung-{app_id}.md` (`scripts/agent-runner.py` (gemessen 10.10.2026)) inkl. Visum-Abschnitt – analog könnte der Mentor-Eintrag ergänzt werden.

**Einstiegsreihenfolge (bei Go):** (1) Datenfeld (§3) → (2) HR-Vergabe (§2A) → (3) `{MENTOR}`-Ersatz in Generator + Mail #6 (§5) → (4) Lebenszyklus-Ende (§4).

---

## 6. Kostenloser Connector: KEINER nötig

**Explizit:** Mentoring ist eine reine **DB + UI + Template-Spec**.
- Kein externer Dienst, keine neue MCP-Verbindung, keine API, kein Web-Zugriff.
- Alle Bausteine existieren lokal: SQLite (`data/feedback.db`), NiceGUI-Seiten (`webui/pages/`), bestehender Agent-Runner (`scripts/agent-runner.py`, deterministische Tasks laufen ohnehin direkt), MD-Templates unter `knowledge/templates/`.
- Prüfung: Schritt-0 ohne Connector-Fund; Aufgabe laut Brief „kein Connector".

---

## 7. Verantwortlichkeiten

| Rolle | Verantwortung | Nicht verantwortlich |
|---|---|---|
| **HR (Arbeitgeber)** | Mentor **wählen und zuweisen** (§2A, Klick), Patenschaft **beenden** (§4), ggf. Vorschlag (§2B) prüfen/ablehnen; Angaben für Onboarding-Checkliste | Automatische Entscheidungen des Agenten |
| **Agent (Runner)** | `{MENTOR}`-Platzhalter **befüllen** in Report/Mail/Checkliste, wenn Wert gesetzt ist (§5, deterministisch wie `send_onboarding_mail`); optional Score-Vorschlag erzeugen (§2B, **nur Vorschlag**) | Niemals selbst zuweisen/beenden (Variante A, User-Entscheidung 12.09.2026) |
| **Kandidat** | Patenschaft **annehmen/nutzen**, Fortschritt/Rückfragen; Sicht auf Mentor im Onboarding-Tab (Anzeige, wie `webui/pages/candidate.py` (gemessen 10.10.2026) Freigabe-Report anzeigt) | Auswahl des Mentors |

---

## Offene Entscheidungen (User Go erforderlich)

1. Vergabe-Option: **A (HR-Klick)** vs. **B (Vorschlag)** vs. beides (A Pflicht, B optional) – §2.
2. Speicher-Option: **A (candidates-Spalte)** vs. **B (Report-Feld)** vs. **C (separate Tabelle)** – §3.
3. Ende der Patenschaft: HR-Klick vs. Frist (Wert?) vs. Automatik – §4.
4. Ob und wo Mentor zusätzlich in Kandidaten-Portal angezeigt wird (neuer Tab vs. bestehender Onboarding-Tab, `_TAB_MAP` `webui/pages/candidate.py`, Stand 01.10.2026) –尚 ohne Entscheidung.

---

*Erstellt 24.09.2026 (Phase D, Punkt 10) – reine MD-Spec, kein Code. Alle Zahlen ohne externe Quelle = Design-Entscheidung (Lab-Prinzip 1). Bipperz-Punkt 10: ❌ nicht vorhanden.*
