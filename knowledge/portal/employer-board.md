# Arbeitgeber-Hiring-Board (Phase 1)

> **Status (15.10.2026):** Durchlauf 1 umgesetzt: Board mit 4 Spalten, Reiter Aktiv/Passiv, Navigation mit 4 Punkten, „Mehr“-Seite. **Offen (Durchlauf 2):** rechtes Detail-Panel (Drawer) und Kartenaktionen im Board.
> **Zielcode:** `webui/pages/employer.py` (Codemarken: `ALLOWED_TRANSITIONS`, `_legal_actions`, `_BOARD_COLUMNS`, `_board_rows`, `_page_board`, `_page_mehr`, `_menu_items_emp`, `PAGE_MAP`, `SIDEBAR_KEYS`, `_list_candidates`, `anzeige_name`).

## 1. Ziel und Quelle

Die Bewerberbearbeitung soll auf **ein** Board (Spalten nach Bewerbungsstatus) statt mehrerer Einzelseiten zeigen. Die Sidebar zeigt 5 Punkte statt 12 (Stand 16.10.2026; 4 Punkte seit 15.10.2026).

**Muster-Quellen**

- Progressive Disclosure: Nielsen, „Progressive Disclosure“, NN/g (03.12.2006), https://www.nngroup.com/articles/progressive-disclosure/ — wenige wichtige Optionen zuerst, Details auf Anforderung.
- ATS-Kontext: Eleken, „Applicant Tracking System Design“ (aktualisiert 12.03.2026), https://www.eleken.co/blog-posts/applicant-tracking-system-design-how-to-make-recruitment-better-for-everyone — beschreibt Kandidaten-Tracking über Recruiting-Stufen. Konkrete Kanban-Spalten werden dort **nicht** festgelegt.

**Design-Entscheidung (nicht gemessen):** Spalten folgen der bestehenden Statusmaschine (§2), nicht einem externen Standard. Die 5 Menüpunkte (Stand 16.10.2026) und die Klick-Ziele (§6) sind ebenfalls Design-Entscheidungen.

## 2. Spalten = `ALLOWED_TRANSITIONS`

Quelle: `ALLOWED_TRANSITIONS` (Codemarke) und `_BOARD_COLUMNS` (Codemarke, Spaltenzuordnung).

| Spalte (Code) | Status in `applications.status` | Erlaubte Folgeschritte laut `_legal_actions` |
|---|---|---|
| Eingegangen | `eingegangen` | Als angesehen markieren · Ablehnen |
| Angesehen | `angesehen` | Einladen · Ablehnen |
| Eingeladen | `eingeladen` | Einstellen · Ablehnen |
| Abschluss | `eingestellt` und `abgelehnt` (final) | keine |

Regeln:

- Das Board hat **4 Spalten**. Die finalen Status `eingestellt` und `abgelehnt` teilen sich die Spalte „Abschluss“.
- Die erlaubten Folgeschritte kommen aus `_legal_actions` (Reihenfolge `_MATCH_ACTION_ORDER`). Es gibt keine zweite Whitelist.
- Der Guard `_legal` (Closure in `_page_match`) prüft den Status in der DB erneut, bevor geschrieben wird.
- `zurückgezogen` erscheint nicht im Board (siehe `knowledge/lifecycle/application-status.md`).

## 3. Kartenaktionen (Ist-Stand und offen)

**Ist-Stand:** Jede Bewerbungskarte zeigt die erlaubten Folgeschritte als Text und einen Button „Im Match öffnen“ (Sprung auf die Match-Seite). Die Schreibaktionen (Einladen, Ablehnen, Einstellen) laufen dort über die bestehenden Dialoge `_open_invite`, `_open_reject`, `_open_hire` samt `_notify_statuswechsel`. Diese **drei Match-Dialoge bleiben exklusiv auf der Match-Seite** (gemessen 16.10.2026); die Seite Einladungen öffnet für das Einladen eine **eigene Instanz desselben Mechanismus** (Entscheidung unten).

