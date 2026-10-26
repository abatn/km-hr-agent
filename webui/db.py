"""
KM-HR-Agent – db.py (framework-unabhängiger Datenbank-Layer)
============================================================
Phase 0 der NiceGUI-Migration (ergebnisse/nicegui-phase-0.md).

Enthält NUR SQLite-Zugriff (18 Tabellen in data/feedback.db, inkl. consents).
Keine Streamlit- oder NiceGUI-Importe — von beiden Apps nutzbar.

Quelle der extrahierten Funktionen: app.py (Zeilen siehe
ergebnisse/nicegui-phase-0-bereinigung.md).
"""
from __future__ import annotations

import os
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
# Env-Override KMHR_DB_PATH (E2E-Isolation, 27.09.2026, tests/e2e_isolation.py):
# ohne Env unverändert data/feedback.db — ein zweiter Prozess kann damit auf
# einen Spiegel zeigen, ohne dass dieser Layer geändert werden muss.
DB_PATH = Path(os.environ.get("KMHR_DB_PATH") or (DATA_DIR / "feedback.db"))
AGENT_TASKS_DB = DB_PATH


def get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    """Neue SQLite-Verbindung (Zeilenweise Tupel, wie im Streamlit-Code üblich)."""
    return sqlite3.connect(str(db_path or DB_PATH))


# ─── Agent-Queue (Phase 5) ────────────────────────────────────────────

# Sprach-Transport-Hook (Variante B, P1 07.10.2026, Spec i18n-runner-chain.md §7.1):
# Die Portal-Schicht registriert hier einen Callable, der die Session-Sprache des
# Ausloesers liefert (webui/i18n.py: db.set_language_resolver(get_language)).
# Default None => kein `language` im Payload (Altbestand/Runner/Tests, Fallback de).
# Dieses Modul bleibt framework-frei (kein nicegui-Import).
_language_resolver = None


def set_language_resolver(fn) -> None:
    """Registriert den Session-Sprach-Resolver fuer `queue_agent_task`."""
    global _language_resolver
    _language_resolver = fn


def init_agent_tasks_table() -> None:
    """Legt die agent_tasks-Tabelle an (idempotent) + ergänzt fehlende Spalten.

    Paritätskopie zu `app.py` (Codemarke `init_agent_tasks_table`, Streamlit-Archiv).
    Ergänzung 21.10.2026: `CREATE TABLE IF NOT EXISTS` ändert eine **bestehende**
    Tabelle nicht — ein Altbestand ohne `started_at`/`finished_at`/`result_json`
    würde beim Runner-Claim (`scripts/agent-runner.py::claim_task`) mit
    `sqlite3.OperationalError` abbrechen (Endlosschleife „Loop-Fehler (Runner läuft
    weiter)").
    Die ALTERs sind idempotent (wie `init_notifications_table`,
    `init_candidates_migrations`) — belegt auf einer Kopie: 5 → 11 Spalten, Daten
    erhalten; auf Live- und Seed-DB ein No-op (Messung 21.10.2026).
    Migrationsweg dokumentiert in `knowledge/system/agent-automation.md`
    („Erweitertes Schema" + Abschnitt „5.1 Task-Status, DB-Pfad und
    Score-Fallback", Zeile „Schema-Migration ohne WebUI").
    """
    conn = sqlite3.connect(str(AGENT_TASKS_DB))
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS agent_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        payload TEXT NOT NULL,
        result_path TEXT,
        result_json TEXT,
        error_text TEXT,
        attempts INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        finished_at TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status)")
    # Idempotente Spalten-Ergänzung (Altbestand aus Hand-SQLite-Dateien).
    vorhanden = {r[1] for r in c.execute("PRAGMA table_info(agent_tasks)")}
    for spalte, typ in (("started_at", "TIMESTAMP"), ("finished_at", "TIMESTAMP"),
                        ("result_json", "TEXT"), ("result_path", "TEXT"),
                        ("error_text", "TEXT"), ("attempts", "INTEGER DEFAULT 0")):
        if spalte not in vorhanden:
            c.execute(f"ALTER TABLE agent_tasks ADD COLUMN {spalte} {typ}")
    conn.commit()
    conn.close()


