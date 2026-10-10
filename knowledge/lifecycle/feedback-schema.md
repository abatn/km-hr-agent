# Feedback-Schema – SQLite-Datenbank

> **Stand:** September 2026
> **Phase 3 (11.09.2026):** `match_id` ist UNIQUE (`idx_feedback_match_id`). Speichern ist idempotent: gleicher Tag = UPDATE des bestehenden Eintrags, nächster Tag = neuer Datensatz (Datums-Suffix in match_id). Kein `INSERT OR REPLACE` mehr. Employer-Portal Tab 4: Kandidaten-Picker aus dem tatsächlichen Ranking (Bewerber zuerst, dann passive Matches – gleiche Regeln wie Tab 3) statt freier ID-Eingabe.  
> **Datenbank:** `~/mimo-agents/km-hr-agent/data/feedback.db`  
> **Voraussetzung:** Login + Lebenslauf-Upload (Jobportal-Prinzip)

> **Phase 4 (11.09.2026) – Geschlossener Loop:** `gewichtung_historie` ist jetzt Quelle UND Leser. Jedes **neue** Feedback (INSERT, nicht same-day-UPDATE) ruft `adjust_weights_from_feedback()` auf – aus **beiden** Trigger-Punkten: Employer-Portal Tab 4 UND Skill 8. Erfolg (`eingeladen='Ja'` UND score ≥ 80) → Berufserfahrung +5 (Roh); Misserfolg (`eingeladen='Nein'` UND score < 70) → Sprache +10 (Roh). Caps: Baseline+15 je Kategorie (Sprache: max 15). Scoring liest ausschließlich `get_current_weights()` (Historie → Rohgewichte → Normalisierung auf Summe 100). Gewichte-Detailmodell: `knowledge/lifecycle/matching-criteria.md`.
>
> **⚠️ Korrektur 08.10.2026 (VERIFY, Messung ⓘ08.10.2026):** Die Schwellen sind im Code **kategorieabhängig** (`adjust_weights_from_feedback()` mit hr-benchmark `get_score_category`): Fallback bzw. „Strong"/„Weak" = **80/70** wie oben, Kategorie **„Consider" = 60/60** (Erfolg ab score ≥ 60, Misserfolg ab score < 60). 80/70 gilt also nicht pauschal. Beide Schwellenpaare ohne externe Quelle (Design-Entscheidung).

---

## Datenbankschema

```sql
-- Tabelle: feedback
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL UNIQUE,
    kandidat_name TEXT NOT NULL,
    stellenprofil TEXT NOT NULL,
    score INTEGER NOT NULL,
    kategorie TEXT NOT NULL,  -- Hervorragend/Gut/Bedingt/Schwach/Nicht passend
    datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Feedback-Bewertungen (1–5 Skala)
    fachlich_korrekt INTEGER CHECK(fachlich_korrekt BETWEEN 1 AND 5),
    skills_richtig INTEGER CHECK(skills_richtig BETWEEN 1 AND 5),
    standort_zutreffend INTEGER CHECK(standort_zutreffend BETWEEN 1 AND 5),
    empfehlung_hilfreich INTEGER CHECK(empfehlung_hilfreich BETWEEN 1 AND 5),
    
    -- Ergebnis
    eingeladen TEXT CHECK(eingeladen IN ('Ja', 'Nein', 'Vorgemerkt')),
    compliance_probleme TEXT,  -- JSON-Array oder NULL
    
    -- Anmerkungen
    anmerkungen TEXT,
    
    -- Gewichtungsverlauf
    gewichtung_vorher TEXT,    -- JSON der Gewichtung vor Anpassung
    gewichtung_nachher TEXT,   -- JSON der Gewichtung nach Anpassung
    
    -- Metadaten
    land TEXT DEFAULT 'DE',    -- DE/FR/CH
    branche TEXT,
    rolle TEXT
);

-- Tabelle: gewichtung_historie
CREATE TABLE IF NOT EXISTS gewichtung_historie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    kategorie TEXT NOT NULL,  -- Kernkompetenzen/Erfahrung/Bildung/Standort/Branche/SoftSkills
    alte_gewichtung INTEGER NOT NULL,
    neue_gewichtung INTEGER NOT NULL,
    grund TEXT NOT NULL,
    feedback_anzahl INTEGER NOT NULL  -- Anzahl Feedback-Einträge die zur Änderung führten
);

-- Tabelle: compliance_protokoll
CREATE TABLE IF NOT EXISTS compliance_protokoll (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    land TEXT NOT NULL,
    pruefpunkt TEXT NOT NULL,
    status TEXT NOT NULL,  -- COMPLIANT/WARNUNG/FEHLER
    details TEXT,
    datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Beispiel-Abfragen

### Durchschnittsbewertung der letzten 90 Tage
```sql
SELECT 
    AVG(fachlich_korrekt) as avg_fachlich,
    AVG(skills_richtig) as avg_skills,
    AVG(standort_zutreffend) as avg_standort,
    AVG(empfehlung_hilfreich) as avg_empfehlung,
    COUNT(*) as anzahl_feedbacks
