# Matching-Filter für die Kandidaten-Liste (B2-2)

> **Stand:** 25.09.2026
> **Zweck:** Ein Kandidat erscheint in der Kandidaten-/Match-Liste einer Stelle nur, wenn die dokumentierte Matching-Regel greift: ≥ 1 Must-Have-Skill-Treffer **und** Berufserfahrung ≥ 50 % der Anforderung.
> **Gehört zu:** Skill `employer-portal` Schritt „👥 Kandidaten" / „📄 Match-Ergebnis" · Regelwerk `knowledge/portal/employer-portal-fields.md` · Score-Logik `knowledge/lifecycle/matching-criteria.md` · Scoring-Funktion `webui/logic.py` (gemessen 10.10.2026)
> **Status:** **Umgesetzt 25.09.2026 nach GO B2-2 — TEILWEISE KORRIGIERT 25.09.2026 (Phase-E Runde 6): (c)2 Score-Filter der passiven Matches im Feedback-Picker umgesetzt (`refresh_cands`, Nachweis `tests/e2e_feedback_filter.py` rot→grün PASS); (c)1 auf `_page_match` war ein Paritätsbruch (Passiv-Regel auf Bewerber-Karten angewandt) und wurde ENTFERNT — Bewerber wieder ungefiltert wie `app.py` (gemessen 10.10.2026). Details: (c)-Korrektur, (e)/(f)-Nachtrag, `ergebnisse/entscheidungen.md` Runde 6.**

---

## (a) Ist-Zustand NiceGUI (verifiziert 25.09.2026)

| Datei:Zeile | Befund |
|---|---|
| `webui/pages/employer.py` (Codemarke `def _page_kandidaten`, gemessen 10.10.2026) | `def _page_kandidaten(s: dict) -> None:` – Seite „Kandidaten-Suche" |
| `webui/pages/employer.py` (Codemarke `def filter_candidates`, gemessen 10.10.2026) | `def filter_candidates(status_filter: str) -> None:` |
| `webui/pages/employer.py` (Codemarke `def _list_candidates`, Messung 15.10.2026) | `WHERE c.status IN (CAND_CV_STATUS)` mit `CAND_CV_STATUS = ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")` + `ORDER BY c.id DESC` – **kein LIMIT** (Code: „Kein LIMIT (Tabelle paginiert)“), **nur Status-Filter, kein Must-Have, kein Erfahrungs-Filter, kein Score** |
| `webui/pages/employer.py` (Codemarke `def _page_match`, gemessen 10.10.2026) | `def _page_match(s: dict) -> None:` – Seite „Match-Ergebnis" |
| `webui/pages/employer.py` (gemessen 10.10.2026) | Kandidaten-Query mit `JOIN applications ... WHERE j.employer_id = ? AND a.status != 'zurückgezogen'` – **kein Must-Have/Erfahrungs-Predikat** |
| `webui/pages/employer.py` (gemessen 10.10.2026) | `result = logic.berechne_match_score(k_data, j_data)` |
| `webui/pages/employer.py` (gemessen 10.10.2026) | Auswertung nur `total` / `kategorie` / `erklaerung` – **`result["matches"]` wird nie ausgewertet** |
| `webui/pages/employer.py` (Codemarke `def refresh_cands`, gemessen 10.10.2026) | `def refresh_cands():` (Feedback-Picker) |
| `webui/pages/employer.py` (gemessen 10.10.2026) | Passive Matches: reiner Status-Filter + `LIMIT 20`, **ohne Score-Prüfung** |
| `webui/logic.py` (gemessen 10.10.2026) | `"total": total, "kategorie": kategorie, "matches": matches` – die Filter-Information **wird geliefert**, aber nirgends in `webui/pages/` verwendet |

**Grep-Nachweis (25.09.2026):**
- `grep -n "matches" webui/pages/employer.py` → **0 Treffer**.
- `grep -n "0\.5" webui/pages/*.py webui/logic.py` → nur CSS-/Opacity-Treffer (`webui/pages/admin.py` (gemessen 10.10.2026), `webui/pages/employer.py` (gemessen 10.10.2026), `webui/pages/login.py` (gemessen 10.10.2026)), **kein Erfahrungs-Faktor**.

**Fazit (a):** Die dokumentierte Vier-Bedingungs-Regel existiert in NiceGUI **nicht**. Es werden (je nach Seite) alle Bewerber oder alle Status-Kandidaten gelistet – ungefiltert.

---