def queue_agent_task(task_type: str, payload: dict) -> int | None:
    """Schreibt einen Agent-Task in die Queue (idempotent pro Tag+Typ+Applikation+Generation).
    Kopie aus app.py:445-477 (Streamlit-frei: kein st.*, nur print)."""
    try:
        conn = sqlite3.connect(str(AGENT_TASKS_DB))
        c = conn.cursor()
        # Sprach-Transport (Variante B, P1 07.10.2026, Spec i18n-runner-chain.md
        # §7.1): die Session-Sprache des Ausloesers zentral an JEDES Payload
        # haengen. Payload-Kopie — nie das uebergebene dict mutieren. Fehler oder
        # session-lose Kontexte (Runner/Tests) -> kein `language` (Fallback 'de').
        if _language_resolver is not None and "language" not in payload:
            try:
                _lang = _language_resolver()
            except Exception as ex:  # session-lose Kontexte -> Fallback 'de'
                print(f"[Agent-Queue] language-Resolver fehlgeschlagen: {ex!r}")
                _lang = None
            if isinstance(_lang, str) and _lang:
                payload = {**payload, "language": _lang}
        app_id = payload.get("application_id")
        # R3-2 (30.09.2026): Generation ist Teil der Dedupe-Grenze — dieselbe
        # Bewerbung kann nach Rückzug→„Erneut bewerben" am selben Tag eine
        # zweite Kette (gen = max+1) bekommen, obwohl Tasks desselben Typs
        # heute bereits existieren. Ohne diese Bedingung würde die neue Kette
        # von der alten geschluckt. Altbestand ohne gen-Feld → COALESCE 0,
        # das Dedupe-Verhalten für Bestandsdaten bleibt damit unverändert.
        gen = int(payload.get("gen", 0) or 0)
        # ZEITZONEN-FIX (22.10.2026): `created_at` wird von SQLite als **UTC**
        # gesetzt (CURRENT_TIMESTAMP), die Dedupe-Grenze lief aber ueber das
        # **lokale** Datum => im Fenster 00:00-02:00 (CEST) fielen die Zeilen
        # des heutigen Tages aus dem Filter (Doppel-Insert). Beide Seiten nutzen
        # jetzt UTC (Beleg: pytest-Lauf 22.10.2026 00:00 - 2 Fehlschlaege in
        # tests/test_r32_gatekeeper_gen.py + tests/test_runner_i18n.py).
        heute = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if app_id is not None:
            # P1-7 (30.09.2026): `payload LIKE '%"application_id": N%'` war UNSCHARF —
            # N=1 traf auch 10..19 (live belegt: 34 Fremd-Treffer, 0 eigene).
            # json_extract vergleicht den Zahlenwert exakt.
            c.execute("""SELECT id FROM agent_tasks
                WHERE task_type = ?
                  AND json_extract(payload, '$.application_id') = ?
                  AND COALESCE(json_extract(payload, '$.gen'), 0) = ?
                  AND created_at >= ?""",
                (task_type, app_id, gen, f"{heute} 00:00:00"))
            _dup = c.fetchone() is not None
        else:
            # Dedupe-Schutz (Variante B, P1 07.10.2026): `language` darf den
            # Payload-Vergleich NICHT beeinflussen — ein Alt-Task ohne `language`
            # muss den neuen mit `language` weiterhin als Duplikat erkennen (sonst
            # Doppel-Insert). Deshalb beide Seiten (Ziel-Payload + gespeicherte
            # Rows) ohne den Key via json.loads vergleichen. Semantik sonst
            # unveraendert (nur heutige Rows, Rückgabe None bei Duplikat).
            _ziel = json.dumps({k: v for k, v in payload.items() if k != "language"},
                               ensure_ascii=False, sort_keys=True)
            c.execute("""SELECT payload FROM agent_tasks
                WHERE task_type = ? AND created_at >= ?""",
                (task_type, f"{heute} 00:00:00"))
            _dup = False
            for (_gespeichert,) in c.fetchall():
                try:
                    _payload = json.loads(_gespeichert) if _gespeichert else {}
                except (TypeError, ValueError):
                    _payload = {}
                if not isinstance(_payload, dict):
                    continue
                _payload.pop("language", None)
                if json.dumps(_payload, ensure_ascii=False, sort_keys=True) == _ziel:
                    _dup = True
                    break
        if _dup:
            conn.close()
            return None  # bereits gequeued (heute)
        c.execute("INSERT INTO agent_tasks (task_type, payload) VALUES (?, ?)",
                  (task_type, json.dumps(payload, ensure_ascii=False, sort_keys=True)))
        tid = c.lastrowid
        conn.commit()
        conn.close()
        print(f"[Agent-Queue] Task #{tid} ({task_type}) gequeued")
        return tid
    except Exception as e:
        print(f"[Agent-Queue] Fehler (App läuft weiter): {e}")
        return None


# ─── Bewerbung + Agent-Kette (Phase 5/v6.2, Port app.py:3294-3330) ───

def apply_to_job(candidate_id: int, job_id: int, bewerbungstext: str | None = None) -> int:
    """Erzeugt eine Bewerbung (UNIQUE(candidate_id, job_id) schuetzt vor Doppelbewerbung)
    und queued die 10-fach Agent-Kette aus Spec v3/v6/v6.2 – exakt die Reihenfolge
    aus app.py:3305-3330 (Streamlit-Wahrheit):
    send_confirmation, extract_profile, match_candidate, check_compliance,
    assess_culture_fit, verify_documents, check_visa, explain_match, check_gdpr,
    notify_user.
    Rückgabe: application_id (neu angelegt ODER reaktiviert).
    Wirft sqlite3.IntegrityError bei Doppelbewerbung.

    REAKTIVIERUNG (P1-1, 30.09.2026, Nutzerentscheid „Reaktivieren“): Eine
    zurückgezogene Bewerbung hat dieselbe UNIQUE(candidate_id, job_id)-Zeile
    belegt. Statt mit IntegrityError abzubrechen, wird DIESE Zeile wieder auf
    'eingegangen' gesetzt (neuer bewerbungstext, frischer Zeitstempel) — die
    Sperre ist damit aufgehoben. Die alte Historie bleibt erhalten, der neue
    Übergang wird als 'eingegangen' protokolliert. Alle anderen Status
    (eingegangen/angesehen/eingeladen/eingestellt/abgelehnt) bleiben gesperrt
    und loesen weiterhin sqlite3.IntegrityError aus.

    GENERATION (R3-2, 30.09.2026, Nutzer-GO „A: Generation-Zähler“):
    Die Reaktivierung verlaesst sich NICHT mehr auf ein fruehes `return app_id`
    (das den Queue-Block uebersprungen haette), sondern rechnet die Kette wie
    die Erstbewerbung durch. Jedes Queue-Payload traegt `gen`:
      * Erstbewerbung  -> gen = 0
      * Reaktivierung  -> gen = MAX(COALESCE(gen,0)) ueber alle Tasks dieser
        Application + 1  (Altbestand ohne gen-Feld zaehlt als 0)
    `gen` ist Teil der Dedupe-Grenze in queue_agent_task und Teil des
    notify_hr-Guards in scripts/agent-runner.py::_maybe_gatekeeper — dadurch
    laeuft die HR-Benachrichtigung nach Rueckzug->„Erneut bewerben“ ein zweites Mal.
    Design-Entscheidung (keine externe Quelle): Die Reaktivierung queue't
    dieselbe Task-Liste wie die Erstbewerbung (eine Codepfad-Quelle); die
    erneute Bestaetigungsmail gilt als Bestaetigung der Neubewerbung.
    """
    conn = get_conn()
    _c0 = conn.cursor()
    _c0.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,))
    _row = _c0.fetchone()
    if not _row or _row[0] not in ("lebenslauf_hochgeladen", "profil_geprueft",
                                   "match_berechnet", "eingeladen"):
        conn.close()
        raise ValueError(
            f"CV-Pflicht: Status '{_row[0] if _row else None}' erlaubt keine Bewerbung "
            "(Lebenslauf zuerst hochladen)."
        )
    try:
        c = conn.cursor()
        # Reaktivierung? (P1-1) Nur 'zurückgezogen' hebt die UNIQUE-Sperre auf.
        c.execute(
            "SELECT id FROM applications WHERE candidate_id = ? AND job_id = ? "
            "AND status = 'zurückgezogen'",
            (candidate_id, job_id),
        )
        _w = c.fetchone()
        if _w:
            app_id = _w[0]
            c.execute(
                "UPDATE applications SET status='eingegangen', bewerbungstext=?, "
                "aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?",
                (bewerbungstext or None, app_id),
            )
            c.execute(
                "INSERT INTO application_status_history "
                "(application_id, status, changed_by) VALUES (?, 'eingegangen', 'kandidat')",
                (app_id,),
            )
            conn.commit()
            # R3-2: Generation = hoechster bestehender Wert + 1. Steht VOR
            # conn.close(), weil der Queue-Block NACH dem finally laeuft.
            # Altbestand ohne gen-Feld zaehlt via COALESCE als 0.
            c.execute(
                """SELECT COALESCE(MAX(COALESCE(json_extract(payload, '$.gen'), 0)), 0)
                   FROM agent_tasks
                   WHERE json_extract(payload, '$.application_id') = ?""",
                (app_id,),
            )
            gen = c.fetchone()[0] + 1
        else:
            c.execute(
                "INSERT INTO applications (candidate_id, job_id, status, bewerbungstext) VALUES (?, ?, 'eingegangen', ?)",
                (candidate_id, job_id, bewerbungstext or None),
            )
            app_id = c.lastrowid
            c.execute(
                "INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'eingegangen', 'kandidat')",
                (app_id,),
            )
            conn.commit()
            gen = 0  # frische Bewerbung: erste Generation
    finally:
        conn.close()
    payload = {"application_id": app_id, "candidate_id": candidate_id,
               "job_id": job_id, "gen": gen}
    queue_agent_task("send_confirmation", payload)
    queue_agent_task("extract_profile", payload)
    queue_agent_task("match_candidate", payload)
    queue_agent_task("check_compliance", payload)
    queue_agent_task("assess_culture_fit", payload)
    queue_agent_task("verify_documents", payload)
    queue_agent_task("check_visa", payload)
    queue_agent_task("explain_match", payload)
    queue_agent_task("check_gdpr", payload)
    queue_agent_task("notify_user", payload)
    return app_id


