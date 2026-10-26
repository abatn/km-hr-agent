# Compliance-Regeln – Länderspezifische Arbeitsgesetze

> **Stand:** September 2026
> **Geltungsbereich:** Automatische Prüfung bei jedem Match
> **Voraussetzung:** Login + Lebenslauf-Upload (Jobportal-Prinzip)
> **Connectors:** ansvar-german-law (DE), ansvar-french-law (FR), ansvar-swiss-law (CH)
> **Gateway:** https://gateway.ansvar.eu/mcp (gemeinsamer Ansvar Gateway)

---

## 🇩🇪 Deutschland

### Connector
- **ansvar-german-law**: AGG, BDSG, MiLoG, EU AI Act (via Ansvar Gateway)
- **Gateway:** https://gateway.ansvar.eu/mcp
- **Tools:** search, validate_citation, get_provision, list_coverage + 28 weitere
- **Auth:** OAuth-Token vorhanden (Free-Tier)
- **Umfang:** 6.870 Gesetze, 91.843 Artikel, 5.000 Urteile

### Relevante Gesetze

| Gesetz | Kurzbeschreibung | Relevanz für Match |
|---|---|---|
| **AGG** (Allgemeines Gleichbehandlungsgesetz) | Verbot von Diskriminierung bei Einstellung | Prüfung auf Alters-, Geschlechts-, Herkunftsdiskriminierung |
| **EU AI Act** | Verordnung für KI-Systeme | Transparenz bei automatisierter Entscheidungsfindung |
| **BDSG** (Bundesdatenschutzgesetz) | Datenschutz bei Bewerberdaten | Verarbeitung personenbezogener Daten rechtmäßig |
| **ArbZG** (Arbeitszeitgesetz) | Arbeitszeitregelungen | Prüfung ob Stelle overtime/überstunden-kompatibel |
| **MiLoG** (Mindestlohngesetz) | Mindestlohn | Gehaltsangabe ≥ Mindestlohn |

### Automatische Prüfpunkte

| Prüfpunkt | Methode | Warnung bei Verstoß |
|---|---|---|
| AGG-Compliance | Keine Diskriminierung in Stellenausschreibung | WARNUNG |
| EU AI Act Transparenz | Hinweis auf KI-gestützte Entscheidung | HINWEIS |
| BDSG Bewerberdaten | Einwilligung zur Datenverarbeitung | WARNUNG |
| Gehalt ≥ Mindestlohn | MiLoG-Prüfung | FEHLER |

### Regel-Texte (Auszug)

```
AGG §1: Benachteiligungen aus Gründen der Rasse, der ethnischen Herkunft, des Geschlechts,
der Religion oder Weltanschauung, einer Behinderung, des Alters oder der sexuellen Identität
sind unzulässig.

EU AI Act Art. 50: Anbieter von KI-Systemen, die für die Interaktion mit natürlichen
Personen bestimmt sind, stellen sicher, dass diese Systeme als KI-generiert gekennzeichnet werden.

BDSG §26: Die Verarbeitung personenbezogener Daten von Beschäftigten ist zulässig, wenn sie
für die Entscheidung über die Begründung eines Beschäftigungsverhältnisses erforderlich ist.
```

---

## 🇫🇷 Frankreich

### Connector
- **ansvar-french-law**: Code du travail, Code pénal, Code civil, RGPD (via Ansvar Gateway)
- **Gateway:** https://gateway.ansvar.eu/mcp
- **Tools:** search, validate_citation, get_provision + 28 weitere
- **Auth:** OAuth-Token vorhanden (Free-Tier)
- **GitHub:** https://github.com/Ansvar-Systems/french-law-mcp
- **Umfang:** 3.958 Gesetze, 193.793 Artikel

### Relevante Gesetze

| Gesetz | Kurzbeschreibung | Relevanz für Match |
|---|---|---|
| **Code du travail** | Französisches Arbeitsgesetzbuch | Vertragsbedingungen, Kündigungsfristen |
| **LOI n° 2016-1088** | Digitale Souveränität | IT-Sicherheit, Datenaufbewahrung |
| **RGPD** (franz. DSGVO) | Datenschutz-Grundverordnung | Verarbeitung personenbezogener Daten |
| **Loi sur le travail** | Arbeitszeitgesetz | 35h-Woche, Überstundenregelungen |
| **Code pénal** | Strafgesetzbuch | Diskriminierungsverbote |

