# Doku-Authority: Quelle-der-Wahrheit je Doku-Typ (v1.0)

> **Diese Datei ist die verbindliche Authority-Regel der Doku-Hierarchie.**
> **Status:** Design-Entscheidung (Auftrag „v1 einfrieren + Doku/Code 100 % konsistent", Phase S2, 10.10.2026). Die Einteilung der Dokus in Typen ist eine Projekt-Konvention — keine externe Quelle.
> **Grundregel: Ein Fakt steht an genau einem Ort.** Alles andere ist Verweis oder datierte Messung.

## 1. Die vier Doku-Typen

| Typ | Inhalt | Steht in | Bei MD↔Code-Konflikt |
|---|---|---|---|
| **normativ** | Verbindliche Regeln, Specs, Prozessvorgaben (Soll) | `knowledge/**` (Specs), `skills/*/SKILL.md`, `AGENTS.md` (nur Lab-Prinzipien + Conventions) | **Code korrigieren** (außer bewusste Spec-Änderung → als Design-Entscheidung in `ergebnisse/entscheidungen.md` protokollieren, dann Spec ändern) |
| **deskriptiv** | Beschreibt den Ist-Zustand (Ist) | `knowledge/portal/*-fields.md`, `knowledge/lifecycle/feedback-schema.md`, Inventar-/Übersichts-Dokus (`README.md`, `knowledge.md`, `instructions.md`) | **Doku korrigieren** |
| **historisch** | Datierte Ereignisse, Verlauf, Messungen, Entscheidungsbelege | **ausschließlich** `ergebnisse/entscheidungen.md` (Lab-Schritt 4) | nicht anwendbar (Beleg, keine Regel) |
| **tot / Duplikat** | Inhalt woanders belegt, Stand überholt, ohne Beleg | **löschen** (Stopp-Punkt: vor dem Löschen von Dateien den Nutzer fragen) oder zu einem Verweis auf den einen Ort kürzen | nicht anwendbar |

## 2. Konflikt-Hierarchie (verbindlich)

1. **Normativ** gewinnt gegen deskriptiv — bei Widerspruch wird die deskriptiv-Doku korrigiert.
2. **Code** gewinnt gegen deskriptiv — die Doku beschreibt den Code, nicht umgekehrt (Lab-Schritt 3).
3. **Normativ vs. Code:** der Konflikt wird *entschieden*, nicht geregelt: entweder Code an die Spec (Umsetzung) oder Spec als Ist bestätigen (Design-Entscheidung). Jede Entscheidung → `ergebnisse/entscheidungen.md`.
4. **Historisch** hat nie Vorrang: eine datierte Messung bleibt gültig (mit Messdatum), ersetzt aber keine aktuelle Regel.

## 3. Rollen der Root-Dokus (keine Überschneidungen)

| Datei | Rolle | Enthält | Enthält NICHT |
|---|---|---|---|
| `AGENTS.md` | operativ (normativ) | Setup, Tests, CI-Gates, Gotchas, bindende Conventions, Zeiger auf Specs | Changelog, datierte „NEU …"-Blöcke, Detail-Specs |
| `README.md` | Einstieg für Menschen (deskriptiv, global) | Kurzüberblick, Startbefehle, Projektstruktur, Verweise | Wiederholung von Spec-Fakten |
| `instructions.md` | Workflow-Handbuch + MCP-Connector-Census (deskriptiv) | Standard-/Job-API-Workflow, Connector-Census (aktuell + entfernt), Speicherorte | Rollen-Regeln (→ `knowledge/system/access-control.md`), Scoring (→ `knowledge/lifecycle/matching-criteria.md`), Verlauf |
| `knowledge.md` | Wissens-Index (deskriptiv) | Inventar-Messung (datiert), Verweis-Index auf `knowledge/**`, Test-Report-Index | eigene Fakten, die in einer Spec stehen |
| `ergebnisse/entscheidungen.md` | Beweislog (historisch, gitignored) | jede Entscheidung: Was/Warum/Quelle | Regeln (→ Specs) |

## 4. Zitier-Regel (normativ, seit 01.10.2026)

`Datei:Zeile` ist kein stabiler Verweis (Zeilenangaben-Drift, Befund `ergebnisse/zeilenangaben-drift-2026-10-01.md`). Verbindlich: **Codemarke** (z. B. `PAGE_MAP`, `def berechne_match_score`) + **Messdatum**, vor dem Zitat `grep -n "<marke>" <datei>` prüfen. Ausnahme: datierte Alt-Reports in `ergebnisse/` bleiben unangetastet.

## 5. Konsequenzen für neue Doku

- Neue Fakten: zuerst prüfen, ob eine Spec der rechtmäßige Ort ist; wenn ja → dort ergänzen, andernorts nur verweisen.
- Zahlen ohne Quelle sind verboten — entweder externe Quelle (Gesetz, Studie, offizielle Doku) oder Kennzeichnung **„Design-Entscheidung"** (Lab-Schritt 1).
- Datierte Änderungsnarrative gehen **nie** in Specs, sondern nach `ergebnisse/entscheidungen.md`.