def get_invitation_artifacts(application_id: int) -> dict | None:
    """Lädt Einladungs-Artefakte (Meeting-Link VDO.Ninja, ICS, Termin) aus dem create_invitation-Task.
    Kopie aus app.py:478-494."""
    try:
        conn = sqlite3.connect(str(AGENT_TASKS_DB))
        cur = conn.cursor()
        cur.execute("""SELECT result_json FROM agent_tasks
            WHERE task_type = 'create_invitation' AND status = 'done'
              AND json_extract(payload, '$.application_id') = ?
            ORDER BY id DESC LIMIT 1""",
            (application_id,))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception as ex:
        print(f"[db] get_invitation_artifacts({application_id}) fehlgeschlagen: {ex!r}")
    return None


def get_invitation_task_status(application_id: int) -> str | None:
    """Status des jüngsten create_invitation-Tasks der Bewerbung (oder None).

    22.10.2026 (Einladungs-Hinweis, Vorfall Bewerbung #42): `get_invitation_
    artifacts` liest NUR `status='done'` und liefert in allen anderen Fällen
    None — die Employer-Seite konnte zwischen „Task hängt noch in der Queue"
    (63 min Wartezeit, gemessen 22.10.2026) und „gar kein Task" nicht
    unterscheiden und schwieg komplett. Diese Funktion liefert nur den reinen
    Status ('pending'/'running'/'failed'/'done'), damit die Seite zwischen-
    unterscheiden kann. Eigene Verbindung, wie alle db-Leser (Handler-
    Connection-Gotcha) — read-only.
    """
    try:
        conn = sqlite3.connect(str(AGENT_TASKS_DB))
        cur = conn.cursor()
        cur.execute("""SELECT status FROM agent_tasks
            WHERE task_type = 'create_invitation'
              AND json_extract(payload, '$.application_id') = ?
            ORDER BY id DESC LIMIT 1""",
            (application_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as ex:
        print(f"[db] get_invitation_task_status({application_id}) fehlgeschlagen: {ex!r}")
        return None


def get_application_status_history(application_id: int) -> list:
    """Gibt die Status-Historie einer Bewerbung zurück (chronologisch).
    Jede Zeile: (status, changed_at, changed_by)."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("""SELECT status, changed_at, changed_by FROM application_status_history
            WHERE application_id = ? ORDER BY changed_at ASC""", (application_id,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        print(f"[db] get_application_status_history({application_id}) fehlgeschlagen: {ex!r}")
        return []


def get_agent_task_status(application_id: int) -> dict | None:
    """Letzter Status je Task-Typ für eine Bewerbung (Badge in HR-/Candidate-Sicht).
    Kern der Duplikat-Bereinigung: ersetzt die inline-SQL-Blöcke app.py:3355-3363
    (Candidate-Portal) und app.py:3085-3105 (HR-Kandidaten-Tab)."""
    try:
        conn = sqlite3.connect(str(AGENT_TASKS_DB))
        cur = conn.cursor()
        cur.execute("""SELECT task_type, status FROM agent_tasks
            WHERE id IN (SELECT MAX(id) FROM agent_tasks
                         WHERE json_extract(payload, '$.application_id') = ?
                         GROUP BY task_type)
            ORDER BY id""",
            (application_id,))
        rows = cur.fetchall()
        conn.close()
        return dict(rows) if rows else None
    except Exception as ex:
        print(f"[db] get_agent_task_status({application_id}) fehlgeschlagen: {ex!r}")
        return None


def get_candidate_agent_tasks(candidate_id: int, conn=None) -> list:
    """P8.2 (08.10.2026): letzte Agent-Task je `task_type` für ALLE Bewerbungen
    eines Kandidaten — Badge-/Berichts-Quelle für `_page_agent_details`
    (ersetzt den lokalen `ergebnisse/*.md`-Glob, der in CI/Cloud leer ist).

    Spec: knowledge/system/p8-cloud-datenquellen.md.

    Rückgabe je Eintrag (Dict): task_type, status, text (aus
    `result_json["text"]`, sonst None), created_at, application_id, gen.
    `application_id`/`gen` stammen aus `agent_tasks.payload`; die Zuordnung zur
    Bewerbung erfolgt über `applications.candidate_id` (app-IDs vorab laden,
    `payload` in Python parsen). BEWUSST OHNE `json_extract` (kein Dialekt-Sonderfall).

    Muster `own_conn`: nur eine selbst geöffnete Verbindung wird geschlossen; eine
    übergebene wird nie geschlossen. Leere Bewerbungsliste ⇒ [] ohne Task-Query.
    """
    own_conn = conn is None
    try:
        if own_conn:
            conn = sqlite3.connect(str(AGENT_TASKS_DB))
        cur = conn.cursor()
        cur.execute("SELECT id FROM applications WHERE candidate_id = ?",
                    (candidate_id,))
        app_ids = {int(r[0]) for r in cur.fetchall() if r[0] is not None}
        if not app_ids:
            return []
        cur.execute("""SELECT id, task_type, status, payload, result_json, created_at
            FROM agent_tasks ORDER BY id DESC""")
        latest = {}
        for _id, task_type, status, payload, result_json, created_at in cur.fetchall():
            try:
                p = json.loads(payload) if payload else {}
            except (ValueError, TypeError):
                p = {}
            app_id = p.get("application_id") if isinstance(p, dict) else None
            try:
                app_id = int(app_id)
            except (TypeError, ValueError):
                continue  # ohne Bewerbungsbezug nicht zuordenbar
            if app_id not in app_ids:
                continue
            if task_type in latest:
                continue  # ORDER BY id DESC ⇒ erste passende Zeile je Typ = höchste id
            text = None
            if result_json:
                try:
                    rj = json.loads(result_json)
                    if isinstance(rj, dict):
                        text = rj.get("text")
                except (ValueError, TypeError):
                    text = None
            latest[task_type] = {
                "task_type": task_type,
                "status": status,
                "text": text,
                "created_at": created_at,
                "application_id": app_id,
                "gen": p.get("gen") if isinstance(p, dict) else None,
            }
        return list(latest.values())
    except Exception as ex:
        print(f"[db] get_candidate_agent_tasks({candidate_id}) fehlgeschlagen: {ex!r}")
        return []
    finally:
        if own_conn and conn is not None:
            conn.close()


def get_language_tests(candidate_id: int) -> list:
    """Alle Sprachtest-Ergebnisse eines Kandidaten (neueste zuerst).
    Kern der Duplikat-Bereinigung: ersetzt die SQL-Blöcke app.py:~2790 und ~3560
    (einmal Candidate-Sicht, einmal HR-Dokumente-Tab)."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("""SELECT id, sprache, niveau, punkte, cefr_level, test_datum
            FROM language_tests WHERE candidate_id = ? ORDER BY id DESC""", (candidate_id,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        print(f"[db] get_language_tests({candidate_id}) fehlgeschlagen: {ex!r}")
        return []


def insert_language_test(candidate_id: int, sprache: str, niveau: str,
                         fragen_anzahl: int, punkte: float, cefr_level: str,
                         details: str = "") -> int | None:
    """Speichert ein Sprachtest-Ergebnis. Kopie aus app.py:3000-3002.
    Gibt die neue Zeilen-ID zurueck (lastrowid, Muster: insert_job)."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO language_tests (candidate_id, sprache, niveau, fragen_anzahl, punkte, cefr_level, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (candidate_id, sprache, niveau, fragen_anzahl, punkte, cefr_level, details),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id
    except Exception as ex:
        print(f"[db] insert_language_test(cand={candidate_id}, sprache={sprache!r}) "
              f"fehlgeschlagen: {ex!r}")
        return None


def get_documents(candidate_id: int) -> list:
    """Alle Dokumente eines Kandidaten (Candidate-Portal + HR-Dokumente-Tab).

    P0 (28.09.2026): Spaltenname war 'dokument_typ', die Tabelle hat
    'dokumententyp' (siehe insert_document + Schema). sqlite3 wirft
    "no such column", das bisherige stille except lieferte [] → die UI zeigte
    "Noch keine Dokumente hochgeladen", obwohl die Datei in der DB lag
    (Beweis: ergebnisse/reports/screenshots/vorher/messung-vorher.json,
     Flag 'dokument-empty-state'). Fehler werden jetzt geloggt, nicht
    verschluckt.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("""SELECT id, dokumententyp, datei_pfad, hochgeladen_am
            FROM candidate_documents WHERE candidate_id = ? ORDER BY id DESC""", (candidate_id,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        print(f"[db] get_documents({candidate_id}) fehlgeschlagen: {ex!r}")
        return []


def insert_document(candidate_id: int, datei_pfad: str, dokument_typ: str) -> bool:
    """Speichert ein Dokument. Kopie aus app.py:2851-2853.

    P1-11 (30.09.2026): `except Exception: return False` verwarf den Grund
    vollstaendig — weder Log noch Meldung. Jetzt wird die Ausnahme protokolliert
    (Konvention der Datei: print nach stderr mit Praefix [db]).
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO candidate_documents (candidate_id, datei_pfad, dokumententyp) VALUES (?, ?, ?)",
            (candidate_id, datei_pfad, dokument_typ),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as ex:
        print(f"[db] insert_document(cand={candidate_id}, typ={dokument_typ!r}) "
              f"fehlgeschlagen: {ex!r}")
        return False


def delete_document(doc_id: int, candidate_id: int) -> bool:
    """Loescht ein Dokument (Art. 17 Selbstservice). Kopie aus app.py:2876."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "DELETE FROM candidate_documents WHERE id = ? AND candidate_id = ?",
            (doc_id, candidate_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as ex:
        print(f"[db] delete_document(doc={doc_id}, cand={candidate_id}) "
              f"fehlgeschlagen: {ex!r}")
        return False


def upsert_employer(employer_id: int, branche: str, groesse: str,
                    standort: str, website: str, beschreibung: str,
                    telefon: str) -> bool:
    """Aktualisiert das Firmenprofil. Kopie aus app.py:3481-3483."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            """UPDATE employers SET branche=?, groesse=?, standort=?, website=?, beschreibung=?, telefon=?, aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?""",
            (branche, groesse, standort, website, beschreibung, telefon, employer_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as ex:
        print(f"[db] upsert_employer({employer_id}) fehlgeschlagen: {ex!r}")
        return False


def insert_job(employer_id: int, titel: str, beschreibung: str, standort: str,
               land: str, stellentyp: str, hard_skills: str, soft_skills: str,
               berufserfahrung_jahre: int, deutsch_level: str, englisch_level: str,
               abschluss: str, gehaltsrahmen_min: int | None,
               gehaltsrahmen_max: int | None) -> int | None:
    """Legt eine neue Stelle an. Kopie aus app.py:3515-3520.

    P1-11 (30.09.2026): Fehlerursache wird protokolliert (vorher `except Exception:
    return None` ohne jede Spur); der Aufrufer zeigt bereits eine Fehlermeldung,
    konnte aber keinen Grund nennen.

    Doppelklick-Schutz (11.10.2026, Design-Entscheidung): eine identische Stelle
    (employer_id + titel + standort) innerhalb der letzten 60 s wird nicht erneut
    eingefuegt — stattdessen wird die vorhandene id zurueckgegeben. Nur dieses
    kurze Fenster; spaetere legitime Wiederholungen bleiben erlaubt.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id FROM jobs WHERE employer_id = ? AND titel = ? AND standort = ? "
            "AND erstellt_am >= datetime('now', '-60 seconds') ORDER BY id DESC LIMIT 1",
            (employer_id, titel, standort),
        ).fetchone()
        if row:
            conn.close()
            return row[0]
        cur.execute(
            """INSERT INTO jobs (employer_id, titel, beschreibung, standort, land, stellentyp,
               hard_skills, soft_skills, berufserfahrung_jahre, deutsch_level, englisch_level,
               abschluss, gehaltsrahmen_min, gehaltsrahmen_max)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (employer_id, titel, beschreibung, standort, land, stellentyp,
             hard_skills, soft_skills, berufserfahrung_jahre, deutsch_level, englisch_level,
             abschluss, gehaltsrahmen_min or None, gehaltsrahmen_max or None),
        )
        job_id = cur.lastrowid
        conn.execute(
            "INSERT INTO job_status_history (job_id, status, changed_by) VALUES (?, 'aktiv', ?)",
            (job_id, "system"),
        )
        conn.commit()
        conn.close()
        return job_id
    except Exception as ex:
        print(f"[db] insert_job(employer={employer_id}, titel={titel!r}) "
              f"fehlgeschlagen: {ex!r}")
        return None


def update_job_status(job_id: int, neuer_status: str, changed_by: str = "system") -> bool:
    """Aendert den Stellen-Status. Kopie aus app.py:3541-3543."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "UPDATE jobs SET status=?, aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?",
            (neuer_status, job_id),
        )
        conn.execute(
            "INSERT INTO job_status_history (job_id, status, changed_by) VALUES (?, ?, ?)",
            (job_id, neuer_status, changed_by),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as ex:
        print(f"[db] update_job_status(job={job_id}, status={neuer_status!r}) "
              f"fehlgeschlagen: {ex!r}")
        return False


# ─── Notifications ────────────────────────────────────────────────────

def init_notifications_table() -> None:
    """Legt die notifications-Tabelle an (idempotent).

    17.10.2026 (Notification-Sprache, Änderung B): msg_key (i18n-msgid
    Praefix, z.B. 'notify.statuswechsel') + params (JSON-String mit den
    Formatwerten) — Altbestands-DBs bekommen die Spalten per ALTER TABLE
    (Muster: init_compliance_protokoll_table). `gelesen` bleibt vestigial
    (Löschen beim Lesen, 17.10.2026).
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        titel TEXT,
        nachricht TEXT,
        gelesen INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        msg_key TEXT,
        params TEXT
    )""")
    spalten = {r[1] for r in c.execute("PRAGMA table_info(notifications)").fetchall()}
    if "msg_key" not in spalten:
        c.execute("ALTER TABLE notifications ADD COLUMN msg_key TEXT")
    if "params" not in spalten:
        c.execute("ALTER TABLE notifications ADD COLUMN params TEXT")
    conn.commit()
    conn.close()


# ─── Mentoring / Patenschaft (Phase D P10, User-GO 24.09.2026) ────────
# Spec: knowledge/lifecycle/mentoring.md §§2A (HR-Klick), 3C (eigene
# Tabelle, Vorbild candidate_status_history), 4 (Ende per HR-Klick).

def init_mentoring_table() -> None:
    """Legt die mentoring-Tabelle an (idempotent). Spec §3 Option C."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS mentoring (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL,
        mentor_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'aktiv',
        changed_by TEXT,
        notizen TEXT,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        start_at TIMESTAMP,
        end_at TIMESTAMP,
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )""")
    conn.commit()
    conn.close()


