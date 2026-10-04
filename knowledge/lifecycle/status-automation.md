# Status-Automation: Whitelist + „angesehen"-Auto-Setzer (B2-5)

> **Stand:** 25.09.2026
> **Zweck:** (a) Statusübergänge strikt an die Whitelist `ALLOWED_TRANSITIONS` binden – auch in den Modal-Handlern; (b) Auto-Setzer für `angesehen` (NEUE Design-Entscheidung, Feature-Freeze/GO-pflichtig).
> **Gehört zu:** Skill `employer-portal` Schritt 7 · `knowledge/lifecycle/application-status.md` („Erlaubte Übergänge", `:23-55`) · Agent-Hooks `knowledge/system/agent-automation.md`
> **Status:** **Geteilt, ehrlich: Teil (a) (Whitelist-Guard `_legal` + 3 Modal-Call-Sites) UMGESETZT 25.09.2026 nach GO B2-5a; Teil (b) (Auto-Setzer „angesehen") weiterhin OFFEN/GO-pflichtig. Nachweis `ergebnisse/entscheidungen.md` B2-RUNDE L1/L4 — `tests/e2e_transition_guard.py` PASS (Teil a).**

---

## (a) Ist-Zustand NiceGUI (verifiziert 25.09.2026)

### Whitelist – an **einer** Stelle gebunden, an **einer** Stelle tot
| Datei:Zeile | Befund |
|---|---|
| `webui/pages/employer.py:369` | `AKTIV = ("eingegangen", "angesehen", "eingeladen")` |
| `webui/pages/employer.py:373-374` | `erl = {"eingegangen": ["angesehen", "abgelehnt"], "angesehen": ["eingeladen", "abgelehnt"], "eingeladen": ["eingestellt", "abgelehnt"], "eingestellt": [], "abgelehnt": [], "zurückgezogen": []}` |
| `webui/pages/employer.py:377-378` | `_hook_task = {"eingeladen": "create_invitation", "abgelehnt": "send_rejection", "eingestellt": "onboarding_release"}` |
| `webui/pages/employer.py:404` | `naechste = erl.get(a_status, [])` → **Whitelist-getriebene Button-Darstellung** |
| `webui/pages/employer.py:418` / `:421` / `:443` | `for ns in naechste:` → `def make_transition(...)` → `ui.button(f"→ {ns}", on_click=make_transition())` – Übergang nur über Whitelist-Button |
| `webui/pages/employer.py:574-578` | `ALLOWED_TRANSITIONS = {"eingegangen": {"angesehen","abgelehnt"}, "angesehen": {"eingeladen","abgelehnt"}, "eingeladen": {"eingestellt","abgelehnt"}}` |
| **`grep -n "ALLOWED_TRANSITIONS" webui/pages/employer.py`** | **genau 1 Treffer = die Definition bei `:574`** → **toter Code, nirgends gelesen** |
| `webui/pages/employer.py:580-586` | `def _active_app_ids(cid: int)` … `AND a.status IN ('eingegangen', 'angesehen', 'eingeladen')` – liefert nur aktive IDs, **keinen Statuswert** |
| `webui/pages/employer.py:608-626` | `def do_invite():` → `UPDATE applications SET status='eingeladen' …` (`:622`, History `:623`) – **kein Whitelist-Check gegen den Ausgangsstatus** |
| `webui/pages/employer.py:640-652` | `def do_reject():` → `UPDATE applications SET status='abgelehnt' …` (:648) – kein Check |
| `webui/pages/employer.py:665-676` | `def do_hire():` → `UPDATE applications SET status='eingestellt' …` (:674) – kein Check |
| `webui/pages/admin.py:541` / `:572` | Admin-Ebene spiegelt dieselbe Whitelist (`erl` / `naechste = erl.get(...)`) – **hier ebenfalls kein `ALLOWED_TRANSITIONS`-Guard** |

**Konkrete Lücke:** Über die drei Modal-Buttons in `_page_match` sind Sprünge möglich, die die Whitelist verbietet, z. B.
`eingegangen → eingestellt` (überspringt `angesehen` und `eingeladen`) oder `eingegangen → eingeladen` (überspringt `angesehen`). `_active_app_ids` verhindert das nicht – es filtert nur auf Status ∈ AKTIV.

### „angesehen"-Auto-Setzer – existiert **nirgends**
| Suche | Ergebnis (25.09.2026) |
|---|---|
| `grep -rn "UPDATE applications SET status='angesehen'\|status='angesehen'" app.py` | **0 Treffer** |
| `grep -rn "angesehen" webui/pages/*.py webui/db.py webui/logic.py` | nur Konstanten/Badges/Whitelist-Ziele (`employer.py:369,373,375,376,575,576,586,1162,1164,1168`; `admin.py:537,541,543`; `candidate.py:474,483`) – **kein Schreibzugriff** |
| `app.py:3742` | `bew_actions = ["(keine Änderung)", "angesehen", "eingeladen", "abgelehnt", "eingestellt"]` → **nur manuelle Aktion im Selectbox-Pfad** |

**Fazit (a):** Whitelist ist an der Button-Seite (`_page_stellen`) gebunden, in den Modals (`_page_match`) **nicht**. Ein Auto-Setzer für `angesehen` fehlt in **beiden** Codebasen.

---

## (b) Paritätsbeleg `app.py` (verifiziert 25.09.2026)

| Zeile | Zitat |
|---|---|
| `app.py:3136-3137` | `erl_hr = {"eingegangen": ["angesehen", "abgelehnt"], "angesehen": ["eingeladen", "abgelehnt"], "eingeladen": ["eingestellt", "abgelehnt"], "eingestellt": [], "abgelehnt": [], "zurückgezogen": []}` (genutzt `app.py:3168` `naechste = erl_hr.get(a_status, [])`, Buttons `app.py:3186-3192`) |
| `app.py:3742` | `bew_actions = ["(keine Änderung)", "angesehen", "eingeladen", "abgelehnt", "eingestellt"]` – **nur manuelle Auswahl** |
| `app.py:3761-3765` | `allowed_transitions = { "eingegangen": {"angesehen", "abgelehnt"}, "angesehen": {"eingeladen", "abgelehnt"}, "eingeladen": {"eingestellt", "abgelehnt"}, }` (Zeile `:3762` = `"eingegangen": {"angesehen", "abgelehnt"},`) |
| `app.py:3766-3768` | `if neue_bew_status in allowed_transitions.get(app_status, set()):` → `UPDATE applications SET status=? …` → `INSERT INTO application_status_history …` |
| `app.py:3192-3193` | HR-Sicht-Button-Pfad: `UPDATE applications SET status = ? … WHERE id = ?` + History mit `changed_by='arbeitgeber_hr_seite'` – **hier kein zweiter Check** (Whitelist steckt im Rendering) |

**Paritäts-Befund (ehrlich):**
- **(a) Whitelist-Guard** hat eine Streamlit-Entsprechung: `app.py:3761-3766` (Selectbox-Pfad). Der Button-Pfad `app.py:3189-3192` prüft ebenso wenig explizit wie NiceGUI – dort steckt die Whitelist im Rendering. NiceGUI `ALLOWED_TRANSITIONS` (`:574`) ist die portierte Entsprechung zu `app.py:3761`, **wurde aber nie eingehängt**.
- **(b) Auto-Setzer `angesehen`** hat **keine** Streamlit-Entsprechung: `app.py:3742` ist eine manuelle Selectbox-Option; nirgends wird `angesehen` automatisch gesetzt.

---

## (c) Soll-Zeilen für den Code-Edit (KEIN Eingriff in B1 – nur Plan)

### (c-a) Whitelist-Anbindung
1. `webui/pages/employer.py::_page_match` – `ALLOWED_TRANSITIONS` (`:574`) als echte Guard-Funktion, z. B. direkt darunter:
   `_def _legal(new_status: str, app_id: int) -> bool_` → `SELECT status FROM applications WHERE id = ?` → `new_status in ALLOWED_TRANSITIONS.get(old, set())`.
2. `do_invite()` (`:608`): vor `UPDATE` (`webui/pages/employer.py:622`) `if not _legal("eingeladen", app_id): ui.notify(...); return`.
3. `do_reject()` (`:640`): vor dem `UPDATE` (`:648`) je ID prüfen (`abgelehnt` ist aus AKTIV-Sicht immer legal, aber der Check macht die Absicht explizit).
4. `do_hire()` (`:665`): vor `UPDATE` (`:674`) `if not _legal("eingestellt", app_id): …` → verhindert `eingegangen → eingestellt`.
5. Alternativ (weniger Code): `_active_app_ids()` (`:580`) um den Status erweitern und den Guard dort zentral legen – **Design-Entscheidung**.
6. `webui/pages/admin.py:572` (Admin-Pfad) **mitziehen**, sonst entsteht ein Bypass; `webui/pages/employer.py:421 make_transition()` bleibt unverändert (Rendering-Guard ist bereits korrekt).

### (c-b) „angesehen"-Auto-Setzer — **NEUE Design-Entscheidung, kein Code in B1**
Vorschlag zur Spezifikation (Ziel: `changed_by = 'system'`, Einmaligkeit, kein Endstatus-Überschreiben):
- Einfügestelle 1: `webui/pages/employer.py::_page_stellen`, Kandidaten-/Bewerber-Card wird gerendert (ab `:390`) → einственный
  `UPDATE applications SET status='angesehen', aktualisiert_am = CURRENT_TIMESTAMP WHERE id = ? AND status='eingegangen'` + `INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'angesehen', 'system')`.
- Einfügestelle 2 (Alternative): `webui/pages/employer.py::_page_match.match_content()` beim Rendern der ersten Job-Klappe eines Kandidaten (`:767`-Schleife).
- **Nicht** setzen bei `abgelehnt`/`zurückgezogen` (Endstatus) – Bedingung `AND status='eingegangen'` deckt das ab.
- Ergebnis: `angesehen` erscheint in der Kandidaten-Historie automatisch; die Whitelist `erl` (`:373`) kann danach `angesehen → eingeladen` anbieten, ohne dass HR erst manuell „→ angesehen" klicken muss.

---

## (d) Quelle je Zahl / Regel

| Wert / Regel | Quelle |
|---|---|
| Whitelist-Inhalt `eingegangen:{angesehen,abgelehnt}` / `angesehen:{eingeladen,abgelehnt}` / `eingeladen:{eingestellt,abgelehnt}` | `knowledge/lifecycle/application-status.md:23-55` („Erlaubte Übergänge") + **Parität** `app.py:3136` / `app.py:3761-3765` |
| Endstatus `abgelehnt` / `eingestellt` / `zurückgezogen` (kein Übergang) | `knowledge/lifecycle/application-status.md:44-46` |
| Jede Statusänderung wird in `application_status_history` protokolliert | `knowledge/lifecycle/application-status.md:49` |
| Agent-Hooks je Übergang (`create_invitation` / `send_rejection` / `onboarding_release`) | `knowledge/lifecycle/application-status.md:52` + `knowledge/system/agent-automation.md` · Umsetzung `webui/pages/employer.py:377-378` |
| Variante A: Agent lädt nie von selbst ein/ab, nur nach HR-Klick | `knowledge/system/agent-automation.md` (user-approved 12.09.2026) |
| **(a)** Guard gegen den Ausgangsstatus in den Modals | **Parität** `app.py:3761-3766` – daher **kein** neues Konzept; die Entscheidung, *welche* NiceGUI-Stelle den Guard bekommt ((c)1 vs. (c)5), ist **Design-Entscheidung** |
| **(b)** Auto-Setzer `angesehen` | **NEUE Design-Entscheidung** – `app.py:3742` belegt **nur** eine manuelle Aktion; kein Auto-Setzer in `app.py` oder `webui/`. Keine externe Quelle, kein Gesetz, keine Studie. |
| Auslöser-Punkt für den Auto-Setzer ((c)-Einfügestelle 1 vs. 2), `changed_by='system'`, Bedingung `AND status='eingegangen'` | **Design-Entscheidung** (offen, Teil des B2-5-Go) |
| DSGVO-Gate für HR-Dokumenten-Ansicht: Sichtbarkeit nach `eingeladen`/`eingestellt` der spezifischen Bewerbung beim Arbeitgeber | **Parität** `knowledge/legal/dsgvo-gate.md` – siehe `webui/pages/employer.py::_page_dokumente()`
| Feature-Freeze-Pflicht vor Code | `knowledge/lifecycle/relocation.md:5` („Umsetzung erfordert User-Go (Feature-Freeze, siehe `ergebnisse/entscheidungen.md:1397`)") und `knowledge/lifecycle/relocation.md:91` („**Vor** Code: User-Go (Feature-Freeze `entscheidungen.md:1397`)") · wörtlich in `ergebnisse/entscheidungen.md:1397`: „**STOPP — User wählt Option(en). Kein Code ohne Go. Feature-Freeze intakt.**" |

---

## (e) Auswirkung + GO-Bedarf

**GO-Bedarf: B2-5, gesplittet in (a) und (b) – beide eigenständig freigeben.**

**(a) Whitelist-Anbindung — B2-5a**
- **Was HR jetzt kann:** Über die drei Modal-Buttons auf `📄 Match-Ergebnis` ungültige Sprünge auslösen (`eingegangen → eingestellt`, `eingegangen → eingeladen`) – die Historie protokolliert den Sprung dann so, als wäre er regulär.
- **Was HR nach GO sieht:** Ungültige Sprünge werden mit `ui.notify` abgewiesen; es ändert sich **nur im Fehlerfall** etwas. Die Button-Seite `💼 Stellenangebote` (`erl`-Buttons) bleibt unverändert.
- **Warum trotzdem GO:** Der Guard **entzieht** bisherige (falsche) Möglichkeiten; auch wenn die UI-Oberfläche unverändert aussieht, ändert sich das erlaubte Verhalten → B2-Nummer statt stiller Änderung.

**(b) „angesehen"-Auto-Setzer — B2-5b (NEUE Design-Entscheidung)**
- **Was HR jetzt sieht:** `angesehen` muss per Hand gesetzt werden (NiceGUI-Button „→ angesehen" in `erl`, `webui/pages/employer.py:373/443`; Streamlit-Select `app.py:3742`). Bis dahin steht die Bewerbung auf `eingegangen`, obwohl HR sie längst geöffnet hat.
- **Was HR nach GO sieht:** Beim Öffnen einer Bewerbung/Detailansicht springt der Status automatisch auf `angesehen` (Historie-Eintrag `changed_by='system'`); die nächste Whitelist-Stufe `→ eingeladen` steht sofort bereit. Für den Kandidaten ändert sich nur die Statusanzeige (`👁️ angesehen`).
- **Warum neu und nicht Parität:** `app.py:3742` belegt ausschließlich eine **manuelle** Aktion; es gibt in keiner Codebasis einen Auto-Setzer. Zusätzlich **Automatisierung ohne HR-Klick** → bricht sichtbar mit dem Muster „nur der HR-Klick triggert den Agenten" (Variante A), auch wenn hier **kein** Agent-Task entsteht, sondern nur ein DB-Status.
- **Feature-Freeze:** Bevor Code entsteht, gilt derselbe Freezenotiz-Mechanismus wie in `knowledge/lifecycle/relocation.md:5`/`:91` → **User-Go nötig** (`ergebnisse/entscheidungen.md:1397`).

---

## (f) Testplan

- **Unit:** `pytest` (26 Tests) – muss grün bleiben (die 26 enthalten `test_send_rejection_guard.py` / `test_send_onboarding_guard.py` als Guards des Variante-A-Musters; **kein** Whitelist-/Auto-Setzer-Test).
- **E2E (realer Dateinamen-Check `ls tests/e2e_*.py`):**
  - **für (a):** `tests/e2e_invitation_termin.py` – „Einladungs-Termin fließt in `create_invitation`-Payload" (`/employer/stellen`-Pfad): Regression, dass der Guard die legitime `angesehen → eingeladen`-Einladung nicht blockiert. `tests/e2e_invitation_termin_admin.py` – dasselbe auf dem Admin-Pfad (`webui/pages/admin.py:572`), Regression dass (c)6 mitgezogen wurde.
  - **für (a):** `tests/e2e_housing.py` – HR-Klick „Einstellen" → `onboarding_release`: Regression, dass `do_hire` bei **legalem** Übergang (`eingeladen → eingestellt`) weiter funktioniert.
  - **für (b):** `tests/e2e_apply_dialog.py` – DB-Baseline `applications`/`agent_tasks` vor/nach Rendering: Regression, dass ein **reines Rendern** der Stellen-Liste **keinen** unerwarteten Status schreibt, solange B2-5b nicht aktiv ist (und nach GO: dass genau **ein** `angesehen`-Eintrag entsteht, `changed_by='system'`, kein Agent-Task).
  - **für (b):** `tests/e2e_vorgemerkt.py` – Feedback-Flow mit DB-Restore als Restaurationsschema für einen künftigen Auto-Setzer-Test.
- **Testlücke (ehrlich):** Kein vorhandenes E2E prüft (i) den ungültigen Sprung `eingegangen → eingestellt` oder (ii) einen Auto-Setzer. Nach GO sind **neu**: `tests/e2e_transition_guard.py` (ungültiger Sprung abgewiesen, gültiger durchgeht, Historie korrekt) und Erweiterung um einen `angesehen`-Auto-Setzer-Fall. **In B1 nicht angelegt** (kein Code, kein Test ohne GO).
