# Matching-Kriterien – Gewichtung und Scoring (Phase 4: geschlossener Loop, Baseline-Modell + Normalisierung)

> **Stand:** 11.09.2026 (Phase 4)  
> **Voraussetzung:** Login + Lebenslauf-Upload (Jobportal-Prinzip)  
> **Implementierung:** ✅ Phase 2 (Scoring-Funktionen) + Phase 4 (Feedback-Loop: `get_current_weights()`, `adjust_weights_from_feedback()`)  
> **Externe Validierung:** SphinxATS Paper (ICSSAS 2026, DOI: 10.1109/ICSSAS68835.2026.11559449) bestätigt Multi-Attribute-Ansatz → `knowledge/lifecycle/referenz-sphinxats.md`

---

## Score-Verteilung (Baseline-Modell, Rohgewichte)

| Kategorie | Baseline (Roh) | Min | Max (Cap) | Beschreibung |
|---|---|---|---|---|
| Kernkompetenzen | 30 | 15 | 45 | Übereinstimmung der Hard Skills mit Stellenanforderungen |
| Berufserfahrung | 25 | 10 | 40 | Relevanz und Dauer der Berufserfahrung |
| Bildung | 15 | 0 | 30 | Abschluss-Level und fachliche Relevanz |
| Standort | 10 | 0 | 25 | Physische Nähe oder Remote-Möglichkeit |
| Branchenkenntnis | 10 | 0 | 25 | Erfahrung in gleicher oder ähnlicher Branche |
| Soft Skills | 10 | 0 | 25 | Übereinstimmung der weichen Anforderungen |
| Sprache | 0 | 0 | 15 | Deutsch-/Englisch-Level (aktiviert sich nur via Feedback-Loop) |
| **Summe** | **100** | | | **Wird nach Loop-Anpassungen immer wieder auf 100 normalisiert** |

**Baseline = 30/25/15/10/10/10/0 (Summe 100).**

> 📌 **Min-Spalte an den Ist-Code angeglichen (ⓘ09.10.2026):** Die Untergrenze ist im Code **nicht** ein fixes Minimum je Kategorie, sondern `max(0, base − GEWICHT_CAP_ABWEICHUNG)` — Codemarken `webui/logic.py` `GEWICHT_CAP_ABWEICHUNG = 15` (gemessen :658) und Klemm-Zeile `roh[key] = max(max(0, base - GEWICHT_CAP_ABWEICHUNG), min(roh[key], base + GEWICHT_CAP_ABWEICHUNG))` (gemessen :860). Für Bildung (15), Standort (10), Branche (10) und Soft (10) ergibt `base − 15` einen **negativen** Wert → geklemmt auf **0** (vorher fälschlich 5 dokumentiert). Nur Kern (30→15) und Erfahrung (25→10) liegen bei base−15 > 0; Sprache wird separat via `GEWICHT_CAP_SPRACHE_MAX = 15` (Obergrenze) und `max(0, …)` (Untergrenze 0) behandelt.

> ⚠️ **Design-Entscheidung (15.09.2026):** Diese Gewichte wurden beim Projektstart festgelegt und haben **keine externe Quelle** (keine HR-Studie, kein Gesetz, kein Bipperz-Dokument). Sie dienen als Startpunkt für den Feedback-Loop, der sie an echte Einstellungsentscheidungen anpasst. **Alternative:** Gewichte aus SHRM/LinkedIn-Studien oder eigener empirischer Validierung. **Validierung:** Feedback-Loop passt Werte nach 20+ Einstellungsentscheidungen an.

> 📌 **Live-Quelle (Phase-E Runde 2, 24.09.2026):** Der `match_candidate`-LLM-Prompt zieht die Gewichte **nicht mehr als Kopie**, sondern live aus `gewichtung_historie` über `webui.logic.get_current_weights()` (`webui/logic.py:338`) — Aufruf in `scripts/agent-runner.py:754` (`_gewichts_prompt_zeile()`, genutzt `:851`). Damit gilt: **DB-Historie = Quelle der Wahrheit**, die Baseline oben ist nur noch Startwert. Live-Stand 24.09.2026: kern 25.0 / erfahrung 29.2 / bildung 12.5 / standort 8.3 / branche 8.3 / soft 8.3 / sprache 8.3 (Summe 100). **Design-Entscheidungen:** Rundung auf 1 Nachkommastelle, Fallback = Baseline bei leerer Historie/DB-Fehler.