# ─── Compliance-Protokoll (N-K, 01.10.2026) ──────────────────────────────
# User-Entscheidung 01.10.2026: „Beides: Writer + Berichte“ — die MD-Berichte
# bleiben Primärquelle (R3-3), das Protokoll wird wieder aktiv befüllt.
# Additiv: application_id (der Auftrag nennt sie ausdrücklich); Bestands-DBs
# bekommen die Spalte per ALTER TABLE (idempotente Migration).

def init_compliance_protokoll_table(db_path: Path | None = None) -> None:
    """Legt compliance_protokoll an bzw. ergänzt application_id (idempotent).

    `db_path` nur für Tests (Default: DB_PATH).
    """
    conn = sqlite3.connect(str(db_path or DB_PATH))
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS compliance_protokoll (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT NOT NULL,
        land TEXT NOT NULL,
        pruefpunkt TEXT NOT NULL,
        status TEXT NOT NULL,
        details TEXT,
        datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        application_id INTEGER
    )""")
    spalten = {r[1] for r in c.execute("PRAGMA table_info(compliance_protokoll)").fetchall()}
    if "application_id" not in spalten:
        c.execute("ALTER TABLE compliance_protokoll ADD COLUMN application_id INTEGER")
    conn.commit()
    conn.close()


def record_compliance_protokoll(match_id: str, land: str, pruefpunkt: str, status: str,
                                details: str | None = None,
                                application_id: int | None = None,
                                db_path: Path | None = None) -> str:
    """Schreibt/aktualisiert EINEN Protokolleintrag (idempotent).

    Schlüssel = (match_id, pruefpunkt): gleicher Tag → UPDATE, sonst INSERT
    (Muster wie feedback-Speichern). Rückgabe: 'inserted' | 'updated'.
    `db_path` nur für Tests (Default: DB_PATH); der Aufrufer (Runner) nutzt
    das Standardziel, damit der conftest-Spiegel greift.
    """
    ziel = db_path or DB_PATH
    conn = sqlite3.connect(str(ziel))
    try:
        row = conn.execute(
            "SELECT id FROM compliance_protokoll WHERE match_id = ? AND pruefpunkt = ?",
            (match_id, pruefpunkt)).fetchone()
        if row:
            conn.execute(
                "UPDATE compliance_protokoll SET land=?, status=?, details=?, "
                "application_id=?, datum=CURRENT_TIMESTAMP WHERE id=?",
                (land, status, details, application_id, row[0]))
            aktion = "updated"
        else:
            conn.execute(
                "INSERT INTO compliance_protokoll "
                "(match_id, land, pruefpunkt, status, details, application_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (match_id, land, pruefpunkt, status, details, application_id))
            aktion = "inserted"
        conn.commit()
        return aktion
    finally:
        conn.close()


def get_active_mentor(candidate_id: int) -> str | None:
    """Liefert den aktiven Mentor-Namen oder None (Spec §5 Lookup)."""
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute(
        "SELECT mentor_name FROM mentoring WHERE candidate_id = ? AND status = 'aktiv' "
        "ORDER BY changed_at DESC LIMIT 1",
        (candidate_id,),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def assign_mentor(candidate_id: int, mentor_name: str, changed_by: str = "arbeitgeber",
                  notizen: str | None = None) -> int:
    """Vergibt eine aktive Patenschaft (HR-Klick §2A). Nur EINE aktive
    Patenschaft gleichzeitig – vorhandene aktive wird vorher beendet (Design,
    Spec §3C: Status + Laufzeit in einer Tabelle)."""
    name = (mentor_name or "").strip()
    if not name:
        raise ValueError("mentor_name darf nicht leer sein")
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute(
        "UPDATE mentoring SET status = 'beendet', end_at = CURRENT_TIMESTAMP, "
        "changed_at = CURRENT_TIMESTAMP, changed_by = ? "
        "WHERE candidate_id = ? AND status = 'aktiv'",
        (changed_by, candidate_id),
    )
    c.execute(
        "INSERT INTO mentoring (candidate_id, mentor_name, status, changed_by, notizen, start_at) "
        "VALUES (?, ?, 'aktiv', ?, ?, CURRENT_TIMESTAMP)",
        (candidate_id, name, changed_by, notizen),
    )
    mid = c.lastrowid
    conn.commit()
    conn.close()
    return mid


def end_mentoring(candidate_id: int, changed_by: str = "arbeitgeber") -> bool:
    """Beendet die aktive Patenschaft (HR-Klick §4, manuell – keine Automatik).
    True wenn eine aktive Patenschaft existierte."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute(
        "UPDATE mentoring SET status = 'beendet', end_at = CURRENT_TIMESTAMP, "
        "changed_at = CURRENT_TIMESTAMP, changed_by = ? "
        "WHERE candidate_id = ? AND status = 'aktiv'",
        (changed_by, candidate_id),
    )
    changed = c.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def insert_notification(user_id: int, role: str, titel: str, nachricht: str,
                        msg_key: str | None = None,
                        params: dict | None = None) -> None:
    """Fuegt eine Benachrichtigung hinzu.

    17.10.2026 (Notification-Sprache, Änderung B): optional msg_key +
    params (dict, als JSON mit sort_keys gespeichert). Rueckwaertskompatibel
    (Default None) — titel/nachricht bleiben IMMER gefuellt (Fallback-Text
    fuer DB-Leser ohne i18n und E2E-Plaintext-Asserts).
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO notifications (user_id, role, titel, nachricht, msg_key, params) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, role, titel, nachricht, msg_key,
         json.dumps(params, sort_keys=True) if params is not None else None),
    )
    conn.commit()
    conn.close()


def get_notifications(user_id: int, role: str, limit: int = 20) -> list:
    """Holt Benachrichtigungen fuer einen User (neueste zuerst).

    17.10.2026 (Notification-Sprache, Änderung B): liefert 7 TUPEL-ELEMENTE
    (id, titel, nachricht, gelesen, created_at, msg_key, params) — die
    neuen Spalten haengen hinten an, bestehende Positions-Zugriffe bleiben
    gueltig. Altbestand: msg_key/params NULL -> Anzeige verbatim.
    """
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT id, titel, nachricht, gelesen, created_at, msg_key, params "
        "FROM notifications "
        "WHERE user_id = ? AND role = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, role, limit),
    ).fetchall()
    conn.close()
    return rows


def get_unread_count(user_id: int, role: str) -> int:
    """Anzahl ungelesener Benachrichtigungen."""
    conn = sqlite3.connect(str(DB_PATH))
    count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND role = ? AND gelesen = 0",
        (user_id, role),
    ).fetchone()[0]
    conn.close()
    return count


def delete_notifications(user_id: int, role: str) -> None:
    """Loescht alle Benachrichtigungen eines Users (Rolle).

    17.10.2026 (Löschen beim Gelesen-Markieren): Ersetzt mark_notifications_read
    (entfernt). Die Spalte `gelesen` bleibt als vestigialer Default stehen
    (kein Schema-Change), wird aber nicht mehr gesetzt.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "DELETE FROM notifications WHERE user_id = ? AND role = ?",
        (user_id, role),
    )
    conn.commit()
    conn.close()


