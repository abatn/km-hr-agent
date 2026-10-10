# Bewerbungs-Status (Application Lifecycle)

> **Stand:** September 2026
> **Zweck:** Status-Lebenszyklus für Bewerbungen (Kandidat bewirbt sich auf ausgeschriebene Stelle)
> **Gehört zu:** Skill `job-application` (Kandidaten-Seite) + Skill `employer-portal` Schritt 7 (Arbeitgeber-Seite)
> **Schema:** `applications` + `application_status_history` – siehe `knowledge/portal/employer-portal-fields.md`

---

## Status-Lebenszyklus einer Bewerbung

| Status | Beschreibung | Wer setzt ihn? | Kandidat sieht ihn? |
|---|---|---|---|
| `eingegangen` | Bewerbung abgeschickt (Default bei INSERT) | System (automatisch) | ✅ |
| `angesehen` | Arbeitgeber hat die Bewerbung geöffnet | Arbeitgeber | ✅ |
| `eingeladen` | Zum Vorstellungsgespräch eingeladen | Arbeitgeber | ✅ (+ Kontaktfreigabe beidseitig) |
| `abgelehnt` | Bewerbung abgelehnt | Arbeitgeber | ✅ (mit optionaler Begründung) |
| `eingestellt` | Kandidat wurde für die Stelle eingestellt | Arbeitgeber | ✅ |
| `zurückgezogen` | Kandidat hat die Bewerbung zurückgezogen | Kandidat | ✅ |

---

## Erlaubte Übergänge

```
eingegangen ──▶ angesehen ──▶ eingeladen ──▶ eingestellt
     │              │              │
     │              └──▶ abgelehnt ◀┘
     │
     └──▶ zurückgezogen (nur durch Kandidaten, jederzeit vor 'eingestellt')
```

| Von | Nach | Erlaubt? | Durch |
|---|---|---|---|
| `eingegangen` | `angesehen` | ✅ | Arbeitgeber |
| `eingegangen` | `abgelehnt` | ✅ | Arbeitgeber |
| `eingegangen` | `zurückgezogen` | ✅ | Kandidat |
| `angesehen` | `eingeladen` | ✅ | Arbeitgeber |
| `angesehen` | `abgelehnt` | ✅ | Arbeitgeber |
| `angesehen` | `zurückgezogen` | ✅ | Kandidat |
| `eingeladen` | `eingestellt` | ✅ | Arbeitgeber |
| `eingeladen` | `abgelehnt` | ✅ | Arbeitgeber |
| `eingeladen` | `zurückgezogen` | ✅ | Kandidat |
| `abgelehnt` | * | ❌ Endstatus (kein Übergang) | – |
| `eingestellt` | * | ❌ Endstatus (kein Übergang) | – |
| `zurückgezogen` | `eingegangen` (Reaktivierung) | ⚠️ Endstatus, **aber aufhebbar**: eine erneute Bewerbung setzt **dieselbe** Zeile auf `eingegangen` zurück (kein neuer Eintrag – `UNIQUE(candidate_id, job_id)`) | Kandidat |

**Regeln:**
- Jede Statusänderung wird in `application_status_history` protokolliert (Wer, Wann, optional Notiz).
- Bei `eingestellt`: Arbeitgeber sollte zusätzlich den Stellen-Status auf `besetzt` setzen (Skill `employer-portal` Schritt 6).
- Ablehnung sollte eine kurze, sachliche Begründung enthalten (optional, max. 500 Zeichen) – Fairness und AGG-Konformität.
- **Automatisierungs-Hooks (✅ implementiert, Phase 5, 12.09.2026):** Jeder Arbeitgeber-Übergang erzeugt automatisch einen Agent-Task in der Queue: `→ eingeladen` = `create_invitation` (VDO.Ninja-Raum + Fragen + ICS + Einladungs-Mail), `→ abgelehnt` = `send_rejection` (neutrale Absage-Mail, AGG-sicher), `→ eingestellt` = `onboarding_release`. Der Statuswechsel selbst bleibt manuell (Arbeitgeber-Entscheid) – nur die Nachfolge-Aktionen laufen automatisch.