## Normalisierung (4.4 – korrigierte Mathematik)

Die historische Tabelle summierte 115 (30/30/15/10/10/10/10) – ein Rechenfehler, denn „Gesamt: 100 Punkte" wurde mit der zusätzlichen Sprache-Kategorie überzeichnet. **Verbindliche Regel:** Nach jeder Gewichtungsänderung werden die Rohgewichte **proportional auf Summe 100 skaliert**: `anteil_i = roh_i / sum(roh) × 100`. Die Kategorie-Punkte im Scoring werden mit dem **skalierten** Anteil multipliziert: `punkte_i = (kategorie_score / kategorie_max) × anteil_i`. Die Gesamtsumme liegt dadurch konstruktionsbedingt immer bei ≤ 100.

---

## Der geschlossene Feedback-Loop (Phase 4)

### Loop-Regeln

| Regel | Beschreibung |
|---|---|
| **Auslöser** | Jedes **neue** Feedback (INSERT, nicht same-day-UPDATE) – aus Tab 4 (Arbeitgeber-Portal) **und** Skill 8 (HR-Tool); beide rufen dieselbe Funktion `adjust_weights_from_feedback()` auf |
| **Erfolg** | `eingeladen = 'Ja'` UND `score >=` Erfolgsschwelle → **Berufserfahrung +5** (Rohgewicht) — Schwelle **80** (Fallback/„Strong"/„Weak") bzw. **60** bei Kategorie „Consider" (Messung `adjust_weights_from_feedback()` ⓘ08.10.2026) |
| **Misserfolg** | `eingeladen = 'Nein'` UND `score <` Misserfolgsschwelle → **Sprache +10** (Rohgewicht) — Schwelle **70** (Fallback) bzw. **60** bei Kategorie „Consider" (Messung `adjust_weights_from_feedback()` ⓘ08.10.2026) |

