# Benachrichtigungs-Log

> **Stand:** 20.09.2026 (Datei repariert: vorher 1 Zeile mit literalen `\n` — Formatfehler eines früheren Schreibvorgangs)

Schema: | Datum | Typ | Empfänger | Betreff | Status |

Quelle: knowledge/system/agent-automation.md § E-Mail-Matrix (7 Mail-Typen)

> **UI-Verhalten der Glocke (17.10.2026):** Der Benachrichtigungs-Drawer (Header-Glocke) ist nach dem Login **immer geschlossen** (`ui.right_drawer(value=False, fixed=False)`, Codemark `notifications_drawer`) und öffnet **nur per Klick auf die Glocke**. Ohne Klick sichtbar ist nur die Badge-Zahl (`badge.set_visibility(unread > 0)`). Grund (gemessen 17.10.2026): ohne `value` setzte der NiceGUI-Default `None` Quasars `show-if-above` — der Drawer stand ab Layoutbreite 1024 px automatisch offen (Messreihe `/tmp/opencode/bell-*.png`, 10/10; 1000 px zu / 1025 px offen).

> **Nachtrag (17.10.2026):** (a) Der Markieren-Button heißt **„Alle Benachrichtigungen löschen"** und **löscht** beim Klick die Zeilen (`db.delete_notifications`, Codemark `notifications_drawer::_mark_read`) statt sie auf `gelesen=1` zu setzen — der Drawer-Inhalt refresht zu „Keine Benachrichtigungen", die Header-Badge fällt auf 0/verschwindet (ohne Seiten-Reload), Toast „Alle Benachrichtigungen gelöscht". (b) Die Zeilensprache wird **zur Renderzeit** in der Leser-Sprache aufgelöst: `titel/nachricht` kommen aus den Spalten `msg_key`/`params` per `tr(f"{msg_key}.titel", lang)` bzw. `tr(f"{msg_key}.text", lang, **params)` (Codemark `notifications_drawer`), der `status`-Param wird vor dem Format per `status_label` übersetzt; **Altbestand** mit `msg_key`/`params` NULL bleibt unverändert verbatim aus `titel`/`nachricht`. (c) DSGVO-Retention: ungelesene notifications-Zeilen älter als **183 Tage** (6 Monate) werden beim Aufräumen gelöscht (Codemark `dsgvo_cleanup`/`DSGVO_FRIST_TAGE` in `webui/logic.py`, Spec `knowledge/legal/gdpr-policy.md`).

## Log-Einträge

| Datum | Typ | Empfänger | Betreff | Status |
|---|---|---|---|---|
