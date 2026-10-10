---
description: Mentoring / Patenschaft – HR vergibt Mentoren (HR-Klick), Agent befüllt {MENTOR} in Onboarding-Artefakten, Lebenszyklus aktiv/beendet historisiert (USER-GO 24.09.2026, implementiert §2A/§3C/§4)
---

## Funktionierende MCP-Connectors

| Connector | Tool | Zweck |
|---|---|---|
| `filesystem` | `read_text_file` | Knowledge-Dateien (`knowledge/lifecycle/mentoring.md`, Sprachtemplates) lesen |
| `filesystem` | `write_file` | Onboarding-Freigabe-Report mit Mentor-Eintrag schreiben |
| `email-sender` | `send_email` | Onboarding-Willkommens-Mail #6 mit befülltem `{MENTOR}` senden (bestehend `send_onboarding_mail`) |

**Hinweis (Spec §6):** Mentoring ist eine reine **DB + UI + Template-Spezifikation** – KEIN externer Dienst, KEINE neue MCP-Verbindung, KEINE API. Alle Bausteine existieren lokal (SQLite `data/feedback.db`, NiceGUI `webui/pages/`, Agent-Runner `scripts/agent-runner.py`, MD-Templates `knowledge/templates/`).

**Externe Quelle (Lab-Prinzip 1):** Bipperz-Checklisten-Punkt 10 (Mentoring) **❌ nicht vorhanden**; `anysearch` derzeit nicht nutzbar (`invalid_auth_header`), SHRM/CIPD-Urls 404. Einzige externe Zitation: Wikipedia „Mentoring" (Bozeman & Feeney 2007-Definition) – nur als Begriffsrahmen, **NICHT** als Programm-Struktur-Quelle. → Jeder hier spezifizierte Mechanismus/Wert ist **Design-Entscheidung** (Kennzeichnungspflicht).

**Status (User-GO 24.09.2026):** §2A (HR-Klick), §3C (separate Tabelle `mentoring` in `webui/db.py: init_mentoring_table/assign_mentor/end_mentoring/get_active_mentor`), §4 (Ende per HR-Klick manuell), Anzeige Candidate-Onboarding-Tab **implementiert**. `{MENTOR}`-Befüllung in Generator + Mail #6 + Freigabe-Report aktiv. Option B (Score-Vorschlag-UX) und Frist-Automatik **nicht** umgesetzt (optional, kein GO).

---

## Zugriff (v4.5, Zwei-Ebenen-Modell)

| Rolle | Zugriff |
|---|---|
| **EMPLOYER (HR)** | ✅ Mentor **wählen und zuweisen** (HR-Klick, Spec §2 Option A – empfohlen); Patenschaft **beenden** (§4); optionalen Agent-Vorschlag (§2B) prüfen/ablehnen; Angaben für Onboarding-Checkliste |
| **CANDIDATE** | ✅ Mentor **im bestehenden Onboarding-Tab ansehen** (Anzeige-Endpunkt, `webui/pages/candidate.py` (gemessen 10.10.2026) Muster); Patenschaft nutzen – **keine** Auswahl |
| **ADMIN** | ✅ alle Funktionen |
| **Agent-Ebene** | ✅ `{MENTOR}`-Platzhalter deterministisch befüllen in Report/Mail/Checkliste (§5); optional Score-Vorschlag erzeugen (§2B, **nur Vorschlag**) – **niemals** selbst zuweisen/beenden (Variante A, User-Entscheidung 12.09.2026) |

**Portal-Sitz (Spec §2A, Beweis `webui/pages/employer.py` (Codemarke `def do_hire`, gemessen 10.10.2026) `do_hire`):** HR-Klick im Employer-Portal (Onboarding- oder Kandidaten-Verwaltung), analog `→ eingestellt` mit `db.queue_agent_task(..., trigger="hr_klick_portal")`.

---

## Trigger