**Entscheidung 16.10.2026 (Iteration „Einladungen“, Nutzerbefehl) — umgesetzt 16.10.2026:** Die Seite **Einladungen** (`/employer/einladen`, Codemark-Kette `_page_einladen` → `_ein_send_invite` / `_ein_mark_seen`) ist die **dritte Aufrufstelle des GLEICHEN Mechanismus** — Whitelist-Guard `ALLOWED_TRANSITIONS`, Status-History (`changed_by 'arbeitgeber'`), `queue_agent_task("create_invitation")`; ein eigener Mail-/Status-Codezweig ist verboten. **Kein DB-Schema-Change.** Kartenschnellaktionen bleiben damit erlaubt, solange sie nur den bestehenden Mechanismus aufrufen (Ist: `do_invite` Match-Dialog, `make_transition` Stellenangebote, `_ein_send_invite` Seite Einladungen).

**Entscheidung + Umsetzung 16.10.2026 (UX-Korrektur auf Nutzerbefehl, Messdatum 16.10.2026):** Die Seite **Einladungen** nutzt für das Einladen **dasselbe Dialog-MECHANISMUS wie die Match-Seite — gleicher Mechanismus, EIGENE Instanz**. Neue Marker: `_ein_ctx` (Context-Dict, Gegenstück zu `_invite_ctx`), `_ein_dialog` (`ui.dialog`-Instanz), `_ein_confirm` (Bestätigungs-Handler, Gegenstück zu `do_invite`), `_ein_open_confirm` (Öffner, Gegenstück zu `_open_invite`). Der Karten-Button „Einladen“ öffnet **nur noch** diesen Dialog (C1-Muster der Match-Seite): Klartext-Frage mit Pseudonym + Stellentitel, Termin-Widgets `ui.date`/`ui.time` **MIT Defaults (morgen 10:00/30) IM Dialog**, Fehler-Label im Dialog, Aktionen „Abbrechen“ und „Einladen“. **Erst der Bestätigen-Klick führt `_ein_send_invite` aus** — der Schreibpfad bleibt damit `_ein_send_invite` (**dritte Aufrufstelle des gleichen Mechanismus, kein zweiter Schreibpfad**, kein zweiter Mail-/Status-Codezweig, kein DB-Schema-Change). Zusätzlich Kontext-Link „Match-Seite öffnen“ → `ui.navigate.to(f"/employer/match?kandidat={cid}")`. **Die drei Match-Dialoge `_open_invite` / `_open_reject` / `_open_hire` bleiben exklusiv auf der Match-Seite** — von der Einladungen-Seite weder wiederverwendet noch geklont. Der bisherige Direkt-Invite der Karte (Widgets + Button ohne Dialog) ist damit **entfernt**; Klick-Folge und IST-Nachweis: §6 (Soll 3 statt 2, E2E-Messung folgt in S5).

## 4. Drawer (rechtes Detail-Panel) — offen

**Ist-Stand:** Nicht implementiert. Es gibt kein `ui.right_drawer` im Board. Karten führen auf die Match-Seite.

**Soll (Durchlauf 2):** Muster `ui.right_drawer` aus `webui/components.py` (Codemarke: `notifications_drawer`-Funktion). Der Drawer zeigt die gewählte Bewerbung mit Profil (Pseudonym bzw. Klarname nach §5), Agent-Status, Dokumenten-Sichtbarkeit nach Status, Visum-Hinweis, Feedback-Verlinkung und Kontext-Links.

## 5. Aktive vs. passive Kandidaten (zwei Reiter)

Das Board hat die Reiter **Aktiv** und **Passiv**.