# ─── Passwort-Reset (18.10.2026) ────────────────────────────────────────
# Spec: knowledge/system/configuration-secrets.md §(g). Framework-frei (nur
# sqlite3) — von Web-Schicht UND Agent-Runner nutzbar. Der Klartext-Token wird
# hier NIE gehalten: gespeichert wird nur der SHA-256-Lookup-Hash.
# Design-Entscheidungen (keine externe Quelle): Ablauf 60 Min, Rate-Limit
# 3 Anfragen / 10 Min pro E-Mail.
RESET_TTL_MINUTES = 60
RESET_RATE_LIMIT = 3
RESET_RATE_WINDOW_MINUTES = 10


def init_password_resets_table(db_path: Path | None = None) -> None:
    """Legt die password_resets-Tabelle an (idempotent). Spec §(g)."""
    conn = sqlite3.connect(str(db_path or DB_PATH))
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        role TEXT NOT NULL,
        token_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        used_at TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_password_resets_token "
              "ON password_resets(token_hash)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_password_resets_email "
              "ON password_resets(email)")
    conn.commit()
    conn.close()


def hash_reset_token(token: str) -> str:
    """SHA-256-Lookup-Hash des Reset-Tokens (kein Passwort-Hash-Verfahren —
    der Token ist kein Nutzer-Passwort). Deterministisch für den Lookup."""
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_reset(conn, email: str, role: str,
                          token_hash: str, expires_at: str) -> int:
    """Schreibt eine Reset-Zeile, gibt die id zurück. `expires_at` im
    UTC-Format '%Y-%m-%d %H:%M:%S' (passt zu strftime('%s','now'))."""
    c = conn.cursor()
    c.execute("INSERT INTO password_resets (email, role, token_hash, expires_at) "
              "VALUES (?, ?, ?, ?)", (email, role, token_hash, expires_at))
    conn.commit()
    return c.lastrowid


