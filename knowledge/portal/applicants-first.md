# Applicants-First: Bewerber vor passiven Matches (B2-4)

> **Stand:** 25.09.2026
> **Zweck:** Einheitliche Rangfolge im Arbeitgeber-Portal: **aktive Bewerber zuerst**, danach passive Matches – mit identischen Status-/Sortier-Regeln auf allen HR-Seiten, die Kandidaten auflisten.
> **Gehört zu:** Skill `employer-portal` · Regelfundstelle `knowledge/portal/employer-portal-fields.md` („Bewerber-Sichtbarkeit … Rangfolge im Arbeitgeber-Tab") · `knowledge/lifecycle/application-status.md`
> **Status:** **Umgesetzt 25.09.2026 nach GO B2-4 (`webui/pages/employer.py` (Codemarke `def refresh_cands`, gemessen 10.10.2026) Bewerber-Query + De-Dup-Subquery); Nachweis `ergebnisse/entscheidungen.md` B2-RUNDE L1/L4 — `tests/e2e_applicants_first.py` PASS.**

---

## (a) Ist-Zustand NiceGUI (verifiziert 25.09.2026)

### Umgesetzt (das Vorbild)
| Datei:Zeile | Befund |
|---|---|
| `webui/pages/employer.py` (Codemarke `def refresh_cands`, gemessen 10.10.2026) | `def refresh_cands():` – Kandidaten-Picker der Feedback-Seite |
| `webui/pages/employer.py` (gemessen 10.10.2026) | Kommentar `# Bewerber dieser Stelle` |
| `webui/pages/employer.py` (gemessen 10.10.2026) | `applicants = … WHERE a.job_id = ? AND a.status != 'zurückgezogen'` + `ORDER BY a.erstellungsdatum DESC` |
| `webui/pages/employer.py` (gemessen 10.10.2026) | `passive = … WHERE c.status IN ('lebenslauf_hochgeladen','zugeordnet','aktiv') AND c.id NOT IN (SELECT candidate_id FROM applications WHERE job_id = ?) ORDER BY c.id DESC LIMIT 20` |
| `webui/pages/employer.py` (gemessen 10.10.2026) | `all_cands = applicants + passive` → **Bewerber stehen in der Liste zuerst** |
| `webui/pages/employer.py` (gemessen 10.10.2026) | `options={c[0]: f"{'📩 ' if c[2] else ''}…" for c in all_cands}` – Bewerber 📩-markiert |

### Abweichungen / Lücken
| Datei:Zeile | Befund |
|---|---|
| `webui/pages/employer.py` (gemessen 10.10.2026) | `ORDER BY a.erstellungsdatum DESC` → **Streamlit nutzt `ASC`** (älteste Bewerbung zuerst) |
| `webui/pages/employer.py` (gemessen 10.10.2026) | `a.status != 'zurückgezogen'` → listet auch `eingestellt`/`abgelehnt` als „Bewerber"; Streamlit filtert auf AKTIV |
| `webui/pages/employer.py` (Codemarke `def match_content`, gemessen 10.10.2026) | `_page_match.match_content()`: `JOIN applications … a.status != 'zurückgezogen'` → **nur Bewerber, keine passiven Matches**, also keine „zuerst-dann"-Struktur |
| `webui/pages/employer.py` (Codemarke `def filter_candidates`, gemessen 10.10.2026) | `_page_kandidaten.filter_candidates()`: `ORDER BY c.id DESC LIMIT 50`, **keine Bewerber-Kennzeichnung, keine Gruppierung** |
| `webui/pages/employer.py` (Codemarke `def _page_stellen`, gemessen 10.10.2026) | `_page_stellen`: Bewerbungen über alle Stellen, `ORDER BY a.erstellungsdatum DESC`, AKTIV-Split erst |

**Fazit (a):** „Applicants-First" existiert in NiceGUI **nur** im Feedback-Picker (`_page_feedback`) – und dort mit zwei Abweichungen zur Streamlit-Parität (DESC statt ASC, kein AKTIV-Status-Filter). Die HR-Hauptseiten `🔍 Kandidaten-Suche` und `📄 Match-Ergebnis` kennen die Reihenfolge nicht.

---

## (b) Paritätsbeleg `app.py` (verifiziert 25.09.2026)

| Zeile | Zitat |
|---|---|
| `app.py` (gemessen 10.10.2026) | `# ── Abschnitt 1: Aktive Bewerber ──` |
| `app.py` (gemessen 10.10.2026) | `# Bewerbungen zu dieser Stelle laden (Phase 1: Bewerber zuerst)` |
| `app.py` (gemessen 10.10.2026) | `c.execute("""SELECT a.id, a.candidate_id, a.status, a.bewerbungstext, a.erstellungsdatum` / `FROM applications a WHERE a.job_id = ? AND a.status IN ('eingegangen', 'angesehen', 'eingeladen')` / `ORDER BY a.erstellungsdatum ASC""", (job_id_sel))` |
| `app.py` (gemessen 10.10.2026) | `st.markdown(f"### 📥 Bewerber ({len(bewerber_rows)})")` |
| `app.py` (gemessen 10.10.2026) | `# ── Abschnitt 2: Passive Matches (wie bisher) ──` → `st.markdown("### 👥 Passive Matches")` |
| `app.py` (gemessen 10.10.2026) | `# Bewerber werden im Abschnitt 1 angezeigt – hier nicht doppelt` → `if k_id in bewerbung_map:` (De-Duplizierung) |
| `app.py` (gemessen 10.10.2026) | Feedback-Picker: `FROM applications a` / `WHERE a.job_id = ? AND a.status IN ('eingegangen', 'angesehen', 'eingeladen') ORDER BY a.erstellungsdatum ASC` |
| `app.py` (gemessen 10.10.2026) | `st.caption(f"Ausgewählt: {fb_choice} · Quelle: Tab '👥 Kandidaten' (Bewerber zuerst, dann passive Matches – gleiche Regeln wie Tab 3)")` |

---

## (c) Soll-Zeilen für den Code-Edit (KEIN Eingriff in B1 – nur Plan)

1. **Feedback-Picker angleichen** – `webui/pages/employer.py` (Codemarke `def _page_feedback`, gemessen 10.10.2026):
   - `webui/pages/employer.py` (gemessen 10.10.2026) → `WHERE a.job_id = ? AND a.status IN ('eingegangen', 'angesehen', 'eingeladen')` (Parität `app.py` (gemessen 10.10.2026)).
   - `webui/pages/employer.py` (gemessen 10.10.2026) → `ORDER BY a.erstellungsdatum ASC` (Parität `app.py` (gemessen 10.10.2026)).
2. **Reihenfolge-Verbot „doppelt"** – passive-Query `webui/pages/employer.py` (live Bewerber-Query, Subquery, Sammlung) hat bereits `c.id NOT IN (SELECT candidate_id FROM applications WHERE job_id = ?)` – **erweitert** auf `… WHERE job_id = ? AND status IN ('eingegangen','angesehen','eingeladen')`. **Begründung korrigiert (Nachtrag 25.09.2026):** die ursprüngliche Formulierung („damit ein Bewerber mit Status `abgelehnt` nicht als „passiver Match" wieder auftaucht") war **falsch** – die Erweiterung bewirkt das **Gegenteil**: ausgeschlossen werden nur *aktive* Bewerber, `abgelehnt`/`eingestellt` erscheinen **wieder** als passiver Match. Genau das ist die Streamlit-Parität (`app.py` (gemessen 10.10.2026) →, Feedback-Picker); NiceGUI-IST **vor** B2-4 schloss dagegen *alle* Bewerber aus. Parität gewinnt (Lab Schritt 3) → so umgesetzt und protokolliert: `ergebnisse/entscheidungen.md` B2-RUNDE **L3-1**.
3. **`_page_match.match_content()`** – `webui/pages/employer.py` (Codemarke `def match_content`, gemessen 10.10.2026): entweder (i) passiven Matches als **Abschnitt 2** anhängen (Struktur `app.py` (gemessen 10.10.2026) +), oder (ii) die Seite ausdrücklich als „nur Bewerber" labeln (`section_header`-Subtitle). **Empfehlung (ii)** = weniger Code, aber Abweichung zum Streamlit-Tab-3-Layout → **Design-Entscheidung**.
4. **`_page_kandidaten`** – `webui/pages/employer.py` (Codemarke `def _page_kandidaten`, gemessen 10.10.2026): Bewerber-Kennzeichnung (Join auf `applications` für die aktuelle Stelle) + Sortierung „Bewerber zuerst, dann Rest". Braucht wie Punkt B2-2 (c)3 einen Job-Kontext → **Design-Entscheidung, mit B2-2 zu entscheiden**.
5. **`_page_stellen`** – `webui/pages/employer.py` (Codemarke `def _page_stellen`, gemessen 10.10.2026) ist bereits korrekt (AKTIV-Split = Parität `app.py` (gemessen 10.10.2026)), Sortierung `DESC` (`webui/pages/employer.py` (Codemarke `def _page_stellen`, gemessen 10.10.2026)) entspricht Streamlit `app.py` (gemessen 10.10.2026) (`WHERE e.id = ? ORDER BY a.erstellungsdatum DESC`) – hier **kein Eingriff nötig**.
6. **Nicht anfassen:** `app.py`, `scripts/**`, `webui/db.py`.

---

## (d) Quelle je Zahl / Regel

| Wert / Regel | Quelle |
|---|---|
| „Aktive Bewerber (Status `eingegangen`/`angesehen`) werden ZUERST gelistet, danach die passiven Matches." | `knowledge/portal/employer-portal-fields.md` (wörtlich) |
| Aktiv-Status-Menge `('eingegangen','angesehen','eingeladen')` | **Parität** `app.py` (gemessen 10.10.2026) und `app.py` (gemessen 10.10.2026) – identisch mit `AKTIV` in NiceGUI `webui/pages/employer.py` (gemessen 10.10.2026) und `app.py` (gemessen 10.10.2026) |
| Sortierung `ORDER BY a.erstellungsdatum ASC` | **Parität** `app.py` (gemessen 10.10.2026) / `app.py` (gemessen 10.10.2026) |
| Passiv-Match-Status-Menge `('lebenslauf_hochgeladen','zugeordnet','aktiv')` | `webui/pages/employer.py` (gemessen 10.10.2026) = Streamlit-Pool (`app.py` (gemessen 10.10.2026)-Pool-Query `… status IN ('lebenslauf_hochgeladen', 'profil_geprueft', 'match_berechnet', 'eingeladen')`) ⚠️ **NiceGUI und Streamlit verwenden hier unterschiedliche Status-Mengen** → unter (c) als offene Inkonsistenz vermerkt |
| Bewerber-Sichtbarkeit (Kontaktdaten erst nach `eingeladen`) | `knowledge/portal/employer-portal-fields.md` (Art. 6(1)(b)) |
| Welche HR-Seite die kombinierte „Bewerber + passive"-Liste bekommt (`_page_match`, `_page_kandidaten`) | **Design-Entscheidung** ((c)3 und (c)4) |
| Externe Quelle (Gesetz/Studie) für die Sortierfolge selbst | **nicht vorhanden** – reine Projekt-/UX-Regel (Datenminimierung als *Begründung* ist belegt: `knowledge/portal/employer-portal-fields.md`, die Reihenfolge selbst ist Projektentscheidung) |

**Offene Inkonsistenz (ehrlich):** NiceGUI passiver Pool `('lebenslauf_hochgeladen','zugeordnet','aktiv')` (`webui/pages/employer.py` (gemessen 10.10.2026)) vs. Streamlit Kandidaten-Pool `('lebenslauf_hochgeladen','profil_geprueft','match_berechnet','eingeladen')` (`app.py` (gemessen 10.10.2026)). Status `zugeordnet`/`aktiv` kommen aus einem älteren Status-Modell. Beide Mengen müssen vor B2-4 entschieden werden → **Design-Entscheidung**.

---

## (e) Auswirkung + GO-Bedarf

**GO-Bedarf: B2-4.**

- **Was HR jetzt sieht:**
  - Feedback-Picker: Bewerber zuerst (stimmig), aber **neueste Bewerbung zuerst** und auch **abgelehnte/eingestellte** Kandidaten noch als Bewerber.
  - `📄 Match-Ergebnis`: nur Bewerber, keine passiven Kandidaten.
  - `🔍 Kandidaten-Suche`: flache ID-Reihenfolge ohne Bewerber-Markierung.
- **Was HR nach GO sieht:** Eine konsistente Reihenfolge auf allen Seiten: `📥 Bewerber (n)` → `👥 Passive Matches`, AKTIV-Status-Menge überall identisch, älteste Bewerbung zuerst, keine Dopplung.
- **Was der Kandidat merkt:** nichts Direct (Darstellungs-Sache), indirekt: sein Status-Verlauf erscheint in der richtigen Gruppe.
- **Risiko:** Sortier-Umstellung `DESC → ASC` ändert die sichtbare Reihenfolge im Picker – Gewöhnungseffekt für HR, daher GO statt stiller Änderung.

---

## (f) Testplan

- **Unit:** `pytest` (26 Tests) – muss grün bleiben.
- **E2E (realer Dateinamen-Check `ls tests/e2e_*.py`):**
  - `tests/e2e_vorgemerkt.py` – **direktes Gegenstück** für den Feedback-Picker (`/employer/feedback`, Select-Optionen, DB-Restore): Regression für Punkt (c)1 – Auswahl-Reihenfolge und 📩-Präfix dürfen nicht kippen.
  - `tests/e2e_gehalt_match.py` – `/employer/match` view-only: Regression für Punkt (c)3 (Match-Seite bleibt renderbar).
  - `tests/e2e_agent_details.py` – Employer-Taben view-only: Regression für Seiten-Navigation nach Gruppierungs-Umbau.
  - `tests/e2e_housing.py` – HR-Klick „Einstellen" → Freigabe-Report: Regression dass der Bewerber-Status-Flow (`eingestellt` → Archiv) durch die AKTIV-Listen-Änderung nicht kippt.
- **Testlücke (ehrlich):** Kein E2E prüft die Reihenfolge „Bewerber vor passiven Matches". Nach GO B2-4 wäre `tests/e2e_applicants_first.py` **NEU**: Stelle mit ≥1 Bewerbung + ≥1 passivem Kandidaten → (a) Reihenfolge im Picker, (b) `abgelehnt`-Bewerber erscheint **nicht** unter „passiv", (c) ASC-Sortierung. **In B1 nicht angelegt.**
