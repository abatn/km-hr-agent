# Markdown-Schreib-Konvention (Laufzeit-Artefakte)

> **Stand:** 21.10.2026 · **Art:** MD-only (kein Code, keine DB-Änderung) · **Status:** verbindliche Spec
> **Anlass:** Messung 21.10.2026 — mehrere Laufzeit-Schreiber wählten als Ziel die **neueste existierende** Datei statt der **heutigen**, übernahmen Abschnitte aus **anderen** Dateien, hängten Zeilen an eine **normative** Spec (`knowledge/error-statistics.md`) und lieferten **formal defekte** Kalenderdateien. Belege: `ergebnisse/entscheidungen.md`, Eintrag 21.10.2026 (Abschnitt „md-Disziplin").
> **Geltungsbereich:** alle Schreiber, die Markdown-Dateien zur Laufzeit anlegen oder ändern (Produktivcode, MCP-Agent-Ebene, Tests).
> **Abgrenzung:** `knowledge/**` und `skills/*/SKILL.md` sind **normativ** (`knowledge/system/doku-authority.md` §1) — Laufzeitcode darf dort **nicht** schreiben.

---

## 0. Zwei Bereiche, zwei Regeln

| Bereich | Charakter | Wer schreibt | Regelwerk |
|---|---|---|---|
| `knowledge/**`, `skills/*/SKILL.md`, `AGENTS.md` | **normativ** (Soll) | nur redaktionell (Mensch/Agent im Doku-Workflow) mit staledocs-Re-Ack + docrot + pytest | §2 (Schreib-Regel 5) + §3 (Prüfregeln) |
| `ergebnisse/*.md` (Laufzeit-Artefakte) | **historisch** (Ist) | Produktivcode, MCP-Agent-Ebene, Tests | §1 (Schreib-Regeln 1–4, 6) + §3 |

**Doku-Authority-Hinweis (21.10.2026):** Laufzeit-Artefakte unter `ergebnisse/` sind **historische Belege**, **keine Norm**. Ein Fakt, der in `ergebnisse/*.md` steht, ist erst dann verbindlich, wenn er in der zuständigen Spec (`knowledge/**`) steht — sonst gilt „keine Behauptung ohne Beweis" (`AGENTS.md`, Lab-Prinzipien).

---

## 1. Schreib-Regeln (Laufzeit-Artefakte)

**R-S1 — Vollständig neu schreiben ODER Abschnitt per Heading-Anker ersetzen.**
Ein Laufzeit-Schreiber schreibt entweder die **ganze** Datei neu (dann ist der Inhalt aus dem aktuellen Code berechnet) **oder** er ersetzt **genau einen** Abschnitt, identifiziert über seinen **Heading-Anker** (`## Video-Vorstellung`). Erlaubt ist **nicht** „Text-Teil + angehängter Abschnitt" (das erzeugt Duplikate und verliert die Abschnittsgrenze).
**Ausnahme — Append-only-Protokolle (21.10.2026):** Protokolle, in denen **jede Zeile ein neuer Eintrag** ist (Fehlerstatistik `error-statistik-{JJJJ-MM-TT}.md`, Tagesprotokoll `pushstate-protokoll-{YYYY-MM-DD}.md`), dürfen angehängt werden — dort gibt es keinen Abschnitts-Anker. Im Code: `MDGUARD_APPEND_ERLAUBT`.

**R-S2 — Kein Carry-over aus anderen Markdown-Dateien (Schreiber-Regel).**
Ein Abschnitt darf **nie** aus einer anderen Datei übernommen werden. Der Inhalt ist **immer aus dem aktuellen Code neu zu berechnen** (oder aus dem Zustand, den der Code selbst in der **Zieldatei** hält — dieselbe Datei, gleicher Tag; siehe R-S3/R-S5).
**Leser-Regel (21.10.2026, Ergänzung):** R-S2/R-S3 gelten für **Schreiber**. Ein **Leser** (z. B. der Portal-Reader `def load_video_link`, `webui/pages/candidate.py`) darf auf den **letzten bekannten Stand** zurückgreifen: die heutige Datei wird bevorzugt, sonst die neueste Datei **mit** dem gesuchten Abschnitt. Grund: der Kandidat soll seinen bereits erzeugten Link sehen, auch wenn er gestern erzeugt wurde (Messung 21.10.2026: Kandidaten 2 und 20 sahen ihren Link im Portal nicht mehr, während der HR-Recruiting-Modus die Altdatei weiter anzeigte).

**Leser-Regel — HR-Sicht (21.10.2026, V-19):** Dieselbe Regel gilt für die Arbeitgeber-/HR-Ansicht (`def prescreen_recruiting_section`, `webui/components.py`): je Kandidat wird **nur der neueste Stand mit nutzbarem Video-Abschnitt** ausgegeben (heutige Datei zuerst, sonst die neueste Datei mit Abschnitt; Auswahl-Helfer `def selbstpraesentation_je_kandidat`, `webui/components.py`). **Verhaltensänderung (21.10.2026):** zuvor wurden **alle** Fassungen eines Kandidaten gelistet. Zusätzlich gilt: ein `?director=`-Link ist **kein nutzbarer Link** (veraltet, Spec R2.2) und wird in der HR-Sicht nicht ausgegeben (Hilfer `def _video_link_aus_abschnitt`, `webui/components.py`). Nachweis: `tests/test_video_section.py` (V-19-Proben).

**R-S3 — Zieldatei aus dem heutigen Datum, nie „neueste existierende".**
Das Datum im Dateinamen ist das **heutige** Datum des Schreibvorgangs (`date.today()`/`datetime.now()`), außer die Datei ist **ausdrücklich** ein Fach- oder Startdatums-Artefakt (Datumsrollen-Tabelle, §4). Ein Schreiber darf **nie** per `sorted(glob(...))[-1]` ein **früheres** Artefakt als Ziel wählen.

**R-S4 — Kein Schreiben in `knowledge/**` oder `skills/**` aus Laufzeitcode.**
Ausnahme nur, wenn (a) die Datei **explizit allowlistet** ist, (b) das **Spaltenschema** der Zieldatei vor dem Schreiben geprüft wird und (c) der Anhang **innerhalb** der passenden Tabelle landet (nicht am Dateiende). Für Fehlerstatistiken ist der normative Ort **nicht** zulässig → siehe §6 (Entscheidung `handle_errors`).

**R-S5 — Kein Abschneiden von Inhalt.**
Ein Schreiber darf keinen bestehenden Inhalt verwerfen, der **nicht** zum ersetzten Abschnitt gehört (kein `text.split(HEADING)[0]`, kein `text[:n]`). Ersetzt wird **nur** der per Anker adressierte Abschnitt; alles davor und alles danach bleibt erhalten.

**R-S6 — Der Schreiber liefert die Resultatdatei zurück.**
Jede Schreibfunktion gibt den Pfad (und, wo sinnvoll, den geschriebenen Text) an den Aufrufer zurück, damit der Aufrufer den Erfolg prüfen kann und der Dateiname **eine** Quelle der Wahrheit bleibt (kein „wo war das nochmal?"). **Geltungsbereich (21.10.2026):** dedizierte Schreiber, die eine **Ergebnis-/Markdown-Datei** unter `ergebnisse/` schreiben (Namens-Muster `write_`/`save_`/`persist_`/`create_`); PID-/Logdateien sind nicht Ergebnisdateien. Im Code: `MDGUARD_…` (Prüfung R-S6).

**Ergänzend (Runner, alle Hosts):** Vor dem ersten Schreiben in `ergebnisse/` wird das Verzeichnis angelegt (`ERGEBNISSE.mkdir(parents=True, exist_ok=True)`) — der Ordner ist gitignored und fehlt in einem frischen Checkout ⇒ ohne dieses `mkdir` schlägt der Schreibvorgang mit `FileNotFoundError` **fehl** (Messung 21.10.2026, Server-Befund).

---

## 2. Prüfregeln (R1–R5) — was der Wächter `mdguard` prüft

| Regel | Prüfpunkt | Quelle der Regel |
|---|---|---|
| **R1.1** | **Struktur:** keine doppelten `## `-Überschriften in einer Datei; ein Konflikt-ID-Kandidat+Tag gehört in **genau eine** Datei | Messung 21.10.2026: `write_prescreen_md` konnte denselben Abschnitt doppelt anlegen (Anhang-Logik) |
| **R1.2** | **Konflikt-ID:** für `{Kandidat}+{Tag}` existiert höchstens **eine** Artefaktdatei | Ableitung aus R-S2/R-S3: zwei Dateien mit demselben Schlüssel ⇒ unklare Quelle der Wahrheit |
| **R2.1** | **Linkform:** `?push=`-IDs **ohne Bindestrich** (Raumname alphanumerisch) | `knowledge/system/vdo-ninja-migration.md` §2.5 (Quelle: docs.vdo.ninja …/setup-parameters/room, abgerufen 04.10.2026) |
| **R2.2** | **Linkform:** kein `?director=` in **Selbstpräsentations**-Artefakten | `knowledge/system/vdo-ninja-migration.md` §2.3 (03.10.2026): `&director` = Regieraum **ohne eigenes Bild** ⇒ für die Solo-Selbstpräsentation unbrauchbar |
| **R2.3** | **Linkform:** kein `meet.jit.si` in **neuen** Artefakten (Providerwechsel 27.09.2026 abgeschlossen) | `knowledge/system/vdo-ninja-migration.md` Kopf (27.09.2026) |
| **R3.1** | **md↔Code:** in der Spec genannte Codemarken **existieren** im Code | `AGENTS.md` Conventions („Zitate mit Codemarke + Messdatum") + `knowledge/system/doku-authority.md` §4 |
| **R3.2** | **md↔Code:** Zählwerte in der Spec sind **live** gemessen (Dateien/Tabellen/Server) | `AGENTS.md` Lab-Prinzip 1 (Quelle oder Messdatum) |
| **R4.1** | **Schreiber-Statik (Quelltext):** kein Schreiber wählt „neueste existierende" als Ziel | R-S3 |
| **R4.2** | **Schreiber-Statik:** kein Laufzeit-Schreiber in `knowledge/**`/`skills/**` | R-S4 + `knowledge/system/doku-authority.md` §1 |
| **R4.3** | **Schreiber-Statik:** kein Carry-over (Abschnitt aus anderer Datei) | R-S2 |
| **R4.4** | **Schreiber-Statik:** keine Truncation (`split(HEADING)[0]`, `text[:n]`) | R-S5 |
| **R4.5** | **Schreiber-Statik:** Zielverzeichnis wird vor dem Schreiben angelegt | „Ergänzend (Runner, alle Hosts)" §1 |
| **R4.6** | **Schreiber-Statik:** ein Schreiber meldet **keinen** Erfolg, wenn nichts geschrieben wurde (kein „Erfolgsversprechen" trotz `except: pass`) — Erkennung: **breiter** Fehlerhandler (`except Exception`/`BaseException`/nacktes `except:`) **und** **konstante** Erfolgs-Rückgabe (`True`, `"done"`, `"ok"`, `"erfolgreich"` — auch als Dict-Wert `{"logged": True}`) in derselben Funktion | Messung 21.10.2026: `handle_errors` meldete `{"logged": True}`, obwohl beide Schreibvorgänge scheiterten. **Abgrenzung (21.10.2026, V-12):** die korrekte Form (`ok = False` … `ok = True` … `return {"logged": ok}`) ist erlaubt; ein **spezifischer** Fehlerhandler (`except FileNotFoundError`) ohne breite Exception ist erlaubt. Im Code: `def _mdguard_erfolgsversprechen` |
| **R5.1** | **Datei-Auswahl:** „neueste" vs. „heutige" ist **explizit** — Leser, die „neuesten" behaupten, wählen auch den neuesten; Docstring und Code stimmen überein | Messung 21.10.2026: `_visum_auswertung_from_ergebnisse` (Docstring „letzten", Code ältester) |

**R4-Prüfung über Quelltext (statisch):** Die Regeln R4.1–R4.6 sind **statische Eigenschaften des Codes** (kein Laufzeitverhalten) ⇒ sie werden über Quelltext-/AST-Prüfung entschieden (`scripts/ci/checks.py mdguard`, `tests/test_mdguard_checker.py` mit Positiv-/Negativproben, `tests/test_md_writer_discipline.py`), nicht über einen DB- oder UI-Lauf. Die Schreiber-Liste wird **auto-entdeckt** (`webui/**`, `scripts/**`, `connectors/**` **und die Repo-Wurzel** — damit `mcp-*.py` und `app.py` erfasst werden; 21.10.2026, V-07), damit ein neuer Schreiber nicht unbemerkt durchfällt.

**Grenzen der automatischen Erkennung (21.10.2026, V-04/V-05/V-12):**
- **R4.2** erkennt Schreibziele nur über **Pfad-Ausdrücke** im Quelltext (`knowledge/…`, `skills/…` als Teilstring eines Ausdrucks, auch über `BASE / "knowledge" / "x.md"` und `base = Path("knowledge")`).
- **R4.3** (Carry-over) ist **markerbasiert**: erkannt werden Aufrufe der Marker-Funktionen (`MDGUARD_CARRY_OVER_MARKER`) und ein **direktes** `read_text()`/`read_bytes()` einer *anderen* Datei, dessen Ergebnis in den geschriebenen Inhalt einfließt. Eine selbstdefinierte Hilfsfunktion **ohne** Markernamen wird **nicht** erkannt (Beleg 21.10.2026: eine generische Variablen-Propagation erzeugte Fehlalarme — die Variable `i` aus `text.find(...)` wurde zum Carry-over-Indikator) ⇒ Pflege über `MDGUARD_CARRY_OVER_MARKER`.
- **R4.6** ist eine **Heuristik** (breiter Handler + konstante Erfolgs-Rückgabe in derselben Funktion) — kein Beweis für einen Fehlpfad, aber ein zuverlässiger Hinweis.

---

## 3. Allowlisten und Abgrenzungen (damit rc=0 heute erreichbar ist)

| Allowlist | Inhalt | Begründung |
|---|---|---|
| **Alt-Bestand** | Artefakte mit Datum **< 21.10.2026** werden **nicht** rot gemeldet | Sie sind historische Belege (Doku-Authority §1 „historisch") und werden **nicht** umgeschrieben (AGENTS: Alt-Reports in `ergebnisse/` bleiben unangetastet) — im Code: `MDGUARD_STICHTAG` |
| **Changelog-Append** | `ergebnisse/entscheidungen.md` | Historisches Beweislog (Lab-Schritt 4); Anhängen ist hier **gewollt** (ein Ort, chronologisch) — im Code über die Regel „kein Datum im Namen ⇒ nicht rot" abgedeckt (kein eigener Eintrag) |
| **Datumsfreie Muster** | `einladung-bewerbung-*`, `onboarding-freigabe-bewerbung-*`, `contract-preflight-bewerbung-*` | Das Datum steht **im Inhalt** (Bewerbung/Trigger-Zeitpunkt), nicht im Dateinamen — „kein Datum" ist hier **by design** — im Code: `MDGUARD_UNDATUM` |
| **Startdatum-Muster** | `onboarding-{name}-{STARTDATUM}.md` | Der Dateiname trägt das **Startdatum** (Fachdatum), nicht das Erstellungsdatum — im Code: `MDGUARD_UNDATUM` (Eintrag `onboarding-`, 21.10.2026) |
| **Historische Reports ohne Datum** | **jede** Datei ohne `JJJJ-MM-TT` im Dateinamen (Messung 21.10.2026: **132** `.md` in `ergebnisse/`, davon **91** Einmal-Reports ohne Schema) | Ohne Datumsrolle ist eine „neueste/heutige"-Sortierung ohnehin sinnlos — im Code: `_mdguard_neu` (`if not m: return False`) |
| **`app.py` (Streamlit-Parität)** | wird seit 21.10.2026 (V-07) **mitgeprüft** — der Code ist real, nur der Start ist abgeschaltet (`start.sh` verweigert den Start) | `AGENTS.md` („`app.py` bleibt als Paritäts-Referenz") — im Code: `MDGUARD_PARITAET` (leer seit 21.10.2026) |
| **`tests/**` (Auto-Discovery)** | **ausgenommen** von der Auto-Discovery der Schreiber (`MDGUARD_AUTO_AUSSCHLUSS`) — dort wird bewusst nach `ergebnisse/` geschrieben (E2E-Fixtures, `tests/e2e_*.py`) | Ausnahme ist **bewusst** und in dieser Spec begründet: Testartefakte sind keine Produktiv-Schreiber. Die Wächter-Regeln selbst sind in `tests/test_mdguard_checker.py` **gegen den echten Checker** nachgewiesen (Positiv-/Negativproben) — der Nachweis ersetzt die Aufnahme in die Auto-Discovery |

**Wirkung in der CI (21.10.2026, gemessen und korrigiert):** `ergebnisse/` ist gitignored ⇒ in einem frischen Checkout existiert der Ordner nicht ⇒ die **artefaktbezogenen** Regeln (R1.1/R1.2/R2.1–R2.3) liefen in der CI **nicht**. **Korrektur (21.10.2026, V-10):** die getrackten Fixtures unter `tests/fixtures/md-guard/` (1 gültige + 1 absichtlich verstoßende Datei) werden mitgeprüft; der Wächter **verifiziert seine eigenen Erwartungen** (`gueltig-*` muss grün sein, `verstoss-*` muss rot sein — Abweichung = Fehler, der Lauf bleibt dann rot). Damit ist der Nachweis der artefaktbezogenen Regeln in der CI **belastbar** (Code: `MDGUARD_FIXTURES`, `def _mdguard_fund`).

**Stichtag (21.10.2026, V-09):** Der Stichtag ist eine **Konstante** (`MDGUARD_STICHTAG`); er darf **nicht** fest verdrahtet werden, sondern ist beim Anheben der Regeln mitzuziehen. Die **Tests lesen dieselbe Konstante** (Helfer `_stichtag`, `tests/test_mdguard_checker.py`) ⇒ ein Anheben des Stichtags bricht die Proben nicht mehr.

---

## 4. Datumsrollen-Tabelle (welches Datum trägt der Dateiname?)

| Rolle des Datums im Dateinamen | Muster (Beispiel) | Bedeutung | „neueste Datei" sinnvoll? |
|---|---|---|---|
| **heutiges** Datum (Erstell-/Berichtsdatum) | `{task}-kandidat-{id}-{YYYY-MM-DD}.md`, `self-presentation-kandidat-{id}-{YYYY-MM-DD}.md`, `export-kandidat-{cid}-job-{jid}-{YYYY-MM-DD}.md` | Tag, an dem erzeugt wurde | **ja** — für **Leser** (R5.1/Leser-Regel: heutige Datei zuerst, sonst neueste mit Abschnitt). **Nein** für **Schreiber** als Zielwahl (R-S3: Schreiber wählt immer die **heutige** Datei) |
| **Startdatum** (Termin/Fachdatum) | `onboarding-{name}-{STARTDATUM}.md` | geplanter Arbeitsbeginn (Standard: Erstellungsdatum + 30 Tage) — **im Code allowlistet** (`MDGUARD_UNDATUM`, 21.10.2026) | **nein** — die Datei mit dem grössten Datum ist die mit dem **spätesten Starttermin** |
| **Fachdatum** (inhaltlicher Stand) | `paritaets-matrix-final-{STAND}.md`, `recherche-plan-restpunkte-{STAND}.md` | Stand, den der Report behandelt | **nein** |
| **kein Datum** (Vorgangs-ID) | `einladung-bewerbung-{app_id}.md`, `onboarding-freigabe-bewerbung-{app_id}.md`, `contract-preflight-bewerbung-{app_id}.md` | Datumsangabe steht im **Inhalt** (Termin/Trigger) | **nein** (alphabetisch = chronologisch nutzlos) |
| **Name statt ID** | `pre-screen-{name}-{YYYY-MM-DD}.md`, `feedback-{name}-{YYYY-MM-DD}.md`, `export-kandidat-{name}-job-{jid}-{YYYY-MM-DD}.md` | Bericht über eine Person, deren Kandidaten-ID im Namen fehlt ⇒ **nicht eindeutig** einem Kandidaten zuordenbar (manuelle Prüfung) | **nein** (Name ist kein Datum) |
| **Ziel-ID leer** | `export-kandidat-{cid}-job-None-{YYYY-MM-DD}.md` | `jid` war im Task `None` ⇒ der Report ist **nicht** zuordenbar (manuelle Prüfung) | **nein** |
| **Protokoll (Tagesprotokoll)** | `pushstate-protokoll-{YYYY-MM-DD}.md` | Log des Tages ohne Kandidatenbezug | **nein** (Inhalt ist Protokoll) |
| **Einmal-Report (kein Schema)** | `*.md` ohne Datum und ohne Task-Präfix (Messung 21.10.2026: **91** von **408** top-level `.md` in `ergebnisse/`) | historischer Einmal-Beleg, kein Schema ⇒ Auswahl nur manuell/inhaltlich | **nein** |
| **unaufgelöster Template-Platzhalter** | Dateinamen mit literalem `**name:**` (Messung 21.10.2026: **4** Dateien) | Alt-Fehler des Dateinamen-Missbrauchs (P0 28.09.2026) ⇒ **nicht** neu erzeugen | **nein** |
| **Kalenderdatei (kein MD)** | `einladung-ics-bewerbung-{app_id}.ics`, `einladung-ics-hr-bewerbung-{app_id}.ics` (25 Dateien) | Rolle wie „Vorgangs-ID"; vom Wächter nicht erfasst (`*.md`-Glob) | **nein** |

**Konsequenz für Leser (R5.1):** „neueste Datei" ist nur bei der Rolle **heutiges Datum** eine sinnvolle Sortierung. Bei Start-/Fach-/datumsfreien Mustern muss über den **Inhalt** (Datumsfeld) oder über eine **Vorgangs-ID** ausgewählt werden. **Schreiber** wählen nie eine „neueste existierende" Datei, sondern die Datei des heutigen Datums (R-S3) — die Ausnahme „Startdatum-Muster" ist in §3 allowlistet.

---

## 5. Umsetzungsentscheidungen (21.10.2026, mit Begründung)

1. **`_score_from_ergebnisse` / `_compliance_from_ergebnisse` / `_visum_auswertung_from_ergebnisse`:** Auswahl auf den **neuesten** Report umgestellt. Begründung: `knowledge/system/agent-automation.md` (Ist-Code-Beleg, 10.10.2026) hält fest: „**Gatekeeper wertet die jüngste Datei aus — by design**" ⇒ der Code widersprach der Spec; nach `knowledge/system/doku-authority.md` §2 Ziffer 3 wird der **Konflikt entschieden** (Code an Spec).
2. **`handle_errors`:** Der Laufzeitcode schreibt **nicht** mehr in `knowledge/error-statistics.md` (normativ, Read-Modify-Write ohne Lock, abweichendes Spaltenschema). Stattdessen: Tagesdatei `ergebnisse/error-statistik-{YYYY-MM-DD}.md` mit eigenem 5-Spalten-Schema (historischer Bereich). Die normative Datei bleibt **aggregiert** und wird nur redaktionell gepflegt (`skills/handle-errors/SKILL.md` §6, MCP-Ebene). Doku-Authority §1 („Code korrigieren" bei MD↔Code-Konflikt) + R-S4.
3. **Selbstpräsentation:** Carry-over über Tagesgrenzen entfällt (R-S2); die heutige Datei enthält nur, was **heute** erzeugt wurde. Die Spec `knowledge/system/vdo-ninja-migration.md` §2.3 („Bereits persistierte Alt-Links bleiben `?director=` — **keine Migration**") bleibt damit **wahr**: ein Alt-Link wird nicht migriert, sondern **nicht** weitergetragen.
4. **`knowledge/system/vdo-ninja-migration.md` §2.3** bleibt unverändert (kein Widerspruch mehr, weil Carry-over entfällt).
5. **Export ohne `job_id` (21.10.2026, V-13):** `export_report` (Codemarke `def export_report`) schreibt **keinen** erfundenen Score „0/100" mehr, wenn kein Bericht zur Stelle vorliegt, sondern „**unbekannt**" (Status `unbekannt — kein Bericht zur Stelle`). Grund: `_score_from_ergebnisse` liefert `None` statt `0` (siehe `knowledge/system/agent-automation.md`). Auswirkung auf diese Spec: Artefakte der Rolle „Ziel-ID leer" (`export-kandidat-{cid}-job-None-{date}.md`) sind **nicht** mehr mit einer erfundenen Zahl belastbar ⇒ der Report bleibt „historischer Beleg" und wird **nicht** umgeschrieben (Alt-Reports bleiben unangetastet, `AGENTS.md`).
6. **Carry-over-Erkennung bleibt markerbasiert (21.10.2026, V-05/V-12):** Die generische Variante (Variablen-Propagation über Zuweisungen) wurde verworfen — sie erzeugte Fehlalarme (Beleg: die Schleifenvariable `i` aus `text.find(...)` wurde zum Carry-over-Indikator ⇒ 61 Fehlalarme in `webui/pages/employer.py`). Der Marker-Stand ist deshalb **bewusst** und in §2 dokumentiert; neue Carry-over-Hilfen werden in `MDGUARD_CARRY_OVER_MARKER` eingetragen.

---

## 6. Quellen und Messdaten

| Regel/Quelle | Herkunft | Datum |
|---|---|---|
| R-S1 (Anchor-Replace), R-S5 (keine Truncation), R-S2 (kein Carry-over), R-S3 (heutiges Datum) | Messung der Codemarken `write_prescreen_md`, `persist_video_link` (webui/pages/candidate.py) | 21.10.2026 |
| R-S4 (kein Schreiben in `knowledge/**`), §0 (Bereiche), §1 Allowlist | `knowledge/system/doku-authority.md` §1 (Typen normativ/deskriptiv/historisch) | 21.10.2026 (Datei gelesen) |
| R-S5-Ergänzung (`ERGEBNISSE.mkdir`) | Server-Befund 20.10.2026: `FileNotFoundError` beim ersten `create_invitation` auf dem neuen Host (Ordner `ergebnisse/` fehlt, gitignored) | 20.10.2026 |
| R2.1 (`?push=` ohne Bindestrich) | `knowledge/system/vdo-ninja-migration.md` §2.5 (Quelle docs.vdo.ninja/advanced-settings/setup-parameters/room) | 04.10.2026 (Spec) / 21.10.2026 (geprüft) |
| R2.2 (kein `?director=` in der Selbstpräsentation) | `knowledge/system/vdo-ninja-migration.md` §2.3 | 03.10.2026 (Spec) / 21.10.2026 (geprüft) |
| R2.3 (kein `meet.jit.si`) | `knowledge/system/vdo-ninja-migration.md` Kopf (Providerentscheid 27.09.2026) | 27.09.2026 (Spec) / 21.10.2026 (geprüft) |
| R5.1 („neueste" vs. „heutige") | Messung `_visum_auswertung_from_ergebnisse` (Docstring „letzten", Code ältester) + `_score_from_ergebnisse` (ältester) vs. Kultur-Fit-Lesung in `export_report` (neuester) | 21.10.2026 |
| Umsetzung 1 („neuester Report") | `knowledge/system/agent-automation.md` (Ist-Code-Beleg 10.10.2026) + `knowledge/system/doku-authority.md` §2 Ziffer 3 | 21.10.2026 |
| Zählwerte (Abschnitt „Wächter") | live gemessen: `find knowledge -name "*.md" \| wc -l` = **78** (inkl. dieser Spec) · `sqlite_master`-COUNT = **17** · `opencode.json`-`mcp` = **14** | 25.10.2026 |
| Zählwert-Korrektur (21.10.2026, V-15): „Einmal-Report" | live gemessen: **408** top-level `.md` in `ergebnisse/` (nach Löschung genau **eines** Alt-Artefakts, V-20), davon **132** ohne Datum und **91** Einmal-Reports | 21.10.2026 |
| Allowlist „Alt-Bestand < 21.10.2026" | AGENTS.md Convention („Alt-Reports in `ergebnisse/` bleiben unangetastet") + Doku-Authority §1 „historisch" | 21.10.2026 |
| R4.6-Erkennung (V-12) | Probe gegen den echten Checker: `except Exception: pass` + `return {"logged": True}` ⇒ **1 Fund**; korrekte Form (`ok`-Variable) ⇒ **0 Funde**; `except FileNotFoundError` + konstante Rückgabe ⇒ **0 Funde** | 21.10.2026 |
| R4.3-Grenze (V-05) | Probe: Namensmuster „section" erzeugte **61 Fehlalarme** in `webui/pages/employer.py` ⇒ Marker-Stand + direkter Lesefluss | 21.10.2026 |
| R4.2-/`open()`-Erkennung (V-04) | Probe: `open("knowledge/x.md", "w")` und `with open(…, "w")` ⇒ je **1 Fund**; `open(…, "rb")` ⇒ **0 Funde** (Lesen ist kein Schreiben) | 21.10.2026 |
| Auto-Discovery (V-07) | live: **34** Schreiber geprüft (vorher 27) — Repo-Wurzel ergänzt (`mcp-*.py`, `app.py`); `tests/**` bewusst ausgenommen (§3) | 21.10.2026 |
| HR-Sicht-Leser-Regel (V-19) | live: `selbstpraesentation_je_kandidat(ergebnisse)` ⇒ Kandidaten 1/2/13/20 je **ein** Eintrag (vorher alle Fassungen) | 21.10.2026 |

---

## 7. Wächter

- `scripts/ci/checks.py mdguard` — statische Prüfungen R1.1/R1.2, R2.1–R2.3, R3.1/R3.2, R4.1–R4.6, R5.1, R-S1, R-S6 (rein lesend, kein DB-Write).
- `tests/test_mdguard_checker.py` — **Nachweis** (Positiv-/Negativproben): der Wächter erkennt echte Verstöße (Ziel `x[-1]`, Schreiben nach `knowledge/**`, Carry-over-Aufruf, Truncation, fehlendes `mkdir`, blinder Anhang, fehlende Rückgabe, „ältester" Leser) und lässt die erlaubten Formen durch. **Vollständigkeit (21.10.2026, V-08):** je Regel existiert **mindestens eine** Positiv- und eine Negativprobe — auch für R1.2, R2.2, R2.3, R3.1, R3.2 und R4.6 (vorher ohne Probe). Die Proben laufen **isoliert** (eigenes Temporärverzeichnis, Artefakt-Verzeichnisse leer) — der Repo wird dabei nicht verändert. Der Stichtag kommt aus dem Checker (`_stichtag`), nicht aus einer festen Datumsangabe im Test.
- `tests/test_md_writer_discipline.py` — Quelltext-/AST-Verträge der Schreiber (Muster `tests/test_status_guards_md.py`; keine DB, kein UI-Start).
- `tests/fixtures/md-guard/` — **getrackte Fixtures** (1 gültige + 1 verstoßende Datei), damit die artefaktbezogenen Regeln auch in der CI nachweisbar sind (§3, V-10).
- CI-Anhänger: `.github/workflows/docs.yml` — Pfadfilter seit 21.10.2026 (V-11) um `webui/**`, `scripts/**`, `tests/**`, `connectors/**` erweitert, damit eine Änderung an einem **Schreiber** den `mdguard`-Gate auslöst (vorher lief er nur bei Doku-Änderungen). `ci.yml` bleibt unangetastet (kein Doppel-Lauf).

## 8. Zeiger

| Gebiet | Spec (maßgeblich) |
|---|---|
| Markdown-Schreib-Regeln, Datumsrollen, Wächter | `knowledge/system/md-schreib-konvention.md` |
| Doku-Typen (normativ/deskriptiv/historisch) | `knowledge/system/doku-authority.md` |
| Meeting-Provider (VDO.Ninja), Linkformen | `knowledge/system/vdo-ninja-migration.md` |
| Aufnahme/Einwilligung | `knowledge/legal/recording-consent.md` |