- **Aktiv (Board):** nur Bewerbungen aus §2. Anzeige über `anzeige_name`: Klarname erst ab Status `eingeladen` (`DOC_RELEASE_STATUS`), sonst „Kandidat #N“.
- **Passiv (Liste):** Kandidaten mit Lebenslauf ohne Bewerbung bei diesem Arbeitgeber. Die Karte zeigt das Pseudonym „Kandidat #N“, Skills und die Schaltfläche „Im Kandidaten-Profil öffnen“ (Sprung auf `/employer/kandidaten`). Es gibt **keine** Schreibaktion.
- **„Zu Stelle zuordnen“ entfällt in Phase 1.** Es würde im Namen des Kandidaten eine echte Bewerbung anlegen. Die Rechtsgrundlage dafür ist nicht geklärt (Art. 6(1)(b) knüpft an die Bewerbung des Kandidaten an). Entscheidung und Begründung: `ergebnisse/entscheidungen.md`.

**DSGVO-Regel für Passive und frühe Bewerber** (`knowledge/portal/employer-portal-fields.md`, Abschnitt „Kandidaten-Sichtbarkeit“ und „Bewerber-Sichtbarkeit“):

- Passive Kandidaten zeigen nur das Pseudonym „Kandidat #N“, Skills, Erfahrung, Sprachen, Standort-Region und Match-Score.
- Kein Klarname, keine Kontaktdaten, kein Zugriff auf die Lebenslauf-Datei.

**Umgesetzt (15.10.2026):** `_list_candidates` liefert für alle Zeilen das Pseudonym über `anzeige_name` (passive Kandidaten: immer Pseudonym; Bewerber: Klarname nur ab `eingeladen`). Die Suche filtert weiterhin auf dem Klarnamen, damit die Suche funktioniert. Das Board und die Kandidaten-Seite greifen auf dieselbe Logik zurück.

**Offen (eigener Befund, nicht Teil dieses Fixes):** Die Match-Seite (`_page_match`, Liste mit `name or _("Unbekannt")`) und die Feedback-Seite (`_page_feedback`, gleiche Ausgabe) zeigen Klarnamen unabhängig vom Status. Das muss separat entschieden und behoben werden.

### Passiv-Filter (Specschild, 16.10.2026)

**MD-first (Lab-Schritt 2):** Diese Spez steht **vor** dem Code-Edit der Iteration „Hiring-Board Passiv-Filter" — Zielcode `webui/pages/employer.py`, Reiter **Passiv** in `_page_board`. Stand 16.10.2026: weder die `_pf_*`-Marker noch `tests/e2e_board_passiv_filter.py` existieren (geprüft 16.10.2026 → `grep -n "_pf_" webui/pages/employer.py` = 0 Treffer); das Specschild ist damit die Soll-Spezifikation, der Build-Nachweis folgt.

- **Stellen-Wähler + Default:** ein Stellen-Wähler mit Default **„Alle Stellen"** = **bester Job je Kandidat (Score DESC)** — 1:1-Parität des Passiv-Blocks der Match-Seite (Codemark `_passive_best`, `knowledge/portal/matching-filter.md` Abschnitt (g)). Bei konkreter Stellen-Wahl wird derselbe Job als Score-Kontext je Kandidat genutzt.
- **Filter-Sets und Semantik:**
  - **Mindest-Score:** Bänder **90 / 75 / 60 / 40** plus **„Alle"** (Default „Alle"). Band = Mindestwert: sichtbar bleibt Score ≥ Band.
  - **Mindest-Erfahrung:** Bänder **2 / 5 / 10 Jahre** plus **„Alle"** (Default „Alle").
  - **Sprache:** **Alle / DE / EN / FR** (FR-Band 18.10.2026, Nutzer-GO FR-only) — **DE** = `candidates.deutsch` nicht leer, **EN** = `candidates.englisch` nicht leer, **FR** = `candidates.franzoesisch` nicht leer (Formulierung 18.10.2026 geglättet: „nicht leer" statt „nicht NULL", weil der Code trimmt). FR-Kandidaten erscheinen nur, solange der Passiv-Pool sie enthält; die Karte zeigt weiterhin nur DE · EN (bewusst).
  - Filter kombinieren UND-förmig (alle gesetzten Filter müssen erfüllt sein). Filterung passiert **nur auf der Gate-Menge**: Filter ⊆ Menge ohne Filter.
