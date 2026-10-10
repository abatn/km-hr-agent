---
description: Erstellt Aufforderung für erstes Vorab-Screening (Video/Online)
---

## Funktionierende MCP-Connector

| Connector | Tool | Zweck |
|---|---|---|
| `filesystem` | `read_text_file` | Profile + Knowledge einlesen |
| `jitsi-meeting` | — | ⚠️ **ENTFERNT 27.09.2026** (0 Aufrufe im Code, aus `opencode.json` gelöscht) |
| `meeting-tools` | `generate_screening_questions` | Personalisierte Screening-Fragen |
| `meeting-tools` | `generate_ics_file` | ICS für Calendar-Import |
| `filesystem` | `write_file` | Ergebnis speichern |

**Hinweis:** Der Meeting-Raum ist seit **27.09.2026 VDO.Ninja** (Browser, Peer-to-Peer, kostenlos,
kein Account) — **kein Jitsi** mehr: Jitsis eigene Aufzeichnung bräuchte Jibri auf einem eigenen
Server. Spec: `knowledge/system/vdo-ninja-migration.md`.

> **Korrektur 27.09.2026 (Faktencheck, Lab-Prinzip):** Dieser Skill behauptete bisher, der Raum werde
> über `jitsi-meeting.jitsi_join_meeting` erstellt. **Das stimmte nicht** — gemessen: **0 Aufrufe** von
> `jitsi-meeting` im gesamten Code. Die Raum-URL wird als **String** gebaut:
> `scripts/agent-runner.py` (Einladung), `webui/components.py` (gemessen 10.10.2026) (Werkzeug),
> `webui/pages/candidate.py` (gemessen 10.10.2026) (Selbstpräsentation) — Muster
> `https://vdo.ninja/?director=prescreening{code}` (Raumname **ohne Bindestrich** seit 04.10.2026,
> Quelle: docs.vdo.ninja/advanced-settings/setup-parameters/room — *„1 to 49-characters long:
> aLphaNumEric-characters; case sensitive."*, Spec: `knowledge/system/vdo-ninja-migration.md` §2.5).

## Zwei Modi (v4.3, `knowledge/system/access-control.md`)

| Modus | Rolle | Ablauf |
|---|---|---|
| **Selbstpräsentation** | CANDIDATE | Kandidat sieht seine eigenen Screening-Fragen (aus eigenem Profil: Skills + Lücken) + eigenen VDO.Ninja-Raum `self-presentation-[code]`. Aufgenommene Video-Selbstpräsentation wird im eigenen Profil referenziert und ist für HR im Recruiting-Modus einsehbar — **bewusst OHNE Status-Gate**, damit HR die Vorstellung **vor** der Übernahme (`eingeladen`) bewerten kann (Nutzer-Entscheidung 28.09.2026, Design-Entscheidung; Kontakt-Daten bleiben erst ab `eingeladen` frei). Persistenz des Video-Links: Abschnitt `## Video-Vorstellung` in `ergebnisse/self-presentation-kandidat-{id}-{datum}.md` (Generierung im Sprachtest-Tab, Parität `app.py` (gemessen 10.10.2026)). Keine fremden Kandidaten wählbar. |
| **Recruiting** | EMPLOYER (HR) | Wie bisher: Screening für ausgewählten Matching-Kandidaten (Fragen + VDO.Ninja + ICS). NEU: Einsicht der Selbstpräsentations-Videos der Kandidaten (falls vorhanden). |

### Sackgassen-Regel für Leertexte (P1-3, 29.09.2026, Nutzer-GO)

Jeder Leerzustand in Pre-Screen/Onboarding enthält **mindestens einen klickbaren Weg** (AK aus `ergebnisse/ui-mvp-plan-v2.md` §6 P1-3: „je Stelle ≥1 Aktion (Button/Link)"):

| Leerzustand | Ort | Aktion (NEU) |
|---|---|---|
| Onboarding ohne `eingestellt`-Bewerbung | `webui/pages/candidate.py` `_tab_onboarding` | „→ Stellen ansehen" → `navigate_to("candidate", "stellen")` (echter Weg zur nächsten Bewerbung) |
| Freigabe-Report noch nicht da (nach Einstellung) | ebenso | Info-Text bleibt (Runner schreibt die Datei — bewusst **kein** Schein-Button; Vorbereitung läuft) |
| „Keine Selbstpräsentationen vorhanden" | `webui/components.py` `prescreen_recruiting_section` | Hinweis, woher Selbstpräsentationen kommen (Kandidat generiert sie im Sprachtest-Tab) — keine Schein-Aktion, weil HR hier nichts auslösen kann |
| „Keine Profile gefunden" (Generator) | `webui/components.py` (3 Stellen) | Hinweis + kein hartes `return` mehr: Seite rendert weiter, HR sieht den Hinweis statt einer leeren Seite; Profile entstehen via Admin-Upload → extract_profile |

**Quelle:** Design-Entscheidung auf Nutzer-GO (P1-Reihenfolge laut freigegebenem Plan); Zielregel „kein toter Endpunkt" (Plan §2/§6).

---

## Schritte

### 1. Kandidatenprofil einlesen
- **Connector:** `filesystem`
- **Tool:** `read_text_file`
- **Pfad:** Kandidatenprofil

### 2. Meeting-Link erstellen (VDO.Ninja — **ohne Connector**)
- **Weg:** String-Bildung im Code, **kein** MCP-Aufruf
- **Ort:** `scripts/agent-runner.py` (`create_invitation`), `webui/components.py` (`prescreen_recruiting_section`), `webui/pages/candidate.py` (Selbstpräsentation) — Codemarken `vdo_ninja_url`/`vdo_ninja_gast_url` (gemessen 591/594 ⓘ09.10.2026), `meet_url` (components.py, gemessen 704), `meet_url`/`video_url` (candidate.py, gemessen 1117/1512)
- **Muster:** HR/Director `https://vdo.ninja/?director=prescreening{code}` · Kandidat/Gast `?room=…&record=off` · **Selbstpräsentation = Solo-Sender `?push={code}&record=6000`** — Raumname **alphanumerisch, ohne Bindestrich** seit 04.10.2026 (Quelle: docs.vdo.ninja/advanced-settings/setup-parameters/room: *„1 to 49-characters long: aLphaNumEric-characters; case sensitive."*)
- **Aufnahmeparameter:** Einladungsraum **ohne** aufnahme-aktivierenden Parameter (Director parameterfrei, Gast `&record=off`); die **Selbstpräsentation** trägt seit 04.10.2026 `&record=6000` (`webui/pages/candidate.py`, gemessen 1117/1512 ⓘ09.10.2026). Aufzeichnung nur nach bestätigter Einwilligung, § 26 Abs. 2 BDSG. Spec: `knowledge/system/vdo-ninja-migration.md`
- **Rückgabe:** Meeting-URL (VDO.Ninja)

### 3. Screening-Fragen generieren
- **Connector:** `meeting-tools`
- **Tool:** `generate_screening_questions`
- **Parameter:**
  - `candidate_name`: Name
  - `position`: Stellenbezeichnung
  - `match_score`: Match-Score
  - `cultural_fit_score`: Kultur-Fit-Score
  - `strengths`: Stärken (kommasepariert)
  - `gaps`: Lücken (kommasepariert)

### 4. ICS-Datei erstellen (optional)
- **Connector:** `meeting-tools`
- **Tool:** `generate_ics_file`
- **Parameter:** topic, date, time, duration_minutes, meet_url (VDO.Ninja-Link), description

### 5. Ergebnis speichern
- **Connector:** `filesystem`
- **Tool:** `write_file`
- **Pfad:** `~/mimo-agents/km-hr-agent/ergebnisse/pre-screen-[name].md`

> ⚠️ **Design-Entscheidung (15.09.2026):** Default-Dauer 30 Min hat **keine externe Quelle**. **Alternative:** 15-20 Min (CareerPlug: "aim for 15 minutes and no more than 30"). **Validierung:** Korrelation zwischen Dauer und Einstellungsquote prüfen.

---

## Beispiel-Aufrufe

### Meeting-Raum-URL (seit 27.09.2026 VDO.Ninja, KEIN MCP-Tool)
> ⚠️ **Kein Tool-Aufruf.** `jitsi-meeting` wurde am 27.09.2026 aus `opencode.json` entfernt (0 Aufrufe im Code). Die Raum-URL wird als **String** im Runner gebildet — Codemarken `vdo_ninja_url` (Director) + `vdo_ninja_gast_url` (Kandidaten-Gast-Link mit `&record=off`, seit 28.09.2026), gemessen `scripts/agent-runner.py` (gemessen 10.10.2026) ⓘ09.10.2026; Variante A (Nutzer-Entscheidung 27.09.2026, Härtung 28.09.2026): **kein aufnahme-aktivierender** Parameter in der Einladungs-URL.

```python
code = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))   # 8 Zeichen, pro Einladung neu
vdo_ninja_url = f"https://vdo.ninja/?director=prescreening{code}"
```

| | Wert |
|---|---|
| Muster (HR/Director) | `https://vdo.ninja/?director=prescreening{code}` |
| Muster (Kandidat/Gast) | `https://vdo.ninja/?room=prescreening{code}&record=off` |
| `code` | 8 Zeichen (Kleinbuchstaben + Ziffern) — `random.choices(string.ascii_lowercase + string.digits, k=8)`, gemessen `scripts/agent-runner.py` (gemessen 10.10.2026) ⓘ09.10.2026 — **Design-Entscheidung**, keine externe Quelle |
| Aufnahme | `&record` speichert beim **Gast** (WebM, mit Einwilligung). `&autorecord`/`&autorecordremote` zeichnen **automatisch beim Laden** → § 26 Abs. 2 BDSG. **Nicht verwenden.** |
| Anbieter-Status | Aufnahme = „experimental" (vdo.ninja) |

### Fragen generieren
```json
{
  "name": "generate_screening_questions",
  "arguments": {
    "candidate_name": "Anna Schuster",
    "position": "Senior Cloud/DevOps Engineer",
    "match_score": 95,
    "cultural_fit_score": 89,
    "strengths": "AWS, Kubernetes, Python, CI/CD, Teamführung",
    "gaps": "Terraform"
  }
}
```