### Automatische Prüfpunkte

| Prüfpunkt | Methode | Warnung bei Verstoß |
|---|---|---|
| Non-discrimination | Prüfung auf Diskriminierung | WARNUNG |
| Durée du travail | Arbeitszeit ≤ 35h/Woche (Standard) | HINWEIS |
| RGPD-Compliance | Datenschutz-Bestimmungen | WARNUNG |
| Salaire minimum | SMIC-Prüfung | FEHLER |

### Regel-Texte (Auszug)

```
Code du travail L.1132-1: Aucun salarié ne peut être sanctionné, licencié ou avoir été l'objet
d'une mesure discriminatoire directe ou indirecte.

Loi sur le travail L.3121-27: La durée légale du travail à temps complet est fixée à 35 heures
par semaine.

RGPD Art. 6: Le traitement ne peutporter que sur des données à caractère personnel qui sont
adéquates, pertinentes et limitées à ce qui est nécessaire.
```

---

## 🇨🇭 Schweiz

### Connector
- **ansvar-swiss-law**: OR, ArG, DSG, StGB (via Ansvar Gateway)
- **Gateway:** https://gateway.ansvar.eu/mcp
- **Tools:** search, validate_citation, get_provision + 28 weitere
- **Auth:** OAuth-Token vorhanden (Free-Tier)
- **GitHub:** https://github.com/Ansvar-Systems/switzerland-law-mcp
- **Umfang:** 4.873 Gesetze

### Relevante Gesetze

| Gesetz | Kurzbeschreibung | Relevanz für Match |
|---|---|---|
| **OR** (Obligationenrecht) | Vertragsrecht | Arbeitsvertrag, Kündigungsfristen |
| **ArG** (Arbeitsgesetz) | Arbeitszeitgesetz | 45h/Woche (Industrie), 50h (andere) |
| **DSG** (Datenschutzgesetz) | Datenschutz | Verarbeitung personenbezogener Daten |
| **UVG** (Unfallversicherungsgesetz) | Unfallversicherung | Pflichtversicherung |
| **BBG** (Bundesgesetz über die berufliche Vorsorge) | Pensionskasse | Mindestvorsorge |

### Automatische Prüfpunkte

| Prüfpunkt | Methode | Warnung bei Verstoß |
|---|---|---|
| Arbeitszeit | ≤ 45h (Industrie) / ≤ 50h (andere) | HINWEIS |
| Lohnzahlung | Mindestlohn je nach Kanton | WARNUNG |
| DSG-Compliance | Datenschutz-Bestimmungen | WARNUNG |
| Kündigungsfrist | OR Art. 335 | HINWEIS |

### Regel-Texte (Auszug)

```
OR Art. 319: Das Arbeitsverhältnis kann für unbestimmte Zeit oder für bestimmte Dauer
eingegangen werden.

ArG Art. 9: Die wöchentliche Arbeitszeit der Arbeiter darf 45 Stunden nicht überschreiten
bei industriellen Betrieben und 50 Stunden in anderen Betrieben.

DSG Art. 6: Personendaten dürfen nur verarbeitet werden, wenn dies rechtmässig ist.
```

---

## Automatische Compliance-Prüfung im Match-Workflow

### Integration in match-candidate

1. **Länderkennung**: Erkenne anhand von Stellenprofil und Kandidatenprofil das/die relevanten Länder
2. **Regel-Laden**: Lade passende Compliance-Regeln aus knowledge/compliance/
3. **Prüfung**: Führe alle automatischen Prüfpunkte durch
4. **Dokumentation**: Füge Compliance-Ergebnis dem Match-Bericht hinzu
5. **Warnung**: Bei FEHLER → Match kann nicht fortgesetzt werden
6. **Hinweis**: Bei HINWEIS → Match wird mit Caveat versehen

### Compliance-Score (zusätzlich zum Matching-Score)

| Status | Bedeutung | Aktion |
|---|---|---|
| ✅ COMPLIANT | Alle Prüfungen bestanden | Match fortsetzen |
| ⚠️ WARNUNG | Nicht-kritische Verstöße | Match mit Caveat |
| ❌ FEHLER | Kritische Verstöße | Match pausieren, manuelle Prüfung |
