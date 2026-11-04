# Cron-Plan: automatisierte Job-Akquise

**Code:** `run_all.sh` · **Systemd:** `deploy/systemd/kmhr-jobs.{service,timer}` ·
**Crontab:** `deploy/cron/kmhr-jobs.cron` · **Logs:** `logs/jobs-agent-<datum>.log`

## Zeitplan

| Feld | Wert |
|---|---|
| Laufzeit | **täglich 06:00** (Europe/Berlin) |
| Streuung | `RandomizedDelaySec=300` (0–5 Min), damit nicht alle Instanzen gleichzeitig starten |
| Verpasste Läufe | `Persistent=true` (holt den Lauf nach einem Neustart nach) |
| Laufzeit-Budget | `TimeoutStartSec=3600` (1 h) |
| Priorität | `Nice=10`, `IOSchedulingClass=idle` |

## Was läuft

`run_all.sh` führt in dieser Reihenfolge aus:

1. `jobs_api.py` (BA, DE) – 12 Stellen
2. `jobs_ch.py` (Job-Room, CH) – 8
3. `jobs_eures.py` (EURES, DE/FR/CH) – 12
4. `jobs_lhr.py` (LHR, FR Hotellerie) – 6
5. `jobs_jdp.py` (Journal des Palaces RSS, FR) – 4
6. `jobs_recipients.py` (Empfängerliste + Entwürfe)
   - alte `outbox/final/*.eml` → `outbox/backup-<Zeitstempel>/`
   - Backups älter als 1 Tag löschen
   - Outbox leeren, gesperrte Firma+Anzeige (`jobs/ansprache.jsonl`) überspringen
7. optional `jobs_enrich.py` (Impressum-Recherche, `JOBS_ENRICH=1`)
8. `jobs_recipients.py --prepare-only` (Entwürfe/Formularnachrichten aktualisieren;
   **kein** Backup, **kein** Leeren)
9. `jobs_induce.py induce` / `transfer` / `forms` (Skill-Lattice)

**Es wird nie automatisch eine E-Mail versendet.** Der Versand ist ein separater
manueller Schritt (`scripts/jobs_mail.py --send --yes`).

## Rate-Limits und Schutz

| Quelle | Verhalten im Agenten |
|---|---|
| Bundesagentur (DE) | max. 25 Treffer/Suche, 0,2 s Pause zwischen Detail-Calls |
| Job-Room (CH) | 50 Treffer/Seite, 0,2 s Pause, nur öffentliche `_search` |
| EURES | 20 Treffer/Abfrage, 0,2 s Pause |
| LHR (FR) | 1 Request/s, max. 6 Métiers |
| Journal des Palaces | **1 RSS-Abruf pro Lauf** (1 MB) |
| Kontakt-Recherche | 0,7 s pro Request, max. 3 Domains × 4 Seiten je Arbeitgeber |

## Ruhezeiten (E-Mail)

`scripts/jobs_mail.py` verweigert den Versand **vor 08:00 und ab 20:00 Uhr**
(`--force` überschreibt nur bewusst). Der Cron-Job versendet ohnehin nicht.

## Log-Rotation

- `deploy/logrotate/kmhr-jobs` → täglich, 14 Archive, komprimiert, `copytruncate`.
- `run_all.sh` löscht zusätzlich `logs/jobs-agent-*.log`, die älter als 14 Tage sind.
- Installation: `install -m 644 deploy/logrotate/kmhr-jobs /etc/logrotate.d/kmhr-jobs`

## Installation

```sh
# systemd (empfohlen)
install -m 644 deploy/systemd/kmhr-jobs.service deploy/systemd/kmhr-jobs.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now kmhr-jobs.timer
systemctl list-timers kmhr-jobs.timer

# oder crontab
crontab -u root deploy/cron/kmhr-jobs.cron
```

## Voraussetzungen (Umgebungsvariablen)