- **Vergabe:** HR-Klick im Employer-Portal (Variante A – human-in-the-loop). Kein automatischer Trigger.
- **Befüllung:** läuft nach erfolgter Vergabe automatisch, sobald `{MENTOR}`-Wert aus DB gesetzt ist (deterministisch wie `send_onboarding_mail`, `scripts/agent-runner.py` (Codemarke `def send_onboarding_mail`, gemessen 10.10.2026)).
- **Vorschlag (§2B, optional):** Score-Keyword `webui/logic.py` (gemessen 10.10.2026) (`teamführung`/`mentoring` → +3 Pkt.) kann als Vorschlags-UX dienen – **nie** automatische Zuweisung.
- **Feature-Freeze:** ❌ ~~aufgehoben~~ **USER-GO erteilt 24.09.2026** für §2A (HR-Klick), §3C (separate Tabelle), §4 (Ende HR-Klick manuell), Anzeige im bestehenden Onboarding-Tab. Offene optionale Punkte: §2B (Score-Vorschlag-UX), Frist-Automatik (§4-Option 2), Anzeige in weiteren Tabs.

---

## Schritte (Einstiegsreihenfolge bei Go, Spec §5)

### 1. Datenfeld festlegen (§3 – User-Go)

**Empfehlung (Design-Entscheidung):** Option C – **separate Tabelle `mentoring`** (Vorbild `candidate_status_history`, `app.py` (gemessen 10.10.2026)):
- Spalten (Design, angelehnt an History-Muster): `id`, `candidate_id` (FK), `mentor_name`, `status` (`vorgeschlagen`/`aktiv`/`beendet`), `changed_by`, `notizen`, `changed_at`, `start_at`, `end_at`
- Vorteil: Historie + Laufzeit + eigene DSGVO-Löschung koppelbar
- Alternative A (`candidates.mentor_name`-Spalte) nur 1 Patenschaft ohne Historie; Alternative B (Report-Feld) unstrukturiert

### 2. HR-Vergabe (§2 Option A – HR-Klick)

**Muster:** `do_hire()` `webui/pages/employer.py` (Codemarke `def do_hire`, gemessen 10.10.2026)
1. HR wählt Mentor (Name/Freitext – Quelle: HR-Eingabe, keine externe Mentor-Datenbank)
2. HR-Klick → `UPDATE mentoring SET status='aktiv', changed_by='arbeitgeber', changed_at=now` (bei Go: INSERT mit History)
3. History-Insert analog `application_status_history` (`knowledge/lifecycle/application-status.md`)
4. Optional: `db.queue_agent_task(..., trigger="hr_klick_portal")` für nachgelagerte Befüllung

**Variante B (optional, nur Vorschlag):** `berechne_match_score()`-Keyword `webui/logic.py` (Codemarke `def berechne_match_score`, gemessen 10.10.2026) listet Kandidaten mit `+3 Pkt: Teamführung/Mentoring` (`knowledge/lifecycle/matching-criteria.md`) als Vorschlag – HR prüft/lehnt ab, **kein** Auto-Match (Score misst Kandidaten-Passing, nicht Mentor-Qualität – Design-Entscheidung).

### 3. `{MENTOR}` befüllen (§5 – Agent, deterministisch)

Platzhalter (toter Platzhalter seit Schritt-0, `ergebnisse/phase-d-p10-mentoring.md`):

| Datei | Zeile | Exakter Inhalt |
|---|---|---|
| `knowledge/templates/language-templates/templates-de.md` | 54 | `Dein Ansprechpartner: {MENTOR}` |
| `knowledge/templates/language-templates/templates-en.md` | 54 | `Your point of contact: {MENTOR}` |
| `knowledge/templates/language-templates/templates-fr.md` | 54 | `Votre contact: {MENTOR}` |

**Drei Konsum-Punkte (Bestandsmuster):**
1. **Onboarding-Generator (UI):** `onboarding_generator_section()` `webui/components.py` (Codemarke `def onboarding_generator_section`, gemessen 10.10.2026) – Mentor-Zeile in Willkommens-E-Mail-Abschnitt ergänzen (`webui/components.py` (gemessen 10.10.2026), aktuell ohne Mentor)
2. **Mail #6:** `send_onboarding_mail()` `scripts/agent-runner.py` (Codemarke `def send_onboarding_mail`, gemessen 10.10.2026) – Mentor per String-Ersatz wie `name`/`titel` (`scripts/agent-runner.py` (gemessen 10.10.2026)), JOIN aus DB analog `scripts/agent-runner.py` (gemessen 10.10.2026)
3. **Freigabe-Report:** `onboarding_release` schreibt `onboarding-freigabe-bewerbung-{app_id}.md` (`scripts/agent-runner.py` (gemessen 10.10.2026)) – Mentor-Abschnitt analog Visum-Abschnitt ergänzen

**Kein Wert gesetzt → `{MENTOR}` bleibt unangetastet oder wird Zeile-weise ausgelassen (Design-Entscheidung).**

