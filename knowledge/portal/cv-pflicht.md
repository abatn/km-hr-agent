# CV-Pflicht vor der Bewerbung (B2-3)

> **Stand:** 25.09.2026
> **Zweck:** Bewerben ist erst nach Lebenslauf-Upload erlaubt (Kandidat-Status ≥ `lebenslauf_hochgeladen`). Stellen ansehen bleibt erlaubt.
> **Gehört zu:** Skill `job-application` (Kandidaten-Seite) · Regelwerk `knowledge/lifecycle/application-status.md` („Bewerbungs-Voraussetzung (CV-Pflicht)")
> **Status:** **Umgesetzt 25.09.2026 nach GO B2-3 (`webui/pages/candidate.py` UI-Gate + `webui/db.py` (Codemarke `def apply_to_job`, gemessen 10.10.2026) Guard); Nachweis `ergebnisse/entscheidungen.md` B2-RUNDE L1/L4 — `tests/e2e_cv_pflicht.py` PASS.**

---

## (a) Ist-Zustand NiceGUI (verifiziert 25.09.2026)

### Was GATE ist
| Datei:Zeile | Befund |
|---|---|
| `webui/pages/candidate.py` (gemessen 10.10.2026) | `show_scores = bool(cand and (cand[7] or "").strip())` – **CV-Gate nur für Scores/Badges** (Kommentar, „CV-Gate (§6, Design-Entscheidung): ohne lebenslauf_text keine Scores/Badges") |
| `webui/pages/candidate.py` (Codemarke `def _tab_prescreen`, gemessen 26.10.2026) | `non_app_allowed = status in ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet")` + `app_allowed` (Status `eingeladen`/`eingestellt` in `applications`) |
| `webui/pages/candidate.py` (Codemarke `def _tab_prescreen`, gemessen 10.10.2026) | `if status not in erlaubt:` → `⚠️ CV-Pflicht: Laden Sie zuerst Ihren Lebenslauf hoch (Status: …)` – **in `_tab_prescreen()`**, mit `return` (Blockiert den Pre-Screen-Tab) |

### Was NICHT gate ist (die Lücke)
| Datei:Zeile | Befund |
|---|---|
| `webui/pages/candidate.py` (Codemarke `def _tab_stellen`, gemessen 10.10.2026) | `def _tab_stellen(s: dict) -> None:` – Stellenangebote |
| `webui/pages/candidate.py` (gemessen 10.10.2026) | `cand = … SELECT hard_skills, soft_skills, berufserfahrung_jahre, abschluss, deutsch, englisch, standort, lebenslauf_text, status FROM candidates WHERE id = ?` – **`status` wird seit B2 mitgeliefert (`cand[8]`)** |
| `webui/pages/candidate.py` (Codemarke `def _open_apply_dialog`, gemessen 10.10.2026) | `def _open_apply_dialog(jid=j_id):` – Bewerbungs-Dialog, keine Statusprüfung |
| `webui/pages/candidate.py` (Codemarke `def _submit`, gemessen 10.10.2026) | `def _submit():` → `db.apply_to_job(s["user_cand_id"], jid, bew_text.value or None)` – **kein `cv_ok`-Check** |
| `webui/pages/candidate.py` (Codemarke `def _open_apply_dialog`, gemessen 10.10.2026) | `ui.button("Bewerben", icon="send", on_click=_open_apply_dialog)` – **Button immer klickbar, nie deaktiviert** |
| `webui/db.py` (Codemarke `def apply_to_job`, gemessen 10.10.2026) | `def apply_to_job(candidate_id: int, job_id: int, bewerbungstext: str \| None = None) -> int:` |
| `webui/db.py` (gemessen 10.10.2026) | `INSERT INTO applications (candidate_id, job_id, status, bewerbungstext) VALUES (?, ?, 'eingegangen', ?)` – **kein Status-Prädikat vor dem INSERT** |

**Fazit (a):** Die CV-Pflicht greift im NiceGUI **nur** für (1) Score-Badges im Stellen-Tab und (2) den Pre-Screen-Tab. Das **Bewerben selbst ist nicht gesperrt** – ein Kandidat ohne Lebenslauf kann sich bewerben; die 10er-Agent-Kette (`webui/db.py` (gemessen 10.10.2026)) läuft dann auf einem leeren Profil an.

---

## (b) Paritätsbeleg `app.py` (verifiziert 25.09.2026)

| Zeile | Zitat |
|---|---|
| `app.py` (gemessen 10.10.2026) | `# Eigenen Kandidaten-Status laden (CV-Pflicht: Bewerben nur ab lebenslauf_hochgeladen)` |
| `app.py` (gemessen 10.10.2026) | `cv_ok = mein_status in ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")` |
| `app.py` (gemessen 10.10.2026) | `if not cv_ok:` → `st.warning("⚠️ CV-Pflicht: Bewerben ist erst nach Lebenslauf-Upload möglich (👤 Candidate Portal → 📄 Lebenslauf). Stellen ansehen ist erlaubt.")` |
| `app.py` (gemessen 10.10.2026) | `elif not cv_ok:` → `st.button("🔒 Lebenslauf nötig", key=f"apply_lock_{j_id}", disabled=True, help="Bitte zuerst Lebenslauf hochladen (Candidate Portal → Lebenslauf)")` |

**Wichtig (hier selbst gefunden, geht über den Aufgaben-Prompt hinaus):** Das eigentliche **Harte Gate** in `app.py` steht nicht (das ist nur die Warnzeile oben im Tab), sondern bei **`app.py` (gemessen 10.10.2026)** – der Bewerben-Button wird durch einen `disabled=True`-Button ersetzt. Das ist die Stelle, die NiceGUI nachbilden muss.

Zweiter, bereits portierter CV-Gate (nur Pre-Screen): `app.py` (gemessen 10.10.2026) `st.warning("⚠️ CV-Pflicht: Laden Sie zuerst Ihren Lebenslauf hoch (📤 Upload oder 👤 Candidate Portal).")` → portiert als `webui/pages/candidate.py` (gemessen 10.10.2026) (`ui.label(...)` mit `⚠️ CV-Pflicht`, Gate).

---

## (c) Soll-Zeilen für den Code-Edit (KEIN Eingriff in B1 – nur Plan)

1. **Query erweitern** – `webui/pages/candidate.py` (Codemarke `def _tab_stellen`, gemessen 10.10.2026), `cand`-Query:
   `SELECT hard_skills, soft_skills, berufserfahrung_jahre, abschluss, deutsch, englisch, standort, lebenslauf_text, status FROM candidates WHERE id = ?`
   ⚠️ **Index-Folge:** `cand[7]` (genutzt in `show_scores` `webui/pages/candidate.py` (gemessen 10.10.2026) und im `k_data`-Dict) würde zu `cand[8]`; das sind die **einzigen** `cand[i]`-Zugriffe (`grep -n "cand\[" webui/pages/candidate.py` → nur). Empfehlung: `status` ans **Ende** der Query (geringste Nebenwirkung: nur `cand[7]` → `cand[8]`).
2. **`cv_ok` ableiten** – `webui/pages/candidate.py` (Codemarke `def _tab_stellen`, gemessen 10.10.2026), direkt nach:
   `cv_ok = (cand[8] or "") in ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")` (Liste = Parität `app.py` (gemessen 10.10.2026)).
3. **Button-Gate** – `webui/pages/candidate.py` (gemessen 10.10.2026):
   - wenn `cv_ok`: unverändert `ui.button("Bewerben", …)`;
   - sonst: deaktivierter Button `🔒 Lebenslauf nötig` + `help`/Tooltip (Parität `app.py` (gemessen 10.10.2026)); Alternative (NiceGUI-idiomatisch): `ui.button(...).props("disable")` – **Design-Entscheidung**.
4. **Persistente Warnzeile** – `webui/pages/candidate.py` (Codemarke `def _tab_stellen`, gemessen 10.10.2026) über der Job-Liste: `ui.label("⚠️ CV-Pflicht: Bewerben ist erst nach Lebenslauf-Upload möglich …")` mit demselben Styling-Muster wie `webui/pages/candidate.py` (Codemarke `def _tab_stellen`, gemessen 10.10.2026) (Parität `app.py` (gemessen 10.10.2026)).
5. **Defense-in-Depth** – `webui/db.py` (Codemarke `def apply_to_job`, gemessen 10.10.2026) vor:
   `SELECT status FROM candidates WHERE id = ?` → wenn nicht in der 4er-Liste: `raise ValueError("CV-Pflicht: Status …")`; `_submit` in `webui/pages/candidate.py` (Codemarke `def _submit`, gemessen 10.10.2026) fängt das als `except`-Zweig (heute nur `IntegrityError` und `Exception` – der generische Zweig fängt es bereits, Meldung wäre aber unspezifisch).
6. **Nicht anfassen:** `_tab_prescreen` (`webui/pages/candidate.py` (Codemarke `def _tab_prescreen`, gemessen 10.10.2026)), `scripts/**`, `app.py`.

---

## (d) Quelle je Zahl / Regel

| Wert / Regel | Quelle |
|---|---|
| „Bewerben setzt Kandidat-Status ≥ `lebenslauf_hochgeladen` voraus" | `knowledge/lifecycle/application-status.md` |
| „Ohne CV: Stellenangebote können angeschaut, aber nicht beworben werden – UI zeigt Hinweis …" | `knowledge/lifecycle/application-status.md` |
| Status-Liste `("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")` | **Parität** `app.py` (gemessen 10.10.2026) (Projekt-Definition, kein Gesetz) |
| Warn-Text | **Parität** `app.py` (gemessen 10.10.2026) |
| Sperr-Button „🔒 Lebenslauf nötig" + `disabled=True` | **Parität** `app.py` (gemessen 10.10.2026) |
| Maximale Motivationstext-Länge 2000 Zeichen | **bereits implementiert** `webui/pages/candidate.py` (gemessen 10.10.2026) (Parität `app.py` (gemessen 10.10.2026)) – unverändert |
| Ob die Sperrung **zusätzlich** in `db.apply_to_job()` erzwungen wird (Defense-in-Depth) | **Design-Entscheidung** (Punkt (c)5) |
| Schrift-Icon/„disabled"-Darstellung in NiceGUI | **Design-Entscheidung** (Punkt (c)3) |

---

## (e) Auswirkung + GO-Bedarf

**GO-Bedarf: B2-3.**

- **Was der Kandidat jetzt sieht:** „Bewerben" ist immer klickbar; ohne CV läuft die Bewerbung durch, der Agent verarbeitet ein leeres Profil (Extract/Match auf `lebenslauf_text = ""`), der Score im Stellen-Tab fehlt nur (`show_scores` = False).
- **Was der Kandidat nach GO sieht:** Ohne CV ein 🔒-gesperrter Button + Warnhinweis; erst nach Upload (Tab `Upload`, Status-Setzung `webui/pages/candidate.py` (gemessen 10.10.2026) → `status='lebenslauf_hochgeladen'`) wird wieder „Bewerben" aktiv.
- **Was HR merkt:** weniger sinnlose/leere Bewerbungen in `eingegangen` (paradoxerweise weniger, aber aussagekräftigere Eingänge) – die Agent-Kette startet nur noch mit Substanz.
- **Risiko:** Kandidaten mit CV in externer Form (noch nicht hochgeladen) werden blockiert → der Hinweis muss den Upload-Weg nennen (Parität `app.py` (gemessen 10.10.2026) nennt ihn bereits).

---

## (f) Testplan

- **Unit:** `pytest` (26 Tests) – muss grün bleiben (kein CV-Gate-Test vorhanden → nur Regression).
- **E2E (realer Dateinamen-Check `ls tests/e2e_*.py`):**
  - `tests/e2e_apply_dialog.py` – **das direkte Gegenstück**: prüft heute den positiven Fall (CV vorhanden → Dialog → „Jetzt bewerben" → Toast → DB-Row). Nach GO muss um **(a) Negativfall** ergänzt werden: Kandidat **ohne** `lebenslauf_text` → Button `🔒 Lebenslauf nötig` deaktiviert, **kein** Dialog, `applications` unverändert.
  - `tests/e2e_candidate_score.py` – prüft den bestehenden CV-Gate für Scores (`§6`), Regression dass `show_scores`/`cand[7→8]`-Umbau korrekt war.
  - `tests/e2e_profile_save.py` + `tests/e2e_profile_readview.py` – 12-Felder-Save/Read, Regression dass der Query-Umbau in `_tab_stellen` keine Indexverschiebung in andere Tabs trägt.
- **Testlücke (ehrlich):** `e2e_apply_dialog.py` deckt nur den **Positivfall** ab; der Negativfall „ohne CV gesperrt" existiert als Test **nicht** und ist nach GO B2-3 nachzulegen (Erweiterung desselben Skripts, kein neuer Dateiname nötig).

---

## (g) Profil-Save-Regel (P0-1, Design-Entscheidung 29.09.2026)

**Problem:** `save_profile` (`webui/pages/candidate.py` (Codemarke `def save_profile`, gemessen 10.10.2026)) setzte `status='profil_vollstaendig'` unbedingt — auch bei vorhandenem Lebenslauf. Die 4er-Whitelist (oben) kennt diesen Status nicht → nach ganz normalem Profilspeichern war „Bewerben" dauerhaft gesperrt (Sackgasse; einziger Ausweg: CV-Re-Upload). Live-Beweis 29.09.2026: Kandidat #1 hat `status='profil_vollstaendig'` UND `lebenslauf_datei` gefüllt (DB-Abfrage `SELECT id,status,… FROM candidates WHERE status='profil_vollstaendig'` → `1|profil_vollstaendig|CV-da`).

**Regel (verbindlich ab 29.09.2026):**
1. Profil-Speichern **ohne** CV → `status = profil_vollstaendig` (unverändert, `skills/candidate-portal/SKILL.md`).
2. Profil-Speichern **mit** CV → der Status wird **nie abgesenkt**: `registriert`/`profil_vollstaendig` werden zu `lebenslauf_hochgeladen` (Selbstheilung), alle höheren Status bleiben.
3. Die 4er-Whitelist der Gates bleibt unverändert — CV-Pflicht bleibt: Bewerben nur ab `lebenslauf_hochgeladen`.

**Code folgt MD:** `webui/pages/candidate.py` (gemessen 10.10.2026) → SQL-`CASE` (Umsetzung + Tests: `ergebnisse/entscheidungen.md` #91).
**Quelle:** Design-Entscheidung (keine externe Quelle; `knowledge/portal/cv-pflicht.md` „Projekt-Definition, kein Gesetz"). Lösel den MD-Widerspruch `skills/candidate-portal/SKILL.md` („→ profil_vollstaendig") ↔ `instructions.md` („Verboten: … profil_vollstaendig") zugunsten von „Gates bleiben, Save wird CV-bewusst" (Lab-Prinzip 3).

---

## (h) Sackgassen-Regel: CV-Gate braucht klickbaren Weg (P1-2, 29.09.2026)

**Problem (Plan `ui-mvp-plan-v2.md` §6 P1-2):** Das Pre-Screen-Gate (`webui/pages/candidate.py`, `_tab_prescreen`) zeigte nur eine Warn-Zeile „⚠️ CV-Pflicht: Laden Sie zuerst Ihren Lebenslauf hoch …" + `return` — **kein klickbarer Weg** zum Upload → Sackgasse für Bewerber ohne CV (Status außerhalb der 4er-Whitelist, z. B. `registriert`).

**Regel (verbindlich ab 29.09.2026):** Jede CV-Pflicht-Warnung im Kandidaten-Portal enthält **zusätzlich einen klickbaren Weg** (`ui.button "→ Zum Lebenslauf-Upload"` → `navigate_to("candidate", "upload")`). Die Gate-Sperre selbst bleibt unverändert — die 4er-Whitelist (§ oben) ist nicht angetastet; nur die Sackgasse wird zu einem geführten Weg.

**Code folgt MD:** `webui/pages/candidate.py` `_tab_prescreen` (Button vor dem `return`; Umsetzung + Verifikation: `ergebnisse/entscheidungen.md` #95).
**Quelle:** Design-Entscheidung auf Nutzer-GO (P1-Reihenfolge laut freigegebenem Plan); Zielregel „keine Sackgasse ohne nächsten klickbaren Schritt" (Plan §2, „Sackgassen-Regel").
