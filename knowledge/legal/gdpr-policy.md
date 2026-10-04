# DSGVO-Strategie – KM-HR-Agent

> **Stand:** September 2026  
> **Rechtsgrundlage:** Verordnung (EU) 2016/679 (Datenschutz-Grundverordnung)  
> **Geltungsbereich:** Alle Verarbeitungen personenbezogener Daten im Recruiting-Prozess  
> **Voraussetzung:** Login + Lebenslauf-Upload (Jobportal-Prinzip)

---

## 1. Grundsätze der Datenverarbeitung (Art. 5 DSGVO)

| Grundsatz | Umsetzung im Agenten |
|---|---|
| **Rechtmäßigkeit** | Nur Daten aus legitimen Quellen (Bewerbung, Empfehlung) |
| **Zweckbindung** | Daten nur für konkreten Stellenprozess |
| **Datenminimierung** | Nur relevante Felder extrahieren |
| **Richtigkeit** | Regelmäßige Aktualisierung, Keine Archivierung ohne Aktualisierung |
| **Speicherbegrenzung** | Max. 6 Monate nach Prozessende |
| **Integrität & Vertraulichkeit** | Lokale Verarbeitung, kein Cloud-Upload ohne Einwilligung |
| **Rechenschaftspflicht** | Vollständiges Protokoll aller Verarbeitungsschritte |

---

## 2. Rechtsgrundlagen der Verarbeitung (Art. 6 DSGVO)

### 2a. Einwilligung (Art. 6(1)(a))
- **Wann:** Bei Daten von Dritten (Recruiter, Empfehlung)
- **Form:** Schriftlich (per E-Mail oder Formular)
- **Inhalt:** Klar, konkret, informiert, freiwillig
- **Widerruf:** Jederzeit möglich, ohne negative Folgen

### 2b. Vertragserfüllung (Art. 6(1)(b))
- **Wann:** Bei Daten vom Kandidaten selbst (Bewerbung)
- **Voraussetzung:** Kandidat hat sich aktiv beworben
- **Umfang:** Nur Daten, die für den Bewerbungsprozess nötig sind

### 2c. Berechtigtes Interesse (Art. 6(1)(f))
- **Wann:** Nicht im Recruiting üblich
- **Einschränkung:** Nur bei überwiegendem Interesse + Interessenabwägung
- **Empfehlung:** Im Recruiting NICHT als primäre Rechtsgrundlage nutzen

---

## 3. Kategorien der verarbeiteten Daten

| Kategorie | Enthaltene Daten | Speicherdauer |
|---|---|---|
| **Stammdaten** | Name, Adresse, Telefon, E-Mail | 6 Monate |
| **Qualifikationsdaten** | Lebenslauf, Bildung, Zertifikate | 6 Monate |
| **Berufserfahrung** | Positionen, Unternehmen, Zeiträume | 6 Monate |
| **Bewerbungsdaten** | Anschreiben, Zeugnisse, Referenzen | 6 Monate |
| **Match-Daten** | Score, Begründung, Feedback | 12 Monate (anonymisiert) |
| **Compliance-Daten** | DSGVO-Report, Einwilligung | 36 Monate (Pflicht) |

---

## 4. Betroffenenrechte (Art. 15–22 DSGVO)

| Recht | Umsetzung |
|---|---|
| **Auskunft** (Art. 15) | Kandidat kann jederzeit Auskunft über gespeicherte Daten verlangen |
| **Berichtigung** (Art. 16) | Unrichtige Daten werden unverzüglich korrigiert |
| **Löschung** (Art. 17) | Daten werden nach 6 Monaten automatisch gelöscht – **seit Phase 4.5 (11.09.2026) technisch umgesetzt:** `dsgvo_cleanup()` bei App-Start löscht `applications` + `application_status_history` 183 Tage nach Prozessende (letzter Statuswechsel bei finalem Status; Details: `knowledge/lifecycle/application-status.md`) |
| **Einschränkung** (Art. 18) | Auf Verlangen: Daten werden nur gespeichert, nicht verarbeitet |
| **Datenübertragbarkeit** (Art. 20) | Kandidat kann Daten in maschinenlesbarem Format erhalten |
| **Widerspruch** (Art. 21) | Kandidat kann der Verarbeitung widersprechen |

