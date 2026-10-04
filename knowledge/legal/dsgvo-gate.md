# DSGVO-Gate für HR-Dokumenten-Ansicht (B2-1)

> **Stand:** 25.09.2026 · **Ergänzung 27.09.2026:** Verweis auf `knowledge/legal/recording-consent.md`
> **Zweck:** Sichtbarkeits-Gate für hochgeladene Kandidatendokumente in der Arbeitgeber-Sicht – Dokumente erst nach Status `eingeladen` (bzw. `eingestellt`) der Bewerbung beim jeweiligen Arbeitgeber.
> **Gehört zu:** Skill `employer-portal` Schritt „🗂️ Dokumente" · Rechtsgrundlage `knowledge/legal/gdpr-policy.md` · Feld-/Sichtbarkeits-Regelwerk `knowledge/portal/employer-portal-fields.md` · **Abgrenzung Aufnahmen:** Aufnahme-/Einwilligungs-Regeln stehen in `knowledge/legal/recording-consent.md` (anderes Thema: nicht *Sichtbarkeit*, sondern *Zulässigkeit der Aufzeichnung*)
> **Status:** **Umgesetzt 25.09.2026 nach GO B2-1 (Gate in `webui/pages/employer.py::_page_dokumente`/`refresh_docs`); Nachweis `ergebnisse/entscheidungen.md` B2-RUNDE L1/L4 — `tests/e2e_dsgvo_gate.py` PASS.**

---

## (a) Ist-Zustand NiceGUI (verifiziert 25.09.2026)

| Datei:Zeile | Befund |
|---|---|
| `webui/pages/employer.py:1067` | Sektion-Kommentar `# ─── 6. Dokumente ───` |
| `webui/pages/employer.py:1069` | `def _page_dokumente(s: dict) -> None:` – HR-Seite „Dokumente" |
| `webui/pages/employer.py:1080-1081` | `@ui.refreshable` / `def refresh_docs(typ_val: str = "alle"):` |
| `webui/pages/employer.py:1085` | `SELECT id, candidate_id, datei_pfad, dokumententyp, hochgeladen_am FROM candidate_documents ORDER BY id DESC` – **keine Status-Bedingung, kein JOIN auf `candidates`** |
| `webui/pages/employer.py:1089` | Gleiches Statement mit Typ-Filter `WHERE dokumententyp = ?` – ebenfalls **ohne Status-Gate** |
| `webui/pages/employer.py:1105` | `rows = [{"datei_pfad": d[2] or "--", "typ": d[3] or "--", "datum": d[4] or "--"} for d in docs]` |
| `webui/pages/employer.py:1657` | `"dokumente": _page_dokumente,` im `PAGE_MAP` (`PAGE_MAP` ab `:1649`) |

**Gate-Vergleich (Grep, 25.09.2026):**
- `grep -n "_dsgvo_ok\|dsgvo" webui/pages/*.py webui/logic.py` → in `webui/pages/employer.py` und `webui/pages/candidate.py` **0 Treffer** (das Gate ist jetzt direkt im SQL der `refresh_docs` Funktion).
- Einzige DSGVO-Treffer in `webui/logic.py` sind der **Lösch-Job** (Art. 17), nicht das Sichtbarkeits-Gate: `webui/logic.py:509` `def dsgvo_cleanup()`, `:551` `run_dsgvo_cleanup_once()`, `:827` Aufruf.
- Task-Label `webui/pages/employer.py:1011` `"check_gdpr": "DSGVO pruefen"` ist nur Anzeige-Text der Agent-Details.

**Fazit (a):** Die HR-Seite `🗂️ Dokumente` listet nun **nur** Dokumente von Kandidaten, die beim jeweiligen Arbeitgeber eine Bewerbung mit Status `eingeladen` oder `eingestellt` haben. Das Gate ist direkt im SQL der `refresh_docs` Funktion implementiert.

**Abgrenzung (kein Fehler):** Die Kandidaten-Eigen-Sicht `webui/pages/candidate.py:610` `def _tab_dokumente(...)` arbeitet mit `db.get_documents(cand_id)` (`webui/db.py:214`, `WHERE candidate_id = ?`) – korrekt nach Eigentümer gefiltert; hier greift kein DSGVO-Gate.

