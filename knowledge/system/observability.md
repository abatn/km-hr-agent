# Observability (Health, Circuit-Breaker, Lern-Loop, Audit)

> **Stand:** 02.11.2026 · **Art:** normative Spec (MD-first, keine Code-Änderung in diesem Dokument)
> **Geltung:** verbindlich für Betrieb, Deployment und Tests. Bei Konflikt gilt diese Spec; bei Konflikt mit dem Code wird entschieden und in `ergebnisse/entscheidungen.md` protokolliert (`knowledge/system/doku-authority.md`).
> **Quellenpflicht:** Jede Zahl trägt eine externe Quelle **oder** die Kennzeichnung **Design-Entscheidung** (Lab-Prinzip 1, `CONTRIBUTING.md`).

---

## 0. Zweck

Das System beobachtet sich selbst in vier Schichten:

| Schicht | Frage | Antwort im Code |
|---|---|---|
| **Health** | Läuft die Anlage? | `webui/main.py::healthz` → `webui/db.py::health_snapshot` |
| **Resilienz** | Was passiert bei Ausfall? | `webui/circuit_breaker.py`, `webui/db.py::enable_wal` |
| **Lernen** | Lernt es aus Menschen? | `webui/logic.py::record_hr_decision` |
| **Gedächtnis** | Ist die Vergangenheit unbestechlich? | `webui/db.py::append_audit` / `verify_audit_chain` |

Der Beobachter ist **deterministisch** (SQL, Hash, PID, HTTP) — nicht das LLM. Ein Modell, das sich selbst bewertet, wäre nicht falsifizierbar; ein Hash-Wächter ist es.

---

## 1. Health-Endpunkt `/healthz`

**Codemarke:** `def healthz` (`webui/main.py`), `def health_snapshot` (`webui/db.py`).

- **Route:** `GET /healthz`, ohne Login (Monitoring muss anonym prüfen können).
- **Antwort:** JSON mit `status`, `timestamp`, `db`, `queue`, `runner`, `audit`.
- **HTTP-Code:** `200` bei `ok` und `degraded`; `503` nur, wenn die DB nicht erreichbar ist. Begründung: Ein toter Runner oder ein einzelner fehlgeschlagener Task soll die Erreichbarkeit der Web-App nicht als „down" melden (Alarmierung trennt App- und Runner-Ebene).
- **DB-Prüfung:** `SELECT 1` + Tabellenzahl + `PRAGMA journal_mode` mit **2 s** Timeout (Design-Entscheidung: kurz genug für einen Health-Check, lang genug für einen belegten Schreibvorgang).
- **Queue:** Zähler je Status, `failed_last_hour`, `pending_older_1h` (Fenster **1 h**, Design-Entscheidung).
- **Runner:** liest `data/agent-runner.pid`, prüft per `os.kill(pid, 0)`.
- **Audit:** `verify_audit_chain()` — `ok` nur bei intakter Kette.

**Statuslogik:**

```
db.ok == False                               → status = "error"   (HTTP 503)
runner.alive == False
  OR queue.failed_last_hour > 0
  OR audit.ok == False                       → status = "degraded" (HTTP 200)
sonst                                        → status = "ok"       (HTTP 200)
```

**Sicherheit:** Der Endpunkt gibt **keine** personenbezogenen Daten aus — nur Zähler, Status und Zeitstempel.

---

## 2. SQLite-Homöostase (WAL + Wartezeit)

**Codemarken:** `def get_conn`, `def enable_wal`, `def queue_health` (`webui/db.py`).

| Maßnahme | Wert | Quelle |
|---|---|---|
| `busy_timeout` | **10 000 ms** | SQLite-Doku „PRAGMA busy_timeout": Wartezeit statt sofortigem `SQLITE_BUSY` |
| `journal_mode` | **WAL** | SQLite-Doku „Write-Ahead Logging": Leser blockieren Schreiber nicht |
| `synchronous` | **NORMAL** | SQLite-Doku „PRAGMA synchronous": übliche WAL-Begleiteinstellung |
| Verbindungs-Timeout | **10 s** | Design-Entscheidung (identisch zu `busy_timeout`) |

