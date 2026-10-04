---
description: Extrahiert ein strukturiertes Profil aus einem Lebenslauf (PDF/TXT/MD)
---

## Verfügbare Tools

| Tool | Typ | Zweck |
|---|---|---|
| `pdf-reader` | MCP (local) | PDF-Text extrahieren (PyMuPDF, kein OCR nötig) |
| `filesystem` | MCP (local) | TXT/MD lesen/schreiben |

## Zugriff (v4.3, `knowledge/system/access-control.md`)

- Nur EMPLOYER/HR-Sessions. CANDIDATE-Sessions laden ihren CV über 📤 Upload (eigene-Datei-Bindung) bzw. Candidate Portal.
- **Anonymisierte Anzeige (NEU):** Das UI zeigt extrahierte Profile als Pseudonym „Kandidat #N" OHNE Namen und OHNE Kontaktdaten (E-Mail, Telefon, Adresse). Die Rohdaten werden regulär gespeichert; Namens-/Kontaktanzeige wird erst durch die Einladungs-Freigabe der Phase-1-Logik freigeschaltet (Konsistenz mit Employer-Portal-DSGVO-Regeln).

## Regime: Vollständig lokal – keine externen APIs

## Schritte

### 1. Lebenslauf einlesen

#### A) PDF-Datei → pdf-reader MCP
- **Connector:** `pdf-reader`
- **Tool:** `read_pdf_text`
- **Parameter:** `file_path` = Pfad zur PDF-Datei
- **Beispiel:**
  ```json
  {
    "name": "read_pdf_text",
    "arguments": {
      "file_path": "/home/batnini/mimo-agents/km-hr-agent/Lebenslauf-Batnini.pdf"
    }
  }
  ```
- **Antwort:** `OK|4|3699\n--- Seite 1 ---\nAbdelkader\nBatnini...`

#### B) TXT/MD-Datei → filesystem MCP
- **Connector:** `filesystem`
- **Tool:** `read_text_file`
- **Parameter:** `path` = absoluter Pfad zur TXT/MD-Datei
- **Beispiel:**
  ```json
  {
    "name": "read_text_file",
    "arguments": {
      "path": "/home/batnini/mimo-agents/km-hr-agent/testdaten/lebenslauf-anna-schuster.txt"
    }
  }
  ```

### 2. Strukturierung – Extrahiere folgende Felder

- **Name** (aus Kopfzeile)
- **E-Mail** (aus Kontaktdaten)
- **Telefon** (aus Kontaktdaten)
- **Standort** (aus Kontaktdaten)
- **Berufserfahrung** (Positionen, Unternehmen, Zeiträume, Beschreibungen)
- **Bildung** (Abschlüsse, Hochschulen, Jahrgänge)
- **Hard Skills** (Technologien, Zertifikate)
- **Soft Skills** (Führung, Kommunikation, Teamfähigkeit)
- **Sprachen** (Muttersprache, fließend, Grundkenntnisse)

### 3. Normalisierung

- Einheitliches Datumformat: `YYYY` oder `YYYY-MM`
- Erfahrungsformat: `Position | Unternehmen | Zeitraum | Beschreibung`
- Skill-Format: `Kategorie: Skill`

### 4. Validierung

- Prüfe ob Name vorhanden ist
- Prüfe ob mindestens 1 Berufserfahrung vorhanden ist
- Bei fehlenden Feldern: `[FEHLT]`-Marker setzen

### 5. Speichern

- **Connector:** `filesystem`
- **Tool:** `write_file`
- **Pfad:** `~/mimo-agents/km-hr-agent/testdaten/profil-[name].md`

### 6. Rückgabe

- Gib strukturiertes Profil als Text zurück

---

## Beispiel-Aufrufe

### PDF lesen (pdf-reader MCP)
```json
{
  "name": "read_pdf_text",
  "arguments": {
    "file_path": "/home/batnini/mimo-agents/km-hr-agent/Lebenslauf-Batnini.pdf"
  }
}
```

### TXT lesen (filesystem MCP)
```json
{
  "name": "read_text_file",
  "arguments": {
    "path": "/home/batnini/mimo-agents/km-hr-agent/testdaten/lebenslauf-anna-schuster.txt"
  }
}
```

### Ergebnis speichern (filesystem MCP)
```json
{
  "name": "write_file",
  "arguments": {
    "path": "/home/batnini/mimo-agents/km-hr-agent/testdaten/profil-name.md",
    "content": "# Profil – Name\n\n..."
  }
}
```