### 4. Lebenszyklus-Ende (§4 – User-Go für Mechanismus)

```
(nach Status 'eingestellt')
   ──▶ vorgeschlagen (optional, Agent-Vorschlag B)
   ──▶ aktiv (HR-Klick A)          [Start: changed_at, changed_by='arbeitgeber']
   ──▶ beendet (HR-Klick / Frist)  [Ende: changed_at, changed_by]
```

- **aktiv → beendet:** Optionen (Design, User wählt): (1) HR-Klick manuell, (2) Frist X Wochen (Wert offen, keine Quelle), (3) Automatik bei Status-Ende – **KEINE automatische Beendigung ohne User-Go**
- Jede Änderung historisiert (wie `candidate_status_history`)

### 5. Anzeige Kandidat (optional, User-Go)

- Kein neuer Tab: Anzeige im **bestehenden Onboarding-Tab** `_tab_onboarding` (`webui/pages/candidate.py` (Codemarke `def _tab_onboarding`, gemessen 10.10.2026), zeigt Freigabe-Report ab `status='eingestellt'` `webui/pages/candidate.py` (gemessen 10.10.2026))
- `_TAB_MAP` hat Stand 02.10.2026 **7 Tabs** (📊 Dashboard als 1. Tab; Upload/Dokumente in 👤 Mein Profil) – kein zusätzlicher Tab für Mentoring

---

## Regeln

1. **Human-in-the-loop (Variante A, 12.09.2026):** Agent vergibt/beendet **nie** selbst – nur HR-Klick; Vorschlag (B) ist Vorschlag, keine Zuweisung
2. **Kein Code/DB vor User-Go:** Spec-Feature-Freeze bis Entscheidungen §2/§3/§4/§Anzeige getroffen
3. **Design-Entscheidung kennzeichnen:** Ohne externe Quelle (Bipperz P10 ❌, `anysearch` offline) bleibt jeder Mechanismus/Wert als Design markiert (Lab-Prinzip 1)
4. **Historisierung:** Jede Statusänderung wandert in History-Tabelle (Vorbild `application_status_history`)
5. **DSGVO:** Mentor-Daten in eigener Tabelle (Option C) an DSGVO-Löschung koppelbar; Kandidat sieht nur Mentor-Namen, keine Mentor-Kontaktdaten ohne Freigabe (Art. 6(1)(b)-Muster wie Kontaktdaten-Freigabe)
6. **{MENTOR} nur bei gesetztem Wert** ersetzen – kein „Unbekannt"-Erfinden

---

## Integration mit anderen Skills

| Skill | Verbindung |
|---|---|
| `generate-onboarding` | Onboarding-Generator + Checkliste sind Konsum-Punkt 1 für `{MENTOR}` (`webui/components.py` (gemessen 10.10.2026)) |
| `notify-user` (Mail #6) | `send_onboarding_mail` `scripts/agent-runner.py` (Codemarke `def send_onboarding_mail`, gemessen 10.10.2026) ist Konsum-Punkt 2 (Willkommens-Mail mit Mentor) |
| `export-report` | Freigabe-Report `onboarding-freigabe-bewerbung-{id}.md` ist Konsum-Punkt 3 |
| `match-candidate` | §2B-Vorschlag stützt sich auf Score-Keyword `webui/logic.py` (gemessen 10.10.2026) (+3 Pkt. Teamführung/Mentoring) |
| `check-gdpr` | Eigene Tabelle (§3C) an Löschfristen koppeln |
| `employer-portal` | HR-Klick-Sitz (Seite Onboarding / Kandidaten-Verwaltung, PAGE_MAP `webui/pages/employer.py` (Codemarke `PAGE_MAP`, gemessen 10.10.2026)) |
| `candidate-portal` | Anzeige im bestehenden Onboarding-Tab (kein neuer Tab) |

---

**Stand:** 24.09.2026 – USER-GO erteilt, §2A/§3C/§4/Anzeige implementiert (Lab-Prinzip 2: MD-first vor Code; jetzt Code da, MD↔Code konsistent). Quellen: `knowledge/lifecycle/mentoring.md` (Spec), `ergebnisse/phase-d-p10-mentoring.md` (Schritt-0-Beweise), `ergebnisse/entscheidungen.md` (GO + Implementierungs-Nachtrag); Bipperz P10 ❌; externe Struktur-Quelle nicht auffindbar → Design-Entscheidung.