> ⚠️ **Design-Entscheidung (15.09.2026):** Die Schwellen 80 (Erfolg) und 70 (Misserfolg) haben **keine externe Quelle**. Sie wurden willkürlich gewählt, um den Feedback-Loop zu initialisieren. **Alternative:** Schwellen aus eigener Datenanalyse ableiten (z.B. Median-Score aller Eingeladenen). **Validierung:** Nach 20+ Feedback-Einträgen prüfen ob die Schwellen sinnvoll trennen. **Nachtrag 08.10.2026 (VERIFY):** Der Code weicht für Kategorie „Consider" (hr-benchmark `get_score_category`) auf **60/60** ab — ebenfalls ohne externe Quelle (Design-Entscheidung, Messung ⓘ08.10.2026).
| **Caps** | Max. Abweichung vom Baseline-Wert: **+15 Punkte** (nie über Baseline+15, nie unter 0); Sprache: Baseline 0 → Max 15. Cap erreicht → keine weitere Anpassung (Meldung „Cap erreicht") |
| **Lesen** | `get_current_weights()` leitet Rohgewichte aus `gewichtung_historie` ab (letzte Zeile je Kategorie) und skaliert auf Summe 100; `berechne_match_score()` nutzt ausschließlich diese Funktion |
| **DB-first** | `gewichtung_historie` ist die Quelle der Wahrheit. Leere Historie → Baseline |
| **Idempotenz** | Same-day-UPDATE erzeugt **keine** neue Historien-Zeile (Korrektur, kein neues Signal) |

### Beispiel

Baseline 30/25/15/10/10/10/0 → 1 Erfolg → Erf 30 → 2. Erfolg → Erf 35 → … → Erf 40 (Cap = 25+15). Sprache: 1 Misserfolg → 10 → 2. Misserfolg → 15 (Cap). Nach jeder Änderung: Skalierung auf Summe 100.

---

## Kernkompetenzen (Kategorie-Score 0–30, skaliert mit anteil_kern)

### Bewertungsschema
- **30 Pkt:** Alle Must-Have-Skills vorhanden + Nice-to-Haves erfüllt
- **25–29 Pkt:** Alle Must-Have-Skills vorhanden, einige Nice-to-Haves
- **20–24 Pkt:** Die meisten Must-Have-Skills vorhanden
- **10–19 Pkt:** Einige Must-Have-Skills fehlen
- **0–9 Pkt:** Die meisten Must-Have-Skills fehlen

## Berufserfahrung (Kategorie-Score 0–30, skaliert mit anteil_erf)

- **30 Pkt:** (Baseline+2) Jahre+ direkt relevante Erfahrung + Bonus
- **25–29 Pkt:** (Baseline+2) Jahre+ direkt relevante Erfahrung
- **20–24 Pkt:** 3–5 Jahre relevante Erfahrung
- **10–19 Pkt:** 1–3 Jahre relevante Erfahrung
- **0–9 Pkt:** Keine oder nicht-relevante Erfahrung

### Bonuspunkte
- +3 Pkt: Teamführung/Mentoring
- +2 Pkt: Erfahrung mit agilen Methoden

## Bildung (Kategorie-Score 0–15, skaliert mit anteil_bild)

- **15 Pkt:** Master/PhD/Diplom in passendem Fach
- **12–14 Pkt:** Bachelor in passendem Fach
- **8–11 Pkt:** Anderer/verwandter Abschluss
- **0 Pkt:** Kein Abschluss angegeben (kein Schein-Score, gefixt 15.09.2026)

## Standort (Kategorie-Score 0–10, skaliert mit anteil_stand)

- **10 Pkt:** Remote möglich
- **8 Pkt:** Gleicher Standort
- **6 Pkt:** Region passend (Kürzel-Überlappung)
- **2 Pkt:** Anderer Standort

## Branchenkenntnis (Kategorie-Score 0–10, skaliert mit anteil_branch)

**Seit Phase 4.6 (11.09.2026):** Der Score vergleicht die **Branche des Arbeitgebers** (`employers.branche`, Auswahl beim Firmenprofil) mit der Branchenerfahrung des Kandidaten. Die Branche wird als `branche`-Feld im Job-Kontext an `berechne_match_score()` übergeben; ohne Angabe greift der neutrale Fallback.

| Branche (Arbeitgeber) | Kandidaten-CV passt (IT-Keywords wie DevOps/Cloud/Software/Netzwerk/Infrastruktur/IT-Projekt) | CV ohne passende Keywords | Kein/leerer CV-Text |
|---|---|---|---|
| **IT** | **10** | 4 | 0 (kein CV-Text) |
| **IT-nah** (Telekommunikation, ENGINEERING etc.) | 10 | 5 | 0 (kein CV-Text) |
| **Fremde Branche** (Handel, Gesundheit, Finanzen, Industrie, Consulting, Sonstiges) | 6 (Quereinstieg-Potenzial) | 2 | 0 (kein CV-Text) |
| **Keine Angabe** (NULL/leer) | 10 | 6 | 0 (Fallback, gefixt 15.09.2026) |

## Soft Skills (Kategorie-Score 0–10, skaliert mit anteil_soft)

- **10 Pkt:** Alle geforderten Soft Skills vorhanden
- **0 Pkt:** Keine Soft-Skill-Anforderung (kein Schein-Score, gefixt 15.09.2026)
- **0–9 Pkt:** Anteil der erfüllten Anforderungen

## Sprache (Kategorie-Score 0–10, skaliert mit anteil_spr)

- **Deutsch 6 Pkt:** erfüllt = 6, B1 knapp drunter = 4, sonst 0
- **Englisch 4 Pkt:** gefordert erfüllt = 4, B1+ ohne Anforderung = 3, sonst 0

---

## Kategorisierung

| Score | Kategorie | Aktion |
|---|---|---|
| 90–100 | Hervorragend | Sofort einladen |
| 75–89 | Gut | Einladen |
| 60–74 | Bedingt | Prüfung empfohlen |
| 40–59 | Schwach | Bedenken |
| 0–39 | Nicht passend | Ablehnen |

> ⚠️ **Design-Entscheidung (15.09.2026):** Die Score-Bands 90/75/60/40 haben **keine externe Quelle** (kein Industriestandard). **Alternative:** Branchenübliche Schwellen (z.B. 85/70/55/40 oder 80/65/50/35). **Validierung:** Korrelation zwischen Score und tatsächlicher Einstellungsentscheidung prüfen.

---

## Explainability Layer (nach SphinxATS-Pattern, 16.09.2026)

> **Quelle:** SphinxATS Paper (ICSSAS 2026): "fully transparent, attribute-level justifications"
> → `knowledge/lifecycle/referenz-sphinxats.md`

Für jeden Kandidaten mit Score ≥ 60 wird pro Kategorie eine Begründung generiert:

> ⚠️ **Design-Entscheidung (16.09.2026):** Die Schwelle ≥ 60 für die Erklärungsanzeige hat **keine externe Quelle**. Sie wurde gewählt, weil Scores unter 60 ohnehin als "Nicht passend" gelten und HR dort keine Begründung braucht. Alternativen: Schwelle auf 40 senken (mehr Transparenz) oder auf 80 erhöhen (nur Top-Kandidaten).

| Kategorie | Format | Beispiel |
|---|---|---|
| Kernkompetenzen | Matched Skills / Required Skills | "Python ✅, Docker ✅, AWS ❌ → 2/3" |
| Berufserfahrung | Jahre vs. Anforderung | "5J Erfahrung, Stelle: 3J → 167%" |
| Bildung | Abschluss-Level | "Bachelor Informatik → 12/15" |
| Standort | Match-Typ | "Remote möglich → 10/10" |
| Branchenkenntnis | Branche vs. CV | "IT-Branche, CV hat DevOps → 10/10" |
| Soft Skills | Erfüllte / Geforderte | "Teamarbeit ✅, Feedback ✅ → 2/3" |
| Sprache | Level vs. Anforderung | "Deutsch B2, gefordert B1 → ✅" |

**Zweck:** HR kann nachvollziehen, WARUM ein Score zustande kam (EU AI Act Art. 50 Transparenz).

---

*Erstellt am 09.09.2026 für den KM-HR-Agenten. Aktualisiert: Phase 2 (11.09.2026) + Phase 4 (11.09.2026, geschlossener Loop, Baseline-Modell + Normalisierung).*

---

## Spec: „Das passt zu dir: 82 %" – Match-Score im Candidate-Stellen-Tab (Phase-d pG, 24.09.2026)

> **Status: UMGESETZT 24.09.2026 (User-Go erteilt, Option (ii); davor MD-only nach Feature-Freeze).** Code: `webui/pages/candidate.py` `_tab_stellen` — **kein DB-Write, keine Schema-Änderung**. E2E-Beweis: `tests/e2e_candidate_score.py`.
> **Paritätsurteil (Schritt 0): NEIN → Neues Feature, braucht explizites Go.** app.py hatte im candidate-seitigen Stellen-/Jobs-Tab **keinen** Score; alle 5 `berechne_match_score`-Aufrufe in app.py sind employer-seitig (Belege: unten §1).
> **Beweis-Fundstellen:** Schritt-0-Report `ergebnisse/phase-d-pG-candidate-match-score.md` (24.09.2026).
> **Wahl (a):** Diese Datei statt neuer Datei — sie definiert bereits Score-Semantik, Kategorisierung und Explainability; die Anzeige-Spec gehört neben die Score-Definition, sonst droht Lab-Prinzip-3-Inkonsistenz (MD↔MD-Split). Sie ist scoring-lastig, aber **nicht** employer-lastig (Feedback-Loop + Explainability gelten beide Seiten).

### 1. Ausgangslage (Schritt 0, verifiziert 24.09.2026)

**Paritätsprüfung app.py — Klassifizierung aller 5 Call-Sites (±30 Zeilen Kontext gelesen):**

| Call-Site | umgebender Kontext (Zeilenbeleg) | Klassifikation |
|---|---|---|
| `app.py:1900` | `elif skill == "2️⃣ Match-Ergebnis" and current_role() == "employer":` (`app.py:1860`), Block „Live-Score für gewählten Kandidaten" (`:1869-1903`) | **employer-seitig** |
| `app.py:1925` | gleicher Block — Drift-Check Agent-Bericht vs. Live-Score (`:1914-1927`) | **employer-seitig** |
| `app.py:3649` | Arbeitgeber-Stellen-Tab, „Abschnitt 1: 📥 Bewerber" (`:3635-3661`); Job-Pool `WHERE j.employer_id = ?` (`:3613`) | **employer-seitig** |
| `app.py:3834` | gleicher Tab, „Abschnitt 2: 👥 Passive Matches" Ranking (`:3821-3852`) | **employer-seitig** |
| `app.py:3905` | `with tab4:` = Feedback-Tab, Kandidaten-Picker (`:3872-3916`) | **employer-seitig** |

**Candidate-seitiger Tab in app.py (Paritäts-Referenz):** `elif skill == "💼 Stellenangebote":` (`app.py:3106`) → Candidate-Branch (`:3244-3374`), Tabs `["🔎 Stellenangebote", "📨 Meine Bewerbungen"]` (`:3284`), Job-Query `WHERE j.status = 'aktiv' ORDER BY j.erstellt_am DESC` (`:3288-3292`), Card-Rendering `:3303-3374` — **kein `berechne_match_score`, keine Score-Anzeige** (Repo-Grep: exakt 5 Treffer, alle oben klassifiziert).

**NiceGUI-Stand:** `_tab_stellen` (`webui/pages/candidate.py:301`) zeigt alle aktiv-Jobs ohne Score (Query `:304-311`, `ORDER BY j.id DESC`); `score_color`/`score_label` (Import `:15`) und `score_bar` (Import `:17`) sind **tote Imports** (im File ungenutzt); `berechne_match_score` (`webui/logic.py:439`) wird nur employer-seitig gerufen (`webui/pages/employer.py:779`); `get_matched_jobs_for_candidate` / `ORDER BY score` existieren nicht (Repo-Grep: 0 Treffer); **keine Score-Spalte** in `applications` (`app.py:3249-3260`) oder `jobs` (`app.py:3456-3477`) — Scores werden live berechnet, nirgends gespeichert *(Stand VOR Feature-G-Umsetzung; implementiert am 24.09.2026, siehe §7 Status)*.

**Paritätsurteil:** ❌ **kein 1:1-Paritätsfall** → Klassifikation **„Neues Feature, braucht explizites Go (Feature-Freeze)"**.

### 2. Reihenfolge / Sortierung (Optionen)

| Option | Verhalten | Pro | Contra |
|---|---|---|---|
| **A: Score DESC** | Alle aktiven Jobs, sortiert nach Score absteigend (Tie-Break `id DESC`) | Realisiert den Titel „Das passt zu dir"; braucht **keine erfundene Schwelle** (kein Lab-Prinzip-1-Verstoß); gleicher Aufwand wie Badge-only (N-Berechnungen ohnehin) | Neueste Jobs rutschen nach unten; Query-Änderung ggü. Streamlit-Parität (`ORDER BY j.erstellt_am DESC`, `app.py:3292`) |
| **B: „Gematchte zuerst, dann Rest"** | Schwellen-Split (z. B. ≥60), Rest unverändert darunter | Recency im Rest erhalten; klare Zwei-Zonen-Struktur | Braucht eine Schwellen-**Design-Entscheidung ohne externe Quelle** (Lab-Prinzip 1); Zone 2 ohne eigene Sortierung willkürlich |
| **C: Alle + Badge, Reihenfolge unverändert** | `id DESC` wie heute, nur Score-Badge | Minimale Änderung, query-parität zu heute | Titel-Versprechen „passt zu dir" wird durch Reihenfolge nicht eingelöst |

**Empfehlung: Option A (Score DESC, Tie-Break `id DESC`)** — als **Design-Entscheidung (24.09.2026)** gekennzeichnet: Der Tab-Titel verspricht persönliche Relevanz, Reihenfolge ist der einzige Ort, an dem das Versprechen wirkt; reines Ranking kommt ohne eine zu erfindende Match/Kein-Match-Schwelle aus (Schwellen wären Lab-Prinzip-1-pflichtig). **Fallback falls Recency erhaltenswert:** Option C.

### 3. Darstellung (Badge / Bar / Prozent vs. Bruch / Ort in der Card)

- **Komponenten (bereits vorhanden, tote Imports werden lebendig):** `score_bar` (`webui/components.py:220`, Import `candidate.py:17`), `score_color` (`webui/theme.py:83`, Import `candidate.py:15`), `score_label` (`webui/theme.py:101`, Import `candidate.py:15`), zusätzlich `score_badge_class` (`webui/theme.py:92`) verfügbar.
- **Farben (bestehende Schwellen, `theme.py:83-89`):** ≥80 → SECONDARY (grün), ≥60 → ACCENT (gelb), <60 → DANGER (rot).
- **Prozent vs. Bruch:** Feature-Titel sagt **„82 %"** → Badge als **`82 % passend`** (Prozent). Sekundärfarbe/Bruch „82/100" bleibt das `score_bar`-Label (Komponente zeigt `{score}/{max_score}`, `components.py:242`) — employer-/Streamlit-Seite zeigt durchgängig Bruch (`app.py:1903`, `:3661`, `:3861`), Candidate-Badge darf abweichen, da kundenorientierter Sprachgebrauch (Design-Entscheidung).
- **Ort im Job-Card-Layout:** Badge in der **Titelzeile** (`candidate.py:378-379` `ui.row` mit `#ID Titel – Firma`), rechts neben „Beworben"/„Bewerben" — sofort sichtbar ohne Klick; **`score_bar` im Expansion-Body** (`candidate.py:423-425`, oberhalb der 3-Spalten-Info-Grid) als Detailansicht.

### 4. Live vs. cached (Kosten)

- **N pro Tab-Öffnung:** `SELECT COUNT(*) FROM jobs WHERE status='aktiv'` = **3** (24.09.2026, READ-ONLY) → **3 Berechnungen/Tab-Öffnung** (1 Candidate × 3 Jobs).
- **Aufwand pro Candidate×Job** (`webui/logic.py:439-500`): reines Python (Skill-Strings splitten, 7 Sub-Scores, Normalisierung auf 100) + **1×** `_static_connector_call(HR_BENCHMARK_SERVER, "get_score_category")` (`logic.py:462`). Der Connector ist statisch/gecached (Skill `nicegui-migration` D16: Cold 25.7s / Warm 0.01s, „Nur Erfolge cachen"); Employer rendert bereits 10 Scores/Render, Candidate-Tab mit 3 ist unkritisch.
- **⚠️ Kostenmessung (29.09.2026, #93):** Employer-Render mit **19 hr-benchmark + 3 salary-data Subprozessen = 82,06 s kalt** (gemessen, `ergebnisse/m16-timing-20260929.md`) — Cache hilft nur bei identischen Score-Werten, nicht pro neuem Kandidat×Job-Paar.

### 4a. Kategorie-Quelle: lokal statt Subprozess (M-16-Fix, 29.09.2026)

> **Quelle (Lab-Prinzip 1):** Die Kategorie-Schwellen sind die **ZYTHR-Schwellen aus dem Connector selbst** (`connectors/hr-benchmark-server.py:44-53`, verifiziert 15.09.2026, `get_score_category`: ≥80 = "Strong", ≥60 = "Consider", <60 = "Weak"). Sie werden als **lokale Funktion** in `webui/logic.py` nachgebildet (exakt dieselben Werte) — der Wert ändert sich nicht, nur der Weg (kein Subprozess je Score). **Design-Entscheidung (29.09.2026, Nutzer-GO):** Weg lokal statt Subprozess; der Connector bleibt in `opencode.json` registriert (andere Tools + Runner-Nutzung unberührt; Runner-Restrukturierung = separater Punkt).
> **Grund:** 1 Subprozess ≈ 2–4 s (FastMCP-Import) × 19 Scores kalt = 82,06 s erster Render der Match-Seite (`m16-timing-20260929.md`). Identischer Schwellen-Wert, identische Kategorie-Ausgabe.
- **Empfehlung: live** solange aktive Jobs ≤ ~**20** (Design-Entscheidung, 24.09.2026). **Cache/Persistierung erst sinnvoll wenn:** (i) N > ~20 und Tab-Ladezeit messbar >1s, oder (ii) Score-Persistierung für ML/Reporting gebraucht wird. **Gegen vorzeitige DB-Speicherung:** Scores sind nirgends gespeichert (Schema `app.py:3249-3260`/`:3456-3477`, bewusst), Gewichte ändern sich per Feedback-Loop (`get_current_weights()`, `logic.py:441`) — ein Cache würde veralten und von der Live-Wahrheit abweichen.

### 5. Disclaimer / Transparenz (Explainability)

- **Datenquelle:** `berechne_match_score` liefert `erklaerung`-Dict mit 7 Kategorien (`webui/logic.py:485-493`, Rückgabe `:499`; Streamlit-Parität `app.py:713`/`:727` — Sektion Explainability `matching-criteria.md` oben, Zeilen 128–147; AGENTS.md zitiert veraltet `app.py:665-679`).
- **Vorschlag:** Pro Job-Card ein `ui.expansion` „**Warum passt das?**" im Expansion-Body, das die 7 `erklaerung`-Einträge rendert (Pattern employer-seitig portiert: `employer.py:786/829-831`), plus eine Disclaimer-Zeile: *„Score aus Startgewichten (Design-Entscheidung, keine externe Quelle) — Gewichte werden per Feedback-Loop nach echten Einstellungsentscheidungen kalibriert (siehe matching-criteria.md)."*
- **Skill-Link:** Hinweis auf `skills/explain-match/SKILL.md` — agent-generierte Detailbegründung nach Bewerbung (Task-Trigger `app.py:3363`).
- **Rechtsbezug:** EU AI Act Art. 50 Transparenz (`matching-criteria.md`, Explainability-Sektion, Zeile 147).

### 6. Grenzen — was der Score NICHT sagt

- **Gewichte sind keine Wahrheit:** Baseline 30/25/15/10/10/10/0 ohne externe Quelle = Design-Entscheidung (Zeile 25); Validierung braucht **20+ Einstellungsentscheidungen** (Zeilen 25, 43) — Loop ist implementiert (Phase 4, CLOSED) aber Historie jung → Gewichte ≈ Baseline.
- **Schwellen 90/75/60/40** sind Design-Entscheidungen (Zeile 124), kein Industriestandard.
- **Score ≠ Ergebnis:** sagt nichts über Gehalts-Toleranz, Visa, Compliance, Kultur-Fit oder Dokumenten-Authentizität — das sind getrennte Checks.
- **Ohne CV unbrauchbar:** Berechnung braucht `candidates.lebenslauf_text` etc.; Tab ist allen Eingeloggten sichtbar, CV-Pflicht gilt nur fürs Bewerben (`app.py:3281-3282`) → Badge ggf. erst ab Status `lebenslauf_hochgeladen` (Design-Entscheidung).
- **Verhaltensverzerrung:** öffentlicher Score kann Bewerbungsverhalten steuern (Design-Überlegung, keine Quelle).

### 7. Umfangs-Entscheidung für den User (KEIN Code — Go erforderlich)

| Option | Umfang | Aufwand | Voraussetzungen |
|---|---|---|---|
| **(i) nur Badge** | Prozent-Badge in der Titelzeile (`candidate.py:378`), keine Sortierung, kein Expander | Geringster | Reihenfolge/Sort spec §2 entfällt (Option C) |
| **(ii) Badge + Sortierung** | (i) + `score_bar` im Expansion-Body + Query `ORDER BY score DESC, id DESC` (§2 Option A) | Mittel | Score-Berechnung live in `_tab_stellen`; §4-Regel ≤20 Jobs einhalten |
| **(iii) Badge + Sortierung + Erklärungs-Expander** | (ii) + „Warum passt das?"-Expander mit `erklaerung`-Dict + Disclaimer + explain-match-Link (§5) | Höchster, aber Daten liegen fertig vor (`logic.py:485-499`) | Wie (ii) |

**Empfehlung: (ii)** — realisiert das Titel-Versprechen vollständig bei kleinstem Go-Umfang unter Feature-Freeze; **(iii)** als Folge-Go empfohlen (Transparenz/Daten vorhanden), **(i)** nur als Minimal-Fallback, falls Sortierung unerwünscht.

**Status (24.09.2026): (ii) umgesetzt** — `_tab_stellen` (`webui/pages/candidate.py`) berechnet live pro aktivem Job `logic.berechne_match_score()` (N=3 ≤ §4-Grenze 20; kein DB-Write, keine hardcodierten Schwellen — Gewichte aus `get_current_weights()`, Kategorien/Farben via `hr-benchmark`-Connector-Fallback), sortiert score DESC / id DESC (§2 Option A), zeigt Badge „{n} % passend" in der Titelzeile (`score_badge_class`) + `score_bar` im Expansion-Body (§3), CV-Gate: ohne `lebenslauf_text` keine Scores/Badges, Reihenfolge id DESC (§6). E2E: `tests/e2e_candidate_score.py` ((a) Badge-Anzahl (b) DOM-Reihenfolge == DB-Erwartung (c) score_bar + DB-Baseline unverändert). **(iii) „Warum passt das?"-Expander UMGESETZT 24.09.2026 (GO, gleicher Lauf):** `ui.expansion` im Job-Expansion-Body mit den 7 `erklaerung`-Einträgen (Pattern `employer.py:829-832`) + Disclaimer (Startgewichte/Feedback-Loop) + explain-match-Hinweis; E2E-Check (d). Damit ist §5 umgesetzt — **offene Go-Punkte verbleiben F/D/C/E/A (siehe entscheidungen.md)**.