---

## (b) Paritätsbeleg `app.py` (verifiziert 25.09.2026)

| Zeile | Zitat |
|---|---|
| `app.py:2037` | `elif skill == "🗂️ Dokumente" and current_role() == "employer":` |
| `app.py:2039` | `st.caption("🔒 DSGVO: Dokumente nur sichtbar nach Status 'eingeladen'. "` |
| `app.py:2053` | `_dsgvo_ok = _cand_status in ("eingeladen", "eingestellt")` |
| `app.py:2056-2057` | `if not _dsgvo_ok:` → `st.warning(f"🔒 DSGVO: Dokumente erst nach Status 'eingeladen' sichtbar. Aktueller Status: **{_cand_status}**")` |
| `app.py:2059-2060` | `else:` → `st.success(f"✅ Status: {_cand_status} – Dokumente sind freigegeben (DSGVO Art. 6(1)(b))")` |

**Ehrliche Abweichung (auch in `app.py` selbst):** Die Caption `app.py:2039` sagt „**nur** sichtbar nach Status `eingeladen`", der Code `app.py:2053` erlaubt zusätzlich `eingestellt`. Maßgeblich ist der Code (`eingeladen` **oder** `eingestellt`) – das ist auch fachlich richtig (ein eingestellter Kandidat bleibt eingeladen/ eingestellt). Diese Inkonsistenz wird hier **nicht** beschönigt.

---

## (c) Ist-Zustand nach Implementation (Stand 29.09.2026)

Das Gate ist wie folgt implementiert:

1. **Primär (SQL-Gate)** – `webui/pages/employer.py::_visible_documents()` (reine Funktion mit explizitem `conn`, aufgerufen aus `_page_dokumente()` → `refresh_docs()`).
   - **Schema-Fakt:** Die Tabelle `applications` hat **keine** Spalte `employer_id`. Arbeitgeber-Bezug ausschließlich über `jobs`: `JOIN jobs j ON j.id = a.job_id ... j.employer_id = ?`.
   - Bedingung: `j.employer_id = ? AND a.status IN ('eingeladen','eingestellt')`, gruppiert per abgeleitetem JOIN `GROUP BY a.candidate_id` (verhindert Dokument-Duplikate bei mehreren Bewerbungen eines Kandidaten).
   - Liefert je Dokument u. a. `app_status` = höchste freigebende Bewerbung (`eingestellt` > `eingeladen`) sowie Klarnamen-Fallback `Kandidat #<id>`.
   - Siehe Datei:Zeile `webui/pages/employer.py:71-104` (Gate-Query `:85-90`, Aufruf `refresh_docs` `:1722`).

2. **Fallback / UX** – `_blocked_candidates()` (`webui/pages/employer.py:107-135`) liefert nur Kandidaten, die sich **bei diesem Arbeitgeber** beworben haben, aber keine freigebende Bewerbung besitzen. Über zwei `EXISTS`-Prüfungen (`j2.employer_id = ?` vorhanden, `j3.employer_id = ? AND a3.status IN (...)` nicht vorhanden) — Kandidaten **ohne** Bewerbung bei diesem Arbeitgeber werden bewusst nicht genannt (kein Datenleck fremder Kandidaten).

3. **Nicht anfassen:** `webui/db.py:214 get_documents()` (Kandidaten-Eigenview) und `webui/db.py:214 insert_document()` / `:229 delete_document()`.

4. Der Gate-Text entspricht dem Streamlit-Paritätsbeleg (`app.py:2057`).

**Status:** Implementiert. Testnachweis: `tests/test_employer_agent_b.py` (pytest gegen Spiegel-DB, `tests/conftest.py`-Muster) prüft `_visible_documents`/`_blocked_candidates` read-only gegen `data/feedback.db`: Arbeitgeber 1 sieht Dokumente von Kandidat 13 (3×) und 22 (1×), Arbeitgeber 2 sieht keine.

## (d) Quelle je Zahl / Regel