FROM feedback
WHERE datum > date('now', '-90 days');
```

### Einladungsquote nach Score-Kategorie
```sql
SELECT 
    kategorie,
    COUNT(*) as gesamt,
    SUM(CASE WHEN eingeladen = 'Ja' THEN 1 ELSE 0 END) as eingeladen,
    ROUND(100.0 * SUM(CASE WHEN eingeladen = 'Ja' THEN 1 ELSE 0 END) / COUNT(*), 1) as quote
FROM feedback
GROUP BY kategorie;
```

### Häufigste Compliance-Probleme
```sql
SELECT 
    compliance_probleme,
    COUNT(*) as haeufigkeit
FROM feedback
WHERE compliance_probleme IS NOT NULL
GROUP BY compliance_probleme
ORDER BY haeufigkeit DESC
LIMIT 10;
```

---

## Initialisierung

Die Datenbank wird beim ersten Aufruf von `store-feedback` automatisch erstellt.

---

## UI-Optionsliste „Eingeladen?" (O3, 23.09.2026)

- Employer-Tab-4 (Streamlit `app.py` (gemessen 10.10.2026) + NiceGUI `webui/pages/employer.py`): Options `["Ja", "Nein", "Vorgemerkt"]`, Default `Ja`.
- Semantik: `Vorgemerkt` = neutral — löst den Phase-4-Weight-Loop NICHT aus (`adjust_weights_from_feedback` → `return ""`, Beleg: `ergebnisse/phase-4-feedback-loop.md`). Speicherung unverändert in `feedback.eingeladen` (CHECK Z.32 erlaubt den Wert bereits).
- **Skill-8 bewusst nur 2 Optionen (NB2, Entscheidung 23.09.2026):** Das Skill-8-Feedback-Formular zeigt `['Ja','Nein']` — NiceGUI `webui/components.py` (gemessen 10.10.2026) UND Streamlit `app.py` (gemessen 10.10.2026) identisch (Default `Ja`). `Vorgemerkt` bleibt Tab-4-exklusiv → **keine Paritätslücke, keine Änderung.**

## Restore-Regel `gewichtung_historie` / `gew_max` (NB3, Entscheidung 23.09.2026)

- `gew_max` = `MAX(id) FROM gewichtung_historie` — DB-Ist 23.09.2026: **4 Zeilen** (count=4).
- Es gibt **keinen Festwert-Soll**: grep `gew_max` in knowledge/ + skills/ + instructions.md + AGENTS.md = 0 Treffer. Die in einem E2E-Lauf auftauchende „Soll = 8" war eine Test-Prompt-Annahme, **keine MD-Spezifikation** (Lab-Prinzip 1: keine Quelle → keine Regel).
- **Regel:** E2E-Restore vergleicht pre==post (Zustand vor dem Test vs. danach), nie auf eine konstante Zahlenzahl pochen.
- Skill 8 (`app.py` (gemessen 10.10.2026) / `webui/components.py` (gemessen 10.10.2026)) bewusst nur `["Ja", "Nein"]` — Parität in BEIDEN Apps, keine Lücke.
- Quelle der Portierung: `app.py` (gemessen 10.10.2026) (Streamlit-Verhalten, keine Erfindung).
