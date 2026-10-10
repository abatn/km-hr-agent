# UI Design System – KM-HR-Agent (NiceGUI)

> **Stand:** 20.09.2026 (Phase 2: einheitliche shell()-Navigation, 8/10/12 Seiten) · **NiceGUI:** 3.17.1 · **Framework:** Quasar (Material Design) + Tailwind CSS
> **Referenzen:** Personio (Clean SaaS), Workday (Enterprise Dashboard), Linear (Minimal UI)

---

## 1. Design-Prinzipien

| Prinzip | Umsetzung |
|---|---|
| **Klarheit** | Jede Seite hat 1 primäre Aktion, klare Hierarchie |
| **Konsistenz** | Gleiche Komponenten, Abstände, Farben über alle Rollen |
| **Feedback** | Jede Aktion gibt visuelles Feedback (Notify, Animation, Status) |
| **Liveness** | Live-Daten via timer/refreshable, nie statische Blanko-Seiten |
| **Barrierefreiheit** | Ausreichende Kontraste, keyboard-navigierbar, aria-labels |

---

## 2. Farben

### 2.1 Primäre Palette (Light Mode)

| Token | Hex | Verwendung |
|---|---|---|
| `primary` | `#1E40AF` | Header, Buttons, Links, Aktiver Tab |
| `primary-light` | `#3B82F6` | Hover-State, Sekundäre Buttons |
| `primary-dark` | `#1E3A8A` | Dark-Mode Header |
| `secondary` | `#059669` | Erfolg, Positive Aktionen, Score ≥80 |
| `accent` | `#F59E0B` | Warnungen, Score 60-79, Badge-Hintergrund |
| `danger` | `#DC2626` | Fehler, Ablehnung, Score <60 |
| `info` | `#0EA5E9` | Info-Notifications, Links |

### 2.2 Neutrale Palette

| Token | Hex | Verwendung |
|---|---|---|
| `bg-page` | `#F8FAFC` | Seitenhintergrund |
| `bg-card` | `#FFFFFF` | Karten, Panels |
| `bg-elevated` | `#F1F5F9` | Hover-Hintergrund, Sidebar |
| `border` | `#E2E8F0` | Rahmen, Trennlinien |
| `text-primary` | `#0F172A` | Haupttext |
| `text-secondary` | `#64748B` | Sekundärtext, Labels |
| `text-muted` | `#94A3B8` | Platzhalter, Descriptions |

### 2.3 Dark Mode Palette

| Token | Hex | Verwendung |
|---|---|---|
| `bg-page` | `#0F172A` | Seitenhintergrund |
| `bg-card` | `#1E293B` | Karten, Panels |
| `bg-elevated` | `#334155` | Hover-Hintergrund, Sidebar |
| `border` | `#475569` | Rahmen |
| `text-primary` | `#F8FAFC` | Haupttext |
| `text-secondary` | `#94A3B8` | Sekundärtext |

### 2.4 Rollen-Farben

| Rolle | Farbe | Badge-Hintergrund |
|---|---|---|
| Candidate | `#3B82F6` (Blue) | `bg-blue-100 text-blue-800` |
| Employer/HR | `#7C3AED` (Violet) | `bg-violet-100 text-violet-800` |
| Admin | `#DC2626` (Red) | `bg-red-100 text-red-800` |

### 2.5 Semantik-Buttons: Quasar-`color=` statt Tailwind-`bg-*` (P1-4, 29.09.2026)