## (b) Paritätsbeleg `app.py` (verifiziert 25.09.2026)

| Zeile | Zitat |
|---|---|
| `app.py` (gemessen 10.10.2026) | `# Matching-Regel (identisch zu Phase 1): ≥1 Must-Have (Synonym-Match zählt) und ≥50% der geforderten Erfahrung` |
| `app.py` (gemessen 10.10.2026) | `if not matches:` → `continue` |
| `app.py` (gemessen 10.10.2026) | `if job_erfahrung_lbl and (k_erf or 0) < job_erfahrung_lbl * 0.5:` → `continue` |
| `app.py` (gemessen 10.10.2026) | `st.warning("⚠️ Keine passenden Kandidaten (mindestens 1 Must-Have-Skill nötig).")` |

Gleicher Filter zweitens im Feedback-Picker (Parität für die NiceGUI-Seite `feedback`):
`app.py` (gemessen 10.10.2026) → `if not r_fb["matches"]: continue  # Passive Matches: gleiche Regel wie Tab 3 (≥1 Must-Have)` / `if j_erf and (k_erf or 0) < j_erf * 0.5: continue`.

**Kontext:** `app.py` (gemessen 10.10.2026) `tab1, tab2, tab3, tab4 = st.tabs(["📝 Firmenprofil", "📢 Stellen", "👥 Kandidaten", "💬 Feedback"])`; der Filterblock liegt in **Tab 3 „👥 Kandidaten"** (Sektions-Kommentar `app.py` (gemessen 10.10.2026)).

---

## (c) Soll-Zeilen für den Code-Edit (KEIN Eingriff in B1 – nur Plan)

