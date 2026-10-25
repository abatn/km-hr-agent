# Meeting-Provider: Jitsi → VDO.Ninja (Spec, 27.09.2026)

> **Status: ENTSCHEIDUNG (Nutzer-GO „Variante A", 27.09.2026).** Diese Datei ist ab sofort die
> Source of Truth für den Meeting-Anbieter. Sie ersetzt die frühere Jitsi-Linie
> (Nutzer-Entscheidung 12.09.2026 „Jitsi only, NO Google Meet").
> **Auswahl: Variante A** = Migration **an allen drei Codestellen**, **keine** Aufnahme-Parameter
> in der URL, Aufzeichnung nur manuell nach bestätigter Einwilligung.

## 1. Warum gewechselt wird

Jitsis eigene Aufzeichnung braucht **Jibri auf einer eigenen Maschine** (Chrome-Instanz im
virtuellen Framebuffer + ffmpeg + ALSA-Loopback, nur **eine** Aufnahme gleichzeitig) — das ist genau
der Server-Aufwand, der vermieden werden soll.
*Quelle: https://github.com/jitsi/jibri, Abruf 27.09.2026 — „Jibri provides services for recording
or streaming a Jitsi Meet conference. It works by launching a Chrome instance rendered in a virtual
framebuffer and capturing and encoding the output with ffmpeg. It is intended to be run on a separate
machine (or a VM) … Only one recording at a time is supported on a single jibri."*

## 2. Der Wechsel im Code — alle vier Stellen

| Ort | ALT | NEU |
|---|---|---|
| `scripts/agent-runner.py` (gemessen 10.10.2026) (Director-URL; Gast-URL `&record=off`, Einladung an den Kandidaten) | `jitsi_url = f"https://meet.jit.si/pre-screening-{code}"` | `vdo_ninja_url = f"https://vdo.ninja/?director=prescreening{code}"` + `vdo_ninja_gast_url = f"https://vdo.ninja/?room=prescreening{code}&record=off"` (letzteres seit 28.09.2026, §2.2; **Raumname ohne Bindestrich seit 04.10.2026, §2.5**) |
| `webui/components.py` (gemessen 10.10.2026) (Pre-Screen-Werkzeug) | `meet_url = f"https://meet.jit.si/pre-screening-{room_code}"` | `meet_url = f"https://vdo.ninja/?director=prescreening{room_code}"` (Raumname ohne Bindestrich seit 04.10.2026, §2.5) |
| `webui/pages/candidate.py` (gemessen 10.10.2026) (Selbstpräsentation) | `meet_url = f"https://meet.jit.si/{room_name}"` | `meet_url = f"https://vdo.ninja/?director={room_name}"` (inzwischen `?push=` — §2.3; Stream-ID alphanumerisch seit 20.10.2026 — §2.6) |
| `mcp-meeting-server.py` (Codemarke `def create_meeting_link`, gemessen 10.10.2026) (LEGACY-Tool `create_meeting_link`, 0 py-Aufrufer, per MCP-stdio erreichbar; Details §4 Punkt e) | `https://meet.jit.si/pre-screening-{code}` | `https://vdo.ninja/?director=prescreening{code}` (Raumname ohne Bindestrich seit 04.10.2026, §2.5) |

**Warum trotzdem „keine Code-Änderung nötig" im Auftragstext nicht zutrifft:** Der Auftrag forderte
beides — „URL ersetzen" und „ohne Änderung am Code". Es ist eine **Code-Änderung** an genau diesen
drei Zeilen. Die Projektarchitektur, Abhängigkeiten und Abläufe bleiben unangetastet.

### 2.1 JSON-Feldname: seit 27.09.2026 (§I-F) `vdo_ninja_url` statt `jitsi_url`
Der Runner gibt das Ergebnis als `{"vdo_ninja_url": ..., "vdo_ninja_gast_url": ..., "recording": false, "ics_path_hr": ...}` zurück (`scripts/agent-runner.py` (gemessen 10.10.2026), Stand 28.09.2026).
Gelesen wird der Schlüssel in `webui/pages/candidate.py` (gemessen 10.10.2026) und `webui/pages/employer.py` (gemessen 10.10.2026).

→ **Umbenannt** in einem eigenen Schritt (§I-F, nach dem Nutzer-GO für Variante A). Grund: der alte
Name beschrieb einen Provider, den es nicht mehr gibt; die Feldsumme in `knowledge/system/agent-automation.md`
und die Portal-Specs würden sonst weiter „Jitsi" behaupten.

**Abwärtskompatibilität (bewusst):** Beide Leser prüfen `vdo_ninja_url` **zuerst** und fallen auf
`jitsi_url` zurück (`or _art.get("jitsi_url")`). Grund: In `agent_tasks.result_json` liegen
Alt-Einladungen mit dem alten Schlüssel (Tasks #24, #89, #117, #172). Ohne Fallback zeigte die
Einladungskarte im Employer-Portal für diese vier Bewerbungen **keinen** Link mehr.
*Beleg (UI-Nachweis 27.09.2026):* Auf `/employer/match` rendern weiterhin 4 Jitsi-Links
(„E2E Kette", „taoufik" ×2, „batnini abdelkader") — genau die Alt-Einladungen. Die neue Einladung
zeigt VDO.Ninja.

### 2.2 Gast-Link-Härtung (28.09.2026, Gates 8/9/10 aus `recording-consent.md`)

- **Kandidat (Gast):** `https://vdo.ninja/?room=prescreening{code}&record=off` — Variable `vdo_ninja_gast_url` in `scripts/agent-runner.py` (`create_invitation`). Quellen: docs.vdo.ninja/getting-started/rooms („Guests have their own link to join a room"; Passwort optional) + docs.vdo.ninja/advanced-settings/recording-parameters/and-record (`off` deaktiviert die Aufnahme, auch den Remote-Trigger). **Raumname ohne Bindestrich seit 04.10.2026 (§2.5).**
- **HR (Director):** `https://vdo.ninja/?director=prescreening{code}` (`vdo_ninja_url`); Rollentrennung (`recording-consent.md`: „Der Arbeitgeber ist der Director"). **Raumname ohne Bindestrich seit 04.10.2026 (§2.5).**
- **Leser:** Einladungs-Mail + Kandidaten-ICS (`ics_path`) + Kandidaten-Karte (`candidate.py`) = Gast-Link; HR-Karte (`employer.py`) + HR-ICS (`ics_path_hr`) = Director-Link; Einladungs-Bericht zeigt beide. Alt-Einladungen ohne die neuen Keys fallen per Fallback auf `vdo_ninja_url` zurück.
- **Überholt durch §2.3/§2.4 (Ist 09.10.2026):** `candidate.py` (Selbstpräsentation) — der frühere `?director=`-Stand gilt **nicht mehr**; Ist-Code `webui/pages/candidate.py` (gemessen 10.10.2026) = `https://vdo.ninja/?push=<id>&record=6000` (Solo-Sender + Aufnahme-Knopf, §2.3/§2.4). **Bewusst unverändert:** nur `mcp-meeting-server.py` (Codemarke `mcp`, gemessen 10.10.2026) (LEGACY-Tool, 0 py-Aufrufer).

### 2.3 ⚠️ KORREKTUR (03.10.2026): Selbstpräsentation ist ein **Solo-Sender** (`&push`), nicht `&director`
**Befund (Nutzerauftrag „VDO prüfen", Analyse + offizielle Doku):** Die Selbstpräsentation des
Kandidaten (`webui/pages/candidate.py`, „Selbstpräsentation starten" + „Video-Link generieren")
erzeugte `https://vdo.ninja/?director=…`. **`&director` ist der Regieraum** — laut Anbieter-Doku
sieht er den Raum *„without joining it themselves"*, **sendet also kein eigenes Bild**.
→ Der Kandidat öffnet einen **leeren Regieraum**; es kommt **kein Bild** an ⇒ die Selbstpräsentation
funktioniert nicht.

**Offizielle Lösung** (docs.vdo.ninja, Abruf 03.10.2026): Für eine **Solo-Selbstpräsentation ohne
zweite Person** ist **`&push`** zu verwenden (Sender), **nicht** `&director`:
`https://vdo.ninja/?push=<id>` — optional mit lokaler Aufnahme `&record=6000` (Datei im
Download-Ordner des Kandidaten).
**Rechtliche Sperre:** `&record` erst **nach** dokumentierter Aufnahme-Einwilligung — siehe
`knowledge/legal/recording-consent.md` (i) Punkt 8 (Einwilligung **bei der Registrierung**); bis
dahin **nur** `?push=<id>` **ohne** Aufnahme-Parameter.

**Status:** ✅ **UMGESETZT 03.10.2026** — `webui/pages/candidate.py` („Selbstpräsentation starten"
`?push=…` + „Video-Link generieren" `?push=…`); **Stream-IDs alphanumerisch seit 20.10.2026**
(`selfpresentation{code}` bzw. `vorstellung{cand_id}{uuid8}`, §2.6).
**Hinweis:** Bereits persistierte Alt-Links (`ergebnisse/self-presentation-*.md`) bleiben
`?director=` — **keine Migration** (der Kandidat erzeugt bei Bedarf einen neuen `?push=`-Link).
**Portal-Verhalten (Stand 21.10.2026):** Der Kandidaten-Portal-Leser (`def load_video_link`,
`webui/pages/candidate.py`, gemessen 21.10.2026) bevorzugt die **heutige** Datei und fällt
sonst auf die **neueste Datei mit** Video-Abschnitt zurück — ein persistierter Alt-`?director=`-Link
bleibt damit **im Portal sichtbar** (Leser-Fallback, Spec
`knowledge/system/md-schreib-konvention.md` R-S2 „Leser-Regel"). Für den **Schreiber** gilt
weiterhin: nur die Datei des **heutigen** Datums, kein Carry-over über Tagesgrenzen.

**HR-Sicht (Arbeitgeber/Admin, Stand 22.10.2026, V-19):** Die Recruiting-Ansicht
(`def prescreen_recruiting_section`, `webui/components.py`) wendet **dieselbe Leser-Regel** an,
aber **ohne** Alt-Link-Ausgabe: je Kandidat wird **nur der neueste Stand mit nutzbarem
Video-Abschnitt** gelistet (Auswahl-Helfer `def selbstpraesentation_je_kandidat`,
`webui/components.py`), und ein `?director=`-Link gilt dort **nicht** als nutzbarer Link
(Helper `def _video_link_aus_abschnitt`, `webui/components.py`) — der veraltete Director-Link
wird **nicht** als Link ausgegeben (Spec R2.2). **Verhaltensänderung:** zuvor wurden alle
Fassungen eines Kandidaten gelistet. Nachweis: `tests/test_video_section.py`
(Proben „HR-Sicht zeigt nur den neuesten Stand mit Video" / „Director-Link wird ignoriert").

### 2.4 Aufnahme aktiviert (`&record=6000`) + Video-Upload (04.10.2026, Nutzerauftrag)
**Offiziell belegt** (docs.vdo.ninja, Abruf 04.10.2026): Der **Aufnahme-Knopf** erscheint nur mit
**`&record`** (positiver Integer = Video-Bitrate in kbps; `6000` = 6 Mbps = Default). Ohne den
Parameter fehlt der Knopf (DOM `display:none`), die Aufnahme bleibt nur über Rechtsklick/Director
erreichbar.
- **Fix:** beide Kandidaten-Links tragen jetzt **`&record=6000`**
  (`webui/pages/candidate.py`: „Selbstpräsentation starten" + „Video-Link generieren").
- **Aufnahme-Ablage:** lokal beim Kandidaten (WebM, Download-Ordner) — VDO kann **nicht** in die App
  schreiben.
- **Upload ermöglicht:** Dokumente-Tab (`_dokumente_section`) akzeptiert jetzt **`.webm/.mp4`**
  (`accept` + serverseitige Endungsprüfung) und **`max_file_size=150_000_000`** (≈150 MB für 2–3 min
  @ 6000 kbps); Label „Dokumente (PDF/TXT/Video, …)". Der CV-Upload bleibt unverändert (PDF/TXT, 5 MB).
- ~~**Offen: Stream-ID alphanumerisch**~~ → **✅ erledigt 20.10.2026 (§2.6):** beide Kandidaten-
  `?push=`-IDs sind alphanumerisch (`selfpresentation{code}` bzw. `vorstellung{cand_id}{uuid8}`).
- **Offen (nicht umgesetzt):** Server-RAM bei großen Uploads (`await file.read()` lädt komplett);
  UI-Hinweis zum Aufnahme-Ablauf.

### 2.5 Raumname alphanumerisch: `prescreening{code}` (04.10.2026, Lab Schritt 1–3)

**Quelle (Lab Schritt 1):** docs.vdo.ninja/advanced-settings/setup-parameters/room, Abruf 04.10.2026:
*„&room — 1 to 49-characters long: aLphaNumEric-characters; case sensitive."*
**Live-Befund (04.10.2026):** Bei `pre-screening-{code}` zeigte VDO auf Control Room **und**
Gastseite die Warnung *„Info: Only AlphaNumeric characters should be used for the room name.
The offending characters have been replaced by an underscore"* → der Raum hieß tatsächlich
`pre_screening_{code}` (Bindestriche durch `_` ersetzt). Beide Links normalisierten identisch,
die Verbindung funktionierte — die Warnung und der abweichende Raumname entfallen jetzt.

| Ort | ALT | NEU (seit 04.10.2026) |
|---|---|---|
| `scripts/agent-runner.py` `create_invitation` (Director + Gast) | `?director=pre-screening-{code}` · `?room=pre-screening-{code}&record=off` | `?director=prescreening{code}` · `?room=prescreening{code}&record=off` |
| `webui/components.py` `prescreen_recruiting_section` (Pre-Screen-Werkzeug) | `?director=pre-screening-{room_code}` | `?director=prescreening{room_code}` |

- **Geändert wurde ausschließlich der Raumname** (ohne Bindestrich); `code`/`room_code` bleibt
  8 Zeichen Kleinbuchstaben+Ziffern (`string.ascii_lowercase + string.digits`, `random.choices`).
- **Bewusst unverändert:** `mcp-meeting-server.py` (Codemarke `mcp`, gemessen 10.10.2026) (LEGACY, 0 py-Aufrufer).
  ~~Die Kandidaten-`?push=`-IDs (`self-presentation-…`, `vorstellung-…`)~~ → **seit 20.10.2026
  alphanumerisch (§2.6).**
- **Keine Migration bestehender Links/ICS** (wie §2.3): Alt-Einladungen behalten ihren Raumnamen.
- **Verifikation (04.10.2026, isolierte Browser-Prüfung):** Director- und Gast-Link ohne
  VDO-Warnung geöffnet, Gast beigetreten → Control Room zeigt den Feed (gleicher Raum);
  Screenshots + Messwerte in `ergebnisse/entscheidungen.md` (Abschnitt Raumname alphanumerisch).

### 2.6 Stream-ID alphanumerisch: `selfpresentation{code}` / `vorstellung{cand_id}{uuid8}` (20.10.2026, Lab Schritt 1–3)

**Quelle (Lab Schritt 1):** docs.vdo.ninja/advanced-settings/setup-parameters/push, Abruf 20.10.2026:
*„&push — 1 to 64-characters long. Non-alphanumeric characters are sanitized to _; case sensitive."*
**Live-Befund (20.10.2026):** Bei `?push=self-presentation-{code}` zeigte der VDO-Dialog
*„Info: Only Alphanumeric characters should be used for the stream ID. The offending characters
have been replaced by an underscore."* (Screenshot `/tmp/opencode/vdo-analyse-20261020/C_push.png`) —
die Stream-ID hieß tatsächlich `self_presentation_{code}`. **Auch `_` ist non-alphanumeric**
(sonst läge die Sanitisierung ja auf derselben Ebene) — Unterstriche sind deshalb **kein**
zulässiger Ersatz.

| Ort (Codemark) | ALT (bis 19.10.2026) | NEU (seit 20.10.2026) |
|---|---|---|
| `webui/pages/candidate.py` `start_prescreen` („Selbstpräsentation starten") | `?push=self-presentation-{room_code}` | `?push=selfpresentation{room_code}` |
| `webui/pages/candidate.py` `_gen_video_link` („Video-Link generieren") | `?push=vorstellung-{cand_id}-{uuid8}` | `?push=vorstellung{cand_id}{uuid8}` |

- **Geändert wurde ausschließlich die Stream-ID** (Bindestriche entfernt); die URL-Parameter
  (`?push=…&record=6000` — gleiche Wörter, gleiche Groß-/Kleinschreibung, gleiche Reihenfolge)
  bleiben unverändert. Länge ≤ 64 Zeichen (`selfpresentation` + 8; `vorstellung` + cand_id + uuid8);
  **Eindeutigkeit bleibt über `uuid8`**, die Zufälligkeit wurde nicht verändert (`uuid.uuid4()`
  unverändert; `room_code` weiterhin 8 Zeichen aus `string.ascii_lowercase + string.digits`).
- **Bestehende Alt-Links bleiben hyphenisiert und funktionieren:** VDO sanitizt `?push=`-IDs auf
  **beiden** Seiten identisch (`self_presentation_…` bzw. `vorstellung_…`) — Sender und Empfänger
  landen im selben Stream. **Keine DB-Migration**, keine Änderung an persistierten ICS/MD-Dateien.
- **Bewusst unverändert:** `app.py` (Paritäts-Referenz; Codemarken `room_name` / `video_code`,
  gemessen 20.10.2026 — behält das Alt-Muster) sowie `vdo_ninja_url` / `vdo_ninja_gast_url` in
  `scripts/agent-runner.py` und `mcp-meeting-server.py` (Regie-/Gast-Links haben keine Bindestriche,
  §2.5).

## 3. Aufzeichnungs-Parameter: kein einschaltender gesetzt — Härtung `&record=off` auf dem Gast-Link (28.09.2026)

Alle drei Parameter sind **real** (Quelle: docs.vdo.ninja, Abruf 27.09.2026):

| Parameter | Wirkung laut Anbieter-Doku | Unsere Entscheidung |
|---|---|---|
| `&record` | Aufnahme **für den Gast**, Datei landet „in real-time to the **guest's** local download folder", WebM (H264/VP8 + OPUS/PCM) | ❌ kein einschaltender Wert · ✅ `off` im Kandidaten-Gast-Link seit 28.09.2026 (Gate 8; deaktiviert Aufnahme inkl. Remote-Trigger) |
| `&autorecord` | nimmt lokale **und** entfernte Videos **automatisch beim Laden** auf | ❌ nicht in der URL |
| `&autorecordremote` | nimmt nur die entfernten Videos automatisch beim Laden auf | ❌ nicht in der URL |

**Begründung (rechtlich, nicht technisch):**
`&autorecord` / `&autorecordremote` zeichnen **ohne vorherige Einwilligung** auf. Nach
**§ 26 Abs. 2 BDSG** setzt eine Aufnahme im Bewerbungsverfahren eine **schriftliche oder elektronische,
informierte und freiwillige** Einwilligung voraus; Bewerber gelten laut **§ 26 Abs. 8 BDSG** als
Beschäftigte. Ein automatischer Start würde die Freiwilligkeit strukturell ausschließen.
*Quellen: gesetze-im-internet.de/bdsg_2018/__26.html, Abruf 27.09.2026.*

**Zweiter Grund:** Die Aufnahme landet laut Doku beim **Gast**, nicht beim Arbeitgeber. Für ein
Bewerbungsgespräch ist die Datei beim **Bewerber** das falsche Ziel (Aufbewahrung, Löschfrist).

**Wann die Parameter doch erlaubt sind:** erst wenn (a) die Einwilligungs-Spec
(`knowledge/legal/recording-consent.md`, **geschrieben 27.09.2026**) erfüllt ist, (b) der
Einwilligungsdialog im Portal steht und (c) die Löschfrist festgelegt ist. Diese drei Punkte sind
Voraussetzung, nicht Kür.

> **Stand 27.09.2026:** Bedingung (a) ist erfüllt — `knowledge/legal/recording-consent.md` existiert
> mit einem **12-Punkte-Gate** (Abschnitt d). Die Bedingungen (b) und (c) sind **offen**: kein
> Einwilligungsdialog im Portal, Löschfrist nicht technisch umgesetzt. Das Gate ist zu **12/12 offen**
> ⇒ **es wird kein aufnahme-aktivierender Parameter gesetzt.**
> **Update 28.09.2026 (Nutzer-GO):** Härtung `&record=off` liegt jetzt auf dem Kandidaten-Gast-Link
> (Gates 8/9/10 ✅: `vdo_ninja_gast_url`, HR-Prozessregel als UI-Hinweis, Feld `recording: false`);
> Einwilligungsdialog und Löschfrist bleiben offen.

> ⚠️ **Neuer Befund aus der Anbieter-Doku (27.09.2026), der die obige „keine Parameter"-Begründung
> relativiert:** `&record`-Doku — *„The Director of a room can trigger the record function remotely,
> even if the `&record` parameter has not been added."* Unsere URL ist ein `?director=`-Link, der
> Arbeitgeber ist also der **Director** und **kann** auch ohne Parameter aufnehmen. „Kein Parameter in
> der URL" ist damit **keine technische Garantie**, sondern nur die Voreinstellung. Deshalb verlangt
> `recording-consent.md` (d) zusätzlich die Härtung `&record=off` (Punkt 8) und eine Prozessregel
> für die interviewende HR-Seite (Punkt 9).

⚠️ **Hinweis des Anbieters:** Die Aufnahmefunktion wird auf vdo.ninja selbst als
**„experimental"** bezeichnet. Auch das spricht gegen eine automatische Aktivierung.

## 4. Was unverändert bleibt
- **`meeting-tools`: Screening-Fragen + ICS bleiben unverändert** (`scripts/agent-runner.py` (gemessen 10.10.2026); HR-ICS-Varianz seit 28.09.2026).
  **Ausnahme Punkt e) (27.09.2026, Runde c–g):** das LEGACY-Tool `create_meeting_link`
  (**0 Aufrufer**, gemessen `grep -rn create_meeting_link --include=*.py`) erzeugt seit
  27.09.2026 `https://vdo.ninja/?director=pre-screening-{code}` statt
  `https://meet.jit.si/pre-screening-{code}` – Vorbild = Projektstandard `scripts/agent-runner.py` (gemessen 10.10.2026).
  **Warum Umbau statt Entfernen** (Auftrag lautete „entfernen oder umbauen“): (1) „VDO.Ninja
  only, NO Jitsi“ (`AGENTS.md`) gilt auch für angebotene, ungenutzte Tools – der Server ist
  `enabled` in `opencode.json` (gemessen 10.10.2026) und kann von Agent-Sessions jederzeit aufgerufen werden;
  (2) Löschung hätte den MD-Folat in mindestens 5 Dateien ausgelöst (Census-Zeilen in
  `knowledge/system/mcp-connector-config.md`, `instructions.md`, `skills/README.md`, `knowledge.md`,
  diese Spec) bei gleichem Konsistenznutzen; (3) Präzedenz der §I-F-Migration: alle URL-Stellen
  wurden **umgebaut, nicht gelöscht** (entscheidungen.md, Stand 27.09.2026 00:32).
- Die ICS-Datei enthält nur die `meet_url` — sie zeigt jetzt also auf VDO.Ninja.
- `opencode.json` **wurde** angefasst (§I-F, 27.09.2026): der Server `jitsi-meeting` ist
  **entfernt** (11 Tools, im App-Code 0 Aufrufe). Es bleiben **14** MCP-Server (13 local + 1 remote).
  Der Ordner `jitsi-mcp-server/` **existiert nicht mehr auf Disk** (Stand 01.10.2026: `ls -d jitsi-mcp-server` → No such file or directory).

## 5. Erledigt (§I-F, 27.09.2026)
1. ✅ **`jitsi-meeting` aus `opencode.json` entfernt** (11 Tools, 0 Aufrufe). `mcp` = 14 (13 local +
   1 remote). Zählwerk in `AGENTS.md`, `knowledge/system/mvp.md`, `knowledge/system/mcp-connector-config.md`,
   `knowledge.md`, `instructions.md`, `knowledge/system/c2-service.md` nachgezogen.
2. ✅ **Feldname `jitsi_url` → `vdo_ninja_url`** (siehe 2.1), mit Legacy-Fallback in beiden Lesern.
3. ✅ **Doc-Stellen** in `access-control.md`, `README.md`, `knowledge.md`, `agent-automation.md`,
   `pre-screen/SKILL.md`, `skills/README.md`, `instructions.md`, `mvp.md`, `c2-service.md`, `AGENTS.md`
   auf VDO.Ninja umgestellt.
4. ✅ **Live-Beweis** 27.09.2026: Einladung über den echten „Einladen"-Button des Employer-Portals →
   `https://vdo.ninja/?director=pre-screening-v2mye7b5`, ICS mit VDO.Ninja-LOCATION, Mail versendet.
   Bericht: `ergebnisse/vdo-ninja-bereinigung-2026-09-27.md`.

## 6. Offen (bewusst nicht entschieden)
1. ~~**Alt-Einladungen** (Tasks #24, #89, #117, #172) behalten ihren `jitsi_url`-Schlüssel …~~
   **✅ erledigt 28.09.2026 (Nutzer-GO „führe das"):** einmalige Migration der 4 Alt-Daten:
   `jitsi_url` entfernt (0 Treffer danach), `vdo_ninja_gast_url` (`?room=…&record=off`) +
   `recording: false` ergänzt, `vdo_ninja_url` (Director) bleibt erhalten — die Zeilen entsprechen
   jetzt dem Schema der Neuerungen (Härtung Schritt 2, 28.09.2026). DB-Backup vorher:
   `/tmp/opencode/feedback-db-pre-d-20260928-0138.bak.db`. Nachweis: `ergebnisse/entscheidungen.md`.
2. **Sprachaufzeichnung** (Sprachtest-Tab) — dieselben Regeln, derzeit nicht angeboten.
3. Ob VDO.Ninja **selbst gehostet** wird (offener Quellcode, keine fremden TURN-Server) oder als
   Dienst genutzt wird — Datenschutzfrage, siehe `ergebnisse/browser-recording-plan-2026-09-27.md`.
4. **`jitsi-mcp-server/`-Ordner:** ~~liegt ungenutzt im Repo~~ → **existiert nicht mehr auf Disk** (Stand 01.10.2026). Damit erledigt.

## 7. Quellen (Q1–Q6 abgerufen 27.09.2026 · Q7 abgerufen 20.10.2026)
| # | Quelle | Für |
|---|---|---|
| Q1 | https://github.com/jitsi/jibri | Jibri = eigener Server für Jitsi-Aufzeichnung |
| Q2 | https://docs.vdo.ninja/advanced-settings/recording-parameters/and-record | `&record`, WebM, Ablage beim Gast |
| Q3 | https://docs.vdo.ninja/advanced-settings/recording-parameters/and-autorecord | `&autorecord` = automatisch beim Laden |
| Q4 | https://docs.vdo.ninja/advanced-settings/recording-parameters/and-autorecordremote | `&autorecordremote` |
| Q5 | https://www.gesetze-im-internet.de/bdsg_2018/__26.html | § 26 Abs. 2 + Abs. 8 BDSG (Bewerber = Beschäftigte) |
| Q6 | https://docs.vdo.ninja/readme/why-use-vdo-ninja-over-other-solutions | kostenlos, Peer-to-Peer, quelloffen, selbst hostbar |
| Q7 | https://docs.vdo.ninja/advanced-settings/setup-parameters/push | `&push` = Stream-ID, 1–64 Zeichen, **alphanumerisch** (Non-Alphanumeric → `_`), case sensitive (§2.6) |