> **Regel (verbindlich ab 29.09.2026):** Aktions-/Status-**Buttons** nutzen Quasar-Semantik (`props("color=primary|negative|positive")` + `apply_brand_colors()`-Palette, `webui/theme.py` (Codemarke `def apply_brand_colors`, gemessen 10.10.2026)), **keine** Tailwind-`bg-*`-Klassen. Grund: Tailwind-Klassen werden von Quasars Button-Hintergrund überstimmt → Kontrast unbelegt (Plan-Befund N-S1/M-04-Muster); die Semantik-Palette ist WCAG-geprüft (Primary #1D4ED8 = 6.7:1, Negative #B91C1C = 6.47:1, Positive #15803D = 5.02:1 — alle ≥ 4.5:1). **Nicht Button-Familie** (dürfen Tailwind behalten): Progress-Bars, Info-Karten, Badges/Labels ohne `ui.button`.

| Aktion | Quasar-`color` | Kontrast (weißer Text) |
|---|---|---|
| Einladen / positive Aktion | `positive` | 5.02:1 (✅) |
| Ablehnen / destruktive Aktion | `negative` | 6.47:1 (✅) |
| Neutral/primär (Status weiter, Visum-Bestätigung) | `primary` | 6.7:1 (✅) |
| Abbrechen (sekundär) | `grey-9 flat` oder `primary flat` | je ≥ 4.5:1 |

**Quelle:** WCAG 2.1 SC 1.4.3 (≥ 4.5:1) + Kontrastmessung 28.09.2026 (`apply_brand_colors`, entscheidungen.md M-04/M-12); Umsetzung P1-4 = Nutzer-GO (Plan `ui-mvp-plan-v2.md` §6 P1-4).

---

## 3. Typografie

### 3.1 Font-Stack

```css
font-family: 'Inter', 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

NiceGUI nutzt Quasar → Standard-Font ist bereits Inter-ähnlich.

### 3.2 Hierarchie

| Element | Tailwind-Klasse | Größe |
|---|---|---|
| Page Title | `text-2xl font-bold` | 24px / 700 |
| Section Title | `text-xl font-semibold` | 20px / 600 |
| Card Title | `text-lg font-medium` | 18px / 500 |
| Body | `text-base` | 16px / 400 |
| Small / Label | `text-sm` | 14px / 400 |
| Caption | `text-xs text-muted` | 12px / 400 |
| Stat Number | `text-3xl font-bold` | 30px / 700 |

---

## 4. Abstände & Grid

### 4.1 Spacing Scale

| Token | Tailwind | Pixel |
|---|---|---|
| `xs` | `p-1` / `gap-1` | 4px |
| `sm` | `p-2` / `gap-2` | 8px |
| `md` | `p-4` / `gap-4` | 16px |
| `lg` | `p-6` / `gap-6` | 24px |
| `xl` | `p-8` / `gap-8` | 32px |

### 4.2 Container

```python
# Maximale Breite für Content
"max-w-7xl mx-auto"  # 1280px

# Sidebar-Breite
"left_drawer w-64"   # 256px
```

### 4.3 Responsive Grid

```python
# Stat Cards
ui.grid(columns=4).classes("w-full gap-4")  # Desktop: 4 Spalten
# → md:grid-cols-2 lg:grid-cols-4 (via Tailwind)

# Zwei-Spalten-Layout
ui.grid(columns=2).classes("w-full gap-6")

# Drei-Spalten (Dashboard)
ui.grid(columns=3).classes("w-full gap-4")
```

---

## 5. Schatten & Border

| Element | Tailwind-Klassen |
|---|---|
| Card (ruhig) | `shadow-sm rounded-xl border border-gray-200` |
| Card (hover) | `shadow-md rounded-xl transition-shadow duration-200` |
| Dropdown | `shadow-lg rounded-lg` |
| Badge | `rounded-full px-3 py-1 text-xs font-medium` |
| Button (primary) | `bg-primary text-white rounded-lg px-4 py-2 hover:bg-primary-light` |
| Button (ghost) | `text-primary hover:bg-primary/10 rounded-lg` |

---

## 6. Komponenten

### 6.1 Stat Card

Zeigt eine Kennzahl mit Label und optionalem Trend.

```python
# Nutzung:
stat_card(label="Kandidaten", value=42, icon="people", trend="+12%", color="primary")
```

**Design:** Card → Icon (links) + Value (Mitte, groß) + Label (unten) + Trend (rechts, farbig)

### 6.2 Status Badge

Zeigt einen Status mit Farbe und optionalem Pulse-Animation.

```python
status_badge("eingeladen", status_map={"eingeladen": "green", "abgelehnt": "red"})
```

**Farben:** done=green, pending=amber, failed=red, active=blue (pulsierend)

### 6.3 Score-Balken

Horizontaler Fortschrittsbalken mit Animierung.

```python
score_bar(label="Berufserfahrung", score=25, max_score=30, color="primary")
```

**Animation:** `ui.animate()` von 0% auf den Zielwert bei Page-Load.

### 6.4 Data Table

Sortierbare, filterbare Tabelle mit Pagination.

```python
data_table(columns=[...], rows=[...], pagination=10)
```

**Features:** Sort by column, search filter, row-click action, zebra-striping.

### 6.5 Upload Zone

Drag & Drop Area für Dateien.

```python
upload_zone(label="Lebenslauf hochladen", accepted=".pdf,.txt")
```

**Design:** Gestrichelter Rahmen, Icon in der Mitte, Hover-Effekt.

### 6.6 Timeline

Vertikaler Timeline-Flow für Onboarding/Prozesse.

```python
timeline(items=[
    {"title": "Bewerbung eingegangen", "status": "done", "date": "15.09.2026"},
    {"title": "Pre-Screening", "status": "active", "date": "18.09.2026"},
    {"title": "Onboarding", "status": "pending"},
])
```

### 6.7 Agent Task Badge

Kompakter Badge für Agent-Task-Status mit Farbcodierung.

```python
agent_badge(task_type="match", status="done")  # ✅ Match
agent_badge(task_type="compliance", status="running")  # ⏳ Compliance
agent_badge(task_type="culture_fit", status="failed")  # ❌ Culture-Fit
```

### 6.8 Bewerbungen-Status-Liste

Zeigt alle eigenen Bewerbungen eines Kandidaten mit Status-Tracking.

```python
# Quelle: app.py:3335-3382 (Streamlit), knowledge/system/access-control.md:74
# Features: status_badge, timeline (Status-Historie), ui.timer (Auto-Refresh 15s, candidate.py:605)
# DB: applications + application_status_history
# Aktionen: Bewerbung zurückziehen (nicht-finalen Status)
# Spezial: Bei "eingeladen" → VDO.Ninja-Link + ICS aus Agent-Task (get_invitation_artifacts)
```

### 6.9 Match-Ergebnis (Live-Score)

Berechnet den Match-Score live aus der DB für einen gewählten Kandidaten.

```python
# Quelle: app.py:1837-1906 (Streamlit, „2️⃣ Match-Ergebnis"), logic.py:berechne_match_score (Zeile 338-399)
# DB-Read: applications + jobs + employers + candidates (JOIN)
# Features: berechne_match_score() live, score_bar (7 Kategorien), ui.timer (15s Refresh, employer.py:876)
# Explainability: erklaerung-Dict mit 7 Kategorien (SphinxATS-Pattern)
# Connector: hr-benchmark → get_score_category() für Kategorisierung
# Fallback: Bei leerem Kandidaten → empty_state
```

---

## 7. Liveliness-Features

### 7.1 Live-Updates (ui.timer)

```python
# Quelle: nicegui.io/documentation/timer (offiziell)
# ui.timer(interval, callback, active=True, once=False, immediate=True)
# Properties: active (BindableProperty), interval (BindableProperty)
# Methods: cancel(), activate(), deactivate()

# Employer Dashboard: Agent-Task-Status alle 10s (Code: employer.py:81)
ui.timer(interval=10.0, callback=dashboard_stats.refresh)

# Admin: KEIN Auto-Refresh im Code (eventbasiert, wie Streamlit)

# Candidate Bewerbungen: Status alle 15s (Code: candidate.py:605)
ui.timer(interval=15.0, callback=bewerbungen_list.refresh)

# Match-Ergebnis: Score alle 15s (Code: employer.py:876)
timer = ui.timer(interval=15.0, callback=match_content.refresh)
# Deaktivierbar: timer.active = False / timer.cancel()
```

### 7.2 Animierte Score-Balken (ui.animate)

```python
# Quelle: nicegui.io/documentation/element (ui.animate via CSS Transitions)
# ui.animate(element, property, duration=800, easing='ease-out')
# CSS: @keyframes score-fill (theme.py:120-130)
# Bereits in components.py:score_bar() implementiert

# Score-Balken animiert einblenden
bar = ui.progress(value=0)
ui.animate(bar, 'value', duration=800, easing='ease-out')
bar.value = score / max_score

# Badge-Pulse (CSS-basiert, theme.py:133-139)
# status_badge("eingeladen", pulse=True) → Klasse "badge-pulse"

# Card-Hover (CSS-basiert, theme.py:142-148)
# C.CARD_HOVER → Klasse "card-interactive" mit transition

# Page Fade-In (CSS, design-system §9)
# .page-fade-in { animation: fadeIn 300ms ease-out }
```

### 7.3 Feedback-Notifications (ui.notify)

```python
ui.notify("Profil gespeichert", type="positive")
ui.notify("Fehler beim Upload", type="negative")
ui.notify("Agent-Task gestartet", type="info")
```

### 7.4 Ladezustände (ui.skeleton)

```python
# Platzhalter während Daten geladen werden
with ui.skeleton().classes("w-full h-20"):
    pass
```

### 7.5 Echtzeit-Dashboard (@ui.refreshable)

```python
@ui.refreshable
def dashboard_stats():
    stats = get_live_stats()
    # ... render stats

# Bei Bedarf aufrufen:
dashboard_stats.refresh()
```

### 7.6 Dark Mode Toggle

```python
dark = ui.dark_mode()
ui.switch("Dark Mode", value=dark.value, on_change=lambda e: dark.set_value(e.value))
```

---

## 8. Navigation

> **Phase 2 (20.09.2026):** Alle drei Rollen nutzen die einheitliche `shell()`-Navigation
> aus `components.py` (Header + left_drawer + Notifications + Logout) — die frühere
> Aufteilung „Candidate = Top-Tabs, Employer = Sidebar, Admin = Button-Spalte" ist Geschichte.

### 8.1 Candidate (shell()-Drawer, 7 Tabs – `_TAB_MAP` `webui/pages/candidate.py`, Stand 02.10.2026)

```
📊 Dashboard (NEU 01.10.2026, 1. Tab) · 👤 Mein Profil (inkl. Lebenslauf-Upload + Dokumente, 02.10.2026) · 💼 Stellen · 📨 Bewerbungen · 🗣️ Sprachtest · 📹 Pre-Screen · 📋 Onboarding
```

### 8.2 Employer (shell()-Drawer, 11 Seiten – PAGE_MAP `webui/pages/employer.py` (Codemarke `PAGE_MAP`, gemessen 10.10.2026), Zeilenstand 28.09.2026)

```
📊 Dashboard
🏢 Portal (Firmenprofil + Stellen, P1.2)
💼 Stellenangebote (HR-write: Bewerber + Archiv, 20.09.2026)
🔍 Kandidaten-Suche
📄 Match-Ergebnis
✅ Compliance
🔎 Agent-Details
🗂️ Dokumente
📞 Pre-Screen
📋 Onboarding
💬 Feedback
```

### 8.3 Admin (shell()-Drawer, 12 Seiten – PAGE_MAP `webui/pages/admin.py` (Codemarke `PAGE_MAP`, gemessen 10.10.2026))

```
📊 Dashboard
📤 Upload
1️⃣ Extract Profile
2️⃣ Match-Tool
3️⃣ Compliance-Tool
4️⃣ Contact Candidate
5️⃣ Culture Fit
📞 Pre-Screen
📋 Onboarding
💬 Feedback
💼 Stellenangebote
🏢 Arbeitgeber-Portal
```

---

## 9. Animation & Transitions

| Element | Animation | Dauer |
|---|---|---|
| Score-Balken | width 0→100% | 800ms ease-out |
| Badge Pulse | scale 1→1.05→1 | 2s infinite |
| Card Hover | shadow-sm→shadow-md | 200ms |
| Page Transition | fade-in | 300ms |
| Notification | slide-in from top | 300ms |
| Skeleton | shimmer gradient | 1.5s infinite |

---

## 10. Icons

NiceGUI nutzt Material Icons (via Quasar). Bevorzugte Icons:

| Aktion | Icon |
|---|---|
| Dashboard | `dashboard` |
| Kandidaten | `people` |
| Stellen | `work` |
| Upload | `cloud_upload` |
| Download | `cloud_download` |
| Suche | `search` |
| Filter | `filter_list` |
| Sortieren | `sort` |
| Status: Done | `check_circle` |
| Status: Pending | `schedule` |
| Status: Failed | `error` |
| Editieren | `edit` |
| Löschen | `delete` |
| Hinzufügen | `add` |
| Zurück | `arrow_back` |
| Schließen | `close` |
| Refresh | `refresh` |
| Settings | `settings` |
| Logout | `logout` |
| Info | `info` |
| Warnung | `warning` |
| Erfolg | `task_alt` |

---

## 11. Dropdown-/Filter-Optionen (Regel)

> **Stand:** 01.10.2026 (N-K1 — Befund `ergebnisse/ui-analyse-2026-09-29.md`
> „Kandidaten-Filter zeigt DB-Slug `lebenslauf_hochgeladen`“).

| Regel | Umsetzung | Beispiel |
|---|---|---|
| **Klartext statt DB-Slug** | Beschriftung immer über `status_label()` (`components.STATUS_LABELS`) — der rohe Slug wird nie gerendert | `lebenslauf_hochgeladen` → „Lebenslauf hochgeladen“ |
| **Keine toten Optionen** | Filterwerte = nur Werte, die in der DB **real vorkommen** (Pool ∩ `COUNT > 0`) | `webui/pages/employer.py` (Codemarke `def _cand_status_options`, gemessen 10.10.2026) |
| **Ein Sammelwert** | Erste Option = Sammelwert mit Wert `"alle"` | „Alle mit Lebenslauf“ |

**Umsetzung N-K1 (`webui/pages/employer.py`):** `_cand_status_options(conn)` liefert
`{value: status_label(value)}` für die real vorkommenden Status des CV-Pools
(`CAND_CV_STATUS`, Pool-Definition: `knowledge/portal/applicants-first.md`); die frühere
zweite Label-Kopie `CAND_STATUS_LABELS` ist entfernt — Klartext-Quelle ist ausschließlich
`components.STATUS_LABELS` (Konsistenz-/Lab-Regel).

**Design-Entscheidungen (keine externe Quelle):** (a) „nur real vorkommende Werte“,
(b) Sammelwert „Alle mit Lebenslauf“, (c) Reihenfolge = Pool-Definition.
**Quelle des Verhaltens:** Nutzer-Befund N-K1 (01.10.2026) + Punktion „Klartext statt Slugs“.

**Tests:** `tests/test_kandidaten_filter.py` (Werte/Labels gegen die DB) ·
`tests/e2e_kandidaten_filter.py` (echtes Dropdown + Screenshot
`ergebnisse/screenshots/n-k1-kandidaten-filter.png`).

### 11.1 Klickziel je Tabellenzeile (Regel, M-07)

> **Stand:** 01.10.2026 (M-07 — Befund `ergebnisse/ui-analyse-2026-09-29.md`
> „Zeilen ohne Klickziel“).

| Regel | Umsetzung |
|---|---|
| **Keine tote Zeile** | Jede Datenzeile einer Tabelle hat ein Klickziel — entweder Navigation oder Detail-Dialog; nie ein `cursor: auto`-Zeile ohne Reaktion |
| **`on_row_click` braucht `selection`** | `components.data_table()` setzt `on_select=on_row_click` **nur** wirksam, wenn zugleich `selection` gesetzt ist. NiceGUI setzt sonst den Prop auf `'none'` (Upstream-Code NiceGUI, nicegui/elements/table.py — `selection or 'none'`, gemessen 10.10.2026), das Quasar-`selection`-Event feuert nie. Daher: `selection="single" if on_row_click else None` |
| **Auflösbar → Sprung mit Fokus** | Ist das Zeilen-Ziel ein DB-Objekt, führt der Klick auf die Detailseite **mit Fokus-Parameter** (z. B. `/employer/match?kandidat=<id>`) |
| **Nicht auflösbar → Dialog** | Ist kein Objekt zuordenbar (Altbestand/Datenrest), zeigt der Klick einen **Detail-Dialog** mit dem gespeicherten Datensatz, statt auf eine falsche Seite zu springen |

**Umsetzung M-07:** `webui/components.py` (Codemarke `def data_table`, gemessen 10.10.2026) (Auswahl aktivieren) +
`webui/pages/employer.py` (`_page_kandidaten` `on_select` mit `?kandidat=<id>`;
`_page_feedback` `_zeile_geklickt` mit `_feedback_row_cid()` = 3-stufiger Resolver:
Vorgangs-Nr. `…-cand-<id>` → exakter Klarname → Namens-Token-Menge, nur bei eindeutigem
Treffer).

**Design-Entscheidungen (keine externe Quelle):** (a) Reihenfolge der 3 Resolver-Stufen,
(b) Namens-Token-Menge als Reihenfolge-toleranter Fallback („Abdelkader Batnini“ ==
„batnini abdelkader“), (c) nicht auflösbar ⇒ Dialog statt Fehl-Navigation.
**Quelle des Verhaltens:** Nutzer-GO „umsetzen für alle“ (01.10.2026).

**Tests:** `tests/test_feedback_row_click.py` · `tests/e2e_m07_row_click.py`.

### 11.2 Listen-Kürzung (Regel, M-18)

> **Stand:** 01.10.2026 (M-18 — Befund `ergebnisse/ui-analyse-2026-09-29.md`
> „Skill-Darstellung hart auf 4 gekürzt → Skills unvollständig“).

| Regel | Umsetzung |
|---|---|
| **Keine stille Kürzung** | Eine Liste, die aus Platzgründen nicht vollständig gerendert wird, MUSS die Kürzung sichtbar machen |
| **Marke „+N weitere“** | Erste N Elemente + ein Marker `+{Rest} weitere`; der Marker trägt die übrigen Werte als **Tooltip** (nichts bleibt verborgen) |
| **Leere Werte raus** | Beim Splitten kommaseparierter Felder leere Einträge verwerfen (`if s.strip()`) |

**Umsetzung M-18:** `webui/pages/employer.py` (Codemarke `def _page_match`, gemessen 10.10.2026) (Kandidatenkarte) —
`_skills = [s.strip() for s in str(h_skills).split(",") if s.strip()]`; erste 4 als
`skill_chip`, bei mehr `ui.chip(f"+{n} weitere", color="grey").props("dense").tooltip(...)`.
Datenprobe (read-only): bis zu **21** Skills/Kandidat → „alle zeigen“ würde die Karte
sprengen, deshalb Kürzung **markiert** statt still.

**Design-Entscheidungen (keine externe Quelle):** N = 4 (bestehender Wert beibehalten),
Marke als Chip mit Tooltip statt Aufklapp-Liste.
**Quelle des Verhaltens:** Nutzer-Auftrag M-18 (01.10.2026), AK „Skills vollständig
oder Kürzung markiert“.

**Tests:** `tests/test_match_actions.py` (Quelltext) · `tests/e2e_m18_skills_marker.py`.

### 11.3 Button-Farben (Regel, N-M1)

> **Stand:** 01.10.2026 (N-M1 — Befund `ergebnisse/ui-analyse-2026-09-29.md`).

| Regel | Umsetzung |
|---|---|
| **Quasar-Semantik statt Tailwind-bg** | Buttons färben über `.props("color=primary\|negative\|positive\|warning")`; **kein** `bg-*-… text-white` (Farbwirkung/Kontrast war unbelegt) |
| **Neutraler Abbrechen-Knopf** | `.props("flat")` |
| **Beleg** | `grep -n 'bg-' employer.py` darf **keinen** `ui.button`-Treffer zeigen; Kontrastlauf `tests/ui_measure.py` |

**Umsetzung N-M1 (`webui/pages/employer.py`):** Match-Dialoge ( Einladen=`primary`,
 Ablehnen=`negative` Einstellen=`positive`), Visum/ICS ,
Onboarding . **Beweis:** `tests/test_nm1_nm2.py` (kein Button
mit `bg-`). **Design-Entscheidung:** Farbzuordnung (primary/negative/positive/warning/flat).

---

## 12. Glassmorphism Design System

> **Stand:** 20.09.2026 · **Stil:** Glassmorphism (frosted glass effect)
> **Referenzen:** Apple iOS, Linear, Arc Browser, Vercel

### 12.1 Kern-Prinzipien

| Prinzip | Umsetzung |
|---|---|
| **Transparenz** | Semi-transparente Hintergründe (`rgba(255,255,255,0.7)`) |
| **Blur** | `backdrop-filter: blur(16px)` für Frosted-Glass-Effekt |
| **Gradient-Hintergründe** | Lebendige Farbverläufe hinter den Glass-Karten |
| **Sanfte Ränder** | `border: 1px solid rgba(255,255,255,0.3)` für Glass-Kante |
| **Layering** | Schichten mit verschiedenen Transparenzstufen |

### 12.2 Glass-Varianten

| Klasse | Transparenz | Blur | Verwendung |
|---|---|---|---|
| `.glass` | 70% | 16px | Standard-Karten |
| `.glass-strong` | 85% | 24px | Header, Login-Karten |
| `.glass-subtle` | 50% | 8px | Dekorative Elemente |

### 12.3 Gradient-Hintergründe

```css
/* Hero-Gradient (Login-Seite) — Warm Gold */
background: linear-gradient(135deg, #92400E 0%, #B45309 50%, #D97706 100%);

/* Primary Gradient */
background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 50%, #06B6D4 100%);

/* Mesh Gradient (decorative) */
background:
    radial-gradient(at 40% 20%, hsla(228, 67%, 65%, 0.4) 0px, transparent 50%),
    radial-gradient(at 80% 0%, hsla(189, 64%, 50%, 0.3) 0px, transparent 50%),
    radial-gradient(at 0% 50%, hsla(355, 85%, 63%, 0.2) 0px, transparent 50%);
```

### 12.4 Glow-Effekte

| Klasse | Farbe | Verwendung |
|---|---|---|
| `.glow-blue` | Blau | Aktive Elemente, Links |
| `.glow-green` | Grün | Erfolg, Positive Aktionen |
| `.glow-purple` | Lila | Employer-Portal |
| `.glow-amber` | Bernstein | Warnungen, Pending |
| `.glow-red` | Rot | Fehler, Ablehnung |

### 12.5 Glass-Buttons

```python
# Primär (Blau)
ui.button("Speichern").classes("btn-glass")

# Erfolg (Grün)
ui.button("Bestätigen").classes("btn-glass btn-glass-green")

# Gefahr (Rot)
ui.button("Löschen").classes("btn-glass btn-glass-red")

# Ghost (Transparent)
ui.button("Abbrechen").classes("btn-glass btn-glass-ghost")
```

### 12.6 Translucent Badges

```python
# Standard (Blau)
ui.badge("Status").classes("badge-glass")

# Erfolg (Grün)
ui.badge("Fertig").classes("badge-glass badge-glass-green")

# Warnung (Bernstein)
ui.badge("Pending").classes("badge-glass badge-glass-amber")

# Fehler (Rot)
ui.badge("Fehlgeschlagen").classes("badge-glass badge-glass-red")
```

### 12.7 Glass-Header & Sidebar

```python
# Header
with ui.header().classes("header-glass px-6 items-center"):
    pass

# Sidebar
with ui.left_drawer().classes("sidebar-glass w-64 p-4"):
    pass
```

### 12.8 Floating Orbs (Dekorativ)

```html
<!-- Login-Seite Hintergrund -->
<div class="login-orb orb-1"></div>  <!-- Blau, 400px -->
<div class="login-orb orb-2"></div>  <!-- Lila, 300px -->
<div class="login-orb orb-3"></div>  <!-- Rosa, 200px -->
```

### 12.9 Animationen

| Animation | Dauer | Verwendung |
|---|---|---|
| `float` | 6-8s | Floating Orbs |
| `glow-pulse` | 3s | Glow-Effekte |
| `gradient-shift` | 8s | Animierte Hintergründe |
| `score-fill` | 800ms | Score-Balken |
| `badge-pulse` | 2s | Aktive Badges |

### 12.10 Dark Mode Glass

```css
.dark .glass {
    background: rgba(30, 41, 59, 0.7);
    border-color: rgba(255, 255, 255, 0.1);
}
.dark .glass-strong {
    background: rgba(30, 41, 59, 0.9);
}
```

---

## 13. Dateistruktur (Implementierung)

```
webui/
├── __init__.py
├── main.py              # Routing + Dark Mode (shell()-Layout liegt in components.py)
├── theme.py             # Design Tokens + Glassmorphism CSS
├── components.py        # Wiederverwendbare UI-Komponenten (glass_card, glow_stat_card etc.)
├── db.py                # DB-Layer (Phase 1: +6 Portal-Helfer, insert_language_test etc.)
├── logic.py             # Business-Logik (berechne_match_score Z.338, cefr_from_avg Z.618)
├── pages/
│   ├── __init__.py
│   ├── login.py         # Login/Registrierung (Glassmorphism Design)
│   ├── candidate.py     # 7 Candidate-Tabs (_TAB_MAP, Stand 02.10.2026; Upload/Dokumente in 👤 Mein Profil)
│   ├── employer.py      # 11 Employer-Seiten (PAGE_MAP Z.1649-1660, Zeilenstand 28.09.2026, inkl. HR-write-Stellen-View)
│   └── admin.py         # 12 Admin-Seiten (PAGE_MAP Z.753-766)
```

---

## 14. NiceGUI-Dokumentation (Quellen)

> **Stand:** 20.09.2026 · **NiceGUI:** 3.17.1

### 14.1 CSS-Injection

| Feature | NiceGUI-Doku | Verwendung |
|---|---|---|
| `ui.add_head_html()` | [section_pages_routing#add_html_to_the_page](https://nicegui.io/documentation/section_pages_routing#add_html_to_the_page) | Globale CSS-/JS-Injektion in `@ui.page` |
| `ui.add_body_html()` | (siehe oben) | Body-Inhalte (selten genutzt) |
| `ui.add_css()` | [add_style](https://nicegui.io/documentation/add_style#add_css_style_definitions_to_the_page) | Direkte CSS-Definitionen |

**Regel:** In `@ui.page`-Modus (modularized mode) muss `ui.add_head_html()` in jeder Page-Builder-Funktion aufgerufen werden – nicht auf Modul-Level.

### 14.2 Tailwind CSS

| Feature | Quelle | Verwendung |
|---|---|---|
| `.classes()` | [element#default_classes](https://nicegui.io/documentation/element#default_classes) | Tailwind-Klassen an Elementen |
| `.style()` | [element#default_style](https://nicegui.io/documentation/element#default_style) | Inline-CSS |
| `.props()` | [element#default_props](https://nicegui.io/documentation/element#default_props) | Quasar-Properties |

### 14.3 Layout

| Element | Doku | Verwendung in Projekt |
|---|---|---|
| `ui.tabs` / `ui.tab_panels` | [tabs](https://nicegui.io/documentation/tabs) | Login (5 Tabs); Candidate nutzt seit Phase 2 shell()-Drawer statt Tabs |
| `ui.card` | [card](https://nicegui.io/documentation/card) | Karten-Layout |
| `ui.column` / `ui.row` | [column](https://nicegui.io/documentation/column), [row](https://nicegui.io/documentation/row) | Flexbox-Layout |
| `ui.grid` | [grid](https://nicegui.io/documentation/grid) | Raster-Layout |
| `ui.header` / `ui.footer` | [page_layout](https://nicegui.io/documentation/page_layout) | Seitenstruktur |
| `ui.left_drawer` | [page_layout](https://nicegui.io/documentation/page_layout) | Alle 3 Rollen via shell() (Phase 2) |

### 14.4 Navigation

| Feature | Doku | Verwendung |
|---|---|---|
| `@ui.page` | [page](https://nicegui.io/documentation/page) | Seitendefinition |
| `ui.navigate.to()` | [navigate](https://nicegui.io/documentation/navigate) | Weiterleitung |
| `ui.link()` | [link](https://nicegui.io/documentation/link) | Verknüpfungen |

**SPA-Navigations-Regel (P2, 22.09.2026):**

> Jeder Aufruf von `history.pushState` / `run_javascript` in Navigationspfaden MUSS in `try/except` stehen.
> **Warum:** NiceGUI-Slot-Stack hat keinen aktiven Client im Test-/Headless-Kontext → uncaught Exception killt den Content-Render (Bug-Muster Sidebar `webui/components.py` (Codemarke `def navigate_to`, gemessen 10.10.2026), übernommen für `navigate_to` `webui/components.py` (Codemarke `def navigate_to`, gemessen 10.10.2026)).
> **Umsetzung:** Sidebar-Click nutzt Content-Render zuerst, dann pushState in try/except → Content bleibt sichtbar, URL-Update ist Best-Effort.
> **Quelle (Code):** `webui/components.py` `_make_click()`.

**M-17-Korrektur (01.10.2026, gemessen):** `navigate_to()` nutzt **nicht mehr** `run_javascript(pushState)` — der Best-Effort-Sprung griff aus Klick-Handlern nicht (E2E: Inhalt wechselte auf den Sprachtest-Tab, **URL blieb** `/candidate/prescreen`, Back → `/candidate`; Protokoll `ergebnisse/pushstate-protokoll-2026-10-01.md`). Jetzt: `ui.navigate.to(f"/{role}/{page_key}")` in `try/except` → **URL und Inhalt konsistent** (dasselbe Muster wie Employer-Kandidaten-Tabelle/Dashboard-Kacheln).
> **Regel:** Für Seitensprünge `ui.navigate.to()` verwenden, nicht `history.pushState` per `run_javascript`.

**Toast-vor-Navigation-Regel (06.10.2026, E2E-belegt):**

> Ein Bestätigungs-`ui.notify` darf NICHT zusammen mit `navigate_to()` im selben Event-Zyklus ausgelöst werden — sonst sieht der Nutzer die Bestätigung nie.
> **Mechanismus (Quelle: NiceGUI-Paketquelltext, gemessen 06.10.2026):** `navigate_to()` → `ui.navigate.to()` → `Client.open()` (`.venv-streamlit/…/nicegui/functions/navigate.py`) → Outbox-Message `open` → clientseitig `window.open(url, "_self")` (`.venv-streamlit/…/nicegui/static/nicegui.js`, Handler `open:`) = vollständiger Seitenwechsel; parallel läuft `notify` als `Quasar.Notify.create(msg)` (derselbe JS-Handlerblock) → der Toast wird durch den Seitenwechsel zerstört, bevor er sichtbar wird.
> **Beweis (Messung 06.10.2026):** Isolierter E2E-Lauf `e2e-iso-20261006-211219` — `e2e_apply_dialog_multi` (`get_by_text("Bewerbung gesendet!")`, Timeout 8000 ms) und `e2e_notifications_flow` (Timeout 15000 ms) **rot**; beide noch am 30.09.2026 grün, rot seit der M-17-Korrektur vom 01.10.2026.
> **Umsetzung (Code):** Handler-Reihenfolge `ui.notify(...)` → [`dialog.close()`, nur falls ein Dialog offen ist] → `await asyncio.sleep(1.5)` → `navigate_to(...)`. Danach greift die M-17-Regel unverändert (echter Route-Wechsel, URL + Inhalt konsistent).
> **Design-Entscheidung (kein externer Standard):** Verzögerung **1,5 s** — NiceGUI-Default-Toast-Laufzeit ist 5 s; die Bestätigung soll sichtbar sein, der Sprung danach aber zügig erfolgen.
> **Betroffen (E2E-belegt):** `webui/pages/candidate.py` Bewerbungs-Submit `_submit` (in `_open_apply_dialog`), **`save_profile` („Profil gespeichert!") und CV-Upload `on_upload` („Lebenslauf hochgeladen …") — beide nachgezogen 06.10.2026** (`async def save_profile` + je `await asyncio.sleep(1.5)` vor `navigate_to`); Isolierter E2E-Lauf 06.10.2026 `e2e_profile_save` rc=0, `e2e_cv_upload` rc=0, `e2e_notifications_flow` rc=0 (Port 8090).

### 14.5 Session & Storage

| Feature | Doku | Verwendung |
|---|---|---|
| `app.storage.user` | [storage](https://nicegui.io/documentation/storage) | Login-Session (ersetzt `st.session_state`) |
| `storage_secret` | [run](https://nicegui.io/documentation/run) | Verschlüsselung des Session-Speichers |