- `enable_wal()` läuft **einmal beim App-Start** (`webui/main.py`, nach `app_bootstrap()`); WAL ist eine persistente Datei-Eigenschaft.
- `get_conn()` setzt `timeout` + `busy_timeout` für **jede** Verbindung. Vorher hatten nur 3 von 60 Verbindungen eine Wartezeit (Messung 02.11.2026, `grep` in `webui/` + `scripts/`).
- **Grenze:** WAL hilft gegen Leser/Schreiber-Konflikte, nicht gegen zwei gleichzeitige Schreiber mit langen Transaktionen. Ein `database is locked` bleibt möglich; es wird dann als `failed`/`error` sichtbar, nicht still verschluckt.

---

## 3. Circuit-Breaker (LLM)

**Codemarken:** `class CircuitBreaker` (`webui/circuit_breaker.py`), `_llm_complete` (`scripts/agent-runner.py`).

| Parameter | Wert | Quelle |
|---|---|---|
| Fehlerschwelle | **2** | Design-Entscheidung; per `KMHR_CB_THRESHOLD` übersteuerbar |
| Cooldown | **300 s** | Design-Entscheidung; per `KMHR_CB_COOLDOWN` übersteuerbar |
| Verbindungs-Timeout | **10 s** | Design-Entscheidung (schneller Failover) |
| Lese-Timeout | **600 s** (kimi-k3: 120 s) | bestehende Modellkette, `knowledge/system/agent-automation.md` |
| Versuche pro Modell | **3** | bestehende Spec |

**Zustände:** `closed` → `open` (nach Schwelle) → `half_open` (nach Cooldown) → `closed` (nach Erfolg).

**Wirkung:** Ist ein Modell offen, wird es **sofort übersprungen** (kein 600-s-Timeout). Der Runner versucht das nächste Modell der Kette. Ein unerreichbarer Provider scheitert durch den 10-s-Connect-Timeout, nicht erst nach 10 Minuten.

**Falsifikation:** `tests/test_circuit_breaker.py` (Zustände, Cooldown, Reset) und der Live-Log-Marker `Circuit-Breaker offen`.

---

## 4. Lern-Loop (Business-Beobachter)

**Codemarken:** `def record_hr_decision`, `def last_match_score` (`webui/logic.py`), `def get_learning_stats` (`webui/db.py`).

Jeder menschliche HR-Klick an den sechs Entscheidungsstellen (Match-Dialog, Stellen-Seite, Einladungs-Seite, Hiring-Board) erzeugt Feedback:

| HR-Entscheidung | Feedback | Wirkung |
|---|---|---|
| `eingeladen` / `einstellt` | `Ja` | Score ≥ 80 → `erfahrung` **+5** |
| `abgelehnt` | `Nein` | Score < 70 → `sprache` **+10** |
| sonst | — | kein Eintrag |