---

## 5. Technische und organisatorische Maßnahmen (Art. 32 DSGVO)

### 5a. Technische Maßnahmen
- **Lokale Verarbeitung:** Keine DatenSendung an externe Server (ohne Einwilligung)
- **Verschlüsselung:** AES-256 für gespeicherte Daten
- **Zugriffskontrolle:** Nur autorisierte Personen
- **Protokollierung:** Vollständiges Audit-Log

### 5b. Organisatorische Maßnahmen
- **Datenschutzbeauftragter:** Benannt (falls Pflicht nach Art. 37)
- **Verzeichnis der Verarbeitungstätigkeiten:** Geführt (Art. 30)
- **Datenschutz-Folgenabschätzung:** Durchgeführt (bei hohem Risiko)
- **Schulungen:** Regelmäßige Datenschutz-Schulungen

---

## 6. Internationale Datenübermittlung (Art. 44–49 DSGVO)

| Ziel | Rechtsgrundlage | Maßnahme |
|---|---|---|
| EU/EWR | Keine Einschränkung | Standard |
| Schweiz | Angemessenheitsbeschluss | Standard |
| USA | EU-US Data Privacy Framework | Prüfung erforderlich |
| Andere Drittländer | Standardvertragsklauseln (SCC) | Individuelle Prüfung |

---

## 7. Meldepflichten (Art. 33–34 DSGVO)

| Ereignis | Meldepflicht | Frist |
|---|---|---|
| Datenschutzverstoß | An Aufsichtsbehörde | 72 Stunden |
| Hohes Risiko für Betroffene | An Betroffenen | Unverzüglich |
| Verarbeitungsverzeichnis | An Aufsichtsbehörde | Auf Verlangen |

---

## 8. Implementierung im Agenten

### 8a. check-gdpr-Skill
- Prüft vor jedem Match: Datenherkunft, Einwilligung, Speicherort
- Erstellt DSGVO-Report für jeden Match
- Bei Verstoß: Match wird nicht fortgesetzt

### 8b. Automatische Löschung
- Cron-Job: Täglich prüfen, ob Daten älter als 6 Monate
- Löschung: Vollständig + Protokollierung
- Ausnahme: Compliance-Daten (36 Monate Pflicht)

### 8c. Audit-Log
- Jede Verarbeitung wird protokolliert
- Log-Datei: `logs/agent-errors.log`
- Aufbewahrung: 36 Monate

---

## 9. Verantwortlichkeit

| Rolle | Verantwortlichkeit |
|---|---|
| **Verantwortlicher** | Das Unternehmen, das die Stelle ausschreibt |
| **Auftragsverarbeiter** | KM-HR-Agent (nur auf Weisung) |
| **Datenschutzbeauftragter** | Benannt (falls Pflicht) |
| **Kandidat** | Betroffene Person mit Rechten |

---

## 10. Checkliste für jede Verarbeitung

- [ ] Rechtsgrundlage festgelegt (Art. 6)
- [ ] Einwilligung eingeholt (bei Drittendaten)
- [ ] Informationspflicht erfüllt (Art. 13–14)
- [ ] Verzeichnis der Verarbeitungstätigkeiten aktualisiert (Art. 30)
- [ ] Technische Maßnahmen implementiert (Art. 32)
- [ ] Speicherfrist definiert und umgesetzt
- [ ] Betroffenenrechte sichergestellt (Art. 15–22)
- [ ] Internationale Übermittlung geprüft (Art. 44–49)
- [ ] Meldepflichten beachtet (Art. 33–34)

---

*Erstellt am 10.09.2026 für den KM-HR-Agenten.*
