# Export-Templates

PDF-Vorlagen werden zur Laufzeit generiert (nicht aus Dateien geladen).
Dieses Verzeichnis dient als Platzhalter für manuelle Vorlagen.

## Verfügbare Formate
- PDF (via aspose-pdf-foss-mcp)
- Excel (via excel-mcp)

## Platzhalter
- `{{KANDIDAT_NAME}}` - Name des Kandidaten
- `{{STELLE}}` - Positionsbezeichnung
- `{{SCORE}}` - Match-Score (0-100)
- `{{BEGRUENDUNG}}` - Detaillierte Begründung
- `{{STAERKEN}}` - Top-3 Stärken
- `{{LUECKEN}}` - Offene Fragen/Lücken
- `{{COMPLIANCE_STATUS}}` - Compliance-Status (COMPLIANT/NON-COMPLIANT)
- `{{KULTUR_FIT}}` - Kultur-Fit-Score
