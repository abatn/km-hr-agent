# Benachrichtigungs-Log

> **Stand:** 20.09.2026 (Datei repariert: vorher 1 Zeile mit literalen `\n` — Formatfehler eines früheren Schreibvorgangs)

Schema: | Datum | Typ | Empfänger | Betreff | Status |

Quelle: knowledge/system/agent-automation.md § E-Mail-Matrix (6 Mail-Typen)

> **UI-Verhalten der Glocke (17.10.2026):** Der Benachrichtigungs-Drawer (Header-Glocke) ist nach dem Login **immer geschlossen** (`ui.right_drawer(value=False, fixed=False)`, Codemark `notifications_drawer`) und öffnet **nur per Klick auf die Glocke**. Ohne Klick sichtbar ist nur die Badge-Zahl (`badge.set_visibility(unread > 0)`). Grund (gemessen 17.10.2026): ohne `value` setzte der NiceGUI-Default `None` Quasars `show-if-above` — der Drawer stand ab Layoutbreite 1024 px automatisch offen (Messreihe `/tmp/opencode/bell-*.png`, 10/10; 1000 px zu / 1025 px offen).

## Log-Einträge

| Datum | Typ | Empfänger | Betreff | Status |
|---|---|---|---|---|