def count_recent_password_resets(conn, email: str,
                                 minutes: int = RESET_RATE_WINDOW_MINUTES) -> int:
    """Anzahl Reset-Anfragen für `email` im Zeitfenster (Rate-Limit-Quelle)."""
    row = conn.execute(
        "SELECT COUNT(*) FROM password_resets WHERE lower(email) = lower(?) "
        "AND CAST(strftime('%s','now') AS INTEGER) "
        "- CAST(strftime('%s', created_at) AS INTEGER) < ?",
        (email, minutes * 60)).fetchone()
    return row[0] if row else 0


def find_active_password_reset(conn, token_hash: str):
    """Aktive Reset-Zeile (unbenutzt + nicht abgelaufen): (id, email, role, ...)
    oder None. Ablauf-/Benutzungsprüfung liegt in der SQL-Abfrage."""
    return conn.execute(
        "SELECT id, email, role, expires_at, used_at FROM password_resets "
        "WHERE token_hash = ? AND used_at IS NULL "
        "AND CAST(strftime('%s','now') AS INTEGER) "
        "< CAST(strftime('%s', expires_at) AS INTEGER)", (token_hash,)).fetchone()


def mark_password_reset_used(conn, reset_id: int) -> None:
    """Markiert die Zeile als verbraucht (Einmal-Verwendung)."""
    conn.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP "
                 "WHERE id = ?", (reset_id,))
    conn.commit()


