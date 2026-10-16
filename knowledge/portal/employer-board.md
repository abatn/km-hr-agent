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

**Ist-Stand:** Jede Bewerbungskarte zeigt die erlaubten Folgeschritte als Text und einen Button „Im Match öffnen“ (Sprung auf die Match-Seite). Die Schreibaktionen (Einladen, Ablehnen, Einstellen) laufen dort über die bestehenden Dialoge `_open_invite`, `_open_reject`, `_open_hire` samt `_notify_statuswechsel`.

**Entscheidung 16.10.2026 (Iteration „Einladungen", Nutzerbefehl) — umgesetzt 16.10.2026:** Die Seite **Einladungen** (`/employer/einladen`, Codemark-Kette `_page_einladen` → `_ein_send_invite` / `_ein_mark_seen`) ist die **dritte Aufrufstelle des GLEICHEN Mechanismus** — Whitelist-Guard `ALLOWED_TRANSITIONS`, Status-History (`changed_by 'arbeitgeber'`), `queue_agent_task("create_invitation")`; ein eigener Mail-/Status-Codezweig ist verboten. **Kein DB-Schema-Change.** Kartenschnellaktionen bleiben damit erlaubt, solange sie nur den bestehenden Mechanismus aufrufen (Ist: `do_invite` Match-Dialog, `make_transition` Stellenangebote, `_ein_send_invite` Seite Einladungen).

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
| Einladen über Seite Einladungen | – | **2 gemessen 16.10.2026** (Sidebar „Einladungen" → Karten-„Einladen", Defaults morgen 10:00/30 unangetastet) | ≤ 2 | **erreicht** — ab Status `angesehen`; `eingegangen`: 3 Klicks (+ „Als angesehen markieren"); Termin anpassen: nicht gemessen (Schätzung +2–4, Design-Entscheidung) |
| Feedback öffnen | 1 | 2 (Mehr → Feedback) | ≤ 2 | erreicht |

Belege: `ergebnisse/entscheidungen.md` (Einträge 15.10.2026 und 16.10.2026, Klick-Messung; Log `e2e_einladen_flow` 16.10.2026, `/tmp/opencode/e2e-iso-20261016-*/e2e_einladen_flow.log`). Die Schnellaktionen auf der Board-Karte (§3) und der Drawer (§4) sind **nicht** umgesetzt; das Einladen-Ziel ≤ 3 bleibt auf diesen beiden Pfaden offen — **erreicht wird es seit 16.10.2026 über die Seite Einladungen (gemessen 2, Tabellenzeile oben)**. Der Stellenangebote-Pfad mit Status-Buttons (`_page_stellen`) ist **nicht** gemessen.

- **Messwert (16.10.2026, Playwright, isolierter Spiegel-Lauf, Codemark `e2e_einladen_flow`):** Seite Einladungen — **2 Klicks** ab Status `angesehen` (Menü „Einladungen" → Karten-„Einladen" mit Defaults). Status `eingegangen`: erst „Als angesehen markieren", dann einladbar (3 Klicks bis `eingeladen`; Guard `ALLOWED_TRANSITIONS` verbietet Direkteinladen ab `eingegangen`). Termin anpassen: +2–4 (Schätzung, nicht gemessen).

## 7. Umfang und Stand

- **Durchlauf 1 (erledigt):** Board mit 4 Spalten, Passiv-Reiter, Navigation 4 Punkte, „Mehr“-Seite, Pseudonym-Fix in `_list_candidates`, Unit-Tests nachgezogen, i18n in 4 Sprachen, Doku-Korrekturen der belegten Falschaussagen.
- **Durchlauf 2 (offen):** Drawer (§4), Kartenschnellaktionen (§3), E2E-Skripte an die neue Navigation anpassen, isolierter E2E-Volllauf, Klarname-Befund Match/Feedback (§5).

Kein Commit und kein Push ohne ausdrückliches Go.
