# ANIMATION_ENTSCHEIDUNG — Startseite „Das Agenten-Prinzip"

**Stand:** 25.10.2026 · **Umsetzung:** `webui/pages/landing.py` · **Test:** `tests/e2e_landing_chapters.py`

## Scope und Stack-Abgleich

Der Auftrag nennt ein „Reise-System" mit FastAPI/Jinja2. Dieses Repository ist der **KM-HR-Agent** mit **NiceGUI**; die Startseite `/` liegt in `webui/pages/landing.py`. Die Kapitel sind deshalb domänenneutral formuliert (Gehirn, Loop, Sub-Agenten, Werkzeuge, Ergebnis) und werden auf das HR-Agenten-System angewendet. Der Dokumentationspfad `ui/` bleibt wie im Auftrag; die UI selbst liegt unter `webui/`.

## Recherche (Quellen)

- **Lokales Three.js-Bundling:** `three.module.js` importiert seit r167 relativ `three.core.js`. Beide Dateien plus `LICENSE` müssen gemeinsam ausgeliefert werden; nur die Moduldatei zu kopieren erzeugt einen 404. Quelle: <https://threejs.org/manual/pages/installation.html>
- **Import-Map-Falle:** NiceGUI injiziert bereits eine Import-Map. Ein zweiter `type="importmap"` ist nicht Firefox-portabel. Der URL-Import `/static/three/three.module.js` braucht keine Map und bleibt deshalb die robuste Wahl. Quelle: <https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script/type/importmap>
- **Kamerafahrt:** Eine einzige Master-Zeit `t ∈ [0, 30)` treibt Kamera, Captions, Countdown und Fortschritt. Zwischen den Kapiteln wird mit `smoothstep` interpoliert; die Kamera steht 13 Einheiten vor der aktiven Station. Quelle: <https://threejs.org/docs/#api/en/math/MathUtils>
- **Text-Overlays:** Captions bleiben DOM-Elemente (keine Canvas-Texte), damit sie für Screenreader und Zoom zugänglich sind; das Canvas ist `aria-hidden`. Quelle: <https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/canvas#accessibility>
- **Autoplay/Accessibility:** Bewegte Inhalte über fünf Sekunden brauchen eine Pause-/Stop-Möglichkeit (WCAG 2.2.2). Deshalb gibt es Pause/Weiter, Kapitel-Dots und „Nochmal ansehen". Quelle: <https://w3c.github.io/wcag/understanding/pause-stop-hide.html>
- **Reduced Motion:** `prefers-reduced-motion` wird in JavaScript gelesen; die Szene bleibt dann statisch (Kapitel 1, Countdown 30, Pause deaktiviert). Quelle: <https://web.dev/articles/prefers-reduced-motion>
- **Visuelle Prüfung:** Playwright kann eine Endlos-Canvas-Schleife nicht „auswarten"; die Seite bietet `window.__kmhr.seek(t)` und einen Pause-Zustand. Der Screenshot wird bei eingefrorener Zeit erzeugt. Quelle: <https://playwright.dev/docs/test-snapshots>
- **GitHub-Referenzen:** Three.js-Beispielsammlung (Kamera-/Szenenmuster) <https://github.com/mrdoob/three.js/tree/dev/examples>; Playwright-Screenshot-Doku <https://playwright.dev/docs/api/class-page#page-screenshot>.

## Kapitel und Timeline (exakt 30,0 s)

| # | Kapitel | Fenster | Inhalt der Station |
|---|---|---|---|
| 1 | Das Gehirn | 0,0–5,2 s | Drahtgitter-Kern (Orchestrator), 240 Nervenpartikel, drei Ringbahnen |
| 2 | Die Loop | 6,0–11,2 s | Ringbahn mit Queue → Claim → Task → Retry → Done, goldener Impuls |
| 3 | Die Sub-Agenten | 12,0–17,2 s | Zehn Aufgaben-Knoten (`TASKS`) auf einem Bogen, sequenzielles Glühen |
| 4 | Die Werkzeuge | 18,0–23,2 s | Acht MCP-Pods um einen Hub (PDF, Recht, Mail, Meeting, Sprache, Benchmark, Gehalt) |
| 5 | Das Ergebnis | 24,0–30,0 s | Score-Karte mit sieben Kategorien, Häkchen, „Mensch entscheidet" |

Zwischen den Fenstern liegen 0,8-s-Übergänge (Kamera fährt, Caption bleibt kurz stehen). `TOTAL = 30.0`; die Fenster sind monoton, überlappen nicht und enden exakt bei 30,0 s. Die Struktur wird von `tests/test_landing_page.py::test_kapitelstruktur_synchron` gegen `_CHAPTERS`, `_STEP_LINES` und die `builders`-Liste geprüft.

## Gestaltung

- **Farben:** bestehende UI-Palette — Primär `#1E40AF`, hell `#3B82F6`, Akzent `#F59E0B`, Himmel `#93C5FD`, Hintergrund `#F8FAFC`, Ink `#1E3A8A`.
- **Stationen:** 30 Einheiten auseinander auf der -Z-Achse; die Kamera blickt auf die Stationsmitte. Ein straffer Nebel (18–52) blendet die nächste Station aus, damit die aktive Station ruhig bleibt.
- **Partikel:** 240 Punkte in einem einzigen `THREE.Points`-Objekt; keine 240 Einzelmeshes.
- **Labels:** Canvas-Sprites für 3D-Beschriftungen; die narrativen Texte liegen als DOM-Captions darüber.
- **Interaktion:** Kapitel-Dots springen direkt in ein Kapitel; Pause/Weiter friert die Master-Zeit ein; „Nochmal ansehen" startet bei 0; der Login-CTA erscheint im Ergebnis-Kapitel.
- **Reduced Motion:** statischer Frame, Countdown `30`, Pause-Button deaktiviert; die Szene bleibt visuell stehen.

## Tests und Beweis

```bash
.venv-streamlit/bin/python3 -m pytest tests/test_landing_page.py -q
.venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8097 --only e2e_landing_chapters
```

Der E2E-Lauf prüft Canvas/`window.__kmhr`, alle fünf Kapitel (Titel, Dot, Kamera-Ziel), Countdown, Fortschrittsbalken, Dot-Klick, Pause/Weiter, Reduced Motion und den Login-Link. Screenshots:

- `ergebnisse/screenshots/landing-agent-prinzip.png` (Kapitel 3)
- `ergebnisse/screenshots/landing-agent-ergebnis.png` (Kapitel 5)

Die Screenshots liegen bewusst unter `ergebnisse/` (gitignored, keine personenbezogenen Daten). Der Live-DB-sha256 bleibt beim E2E-Lauf unverändert; die isolierte Instanz nutzt den Spiegel aus `tests/conftest.py`.

## Design-Entscheidungen (nicht extern belegt)

- Fünf Kapitel statt sieben: Der Auftrag fordert mindestens fünf; die fünf Stationen bilden das Agenten-Prinzip präziser ab.
- 30-s-Timeline mit 0,8-s-Übergängen und 13-Einheiten-Kameraabstand.
- Pause/Weiter zusätzlich zu Dots und Replay (WCAG-Konformität, nicht vom Auftrag gefordert).
- Straffer Nebel und feste Label-Zeilen gegen visuelles Rauschen.