def delete_expired_password_resets(conn) -> int:
    """Löscht abgelaufene UND verbrauchte Zeilen (Aufruf aus dsgvo_cleanup)."""
    c = conn.cursor()
    c.execute("DELETE FROM password_resets WHERE used_at IS NOT NULL "
              "OR CAST(strftime('%s','now') AS INTEGER) "
              ">= CAST(strftime('%s', expires_at) AS INTEGER)")
    n = c.rowcount
    conn.commit()
    return n


# ─── Candidates-Spalten-Migration (18.10.2026) ─────────────────────────
# FR-Filter Hiring-Board (Spec: knowledge/portal/employer-board.md, Abschnitt
# „Passiv-Filter"): Altbestands-DBs bekommen die Spalte `franzoesisch` per
# ALTER TABLE — Muster: init_notifications_table (Codemark
# `if "msg_key" not in spalten`). Ein Fakt = das ALTER-Statement steht NUR hier.

def init_candidates_migrations() -> None:
    """Ergänzt candidates-Spalten jüngerer Iterationen (idempotent).

    18.10.2026: `franzoesisch` (FR-Filter Hiring-Board, Spec
    employer-board.md). Ohne candidates-Tabelle nichts zu tun — ein
    ALTER-Try auf einer Frisch-DB ohne Schema soll den Boot nicht brechen.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    spalten = {r[1] for r in c.execute("PRAGMA table_info(candidates)").fetchall()}
    if spalten and "franzoesisch" not in spalten:
        c.execute("ALTER TABLE candidates ADD COLUMN franzoesisch TEXT")
    conn.commit()
    conn.close()


# ─── Consent-Nachweise (26.10.2026) ────────────────────────────────────
# Einwilligungen nach Art. 6/7 DSGVO + Art. 9 Abs. 2 lit. a (besondere
# Kategorien) + § 26 BDSG: je Subjekt (Bewerber/Arbeitgeber) und Zweck wird
# **ein** Nachweis geführt, welche Textversion wann, in welcher Sprache, über
# welchen Kanal und mit welchem Beleg (z. B. Checkbox-ID, IP-Hash) akzeptiert
# wurde. Widerruf löscht nichts, sondern setzt `withdrawn_at` (Rechenschafts-
# pflicht Art. 5 Abs. 2 DSGVO — Nachweis muss den Widerruf überleben).
#
# Design-Entscheidungen (keine externe Quelle nötig, Verhalten):
#   * Ein Fakt = das Schema steht NUR hier (`init_consents_table`), WebUI und
#     Tests rufen nur diese Funktion auf (Muster `init_notifications_table`).
#   * `text_version` ist Teil des Unique-Keys: eine neue Fassung erzeugt eine
#     **neue** Zeile, die Historie der alten Fassung bleibt erhalten.
#   * Keine personenbezogenen Inhalte in der Tabelle — nur IDs, Zweck,
#     Metadaten. `evidence_json` ist für technische Belege gedacht, nicht für
#     Namen, Adressen oder CV-Daten (Datenminimierung Art. 5 Abs. 1 lit. c).

CONSENT_VERSION = "2026-10-26"
CONSENT_FORM_DEFAULT = "electronic"
# Vertrag mit der UI (webui/pages/*): nur diese Werte werden angenommen.
CONSENT_SUBJECT_TYPES = ("candidate", "employer")
CONSENT_PURPOSES = ("terms", "privacy", "talent_pool", "special_category",
                    "language_test", "recording", "marketing")
CONSENT_LANGUAGES = ("de", "en", "fr", "ar")


def init_consents_table(db_path: Path | None = None) -> None:
    """Legt die consents-Tabelle an (idempotent) + ergänzt fehlende Spalten.

    `db_path` nur für Tests (Default: DB_PATH, damit der conftest-Spiegel
    greift). Altbestands-DBs (kein `form`/`language`/`channel`/`evidence_json`)
    werden per ALTER TABLE geheilt — `CREATE TABLE IF NOT EXISTS` ändert eine
    bestehende Tabelle nicht (Muster `init_agent_tasks_table`).
    """
    conn = sqlite3.connect(str(db_path or DB_PATH))
    try:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS consents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            text_version TEXT NOT NULL,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            form TEXT NOT NULL DEFAULT 'electronic',
            language TEXT,
            channel TEXT,
            withdrawn_at TIMESTAMP,
            evidence_json TEXT,
            UNIQUE(subject_type, subject_id, purpose, text_version)
        )""")
        # ALTER-safe: nur fehlende Spalten ergänzen, nie bestehende ändern.
        vorhanden = {r[1] for r in c.execute("PRAGMA table_info(consents)").fetchall()}
        for spalte, typ in (
            ("form", "TEXT NOT NULL DEFAULT 'electronic'"),
            ("language", "TEXT"),
            ("channel", "TEXT"),
            ("withdrawn_at", "TIMESTAMP"),
            ("evidence_json", "TEXT"),
        ):
            if spalte not in vorhanden:
                c.execute(f"ALTER TABLE consents ADD COLUMN {spalte} {typ}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_consents_subject "
                  "ON consents(subject_type, subject_id)")
        conn.commit()
    finally:
        conn.close()