1. **Primär – `webui/pages/employer.py` (Codemarke `def match_content`, gemessen 10.10.2026):**
   - Nach `webui/pages/employer.py` (gemessen 10.10.2026) (Score-Berechnung) und vor (`total = result["total"]`) den Filter einziehen:
     - `if not result["matches"]: continue` (Parität `app.py` (gemessen 10.10.2026))
     - `if j_exp and (exp or 0) < j_exp * 0.5: continue` (Parität `app.py` (gemessen 10.10.2026)); `exp` liegt ab `webui/pages/employer.py` (gemessen 10.10.2026) im `cand`-Tuple, `j_exp` im `job`-Tuple.
   - Leergarnitur: wenn ein Job keine Bewerber mehr hat, Leerhinweis analog `app.py` (gemessen 10.10.2026) statt leerer Klappe.
   - **Korrektur 25.09.2026 (Phase-E Runde 6, aufgedeckt durch `tests/e2e_housing.py`):** Punkt (c)1 in dieser Form war **falsch** — die zitierten Zeilen `app.py` (gemessen 10.10.2026) liegen in der **Passiv-Match-Loop** (nach `app.py` (gemessen 10.10.2026) „Bewerber werden im Abschnitt 1 angezeigt – hier nicht doppelt"), nicht in der Bewerber-Darstellung. `_page_match` listet ausschließlich Bewerber (JOIN applications), der Filter versteckte daher Bewerber ohne Must-Have-Skill (cand1: `matches=[]` → Karte samt Einladen/Einstellen-Buttons weg, HR konnte dort nicht mehr verwalten). **Umgesetzt:** Filter entfernt, `_matched` = ungefilterter Ergebnis-Cache aller `jobs[:3]` = Parität `app.py` (gemessen 10.10.2026); Leergarnitur bleibt. Ein echter Passiv-Filter auf dieser Seite braucht erst Abschnitt 2 = Punkt (c)3 (option i) mit **eigenem GO**.
2. **Feedback-Picker – `webui/pages/employer.py` (Codemarke `def _page_feedback`, gemessen 10.10.2026) :**
   - Passive Matches  vor `all_cands = applicants + passive`  mit `logic.berechne_match_score()` prüfen und Nicht-Treffer verwerfen (Parität `app.py` (Codemarke `def berechne_match_score`, gemessen 10.10.2026)). **Bewerber bleiben ungefiltert** (Parität `app.py` (Codemarke `def berechne_match_score`, gemessen 10.10.2026)).
3. **`_page_kandidaten` :** Derzeit **kein Job-Kontext** auf der Seite – ein Must-Have-Filter ist hier ohne Stellen-Auswahl sinnlos. Soll-Entscheidung (offen): entweder Job-Wähler ergänzen (mehr Aufwand) oder die Seite bewusst als „ungefilterte Suche" deklarieren und den Filter nur in 1+2 umsetzen → **Design-Entscheidung**.
4. **Nicht anfassen:** `webui/logic.py` (Codemarke `def berechne_match_score`, gemessen 10.10.2026) (liefert bereits alles Richtige), `scripts/**`.

---

## (d) Quelle je Zahl / Regel

| Wert / Regel | Quelle |
|---|---|
| Bedingung 1 „Kandidat-Status ≥ `lebenslauf_hochgeladen`" | `knowledge/portal/employer-portal-fields.md` |
| Bedingung 2 „Stelle hat Status `aktiv`" | `knowledge/portal/employer-portal-fields.md` |
| Bedingung 3 „Mindestens 1 Must-Have-Skill-Übereinstimmung" | `knowledge/portal/employer-portal-fields.md` + `app.py` (gemessen 10.10.2026) |
| Bedingung 4 „Berufserfahrung ≥ 50 % der Anforderung (Rundung nach unten)" | `knowledge/portal/employer-portal-fields.md` + `app.py` (gemessen 10.10.2026) (Faktor `0.5`) |
| Ranking „Score 0–100, Kategorien Hervorragend/Gut/Bedingt/…" | `knowledge/portal/employer-portal-fields.md` → `knowledge/lifecycle/matching-criteria.md` |
| Score-Bänder 90/75/60/40 | **Design-Entscheidung** (`knowledge/lifecycle/matching-criteria.md`, ausdrücklich als „keine externe Quelle" gekennzeichnet) |
| Rohgewichte 30/25/15/10/10/10/0 | **Design-Entscheidung** (`knowledge/lifecycle/matching-criteria.md`) |
| Welche der 4 Seiten den Filter bekommt (`_page_match`, Feedback-Picker, `_page_kandidaten` ja/nein) | **Design-Entscheidung** (oben (c)3) |
| Externe Quelle für „1 Must-Have / 50 %" (Gesetz, Studie) | **nicht vorhanden** – es ist eine *Projektregel*, die in `employer-portal-fields.md` steht; hier nicht als extern belegt ausgegeben |

---

## (e) Auswirkung + GO-Bedarf

**GO-Bedarf: B2-2.**

- **Was HR jetzt sieht:** In `📄 Match-Ergebnis` jeden Bewerber mit Score – auch wenn **kein** Must-Have-Skill zutrifft oder die Erfahrung deutlich unter der Anforderung liegt. In `🔍 Kandidaten-Suche` ohnehin jede:r im Status-Filter, ganz ohne Bezug zur Stelle.
- **Was HR nach GO sieht:** Nur noch Kandidaten, die die dokumentierte Regel erfüllen; sonst der Hinweis „Keine passenden Kandidaten (mindestens 1 Must-Have-Skill nötig)" (Parität `app.py` (gemessen 10.10.2026)).
- **Nebenwirkung (bewusst):** Die Trefferzahl sinkt – HR sieht weniger, aber regelkonforme Kandidaten. Bestehende Rankings/Exports (CSV `webui/pages/employer.py` (gemessen 10.10.2026)) ändern sich sichtbar.
- **Sichtbarer Bruch zur Streamlit-Ära:** Das NiceGUI-Verhalten ist seit Migration **weniger streng** als `app.py` – B2-2 stellt die Parität wieder her, es wird also *etwas entfernt*, das Nutzer evtl. schon kennen.
- **~~OFFEN~~ ERLEDIGT (Nachtrag 25.09.2026, historisch) – Teil (c)2:** der Score-Filter der *passiven* Matches im Feedback-Picker (Punkt (c)2, Parität `app.py` (gemessen 10.10.2026)) ist am 25.09.2026 in Phase-E Runde 6 **umgesetzt** (Beweis: neu `tests/e2e_feedback_filter.py`, roter Beweis vor Fix → grün danach; `refresh_cands` baut die passive Menge nur noch aus Score-Treffern, Bewerber ungefiltert). Der frühere OFFEN-Hinweis („nur, `refresh_cands` ohne Filter") gilt nicht mehr – er bleibt hier als Historie stehen.

---

## (f) Testplan

- **Unit:** `pytest` (26 Tests) – muss grün bleiben (darunter die Score-Tests, die `berechne_match_score` unverändert lassen).
- **E2E (realer Dateinamen-Check `ls tests/e2e_*.py`):**
  - `tests/e2e_gehalt_match.py` – „Gehalts-Check live im Match-View (Display-only, keine DB-Schreibung)": Regression, dass die Match-View nach Filtereinbau rendert und `berechne_match_score`/`gehalt_check` weiter greifen.
  - `tests/e2e_candidate_score.py` – Score-Badge + Score-DESC im Candidate-Stellen-Tab (andere Seite, aber gleiche Score-Codebasis): Regression, dass der Filter **nur** die HR-Seiten betrifft.
  - `tests/e2e_vorgemerkt.py` – Employer-Feedback-Select + DB-Restore: Regression für `refresh_cands()` (Punkt (c)2).
- **Testlücke (ehrlich):** Kein bestehendes E2E prüft die Must-Have-/50%-Filterung. Nach GO B2-2 wäre `tests/e2e_matching_filter.py` **NEU**: Stelle mit Must-Have „k8s"/Erfahrung 5 wählen → Kandidat ohne Treffer erscheint nicht, Kandidat mit ≥1 Treffer + ≥50 % erscheint, Leercase zeigt `app.py` (gemessen 10.10.2026)-Text. **In B1 nicht angelegt.** — **Stand Runde 6:** Diese Lücke betrifft nur noch eine künftige Passivmenge (Abschnitt 2, (c)3-option-i); für Bewerber-Karten ist „ungefiltert" jetzt der korrekte Zustand (Korrektur (c)1).
- **~~Teil (c)2 ungetestet~~ aufgelöst (Nachtrag 25.09.2026, Runde 6):** `tests/e2e_feedback_filter.py` prüft (a) Nicht-Treffer fehlt, (b) Bewerber immer da, (c) DB unverändert, (d) ASC — an Job 1 und Job 6. `tests/e2e_vorgemerkt.py` bleibt Reihen-/DB-Restore-Regression von `refresh_cands()`.

---

## (g) Passiv-Block auf Match-Seite (P3, §H-16, 26.09.2026 — ✅ gebaut, Nachweis 09.10.2026)

- **GO:** Option (c)3-i aus Abschnitt 2, eigener GO (entscheidungen:2288). MD-first: diese Zeile vor dem Code.
- **Status:** ✅ **gebaut (Nachweis 09.10.2026).** Der Passiv-Block existiert in `webui/pages/employer.py` (Codemarke `_passive_best`, gemessen 09.10.2026 → `grep -n "_passive_best" webui/pages/employer.py` → `1628`; Rendering/Fokus ebenda), Test `tests/e2e_passive_on_match.py` vorhanden.
- **Reihenfolge:** Bewerber-Karten **zuerst** (Parität Streamlit-Abschnitt 1, `app.py` (gemessen 10.10.2026)), dann `👥 N passiver Match (keine aktive Bewerbung; Score absteigend)`.
- **Gate NUR für Passive:** ≥1 Must-Have-Treffer **und** `berufserfahrung_jahre ≥ 50 % der Anforderung` (Parität `app.py` (gemessen 10.10.2026)). Bewerber bleiben ungefiltert (Korrektur (c)1, 25.09.2026).
- **Pool (Parität Feedback-Picker `app.py` (gemessen 10.10.2026)):** `candidates.status IN ('lebenslauf_hochgeladen', 'profil_geprueft', 'match_berechnet', 'eingeladen')`; Ausschluss: `applications` des Employers mit `a.status != 'zurückgezogen'`; Jobs: `j.status = 'aktiv'`.
- **Sortierung/Dedupe:** Score DESC, bester Job pro Kandidat, **LIMIT 10** = Design-Entscheidung (kein Branchenbeleg).
- **Karten:** info-only (Name, Job, Score, Kategorie, Must-Have-Treffer) — **keine Buttons, keine Kontaktdaten** (DSGVO: Kontaktfreigabe erst Status `eingeladen`, knowledge/legal/dsgvo-gate.md).
- **Leercase:** Label `⚠️ Keine passenden Kandidaten …` nur wenn **weder** Bewerber **noch** Passiv-Treffer (`_treffer == 0 and not _passive`).
- **Roter Beweis (vor dem Code-Edit):** `tests/e2e_passive_on_match.py` — Teil A Quelltext rot → nach E47/E48 grün; Teile B (DB-Replik) und C (`/employer/match`, `greenthread`) view-only.
- **Abnahme:** `tests/e2e_passive_on_match.py` PASS · `tests/e2e_applicants_first.py` + `tests/e2e_housing.py` PASS (Regression) · `pytest` 26 · UI-Label sichtbar bei ≥1 Passiv-Treffer.