---

## DSGVO-Regeln für Bewerbungen

| Regel | Umsetzung |
|---|---|
| Rechtsgrundlage | Art. 6(1)(b) DSGVO – Kandidat bewirbt sich aktiv (vorvertragliche Maßnahmen) |
| CV-Pflicht | Bewerbung nur mit hochgeladenem Lebenslauf (Kandidat-Status ≥ `lebenslauf_hochgeladen`) – entscheidet der Nutzer, bestätigt 11.09.2026 |
| Zweckbindung | Bewerbungsdaten nur für diesen Stellenprozess verwenden |
| Rückzug | Kandidat kann jederzeit zurückziehen → Status `zurückgezogen`; Profil wird danach für diese Stelle nicht mehr angezeigt |
| Wiederverwendung nach Rückzug | **P1-1, 30.09.2026 (Nutzerentscheid „Reaktivieren“)**: `zurückgezogen` ist die EINZIGE aufhebbare Endlage. Erneutes Bewerben setzt dieselbe `applications`-Zeile auf `eingegangen` (neuer `bewerbungstext`, neuer `aktualisiert_am`, zusätzlicher History-Eintrag) – kein INSERT, keine Doppelzeile. Alle übrigen Endstatus (`abgelehnt`, `eingestellt`) sperren weiterhin. Umsetzung: `webui/db.py` (Codemarke `def apply_to_job`, gemessen 10.10.2026); UI: `webui/pages/candidate.py` (Codemarke `def _tab_stellen`, gemessen 10.10.2026) („Erneut bewerben“). Tests: `tests/test_reapply_after_withdraw.py` |
| Löschung | Bewerbungsdaten werden 6 Monate nach Prozessende gelöscht (wie Kandidaten-Portal, siehe `gdpr-policy.md`) – **automatisch via DSGVO-Cleanup-Job, Phase 4.5 (siehe unten)** |

---

## DSGVO-Cleanup-Job (Phase 4.5, implementiert 11.09.2026)

| Regel | Beschreibung |
|---|---|
| **Prozessende** | Datum der letzten Statusänderung einer Bewerbung (`aktualisiert_am`) bei finalem Status (`abgelehnt`, `eingestellt`, `zurückgezogen`) |
| **Frist** | 6 Monate (183 Tage) nach Prozessende |
| **Was wird gelöscht** | Die `applications`-Zeile, alle zugehörigen `application_status_history`-Zeilen **und** passende `agent_tasks` (payload-`application_id`) sowie im zweiten Zweig `candidate_documents` + Dateien — **4 Tabellen** (`dsgvo_cleanup()`, Messung ⓘ08.10.2026; frühere Fassung nannte nur 2) |
| **Was bleibt** | Aktive Bewerbungen (`eingegangen/angesehen/eingeladen`) sind nie löschfähig; `candidates`/`employers`-Stammsätze bleiben (eigene Fristen, siehe `gdpr-policy.md`) |
| **Ausführung** | `dsgvo_cleanup()` läuft beim App-Start (ein Durchlauf pro Session, nach `set_page_config`, vor dem Login-Gate); fehlgeschlagener Lauf blockiert die App nicht (try/except + Log) |
| **Protokoll** | Ergebnis wird in `st.session_state['dsgvo_cleanup']` gehalten; gelöschte Zeilen werden gezählt und im Log vermerkt |
| Ablehnungs-Begründung | Freiwillig für den Arbeitgeber; darf KEINE Diskriminierungsmerkmale enthalten (AGG §1) |
| Anonymisierung | Bewerbung erscheint beim Arbeitgeber als Pseudonym ("Kandidat #N") – Kontaktdaten erst nach `eingeladen` (gleiche Freigabe-Logik wie Matching-Liste, siehe `employer-portal-fields.md`) |

---

## Bewerbungs-Voraussetzung (CV-Pflicht)

- Bewerben setzt Kandidat-Status ≥ `lebenslauf_hochgeladen` voraus (gleiche Schwelle wie Matching, siehe `instructions.md` Profil-Check).
- Ohne CV: Stellenangebote können angeschaut, aber nicht beworben werden – UI zeigt Hinweis "Bitte zuerst Lebenslauf hochladen (Upload oder Candidate Portal)".