def _consent_check(subject_type: str, subject_id: int, purpose: str) -> None:
    """Prüft die Vertragswerte der UI (Fehler früh, statt stiller Falschdaten)."""
    if subject_type not in CONSENT_SUBJECT_TYPES:
        raise ValueError(f"consents: unbekannter subject_type {subject_type!r}")
    if not isinstance(subject_id, int) or isinstance(subject_id, bool) or subject_id < 1:
        raise ValueError(f"consents: ungültige subject_id {subject_id!r}")
    if purpose not in CONSENT_PURPOSES:
        raise ValueError(f"consents: unbekannter purpose {purpose!r}")


def record_consent(subject_type: str, subject_id: int, purpose: str,
                   text_version: str = CONSENT_VERSION, language: str = "de",
                   channel: str = "ui", evidence: dict | None = None,
                   db_path: Path | None = None) -> int:
    """Erteilt/erneuert eine Einwilligung und gibt die Zeilen-id zurück.

    Upsert auf dem Unique-Key `(subject_type, subject_id, purpose,
    text_version)`: erneutes Akzeptieren derselben Textversion setzt
    `granted_at` auf jetzt, hebt einen früheren Widerruf auf (`withdrawn_at`
    = NULL) und aktualisiert Sprache/Kanal/Beleg. Ein neuer `text_version`-
    Wert erzeugt eine neue Zeile (Historie bleibt).
    `evidence` wird als JSON gespeichert (dict oder None).
    """
    _consent_check(subject_type, subject_id, purpose)
    if language not in CONSENT_LANGUAGES:
        raise ValueError(f"consents: unbekannte language {language!r}")
    evidence_json = (json.dumps(evidence, ensure_ascii=False, sort_keys=True)
                     if evidence is not None else None)
    conn = sqlite3.connect(str(db_path or DB_PATH))
    try:
        conn.execute(
            """INSERT INTO consents
                   (subject_type, subject_id, purpose, text_version, form,
                    language, channel, evidence_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(subject_type, subject_id, purpose, text_version)
               DO UPDATE SET
                   granted_at = CURRENT_TIMESTAMP,
                   withdrawn_at = NULL,
                   form = excluded.form,
                   language = excluded.language,
                   channel = excluded.channel,
                   evidence_json = COALESCE(excluded.evidence_json,
                                            consents.evidence_json)""",
            (subject_type, subject_id, purpose, text_version,
             CONSENT_FORM_DEFAULT, language, channel, evidence_json))
        # lastrowid ist beim UPDATE-Pfad nicht verlässlich -> nachlesen.
        row = conn.execute(
            "SELECT id FROM consents WHERE subject_type = ? AND subject_id = ? "
            "AND purpose = ? AND text_version = ?",
            (subject_type, subject_id, purpose, text_version)).fetchone()
        conn.commit()
        return int(row[0])
    finally:
        conn.close()


def withdraw_consent(subject_type: str, subject_id: int, purpose: str,
                     db_path: Path | None = None) -> bool:
    """Widerruft alle aktiven Nachweise eines Zwecks. True = Zeile geändert.

    Die Zeile bleibt erhalten (Rechenschaftspflicht), nur `withdrawn_at` wird
    gesetzt. Mehrfacher Aufruf ist ein No-op (False).
    """
    _consent_check(subject_type, subject_id, purpose)
    conn = sqlite3.connect(str(db_path or DB_PATH))
    try:
        c = conn.execute(
            "UPDATE consents SET withdrawn_at = CURRENT_TIMESTAMP "
            "WHERE subject_type = ? AND subject_id = ? AND purpose = ? "
            "AND withdrawn_at IS NULL",
            (subject_type, subject_id, purpose))
        geaendert = c.rowcount
        conn.commit()
        return geaendert > 0
    finally:
        conn.close()


def get_consents(subject_type: str, subject_id: int,
                 db_path: Path | None = None) -> list[dict]:
    """Alle Nachweise eines Subjekts als dicts (neueste Fassung zuletzt).

    Zusätzlich zu den Spalten enthält jedes dict `active` (bool) — abgeleitet
    aus `withdrawn_at`, damit die UI nicht selbst NULL prüfen muss.
    """
    conn = sqlite3.connect(str(db_path or DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM consents WHERE subject_type = ? AND subject_id = ? "
            "ORDER BY purpose, text_version, id",
            (subject_type, subject_id)).fetchall()
        return [{**dict(r), "active": r["withdrawn_at"] is None} for r in rows]
    finally:
        conn.close()
