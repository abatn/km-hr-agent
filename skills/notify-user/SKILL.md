---
description: Versendet Benachrichtigungen bei Top-Matches per E-Mail oder Slack
---

## Input
- Match-Ergebnis (Score, Kandidat, Stelle)
- Benachrichtigungskanal (E-Mail, Slack, oder beide)
- Empfänger (E-Mail-Adresse, Slack-Channel)

## Schritte

### 1. Benachrichtigungs-Trigger prüfe

| Bedingung | Aktion |
|---|---|
| Score ≥ 90 | **SOFORT** benachrichtigen |
| Score 80–89 | **SOFT** benachrichtigen |
| Score < 80 | Keine Benachrichtigung |

### 2. Benachrichtigungstyp festlegen

#### 📧 E-Mail-Benachrichtigung
```
Betreff: 🎯 Top-Match: [Kandidat] × [Stelle] (Score: [X]/100)

Hallo [Empfänger],

ein neuer Top-Match wurde gefunden:

Kandidat: [Name]
Stelle: [Position] bei [Unternehmen]
Score: [X]/100 ([Kategorie])

Top-3 Stärken:
1. [Stärke]
2. [Stärke]
3. [Stärke]

Nächste Schritte:
- [ ] Kandidaten anrufen
- [ ] Vorstellungsgespräch planen
- [ ] Referenzen einholen

Vollständiger Bericht: [Link/Pfad]

---
KM-HR-Agent v3.0 | Automatische Benachrichtigung
```

#### 💬 Slack-Benachrichtigung
```json
{
  "channel": "#recruiting",
  "blocks": [
    {
      "type": "header",
      "text": "🎯 Top-Match gefunden!"
    },
    {
      "type": "section",
      "fields": [
        {"type": "mrkdwn", "text": "*Kandidat:*\n[Name]"},
        {"type": "mrkdwn", "text": "*Stelle:*\n[Position]"},
        {"type": "mrkdwn", "text": "*Score:*\n[X]/100"},
        {"type": "mrkdwn", "text": "*Kategorie:*\n[Kategorie]"}
      ]
    },
    {
      "type": "section",
      "text": "*Top-3 Stärken:*\n1. [Stärke]\n2. [Stärke]\n3. [Stärke]"
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": {"type": "plain_text", "text": "Vollständigen Bericht ansehen"},
          "url": "[Link]"
        }
      ]
    }
  ]
}
```

### 3. Benachrichtigung versenden

#### Via E-Mail (MCP-Connector):
- Nutze `email-mcp` oder `smtp-connector`
- Parameter: to, subject, body, attachment (optional)

#### Via Slack (MCP-Connector):
- Nutze `slack-mcp` oder `slack-webhook`
- Parameter: channel, blocks/message

### 4. Protokollierung

Speichere Benachrichtigung in `knowledge/notification-log.md`:
```markdown
| Datum | Kandidat | Stelle | Score | Kanal | Empfänger | Status |
|---|---|---|---|---|---|---|
| 2026-09-10 | Julian Bergmann | DevOps Engineer | 100 | E-Mail | hr@firma.de | ✅ Gesendet |
```

### 5. Rückgabe
- Gib Status der Benachrichtigung zurück (Gesendet/Fehlgeschlagen)
- Gib Protokoll-Eintrag zurück