- **Score-Quelle:** letzter `match_candidate`-Task (`result_json`, Feld `text` mit „Match-Score: N"); fehlt er, wird **60** verwendet (Design-Entscheidung: neutral, damit der Regler nichts erfindet).
- **Schwellen 80/70:** Design-Entscheidung ohne externe Quelle (bereits in `knowledge/lifecycle/matching-criteria.md` so geführt).
- **Persistenz:** `gewichtung_historie` (eine Zeile je Anpassung; `grund = hr_entscheidung:<status>:<actor>`).
- **Cap + Normierung:** unverändert `GEWICHT_CAP_ABWEICHUNG = 15`, Summe 100 (`webui/logic.py`).
- **Dashboard:** Admin-Karte „Lern-Dashboard (30 Tage)" (**30 Tage** = Design-Entscheidung) mit Entscheidungen, Anpassungen und letzten Änderungen.

**Ehrlichkeit:** Ohne HR-Entscheidungen bleibt die Historie leer; das Dashboard sagt das ausdrücklich. Es gibt keine simulierten Lernfortschritte.

---

## 5. Audit-Kette (unbestechliches Gedächtnis)

**Codemarken:** `init_audit_log_table`, `append_audit`, `verify_audit_chain`, `get_audit_stats` (`webui/db.py`).

**Schema `audit_log`:** `ts`, `actor_role`, `actor_id`, `action`, `application_id`, `candidate_id`, `job_id`, `prev_status`, `new_status`, `payload`, `prev_hash`, `entry_hash`, `signature`.

**Kette:**

```
entry      = {ts, actor_role, actor_id, action, application_id,
              candidate_id, job_id, prev_status, new_status, payload}
canonical  = JSON(entry, sort_keys=True, ensure_ascii=False)
entry_hash = SHA-256(prev_hash + "|" + canonical)
signature  = HMAC-SHA256(KMHR_AUDIT_SECRET, entry_hash)
```

- **Append-only:** Der Code führt kein `UPDATE`/`DELETE` auf `audit_log` aus. Ein Test prüft die Kette; eine nachträgliche Änderung liefert `broken_id`.
- **Secret:** `KMHR_AUDIT_SECRET` ist **Pflicht**. Ohne Secret verweigert `_audit_secret()` die Signatur (`RuntimeError`) — **fail-closed**. Es gibt **keinen** Entwicklungs-Default mehr.
- **Start-Gate:** `webui/main.py` prüft `KMHR_AUDIT_SECRET` zusammen mit den beiden übrigen Pflicht-Secrets; ohne `KMHR_DEV=1` startet die App nicht (`SystemExit(1)`). `KMHR_DEV=1` erlaubt den Entwicklungsstart, aber **Audit-Schreibvorgänge bleiben fail-closed**, solange kein Secret gesetzt ist.
- **Grenze (ehrlich):** Die Kette erkennt Änderungen **innerhalb** der Tabelle. Ein vollständiges Löschen der Tabelle oder das Abschneiden des Endes ist ohne externen Anker nicht erkennbar. Empfehlung: tägliches Backup + `verify_audit_chain` im Health-Check (bereits implementiert).

**Threat Model:**

| Angriff | Wirkung |
|---|---|
| Direktes `UPDATE` auf einen Eintrag | Kette bricht → `/healthz` `degraded`, Admin-Karte „GEBROCHEN" |
| Direktes `INSERT` mit falschem `prev_hash` | Kette bricht |
| Löschen des letzten Eintrags | **nicht** durch die Kette erkannt (Ende fehlt) → Backup/Anker nötig |
| Fremdes Secret | Signatur ungültig → Kette bricht |

---

## 6. Alerting (Uptime-Check)

**Codemarke:** `scripts/healthcheck.py`; Units `deploy/systemd/kmhr-healthcheck.{service,timer}`; Cron-Alternative `deploy/cron/kmhr-healthcheck.cron`.

| Parameter | Wert | Quelle |
|---|---|---|
| Intervall | **30 s** | Design-Entscheidung (Anforderung: „alle 30 s") |
| HTTP-Timeout | **10 s** | Design-Entscheidung |
| Alarm-Wiederholung | **1800 s** | Design-Entscheidung (verhindert Alarm-Flut) |
| Alarm bei | HTTP ≠ 200 **oder** `status != "ok"` | Anforderung |

**Ablauf:**

1. `GET https://jobs.hanibal-ai.com/healthz` (per `KMHR_HEALTH_URL` übersteuerbar).
2. JSON parsen; `status`, `db.ok`, `runner.alive`, `audit.ok` prüfen.
3. **OK:** eine Zeile `OK` ins Log (`logs/healthcheck.log`), Exit 0.
4. **Alarm:** Log-Zeile `ALARM` (Benachrichtigung) bzw. `STILL` (weiterhin
   kaputt, aber innerhalb des Dedupe-Fensters), optional Webhook
   (`KMHR_ALERT_WEBHOOK`, JSON-POST) und optional E-Mail
   (`KMHR_ALERT_EMAIL` + SMTP-Daten aus `.env-email`), Exit 1.
5. **Dedupe:** Zustandsdatei `logs/healthcheck-state.json`; derselbe Fehler wird höchstens alle 1800 s erneut gemeldet.

**Installation (VPS):**

```bash
cp deploy/systemd/kmhr-healthcheck.service /etc/systemd/system/
cp deploy/systemd/kmhr-healthcheck.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now kmhr-healthcheck.timer
```

**Cron-Alternative** (wenn kein systemd): zwei Zeilen pro Minute (`sleep 0` und `sleep 30`) — siehe `deploy/cron/kmhr-healthcheck.cron`.

---

## 7. Falsifikation (Tests + Befehle)

| Vorhersage | Test / Befehl |
|---|---|
| Kette erkennt Manipulation | `pytest tests/test_audit_chain.py` |
| Ohne Secret keine Signatur | `pytest tests/test_audit_secret_failclosed.py` |
| Breaker öffnet/schließt korrekt | `pytest tests/test_circuit_breaker.py` |
| HR-Entscheidung schreibt Historie | `pytest tests/test_learning_loop.py` |
| `/healthz` meldet DB/Queue/Audit | `pytest tests/test_healthcheck.py` (Evaluator) + Live-`curl` |
| WAL ist aktiv | `sqlite3 data/feedback.db "PRAGMA journal_mode;"` → `wal` |
| Schema exakt | `python3 scripts/ci/checks.py schema` → 21 Tabellen |

**5 Wege, dieses Verständnis zu widerlegen:**

1. Ein Codepfad ruft `queue_agent_task("create_invitation")` ohne `trigger`-Whitelist auf.
2. Ein `UPDATE` auf `audit_log` bleibt von `verify_audit_chain()` unentdeckt.
3. Zwei parallele Schreiber erzeugen trotz WAL ein `database is locked`, das nicht als `failed` sichtbar wird.
4. Der Health-Check meldet `ok`, obwohl der Runner seit Stunden tot ist.
5. Eine HR-Entscheidung erzeugt keine `gewichtung_historie`-Zeile (Lern-Loop tot).

---

## 8. Betrieb (Env-Variablen)

| Variable | Pflicht | Zweck |
|---|---|---|
| `KMHR_AUDIT_SECRET` | **ja** (fail-closed) | HMAC-Schlüssel der Audit-Kette |
| `KMHR_CB_THRESHOLD` | nein (2) | Fehlerschwelle des Circuit-Breakers |
| `KMHR_CB_COOLDOWN` | nein (300) | Cooldown in Sekunden |
| `KMHR_HEALTH_URL` | nein | Ziel des Uptime-Checks |
| `KMHR_ALERT_WEBHOOK` | nein | JSON-POST bei Alarm |
| `KMHR_ALERT_EMAIL` | nein | E-Mail-Empfänger bei Alarm |
| `KMHR_ALERT_REPEAT` | nein (1800) | Alarm-Wiederholung in Sekunden |

**Sicherheit:** `.env` ist in `.gitignore` (`\.env\*`), Vorlage ist `.env.example`. `chmod 600` ist Pflicht.

---

## 9. Nicht-Ziele / Grenzen

- Kein APM, kein Tracing, keine Metrik-Zeitreihen (bewusst: SQLite + Logs statt zusätzlicher Infrastruktur).
- Kein automatisches Rollback bei fehlgeschlagenem Deploy (bestehende Grenze, `knowledge/system/deploy-pipeline.md`).
- Kein Lösch-Schutz gegen einen Angreifer mit Root-Zugriff; die Kette ist ein **Manipulations-Detektor**, kein SSP.
- Der Health-Check ersetzt **kein** externes Monitoring (Cloudflare/UptimeRobot); er ist die Alarmquelle, die auf `/healthz` zeigt.