- **Gate = nur echte Treffer (Parität):** ≥ 1 Must-Have-Skill-Treffer **und** ≥ 50 % der geforderten Erfahrung — **1:1-Parität** zu `_passive_best` / `knowledge/portal/matching-filter.md` Abschnitt (g) (Regeltext dort, hier nicht kopiert). **Nicht-Treffer werden auch bei gesetzten Filtern verworfen** — ein Score-Band allein zieht keinen Kandidaten über das Gate.
- **Score-Anzeige je Karte:** „Passung X/100". Score wird über **`logic.berechne_match_score` wiederverwendet** — kein Zweitschreibpfad, **kein Schema-Change**, `webui/logic.py` unangetastet, **rein lesend**.
- **Karteninhalt:** Pseudonym **`anzeige_name(name, id, None)`** + Skills + Erfahrung + Sprachen + Standort + Score. **DSGVO-Vermerk:** Passive bleiben **immer Pseudonym** — kein Klarname, keine Kontaktdaten, keine Schreibaktion (Pseudonym-Regel = DSGVO-Regel oben, Quelle `knowledge/portal/employer-portal-fields.md`, Abschnitte „Kandidaten-Sichtbarkeit“/„Bewerber-Sichtbarkeit“; DSGVO-Spec `knowledge/legal/dsgvo-gate.md`); keine Lebenslauf-Datei (Dokumenten-Gate erst ab Status `eingeladen`, `knowledge/legal/dsgvo-gate.md`).
- **Neue Code-Marker:** `_pf_jobs` (Stellen-Wähler-Daten), `_pf_pool` (Passiv-Pool), `_pf_state` (Filterzustand), `_pf_view` (gerenderte Sicht) — Soll-Nennung, Umsetzung 16.10.2026.
- **E2E-Nachweis:** `tests/e2e_board_passiv_filter.py` (Gate-Negativ, Score-DESC relativ, Filter ⊆ Menge ohne Filter, residue 0 + sha256 gleich) — **Lauf folgt in S5** (Nachweis folgt in S5; keine Messwerte hier).

**Kennzeichnung nach Lab-Schritt 1 — Design-Entscheidungen 16.10.2026 (Nutzerbefehl, keine externe Quelle):** (1) Stellen-Wähler-Default **„Alle Stellen"** = bester Job je Kandidat (Score DESC), (2) Score-Bänder **90 / 75 / 60 / 40**, (3) Erfahrungs-Bänder **2 / 5 / 10 Jahre**, (4) Sprach-Semantik **DE/EN = Level nicht leer** (18.10.2026 geglättet, weil der Code trimmt; **FR**-Band 18.10.2026 ergänzt — Nutzer-GO FR-only). Für diese vier Werte gibt es **kein Gesetz, keine Studie, keine offizielle Dokumentation** — sie sind ausdrücklich als Design-Entscheidung gekennzeichnet, nicht als belegte Norm. Die Gate-Regel (≥ 1 Must-Have + ≥ 50 %) ist dagegen die bestehende Projektregel aus `matching-filter.md` Abschnitt (g).

## 6. Navigation

- Sidebar: **5 Punkte** — Dashboard · Stellenangebote · Hiring-Board · Einladungen · Mehr (Stand 16.10.2026; Codemarke: `SIDEBAR_KEYS`, `_menu_items_emp`).
- **Mehr** (`_page_mehr`): Liste aller übrigen Seiten (Firmenprofil, Portal, Kandidaten-Suche, Match, Compliance, Agent-Details, Dokumente, Pre-Screen, Onboarding, Feedback — 10 Seiten, gemessen 16.10.2026). Design-Entscheidung nach NN/g, damit keine Seite verloren geht.
- Sub-Routen `/employer/<key>` bleiben erhalten (Deep-Links aus E2E und Benachrichtigungen). `PAGE_MAP` bleibt vollständig (Codemarke: `PAGE_MAP`).

