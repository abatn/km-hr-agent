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

#### Via E-Mail (Ist-Implementierung):
- Nutze **`email-sender`** (MCP, in `opencode.json`) → Tool `send_email`
- Parameter: to, subject, body, attachment (optional)
- Ausführung im Runner: `scripts/agent-runner.py` (`mcp_call(EMAIL_SERVER, …)`), nie SMTP in der App
- ❌ ~~`email-mcp` / `smtp-connector`~~ existieren **nicht** (0 Treffer, Tool-Namen-Pflicht `knowledge/system/mcp-connector-config.md`)

#### Via Slack: **nicht umgesetzt** (Design-Entscheidung, Stand 08.10.2026)
- ❌ ~~`slack-mcp` / `slack-webhook`~~ — **kein Slack im Projekt** (0 Treffer in `opencode.json` + Code)
- Kanäle im Projekt: E-Mail (Pflicht) + Portal-Benachrichtigung (`notifications`-Tabelle, `webui/db.py`)

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