| Wert / Regel | Quelle |
|---|---|
| Rechtsgrundlage Art. 6(1)(b) (vorvertragliche Maßnahmen bei aktiver Bewerbung) | `knowledge/legal/gdpr-policy.md:32-35` (§ 2b) |
| Datenkategorien „Qualifikationsdaten / Bewerbungsdaten", Speicherdauer 6 Monate | `knowledge/legal/gdpr-policy.md:46-51` |
| „E-Mail, Telefon, Lebenslauf-Datei ❌ Nein – erst nach Kandidaten-Zustimmung (Einladung)" | `knowledge/portal/employer-portal-fields.md:86-96` (Tabelle Kandidaten-Sichtbarkeit) |
| „E-Mail, Telefon, Lebenslauf-Datei ❌ Nein – erst nach Status `eingeladen`" | `knowledge/portal/employer-portal-fields.md:102-114` (Tabelle Bewerber-Sichtbarkeit) |
| Gate-Status-Liste `("eingeladen", "eingestellt")` | **Parität** `app.py:2053` (Projektregel, kein Gesetzestext) – nun über `applications.status` im Kontext` im Kontext des Arbeitgebers in `webui/pages/employer.py` implementiert |
| Sichtbar-/Sperr-Text | **Parität** `app.py:2057` |
| Kein externes Gesetz, das genau diese UI-Schwelle vorschreibt | **Design-Entscheidung** (rechtlicher Rahmen Art. 6(1)(b) belegt, die konkrete UI-Gate-Schwelle ist Projektentscheidung) |

---

## (e) Auswirkung + GO-Bedarf

**GO-Bedarf: B2-1.**

- **Was HR jetzt sieht:** Unter `🗂️ Dokumente` alle hochgeladenen Dateien aller Kandidaten sofort, auch vor jeder Einladung.
- **Was HR nach GO sieht:** Die Liste ist leer bzw. enthält nur Dokumente eingeladener/eingestellter Kandidaten; zusätzlich der 🔒-Hinweis mit aktuellem Status. Konsequenz für den Workflow: **Erst `→ eingeladen`, dann Dokumente einsehen** – die Einladung wird damit zum faktischen Freigabe-Schritt (bewusst, Parität Streamlit).
- **Was der Kandidat merkt:** nichts Direct – aber sein Dokument-Archiv wird nicht mehr ungefiltert gezeigt (Datensparsamkeit Art. 5 DSGVO, `knowledge/legal/gdpr-policy.md:10` ff.).
- **Risiko:** HR verliert die „schnelle Sicht" auf Zeugnisse/Visa-Dokumente vor der Einladung – das ist die beabsichtigte Wirkung, aber eine echte Nutzungsänderung → daher **GO-Pflicht**, kein stiller Einbau.

---

## (f) Testplan

- **Unit:** `pytest` (26 Tests) – muss unverändert grün bleiben (kein Gate-Logik-Test in den 26 vorhanden → Regressions-Gate).
- **E2E (bestehend, realer Dateinamen-Check `ls tests/e2e_*.py`):**
  - `tests/e2e_agent_details.py` – view-only Employer-Tab; Regression: Agent-Details/Badges bleiben nach Gate-Einbau unverändert.
  - `tests/e2e_c7_downloads.py` – Employer-/Onboarding-Downloads; Regression: keine Seitenausfälle in der Employer-Navigation.
  - `tests/e2e_apply_dialog.py` – Bewerbungs-Flow bis Agent-Kette; Regression: `verify_documents`-Task (der die Dokumente erzeugt) läuft weiter.
- **Testlücke (ehrlich):** Es gibt **kein** bestehendes E2E, das das DSGVO-Gate prüft. Nach GO B2-1 wäre `tests/e2e_dsgvo_gate.py` **NEU** zu schreiben: Employer-Login → `🗂️ Dokumente` → (a) Kandidat mit Status `eingegangen` → 0 Zeilen + 🔒-Hinweis, (b) nach `→ eingeladen` → Zeilen sichtbar. **In B1 nicht angelegt** (kein Code, kein Test ohne GO).