**Klick-Ziele (Ziele = Design-Entscheidung; Werte = Messung 15.10.2026, Playwright, isoliert):**

Zählt echte Klicks vom Dashboard nach dem Login bis zum Zielzustand. Vorher = `HEAD` (12 Sidebar-Punkte), Nachher = Ist-Stand am Messtag (4 Sidebar-Punkte; IST Stand 16.10.2026: 5 Sidebar-Punkte). Einladen-Zielzustand = Bewerbung in der Spiegel-DB auf `eingeladen`.

| Ablauf | Vorher (gemessen) | Nachher (gemessen) | Ziel | Ergebnis |
|---|---|---|---|---|
| Stelle ausschreiben öffnen | 1 | 2 (Mehr → Stelle ausschreiben) | ≤ 2 | erreicht |
| Bewerber einladen über Kandidaten-Suche | 4 | 5 (Mehr → Kandidaten-Suche → Zeile → Einladen → Dialog-Einladen) | ≤ 3 | verfehlt |
| Bewerber einladen über Hiring-Board | – | 4 (Hiring-Board → Im Match öffnen → Einladen → Dialog-Einladen) | ≤ 3 | verfehlt |
| Einladen über Seite Einladungen (überholt) | – | **2 gemessen 16.10.2026 Vormittag** (Sidebar „Einladungen" → Karten-„Einladen" direkt, Defaults morgen 10:00/30 unangetastet) | ≤ 2 | **überholt 16.10. (UX-Korrektur: Direkt-Invite ohne Dialog entfernt)** — damals „erreicht" ab Status `angesehen`; `eingegangen`: 3 Klicks (+ „Als angesehen markieren"); Termin anpassen: nicht gemessen (Schätzung +2–4, Design-Entscheidung) |
| Einladen über Seite Einladungen (Soll nach UX-Korrektur, Entscheidung 16.10.2026) | – | ab Status `angesehen`: Sidebar(1) → Karte „Einladen"(2) → Dialog „Einladen"(3) = **3 Klicks** — **gemessen 16.10.2026 (E2E, Isolationslauf, Log `/tmp/opencode/e2e-iso-20261016-172250/e2e_einladen_flow.log`)** | 3 (Design-Entscheidung 16.10.2026, statt 2) | **erreicht** — IST = Soll = 3, gemessen 16.10.2026 (E2E, Isolationslauf, Codemark `e2e_einladen_flow`, `KLICKMESSUNG einladen: 3`); `eingegangen`: Soll 4 (+ „Als angesehen markieren"), **nicht gemessen**; Termin anpassen: nicht gemessen (Schätzung +2–4, Design-Entscheidung) |
| Feedback öffnen | 1 | 2 (Mehr → Feedback) | ≤ 2 | erreicht |

Belege: `ergebnisse/entscheidungen.md` (Einträge 15.10.2026 und 16.10.2026, Klick-Messung; Log `e2e_einladen_flow` 16.10.2026, `/tmp/opencode/e2e-iso-20261016-*/e2e_einladen_flow.log`). Die Schnellaktionen auf der Board-Karte (§3) und der Drawer (§4) sind **nicht** umgesetzt; das Einladen-Ziel ≤ 3 bleibt auf diesen beiden Pfaden offen. Der Pfad über die Seite Einladungen war mit **2 Klicks (gemessen 16.10.2026 Vormittag)** erreicht — dieser Wert ist **überholt 16.10. (UX-Korrektur: Direkt-Invite ohne Dialog entfernt)**; Soll danach 3 Klicks (Tabellenzeile oben), **IST-Messung 16.10.2026 (E2E, Isolationslauf): 3 Klicks ab `angesehen` — Soll erreicht** (Log `/tmp/opencode/e2e-iso-20261016-172250/e2e_einladen_flow.log`). Der Stellenangebote-Pfad mit Status-Buttons (`_page_stellen`) ist **nicht** gemessen.

- **Messwert (16.10.2026 Vormittag, Playwright, isolierter Spiegel-Lauf, Codemark `e2e_einladen_flow`):** Seite Einladungen — **2 Klicks** ab Status `angesehen` (Menü „Einladungen" → Karten-„Einladen" mit Defaults). Status `eingegangen`: erst „Als angesehen markieren", dann einladbar (3 Klicks bis `eingeladen`; Guard `ALLOWED_TRANSITIONS` verbietet Direkteinladen ab `eingegangen`). Termin anpassen: +2–4 (Schätzung, nicht gemessen). **Überholt 16.10. (UX-Korrektur: Direkt-Invite ohne Dialog entfernt):** dieser Messwert beschreibt den Stand **vor** dem Bestätigungs-Dialog (Karte führte direkt zu `_ein_send_invite`); Soll nach der Korrektur = 3 Klicks ab `angesehen` bzw. 4 ab `eingegangen` (§6-Tabelle).
- **IST-Messung der korrigierten Klickfolge (16.10.2026, E2E, Isolationslauf, Codemark `e2e_einladen_flow`): 3 Klicks ab Status `angesehen`** — Sidebar(1) → Karte „Einladen"(2) → Dialog „Einladen"(3) → Spiegel-DB `eingeladen`. Damit **IST = Soll = 3, erreicht**. Log `/tmp/opencode/e2e-iso-20261016-172250/e2e_einladen_flow.log` (Erstlauf desselben Skripts mit identischem Wert: `/tmp/opencode/e2e-iso-20261016-172046/e2e_einladen_flow.log`); Isolations-Summary `…/172250/summary.txt` (`Live-Diff rc=0`, `Live-Bytes sha256 … gleich=True`). LOCATOR-FALLE im selben Lauf belegt: nach Klick 2 existieren **2** Buttons mit dem Text „Einladen" (Karte A + Dialog), der Bestätigen-Klick ist deshalb auf `.q-dialog` gescoped. **Negativtest Abbrechen (gleicher Lauf, zweite Bewerbung):** Dialog öffnen → „Abbrechen" → Status bleibt `angesehen` (History/Task-Zeilen unverändert). Klicks außerhalb des Zielpfads („Als angesehen markieren" + Abbrechen-Test) werden im Log getrennt ausgewiesen und zählen nicht in den Zielwert. `eingegangen`-Pfad (Soll 4) und „Termin anpassen" bleiben **nicht gemessen**. **Abschluss-Neumessung nach i18n-Katalogbau (16.10.2026, 18:39 Uhr, Log `/tmp/opencode/e2e-iso-20261016-183919/`):** dritter unabhängiger Lauf, erneut `KLICKMESSUNG einladen: 3`, Abbrechen-Test ✓ (`history+0, tasks+0`), `residue=0`, Live-sha256 gleich — Wert bestätigt.

## 7. Umfang und Stand

- **Durchlauf 1 (erledigt):** Board mit 4 Spalten, Passiv-Reiter, Navigation 4 Punkte, „Mehr“-Seite, Pseudonym-Fix in `_list_candidates`, Unit-Tests nachgezogen, i18n in 4 Sprachen, Doku-Korrekturen der belegten Falschaussagen.
- **Durchlauf 2 (offen):** Drawer (§4), Kartenschnellaktionen (§3), E2E-Skripte an die neue Navigation anpassen, isolierter E2E-Volllauf, Klarname-Befund Match/Feedback (§5).

Kein Commit und kein Push ohne ausdrückliches Go.