| Variable | Pflicht | Zweck |
|---|---|---|
| `FT_CLIENT_ID` / `FT_CLIENT_SECRET` | optional | France Travail (nur mit API-Abo) |
| `JOBS_DE` / `JOBS_CH` / `JOBS_EURES` / `JOBS_LHR` / `JOBS_JDP` | optional | Stellenobergrenzen |
| `JOBS_ENRICH` | optional | `1` = Impressum-Recherche |
| `.env-runner` | empfohlen | wird von `run_all.sh` geladen |

## Beweislauf

```sh
./run_all.sh --quick
```

Erzeugt Belege, Empfängerliste, Entwürfe und die Skill-Lattice; Log unter
`logs/jobs-agent-<datum>.log`.

## Test-Versand (01.11.2026) – Status: erfolgreich

| # | Land | Arbeitgeber | Stelle | Empfänger (Test) | Betreff | Zeit (UTC) | Status |
|---|---|---|---|---|---|---|---|
| 1 | DE | Permacon GmbH | Pflegefachkraft (m/w/d) | batniniabdelkader@yahoo.com | [TEST] Bewerbungsanfrage – Permacon GmbH – Pflegefachkraft (m/w/d) | 23:43:09 | **delivered** |
| 2 | CH | Concordia | Gesundheitsberater:in Telemedizin | batniniabdelkader@yahoo.com | [TEST] Bewerbungsanfrage – Concordia – Gesundheitsberater:in Telemedizin | 23:43:05 | **delivered** |
| 3 | FR | Association ALHPI | Infirmier / Infirmière en soins généraux (IDE) | batniniabdelkader@yahoo.com | [TEST] Bewerbungsanfrage – Association ALHPI – Infirmier / Infirmière … | 23:43:15 | **delivered** |

**Belege:**
- Sende-Log: `jobs/outbox/testversand/versand-004259.md` (3/3 OK)
- Mailtrap-Log: 3× `delivered` (plus je 1 Auto-BCC-Kopie)
- Entwürfe: `jobs/outbox/testversand/*.eml`

**Ruhezeit:** Der Test lief um 00:42 Uhr. Die Regel 08:00–20:00 gilt für
**echte Empfänger**; ein Testversand an die eigene Adresse (`--to`) ist
ausgenommen und im Code dokumentiert.

## Timer aktivieren (nach erfolgreichem Test)

```sh
systemctl daemon-reload
systemctl enable --now kmhr-jobs.timer
systemctl list-timers kmhr-jobs.timer --no-pager
```

**Neustart-fest:** `enable` legt den Symlink in `timers.target.wants`;
`Persistent=true` holt einen verpassten Lauf nach. Nach einem Reboot startet
der Timer automatisch.

## Pausieren / stoppen

```sh
systemctl stop kmhr-jobs.timer          # sofort pausieren
systemctl disable kmhr-jobs.timer       # dauerhaft aus (nach Reboot aus)
systemctl mask kmhr-jobs.timer          # hart sperren (auch gegen Handstart)
systemctl start kmhr-jobs.service       # Einzellauf jetzt
```

**E-Mail-Versand stoppen:** Es gibt keinen automatischen Versand. Ein laufender
manueller Versand lässt sich mit `pkill -f jobs_mail.py` abbrechen; dauerhaft
verhindern, indem `--send` nicht aufgerufen wird (Cron tut das nie).

## Versandregeln

1. Nur 08:00–20:00 Uhr (Europe/Berlin); Code verweigert sonst (`--force` nur bewusst).
2. Jede Mail enthält `Abmelden` / `Unsubscribe` / `Désabonner`.
3. Ein Empfänger = eine Mail (Dedupe); maximal `--limit` pro Lauf.
4. Kein automatischer Versand im Cron; echte Arbeitgeber nur mit `--allow-real`.
5. Nach erfolgreichem Versand wird `Firma + Anzeige` in `jobs/ansprache.jsonl`
   gesperrt; dieselbe Kombination wird nie wieder angeschrieben, eine neue
   Anzeige derselben Firma schon. Dry-Run und `--to` schreiben nichts.