---

## Eigenbewerbung / Double-Apply-Schutz

- `UNIQUE(candidate_id, job_id)` in der Tabelle `applications` verhindert Doppelbewerbungen.
- Eine zweite Bewerbung auf dieselbe Stelle zeigt dem Kandidaten seinen bestehenden Status statt eines Fehlers.
- Nach `abgelehnt` oder `eingestellt` ist eine erneute Bewerbung auf dieselbe Stelle **nicht** möglich, solange der Eintrag existiert (Datenminimierung); die Stelle muss ggf. neu ausgeschrieben werden. Nach `zurückgezogen` IST sie dagegen möglich — genau das ist die Reaktivierung P1-1 (siehe nächste Sektion). *(Korrektur R3-2, 30.09.2026: zuvor stand hier fälschlich auch `zurückgezogen` als gesperrt, was der P1-1-Umsetzung widersprach.)*

---

## Reaktivierung → Re-Queue der Agent-Kette (R3-2, 30.09.2026)

**Regel:** „Erneut bewerben“ nach `zurückgezogen` queue't die Bewerberkette **erneut** — mit neuer Generation `gen`. Ohne Generation hätten Dedupe (Tag + Typ + Application) und der notify_hr-Guard die Neubewerbung geschluckt: HR käme die Ergebnis-Mail nie wieder.

| Schritt | Verhalten | Codestelle |
|---|---|---|
| Reaktivierung | dieselbe `applications`-Zeile auf `eingegangen`, History-Eintrag, **kein** `return` mehr vor dem Queue-Block | `webui/db.py` (gemessen 10.10.2026) |
| Generation berechnen (vor `conn.close()`) | Reaktivierung: `gen = MAX(COALESCE(json_extract(payload,'$.gen'),0)) + 1` über alle Tasks der Application; frischer INSERT: `gen = 0` | `webui/db.py` (gemessen 10.10.2026) (reaktiviert) (frisch) |
| Queue-Payload | alle Kettentasks derselben Bewerbung tragen `"gen": gen` | `webui/db.py` (gemessen 10.10.2026) |
| Dedupe | `queue_agent_task` prüft Tag + Typ + Application **+ Generation** (`AND COALESCE(json_extract(payload,'$.gen'),0) = ?`): gleicher Tag mit neuem `gen` wird gequeued, gleiches `gen` weiterhin geduped | `webui/db.py` (Codemarke `def queue_agent_task`, gemessen 10.10.2026) |
| notify_hr-Guard | `_maybe_gatekeeper` bewertet nur die höchste Generation der Application; ein alter notify_hr-Marker einer früheren Generation blockiert die neue Auswertung **nicht**, zweiter Sweep derselben Generation bleibt idempotent | `scripts/agent-runner.py` (Codemarke `def _maybe_gatekeeper`, gemessen 10.10.2026) |

- **Altbestand ohne `gen`-Feld:** `COALESCE(…, 0)` liest Bestands-Tasks als Generation 0 → Verhalten für Bestandsdaten unverändert.
- **Design-Entscheidung (30.09.2026, keine externe Quelle):** Die Reaktivierung queue't dieselben Task-Typen wie die Erstbewerbung (eine Codepfad-Quelle, `webui/db.py` (Codemarke `def apply_to_job`, gemessen 10.10.2026)). Die erneute Eingangsbestätigung (`send_confirmation`) gilt als **Bestätigung der Neubewerbung**, nicht als Störmail.
- **Tests:** `tests/test_r32_gatekeeper_gen.py` (gen 0 → gen 1 → gen 2, **eine** `applications`-Zeile, History `eingegangen → zurückgezogen → eingegangen`), `tests/test_reapply_after_withdraw.py` (Reaktivierungs-Guards bleiben grün), `tests/test_application_id_match.py` (Quelltext: genau ein `return app_id`, erst nach dem Queue-Block).

---

*Erstellt am 11.09.2026 für den KM-HR-Agenten (Phase 1: Job-Seeker-Flow).*
