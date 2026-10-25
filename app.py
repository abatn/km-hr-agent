"""
KM-HR-Agent – Streamlit Prototyp
=================================
Minimaler Web-Prototyp zum Testen aller 9 Skills.

Start:  streamlit run app.py
URL:    http://localhost:8501
"""

import streamlit as st
import os
import json
import sqlite3
import pymupdf as fitz  # PyMuPDF (fitz deprecated)
import sys
import subprocess
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import asyncio

# MCP-Server Import (pdf-reader)
MCP_PDF_DIR = Path(__file__).parent
sys.path.insert(0, str(MCP_PDF_DIR))

# Phase 0 (NiceGUI-Migration): framework-unabhängiger DB-Layer
from webui import db
from webui.logic import cefr_from_avg

# ─── Pfade ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
TESTDATEN = BASE_DIR / "testdaten"
ERGEBNISSE = BASE_DIR / "ergebnisse"
KNOWLEDGE = BASE_DIR / "knowledge"
DATA_DIR = BASE_DIR / "data"

# HR-Connector-Pfade (verifiziert 15.09.2026)
HR_BENCHMARK_SERVER = BASE_DIR / "connectors" / "hr-benchmark-server.py"
SALARY_DATA_SERVER = BASE_DIR / "connectors" / "salary-data-server.py"
PRESCREEN_CONFIG_SERVER = BASE_DIR / "connectors" / "prescreen-config-server.py"


def _mcp_connector_call(server_py: Path, tool: str, args: dict) -> dict:
    """Ruft ein Tool eines lokalen FastMCP-Servers auf (MCP-Protokoll: initialize → initialized → tools/call)."""
    try:
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05",
                               "capabilities": {},
                               "clientInfo": {"name": "km-hr-app", "version": "1.0"}}}
        initialized_note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        call_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": tool, "arguments": args}}
        proc = subprocess.Popen([sys.executable, str(server_py)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for r in (init_req, initialized_note, call_req):
            proc.stdin.write((json.dumps(r) + "\n").encode("utf-8"))
        proc.stdin.flush()
        resp_text = ""
        for line in proc.stdout:
            line = line.decode("utf-8", errors="replace").strip()
            if line.startswith("{"):
                try:
                    e = json.loads(line)
                    if e.get("id") == 2:
                        resp_text = e.get("result", {}).get("content", [{}])[0].get("text", "{}")
                        break
                except json.JSONDecodeError:
                    pass
        proc.stdin.close(); proc.terminate(); proc.wait(timeout=5)
        if resp_text.startswith("FEHLER") or resp_text.startswith("DRY-RUN"):
            return {}
        return json.loads(resp_text)
    except Exception:
        return {}


# Verzeichnisse erstellen
for d in [TESTDATEN, ERGEBNISSE, KNOWLEDGE, DATA_DIR]:
    d.mkdir(exist_ok=True)

# ─── Hilfsfunktionen ─────────────────────────────────────────────────

def read_file(path: str) -> str:
    """Liest eine Datei (TXT/MD) oder extrahiert Text aus PDF."""
    p = Path(path)
    if not p.exists():
        return f"[FEHLT] Datei nicht gefunden: {path}"
    if p.suffix.lower() == ".pdf":
        return extract_pdf_text(str(p))
    return p.read_text(encoding="utf-8", errors="replace")


def extract_pdf_text(pdf_path: str) -> str:
    """Extrahiert Text aus PDF via MCP pdf-reader oder PyMuPDF Fallback."""
    try:
        # Versuche MCP pdf-reader zu importieren
        from mcp_pdf_server import read_pdf_text, get_pdf_info, analyze_pdf_structure
        result = read_pdf_text(pdf_path)
        if result.startswith("OK|"):
            return result
        # Fallback zu PyMuPDF
    except (ImportError, Exception):
        pass
    
    # PyMuPDF Fallback
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        pages.append(f"--- Seite {i+1} ---\n{text}")
    doc.close()
    return "\n".join(pages)


def save_result(filename: str, content: str, subdir: str = "", base_dir: Path = None) -> str:
    """Speichert Ergebnis. base_dir=TESTDATEN für Profile, ERGEBNISSE für Tests."""
    base = base_dir if base_dir else ERGEBNISSE
    target = base / subdir if subdir else base
    target.mkdir(parents=True, exist_ok=True)
    filepath = target / filename
    filepath.write_text(content, encoding="utf-8")
    return str(filepath)


def list_profiles() -> list:
    """Listet alle Profile in testdaten/ auf."""
    profiles = []
    for f in sorted(TESTDATEN.glob("profil-*.md")):
        profiles.append(f)
    return profiles


def list_stellen() -> list:
    """Listet alle Stellenprofile in testdaten/ auf."""
    stellen = []
    for f in sorted(TESTDATEN.glob("stellenprofil-*.txt")):
        stellen.append(f)
    return stellen


# ─── Matching-Scoring (Phase 2, Spec: knowledge/lifecycle/matching-criteria.md) ──
# Gewichtung laut Doc: Kernkompetenzen 30 / Erfahrung 25 / Bildung 15 /
# Standort 10 / Branche 10 / Soft Skills 10 / Sprache 0 = 100
# (Quelle: BASELINE_GEWINCHTE, siehe knowledge/lifecycle/matching-criteria.md)
SKILL_SYNONYME = {
    "kubernetes": "k8s", "k8s": "kubernetes",
    "javascript": "js", "js": "javascript",
    "typescript": "ts", "ts": "typescript",
    "ci/cd": "ci-cd", "ci-cd": "ci/cd", "ci cd": "ci/cd",
    "github actions": "github-actions", "github-actions": "github actions",
    "node.js": "nodejs", "nodejs": "node.js", "node": "node.js",
    "postgresql": "postgres", "postgres": "postgresql",
    "amazon web services": "aws", "aws": "amazon web services",
    "google cloud platform": "gcp", "gcp": "google cloud platform",
    "microsoft azure": "azure", "azure": "microsoft azure",
}


def normalize_skill(skill: str) -> str:
    """Normalisiert einen Skill: lowercase, trim, Whitespace/Zeichen vereinheitlichen."""
    s = (skill or "").strip().lower()
    s = s.replace(".", "").replace("/", "-").replace("_", "-")
    s = " ".join(s.split())  # mehrfache Leerzeichen
    return s


def skills_match(job_skill: str, cand_skill: str) -> bool:
    """Vergleicht zwei Skills mit Synonym-Map und Normalisierung (Bug #2)."""
    nj, nc = normalize_skill(job_skill), normalize_skill(cand_skill)
    if nj == nc:
        return True
    syn = SKILL_SYNONYME.get(nj)
    if syn and normalize_skill(syn) == nc:
        return True
    return False


def score_kernkompetenzen(must_haves: list, k_skills: list) -> tuple:
    """Kernkompetenzen 0–30: Anteil der erfüllten Must-Have-Skills (mit Synonym-Match)."""
    if not must_haves:
        return 15, []  # keine Anforderungen -> neutrale Mittelpunktzahl
    matches = [m for m in must_haves if any(skills_match(m, ks) for ks in k_skills)]
    score = int(round(len(matches) / len(must_haves) * 30))
    return score, matches


def score_berufserfahrung(k_erf: float, job_erf: float, k_text: str = "") -> int:
    """Berufserfahrung 0–30 nach matching-criteria.md (Schema 25/20/15/10 + Bonus)."""
    job_erf = job_erf or 0
    basis = job_erf if job_erf > 0 else 3  # ohne Angabe: 3 Jahre als Referenz
    j = k_erf or 0
    if j >= basis + 2:
        score = 25
    elif j >= basis:
        score = 22
    elif j >= basis * 0.6:
        score = 15
    elif j >= basis * 0.3:
        score = 10
    else:
        score = 5
    t = (k_text or "").lower()
    if any(w in t for w in ("teamführung", "mentoring", "team lead", "führung")):
        score += 3
    if any(w in t for w in ("agil", "scrum", "kanban")):
        score += 2
    return min(score, 30)


def score_bildung(k_abschluss: str) -> int:
    """Bildung 0–15 nach matching-criteria.md."""
    a = (k_abschluss or "").strip().lower()
    if a in ("master", "m.sc", "m.sc.", "m.sc.", "diplom", "phd", "promotion", "dr."):
        return 15
    if a in ("bachelor", "b.sc", "b.sc.", "b.a", "b.a."):
        return 12
    if a:
        return 8
    return 0  # kein Abschluss angegeben -> 0 (statt 4)


def score_sprache(k_deutsch: str, k_englisch: str, job_deutsch: str, job_englisch: str) -> int:
    """Sprache 0–10: Deutsch + Englisch kombiniert (Bug #3: Englisch zählt mit)."""
    de_req = (job_deutsch or "").strip()
    en_req = (job_englisch or "").strip()
    de_order = ["", "keine anforderung", "a1", "a2", "b1", "b2", "c1", "c2", "muttersprache"]
    def lvl(v):
        return de_order.index((v or "").strip().lower()) if (v or "").strip().lower() in de_order else 0
    # Deutsch 6 Pkt: erfüllt = 6, knapp darunter (B1) = 4, darunter = 0
    k_de = lvl(k_deutsch)
    r_de = lvl(de_req)
    de_pts = 6 if r_de <= 1 or k_de >= r_de else (4 if k_de >= lvl("b1") else 0)
    # Englisch 4 Pkt: gefordert -> erfüllt = 4, B1+ ohne Anforderung = 3, sonst 0
    if en_req and en_req.lower() != "keine anforderung":
        en_pts = 4 if lvl(k_englisch) >= lvl(en_req) else 0
    else:
        en_pts = 3 if lvl(k_englisch) >= lvl("b1") else 0
    return de_pts + en_pts


def score_standort(k_standort: str, job_standort: str, stellentyp: str = "") -> int:
    """Standort 0–10 nach matching-criteria.md (Bug #6: Remote/Metrik-Abstufung)."""
    k = (k_standort or "").strip().lower()
    j = (job_standort or "").strip().lower()
    if "remote" in j or (stellentyp or "").lower() == "remote":
        return 10
    if k and j and k == j:
        return 8
    # heuristische Regional-Kürzel (z.B. 'bayern' vs 'münchen' nicht prüfbar ohne Geo-API)
    if k and j and (j in k or k in j):
        return 6
    return 2


def score_soft_skills(job_soft: str, k_soft: str) -> int:
    """Soft Skills 0–10: Anteil der geforderten Soft Skills (mit Synonym-Match)."""
    job_list = [s for s in (job_soft or "").split(",") if s.strip()]
    if not job_list:
        return 0  # keine Anforderungen -> 0 Punkte (kein Schein-Score)
    k_list = [s for s in (k_soft or "").split(",") if s.strip()]
    hits = sum(1 for js in job_list if any(skills_match(js, ks) for ks in k_list))
    return int(round(hits / len(job_list) * 10))


def gehalt_check(k_gehalt, gmin, gmax) -> str:
    """Gehaltsprüfung (Bug #1): max=0/'offen' korrekt behandeln, unbekannt ausweisen."""
    gmin = gmin or 0
    gmax = gmax or 0
    if k_gehalt is None or (k_gehalt or 0) <= 0:
        return "❓ unbekannt" if (gmin or gmax) else "✅ offen"
    if not gmin and not gmax:
        return "✅ passt (offen)"
    if gmax == 0 or gmax is None:
        # nur Mindestgehalt genannt: Kandidat darf max 20% drunter liegen
        return "✅ passt" if k_gehalt >= gmin * 0.8 else "⚠️ außerhalb Rahmen"
    if gmin == 0:
        # nur Maximalgehalt genannt
        return "✅ passt" if k_gehalt <= gmax * 1.1 else "⚠️ außerhalb Rahmen"
    # Spanne genannt: Kandidat innerhalb Spanne oder max 10% drüber
    # Connector: salary-data → calculate_salary_tolerance() (BambooHR-Formel)
    toleranz_min = 0.8  # Fallback (Design-Entscheidung)
    toleranz_max = 1.1  # Fallback (Design-Entscheidung)
    midpoint = (gmin + gmax) / 2
    try:
        tol = _mcp_connector_call(SALARY_DATA_SERVER, "calculate_salary_tolerance",
                                   {"midpoint": midpoint, "tolerance_percent": 0.15})
        if tol and "tolerance_min" in tol and "tolerance_max" in tol:
            toleranz_min = tol["tolerance_min"] / midpoint if midpoint else 0.8
            toleranz_max = tol["tolerance_max"] / midpoint if midpoint else 1.1
    except Exception:
        pass
    return "✅ passt" if (k_gehalt <= gmax * toleranz_max and k_gehalt >= gmin * toleranz_min) else "⚠️ außerhalb Rahmen"


# Kategorie-Maxima (für Skalierung: punkte_i = kategorie_score / max_i × anteil_i)
KATEGORIE_MAX = {
    "kern": 30, "erfahrung": 30, "bildung": 15, "standort": 10,
    "branche": 10, "soft": 10, "sprache": 10,
}

# Baseline-Rohgewichte (knowledge/lifecycle/matching-criteria.md, Phase 4 – Summe 100)
BASELINE_GEWINCHTE = {
    "kern": 30, "erfahrung": 25, "bildung": 15, "standort": 10,
    "branche": 10, "soft": 10, "sprache": 0,
}

# Caps: max. Abweichung vom Baseline-Wert (Sprache: Baseline 0 → Max 15)
GEWICHT_CAP_ABWEICHUNG = 15
GEWICHT_CAP_SPRACHE_MAX = 15

# Kategorie-Keys der DB-Kategorien in gewichtung_historie
DB_KATEGORIE_MAP = {
    "Berufserfahrung": "erfahrung",
    "Sprache": "sprache",
}


def get_current_weights(conn=None) -> dict:
    """Phase 4: Liest Rohgewichte aus gewichtung_historie (letzte Zeile je Kategorie)
    und normalisiert auf Summe 100. Leere/fehlende Historie → Baseline.
    Quelle der Wahrheit: DB-first (Spec: knowledge/lifecycle/matching-criteria.md).
    """
    own_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DATA_DIR / "feedback.db"))
        own_conn = True
    roh = dict(BASELINE_GEWINCHTE)
    try:
        cur = conn.execute("""SELECT kategorie, neue_gewichtung FROM gewichtung_historie gh
            WHERE id = (SELECT MAX(id) FROM gewichtung_historie WHERE kategorie = gh.kategorie)""")
        for kategorie_db, neue in cur.fetchall():
            key = DB_KATEGORIE_MAP.get(kategorie_db)
            if key and isinstance(neue, (int, float)) and neue >= 0:
                roh[key] = int(neue)
    except sqlite3.Error:
        pass  # Tabelle fehlt/lesbar nicht → Baseline
    finally:
        if own_conn:
            conn.close()
    # Caps anwenden
    for key, base in BASELINE_GEWINCHTE.items():
        if key == "sprache":
            roh[key] = max(0, min(roh[key], GEWICHT_CAP_SPRACHE_MAX))
        else:
            roh[key] = max(max(0, base - GEWICHT_CAP_ABWEICHUNG), min(roh[key], base + GEWICHT_CAP_ABWEICHUNG))
    # Normalisierung auf Summe 100
    s = sum(roh.values()) or 1
    anteile = {k: v / s * 100 for k, v in roh.items()}
    return anteile


def adjust_weights_from_feedback(eingeladen: str, score: int, grund: str, conn) -> str:
    """Phase 4 (4.2/4.3): Geschlossener Loop – passt Rohgewichte nach Feedback an.
    Erfolg (eingeladen='Ja' UND score>=80): Berufserfahrung +5
    Misserfolg (eingeladen='Nein' UND score<70): Sprache +10
    Caps: Baseline+15 (Sprache max 15). Gibt Meldung zurück; NULL-Änderung → ''.
    """
    # Aktuelle Rohgewichte aus DB (ohne Normalisierung – Roh-Ebene)
    roh = dict(BASELINE_GEWINCHTE)
    try:
        cur = conn.execute("""SELECT kategorie, neue_gewichtung FROM gewichtung_historie gh
            WHERE id = (SELECT MAX(id) FROM gewichtung_historie WHERE kategorie = gh.kategorie)""")
        for kategorie_db, neue in cur.fetchall():
            key = DB_KATEGORIE_MAP.get(kategorie_db)
            if key and isinstance(neue, (int, float)) and neue >= 0:
                roh[key] = int(neue)
    except sqlite3.Error:
        pass

    ziel, delta = None, 0
    # ⚠️ Design-Entscheidung (15.09.2026): Schwellen 80/70 haben keine externe Quelle.
    # Alternative: Schwellen aus eigener Datenanalyse ableiten
    # Validierung: Nach 20+ Feedback-Einträgen prüfen ob die Schwellen sinnvoll trennen
    # Connector: hr-benchmark → get_score_category() für Feedback-Schwellen
    erfahrungs_schwelle = 80  # Fallback
    sprache_schwelle = 70     # Fallback
    try:
        cat = _mcp_connector_call(HR_BENCHMARK_SERVER, "get_score_category", {"score": score})
        if cat and "category" in cat:
            if cat["category"] == "Strong":
                erfahrungs_schwelle = 80
            elif cat["category"] == "Consider":
                erfahrungs_schwelle = 60
                sprache_schwelle = 60
    except Exception:
        pass
    if eingeladen == "Ja" and score >= erfahrungs_schwelle:
        ziel, delta = "erfahrung", 5
    elif eingeladen == "Nein" and score < sprache_schwelle:
        ziel, delta = "sprache", 10
    if ziel is None:
        return ""

    base = BASELINE_GEWINCHTE[ziel]
    if ziel == "sprache":
        cap = GEWICHT_CAP_SPRACHE_MAX
    else:
        cap = base + GEWICHT_CAP_ABWEICHUNG
    neu = roh[ziel] + delta
    if neu > cap:
        if roh[ziel] >= cap:
            return f"ℹ️ Cap erreicht ({kategorie_label(ziel)} = {cap}) – keine Anpassung."
        neu = cap
    if neu == roh[ziel]:
        return ""

    label = {v: k for k, v in DB_KATEGORIE_MAP.items()}[ziel]
    conn.execute("""INSERT INTO gewichtung_historie
        (kategorie, alte_gewichtung, neue_gewichtung, grund, feedback_anzahl)
        VALUES (?, ?, ?, ?, 1)""", (label, roh[ziel], neu, grund))
    conn.commit()
    return f"✅ {label}: {roh[ziel]} → {neu} (Rohgewicht, normalisiert auf 100)"


def kategorie_label(key: str) -> str:
    return {v: k for k, v in DB_KATEGORIE_MAP.items()}.get(key, key)


# ─── Agent-Automatisierung (Phase 5, Spec v3): Queue + Hooks ─────────
# Spec: knowledge/system/agent-automation.md – das Portal schreibt NUR Tasks in die
# agent_tasks-Queue; die Ausführung übernimmt der Hintergrund-Runner
# (scripts/agent-runner.py) über die Projekt-MCP-Connectors + opencode (LLM).
AGENT_TASKS_DB = DATA_DIR / "feedback.db"


def init_agent_tasks_table() -> None:
    """Legt die agent_tasks-Tabelle an (idempotent, bei App-Start).
    Erweitertes Schema (v3): result_json speichert Runner-Ausgaben (Jitsi-URL,
    ICS-Pfad, Mail-Status) für die Portal-Sichten.

    Parität zu `webui/db.py::init_agent_tasks_table` (21.10.2026): die
    idempotente Spalten-Ergänzung (ALTER) fehlte hier — ein Altbestand ohne
    `started_at` wäre im Runner-Claim gescheitert. `CREATE TABLE IF NOT EXISTS`
    ändert eine bestehende Tabelle nicht."""
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
    # Idempotente Spalten-Ergänzung (Altbestand) — Parität zu webui/db.py.
    vorhanden = {r[1] for r in c.execute("PRAGMA table_info(agent_tasks)")}
    for spalte, typ in (("started_at", "TIMESTAMP"), ("finished_at", "TIMESTAMP"),
                        ("result_json", "TEXT"), ("result_path", "TEXT"),
                        ("error_text", "TEXT"), ("attempts", "INTEGER DEFAULT 0")):
        if spalte not in vorhanden:
            c.execute(f"ALTER TABLE agent_tasks ADD COLUMN {spalte} {typ}")
    conn.commit()
    conn.close()


def queue_agent_task(task_type: str, payload: dict) -> int | None:
    """Schreibt einen Agent-Task in die Queue (idempotent pro Tag+Typ+Applikation).
    Verhindert Doppel-Tasks bei Streamlit-Reruns. Fehlschlag blockiert die App
    nie (Hook-Ausnahmen werden gefangen, Spec §2/§11)."""
    try:
        conn = sqlite3.connect(str(AGENT_TASKS_DB))
        c = conn.cursor()
        app_id = payload.get("application_id")
        # ZEITZONEN-FIX (22.10.2026): Paritaet zu webui/db.py - `created_at`
        # ist UTC (SQLite CURRENT_TIMESTAMP), die Dedupe-Grenze nutzt jetzt
        # ebenfalls UTC (sonst Doppel-Insert im Fenster 00:00-02:00 lokal).
        heute = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if app_id is not None:
            c.execute("""SELECT id FROM agent_tasks
                WHERE task_type = ? AND payload LIKE ?
                  AND created_at >= ?""",
                (task_type, f'%"application_id": {app_id}%', f"{heute} 00:00:00"))
        else:
            c.execute("""SELECT id FROM agent_tasks
                WHERE task_type = ? AND payload = ? AND created_at >= ?""",
                (task_type, json.dumps(payload, ensure_ascii=False, sort_keys=True), f"{heute} 00:00:00"))
        if c.fetchone():
            conn.close()
            return None  # bereits gequeued (heute)
        c.execute("INSERT INTO agent_tasks (task_type, payload) VALUES (?, ?)",
                  (task_type, json.dumps(payload, ensure_ascii=False, sort_keys=True)))
        tid = c.lastrowid
        conn.commit()
        conn.close()
        print(f"[Agent-Queue] Task #{tid} ({task_type}) gequeued")
        return tid
    except Exception as e:  # App läuft weiter, auch wenn die Queue nicht schreibbar ist
        print(f"[Agent-Queue] Fehler (App läuft weiter): {e}")
        return None


def get_invitation_artifacts(application_id: int) -> dict | None:
    """Lädt die Einladungs-Artefakte (Jitsi, ICS, Termin) aus dem erledigten
    create_invitation-Task (Phase 5). Wird von Kandidaten- UND HR-Sicht genutzt,
    damit HR denselben Kalendereintrag herunterladen kann wie der Kandidat."""
    try:
        conn = sqlite3.connect(str(AGENT_TASKS_DB))
        cur = conn.cursor()
        cur.execute("""SELECT result_json FROM agent_tasks
            WHERE task_type = 'create_invitation' AND status = 'done'
              AND payload LIKE ? ORDER BY id DESC LIMIT 1""",
            (f'%"application_id": {application_id}%',))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def render_hr_ics_download(application_id: int) -> None:
    """HR-Sicht: ICS-Download für den HR-Kalender (direkt neben der Kandidaten-
    Einladung, Spec §5). Zeigt Jitsi-URL + Termin, wenn der Agent eingeladen hat."""
    _art = get_invitation_artifacts(application_id)
    if not _art:
        return  # noch kein create_invitation-Task erledigt – nichts anzeigen
    _jitsi = _art.get("jitsi_url") or _art.get("meet_url")
    _ics = _art.get("ics_path")
    _termin = _art.get("termin", "")
    st.markdown("---")
    st.markdown("**📹 Einladung (Kandidat wurde benachrichtigt):**"
                + (f" {_termin}" if _termin else ""))
    if _jitsi:
        st.caption(f"🔗 {_jitsi}")
    if _ics and Path(str(_ics)).exists():
        with open(str(_ics), "rb") as _icsf:
            st.download_button("📅 Termin in Kalender speichern (.ics) – HR",
                               _icsf.read(), file_name=Path(str(_ics)).name,
                               mime="text/calendar", key=f"ics_hr_{application_id}")
    else:
        st.caption("ℹ️ ICS-Datei noch nicht vorhanden (Dry-Run schreibt keine Dateien).")


def ensure_agent_runner() -> None:
    """Startet den Hintergrund-Runner einmalig, falls er nicht läuft (Spec §4).
    Opt-out via Env KMHR_RUNNER_AUTOSTART=0. PID-File: data/agent-runner.pid."""
    import os as _os
    if _os.environ.get("KMHR_RUNNER_AUTOSTART") == "0":
        return
    pid_file = DATA_DIR / "agent-runner.pid"
    try:
        if pid_file.exists():
            pid = int(pid_file.read_text().strip())
            _os.kill(pid, 0)  # läuft noch?
            return
    except (ProcessLookupError, ValueError, PermissionError):
        pass  # veraltete PID-File -> Runner starten
    except OSError:
        return
    try:
        import subprocess as _sp
        venv_py = Path(".venv-streamlit/bin/python3")
        py = str(venv_py) if venv_py.exists() else "python3"
        _sp.Popen([py, str(Path("scripts/agent-runner.py"))],
                  cwd=str(Path(".")), stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                  start_new_session=True)
        print("[Agent-Runner] Hintergrund-Runner gestartet")
    except Exception as e:
        print(f"[Agent-Runner] Autostart fehlgeschlagen (App läuft weiter): {e}")


def _hr_email_adresse(conn) -> str | None:
    """HR-Benachrichtigungs-Empfänger: kontakt_email der Stelle (Spec §8.2)."""
    try:
        c = conn.cursor()
        c.execute("SELECT kontakt_email FROM employers ORDER BY id LIMIT 1")
        r = c.fetchone()
        return r[0] if r and r[0] else None
    except Exception:
        return None


# ─── DSGVO-Cleanup (Phase 4.5): 6-Monats-Löschung Bewerbungsdaten ────
DSGVO_FRIST_TAGE = 183  # 6 Monate (Spec: knowledge/legal/gdpr-policy.md, application-status.md)
DSGVO_FINALE_STATUS = ("abgelehnt", "eingestellt", "zurückgezogen")


def dsgvo_cleanup() -> dict:
    """Phase 4.5: Löscht Bewerbungsdaten 6 Monate nach Prozessende (Art. 17 DSGVO).
    Prozessende = letzter Statuswechsel (aktualisiert_am) bei finalem Status
    (abgelehnt / eingestellt / zurückgezogen). Aktive Bewerbungen sind nie löschfähig.
    Löscht applications + zugehörige application_status_history-Zeilen.
    Fehlschlag blockiert die App nicht (Aufrufer fängt Exceptions).
    """
    conn = sqlite3.connect(str(DATA_DIR / "feedback.db"))
    c = conn.cursor()
    c.execute("""SELECT id FROM applications
        WHERE status IN (?, ?, ?)
          AND aktualisiert_am IS NOT NULL
          AND CAST(strftime('%s', 'now') AS INTEGER) - CAST(strftime('%s', aktualisiert_am) AS INTEGER) >= ?""",
        (*DSGVO_FINALE_STATUS, DSGVO_FRIST_TAGE * 86400))
    ids = [r[0] for r in c.fetchall()]
    if ids:
        marks = ",".join("?" for _ in ids)
        c.execute(f"DELETE FROM application_status_history WHERE application_id IN ({marks})", ids)
        c.execute(f"DELETE FROM applications WHERE id IN ({marks})", ids)
        # Phase 5 (Spec §9): agent_tasks-Zeilen mit Bewerbungsbezug mitlöschen
        c.execute(f"DELETE FROM agent_tasks WHERE payload LIKE ?", (f'%"application_id": {ids[0]}%',))
        for i in ids[1:]:
            c.execute("DELETE FROM agent_tasks WHERE payload LIKE ?", (f'%"application_id": {i}%',))
        conn.commit()
    # Spec v6.1: candidate_documents + Dateien löschen (gdpr-policy 'Bewerbungsdaten: Zeugnisse' –
    # 6 Monate). Regel: Dokument wird gelöscht, wenn der Kandidat KEINE aktive Bewerbung hat UND
    # das Dokument selbst älter als die Frist ist (hochgeladen_am).
    try:
        gel_doks = 0
        c.execute("""SELECT cd.id, cd.datei_pfad FROM candidate_documents cd
            WHERE cd.candidate_id NOT IN (
                SELECT DISTINCT candidate_id FROM applications
                WHERE status NOT IN (?, ?, ?))
              AND CAST(strftime('%s', 'now') AS INTEGER)
                  - CAST(strftime('%s', cd.hochgeladen_am) AS INTEGER) >= ?""",
            (*DSGVO_FINALE_STATUS, DSGVO_FRIST_TAGE * 86400))
        for d_id, d_pfad in c.fetchall():
            try:
                Path(d_pfad).unlink(missing_ok=True)
            except Exception:
                pass
            c.execute("DELETE FROM candidate_documents WHERE id = ?", (d_id,))
            gel_doks += 1
        if gel_doks:
            conn.commit()
    except Exception:
        pass  # Cleanup blockiert die App nie
    conn.close()
    return {"geloeschte_bewerbungen": len(ids), "geloeschte_dokumente": gel_doks}


def run_dsgvo_cleanup_once() -> dict:
    """Führt den Cleanup max. 1x pro Session/Tag aus (App-Start-Hook)."""
    if st.session_state.get("dsgvo_cleanup_done") == datetime.now().strftime("%Y-%m-%d"):
        return {"geloeschte_bewerbungen": 0, "skip": True}
    try:
        result = dsgvo_cleanup()
        st.session_state["dsgvo_cleanup_done"] = datetime.now().strftime("%Y-%m-%d")
        if result["geloeschte_bewerbungen"]:
            print(f"[DSGVO-Cleanup] {result['geloeschte_bewerbungen']} Bewerbungen gelöscht (6-Monats-Frist)")
        return result
    except Exception as e:  # App darf nie am Cleanup scheitern
        print(f"[DSGVO-Cleanup] Fehler (App läuft weiter): {e}")
        return {"geloeschte_bewerbungen": 0, "fehler": str(e)}


def score_branche(branche: str, k_text: str) -> int:
    """Branchenkenntnis 0–10 (Phase 4.6): Arbeitgeber-Branche vs. Kandidaten-CV.
    Spec: knowledge/lifecycle/matching-criteria.md (Tabelle). Neutrale Fallbacks, wenn
    Branche oder CV-Text fehlen.
    """
    lt = (k_text or "").lower()
    it_treff = any(w in lt for w in ("devops", "cloud", "it-projekt", "software",
                                     "netzwerk", "infrastruktur", "datenbank", "entwickl"))
    if not lt:
        return 0  # kein CV-Text -> 0 (kein Schein-Score)
    b = (branche or "").strip().lower()
    if not b:
        # keine Branche angegeben -> bisherige Heuristik als Fallback
        return 10 if it_treff else 6
    it_nahe = ("telekom", "telekommunikation", "engineering", "technolog", "informatik", "software")
    if b == "it" or any(w in b for w in it_nahe):
        return 10 if it_treff else 4
    # fremde Branche
    return 6 if it_treff else 2


def berechne_match_score(k: dict, j: dict) -> dict:
    """Gesamt-Score 0–100 nach knowledge/lifecycle/matching-criteria.md + Kategorie.
    Phase 4: Kategorie-Scores werden mit den aktuellen (feedback-getriebenen,
    normalisierten) Gewichten skaliert: punkte_i = score_i/max_i × anteil_i.
    k: Kandidaten-Dict (hard_skills, soft_skills, berufserfahrung_jahre, abschluss,
       deutsch, englisch, standort, lebenslauf_text)
    j: Job-Dict (hard_skills, soft_skills, berufserfahrung_jahre, deutsch_level,
       englisch_level, standort, stellentyp)
    """
    anteile = get_current_weights()
    must_haves = [s for s in (j.get("hard_skills") or "").split(",") if s.strip()]
    k_skills = [s for s in (k.get("hard_skills") or "").split(",") if s.strip()]
    kern, matches = score_kernkompetenzen(must_haves, k_skills)
    erfahrung = score_berufserfahrung(k.get("berufserfahrung_jahre"), j.get("berufserfahrung_jahre"), k.get("lebenslauf_text") or "")
    bildung = score_bildung(k.get("abschluss"))
    standort = score_standort(k.get("standort"), j.get("standort"), j.get("stellentyp"))
    soft = score_soft_skills(j.get("soft_skills"), k.get("soft_skills"))
    sprache = score_sprache(k.get("deutsch"), k.get("englisch"), j.get("deutsch_level"), j.get("englisch_level"))
    # Branchenkenntnis 0–10 (Phase 4.6): Arbeitgeber-Branche vs. Kandidaten-CV
    branche = score_branche(j.get("branche"), k.get("lebenslauf_text") or "")
    # Phase 4: gewichtet skalieren (Kategorie-Score / Kategorie-Max × Anteil)
    roh_scores = {"kern": kern, "erfahrung": erfahrung, "bildung": bildung,
                  "standort": standort, "branche": branche, "soft": soft, "sprache": sprache}
    skaliert = {key: (val / KATEGORIE_MAX[key]) * anteile.get(key, 0)
                for key, val in roh_scores.items()}
    total = min(int(round(sum(skaliert.values()))), 100)
    # Connector: hr-benchmark → get_score_category() (ZYTHR-Schwellen)
    hervorragend_schwelle = 90  # Fallback (Design-Entscheidung)
    gut_schwelle = 75          # Fallback (Design-Entscheidung)
    bedingt_schwelle = 60      # Fallback (Design-Entscheidung)
    schwach_schwelle = 40      # Fallback (Design-Entscheidung)
    try:
        cat = _mcp_connector_call(HR_BENCHMARK_SERVER, "get_score_category", {"score": total})
        if cat and "category" in cat:
            cat_map = {"Strong": 90, "Consider": 60}
            if cat["category"] == "Strong":
                hervorragend_schwelle = cat_map.get("Strong", 90)
            elif cat["category"] == "Consider":
                bedingt_schwelle = cat_map.get("Consider", 60)
    except Exception:
        pass
    if total >= hervorragend_schwelle:
        kategorie = "Hervorragend"
    elif total >= gut_schwelle:
        kategorie = "Gut"
    elif total >= bedingt_schwelle:
        kategorie = "Bedingt"
    elif total >= schwach_schwelle:
        kategorie = "Schwach"
    else:
        kategorie = "Nicht passend"
    # ─── Explainability Layer (SphinxATS-Pattern, 16.09.2026) ──────────
    # Quelle: knowledge/lifecycle/matching-criteria.md "Explainability Layer"
    # Jede Kategorie bekommt eine menschenlesbare Begründung.
    must_haves_str = ", ".join(f"{m} {'✅' if m in [mt for mt in matches] else '❌'}" for m in must_haves[:6]) if must_haves else "–"
    erf_j = k.get("berufserfahrung_jahre") or 0
    erf_req = j.get("berufserfahrung_jahre") or 0
    erklaerung = {
        "kern": f"{len(matches)}/{len(must_haves)} Skills: {must_haves_str}" if must_haves else "Keine Skills gefordert",
        "erfahrung": f"{erf_j}J Erfahrung, Stelle: {erf_req}J → {int(erf_j/max(erf_req,1)*100)}%" if erf_req else f"{erf_j}J Erfahrung (keine Angabe)",
        "bildung": f"{(k.get('abschluss') or '–')} → {bildung}/15",
        "standort": f"{'Remote' if 'remote' in (j.get('standort') or '').lower() else k.get('standort') or '–'} → {standort}/10",
        "branche": f"Branche '{j.get('branche') or '–'}' → {branche}/10",
        "soft": f"{soft}/10 ({len([s for s in (j.get('soft_skills') or '').split(',') if s.strip()])} gefordert)" if j.get("soft_skills") else "Keine Soft-Skills gefordert",
        "sprache": f"DE {k.get('deutsch') or '–'}/{j.get('deutsch_level') or '–'}, EN {k.get('englisch') or '–'}/{j.get('englisch_level') or '–'} → {sprache}/10",
    }
    return {
        "total": total, "kategorie": kategorie, "matches": matches,
        "kern": kern, "erfahrung": erfahrung, "bildung": bildung,
        "standort": standort, "branche": branche, "soft": soft, "sprache": sprache,
        "anteile": {kk: round(vv, 1) for kk, vv in anteile.items()},
        "erklaerung": erklaerung,
    }


# ─── Seitenstruktur ───────────────────────────────────────────────────

st.set_page_config(
    page_title="KM-HR-Agent",
    page_icon="🤖",
    layout="wide"
)

# ─── Login-Schutz (Jobportal-Prinzip) ────────────────────────────────
# Unregistrierte User können NICHTS machen (wie ein echtes Jobportal)

if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.user_cand_id = None

# Arbeitgeber-Session (Employer Portal)
if "employer_logged_in" not in st.session_state:
    st.session_state.employer_logged_in = False
    st.session_state.employer_email = None
    st.session_state.employer_firma = None
    st.session_state.employer_id = None

# DSGVO-Cleanup (Phase 4.5): 6-Monats-Löschung, max. 1x pro Tag, fehlersicher
_dsgvo_ergebnis = run_dsgvo_cleanup_once()

# Agent-Automatisierung (Phase 5): Queue-Tabelle anlegen + Runner sicherstellen
try:
    init_agent_tasks_table()
except Exception as _e:
    print(f"[Agent-Queue] Tabellen-Init fehlgeschlagen (App läuft weiter): {_e}")
ensure_agent_runner()

# ─── ADMIN-Session (v4.5/v3.1, knowledge/system/access-control.md §3.4) ─────
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False


def login_admin(admin_id, email):
    """Admin-Login durchführen."""
    st.session_state.admin_logged_in = True
    st.session_state.admin_id = admin_id
    st.session_state.admin_email = email


def logout_admin():
    """Admin-Logout durchführen."""
    st.session_state.admin_logged_in = False
    st.session_state.admin_id = None
    st.session_state.admin_email = None


def check_admin_login():
    """Prüft ob Admin eingeloggt ist (admins-Tabelle, Option 2)."""
    return st.session_state.admin_logged_in


def login_employer(employer_id, email, firma):
    """Arbeitgeber-Login durchführen."""
    st.session_state.employer_logged_in = True
    st.session_state.employer_id = employer_id
    st.session_state.employer_email = email
    st.session_state.employer_firma = firma

def logout_employer():
    """Arbeitgeber-Logout durchführen."""
    st.session_state.employer_logged_in = False
    st.session_state.employer_id = None
    st.session_state.employer_email = None
    st.session_state.employer_firma = None

def check_employer_login():
    """Prüft ob Arbeitgeber eingeloggt ist."""
    return st.session_state.employer_logged_in

def login_user(email, name, cand_id):
    """Login durchführen."""
    st.session_state.user_logged_in = True
    st.session_state.user_email = email
    st.session_state.user_name = name
    st.session_state.user_cand_id = cand_id
    st.session_state.user_last_activity = datetime.now()

def logout_user():
    """Logout durchführen."""
    st.session_state.user_logged_in = False
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.user_cand_id = None
    st.session_state.user_last_activity = None

def check_login():
    """Prüft ob User eingeloggt ist (mit 30-Min-Timeout)."""
    if not st.session_state.user_logged_in:
        return False
    # Session-Timeout: 30 Minuten Inaktivität
    last_activity = st.session_state.get("user_last_activity")
    if last_activity:
        elapsed = (datetime.now() - last_activity).total_seconds() / 60
        if elapsed > 30:
            logout_user()
            return False
    # Aktualisiere Zeitstempel
    st.session_state.user_last_activity = datetime.now()
    return True

def current_role():
    """Rollenmodell v4.5/v3.1 (knowledge/system/access-control.md): guest | candidate | employer | admin."""
    if check_admin_login():
        return "admin"
    if check_employer_login():
        return "employer"
    if check_login():
        return "candidate"
    return "guest"


# ─── Passwort-Hashing (Phase 3.2: SHA256 → argon2id Migration) ──────────

def _hash_password_argon2id(password: str) -> str:
    """Hashed Passwort mit argon2id."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    return ph.hash(password)

def _verify_password_argon2id(password: str, hash_str: str) -> bool:
    """Verifiziert Passwort mit argon2id-Hash."""
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
    ph = PasswordHasher()
    try:
        return ph.verify(hash_str, password)
    except (VerifyMismatchError, InvalidHashError):
        return False

def _is_sha256_hash(hash_str: str) -> bool:
    """Prüft ob ein Hash ein alter SHA256-Hash ist (64 hex-Zeichen)."""
    return len(hash_str) == 64 and all(c in '0123456789abcdef' for c in hash_str)

def _agent_status_symbol(status: str) -> str:
    """Duplikat-Bereinigung (Phase 0): war inline-lambda in der HR-Kandidaten-
    Sicht (app.py:3109). Zentrale Symbolik für Agent-Task-Status."""
    return "✅" if status == "done" else ("⏳" if status in ("pending", "running") else ("❌" if status == "failed" else "–"))


def _migrate_password_if_needed(conn, user_id: int, password: str, table: str = "candidates") -> None:
    """Migration: Wenn alter SHA256-Hash → neu hashen mit argon2id und speichern."""
    import hashlib
    c = conn.cursor()
    c.execute(f"SELECT password_hash FROM {table} WHERE id = ?", (user_id,))
    row = c.fetchone()
    if row and _is_sha256_hash(row[0]):
        old_hash = row[0]
        # Verifiziere mit altem SHA256
        if hashlib.sha256(password.encode()).hexdigest() == old_hash:
            # Neu hashen mit argon2id
            new_hash = _hash_password_argon2id(password)
            c.execute(f"UPDATE {table} SET password_hash = ? WHERE id = ?", (new_hash, user_id))
            conn.commit()

# ─── Login-Bildschirm (wenn nicht eingeloggt) ────────────────────────

if not check_login() and not check_employer_login() and not check_admin_login():
    st.title("🤖 KM-HR-Agent – Jobportal")
    st.markdown("---")
    st.markdown("### 🔒 Bitte melden Sie sich an")
    st.markdown("Nur registrierte Kandidaten können das Portal nutzen.")

    tab_login, tab_register, tab_employer_login, tab_employer_register, tab_admin_login = st.tabs(
        ["🔑 Login", "📝 Registrieren", "🏢 Arbeitgeber-Login", "🏢 Arbeitgeber-Registrieren", "🛡️ Admin"]
    )

    with tab_login:
        login_email = st.text_input("E-Mail:", key="login_email")
        login_password = st.text_input("Passwort:", type="password", key="login_password")

        if st.button("🔑 Einloggen", key="login_btn"):
            if not login_email or not login_password:
                st.error("❌ Bitte E-Mail und Passwort eingeben.")
            else:
                db_path = DATA_DIR / "feedback.db"
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                c.execute("SELECT id, name, email, password_hash FROM candidates WHERE email = ?", (login_email,))
                user = c.fetchone()

                import hashlib
                pw_hash = hashlib.sha256(login_password.encode()).hexdigest()
                if user and user[3] == pw_hash:
                    # Migration: SHA256 → argon2id
                    _migrate_password_if_needed(conn, user[0], login_password, "candidates")
                    login_user(user[2], user[1], user[0])
                    st.success(f"✅ Willkommen, {user[1]}!")
                    st.rerun()
                elif user and _is_sha256_hash(user[3]) and hashlib.sha256(login_password.encode()).hexdigest() == user[3]:
                    # Fallback: Falls Migration fehlgeschlagen
                    _migrate_password_if_needed(conn, user[0], login_password, "candidates")
                    login_user(user[2], user[1], user[0])
                    st.success(f"✅ Willkommen, {user[1]}!")
                    st.rerun()
                elif user and _verify_password_argon2id(login_password, user[3]):
                    login_user(user[2], user[1], user[0])
                    st.success(f"✅ Willkommen, {user[1]}!")
                    st.rerun()
                conn.close()
                # Hinweis, falls die E-Mail ein Arbeitgeber-Account ist
                try:
                    c2 = sqlite3.connect(str(db_path))
                    cu = c2.cursor()
                    cu.execute("SELECT firma FROM employers WHERE email = ?", (login_email,))
                    emp_hint = cu.fetchone()
                    c2.close()
                    if emp_hint:
                        st.error(f"❌ Falsche E-Mail oder Passwort. 💡 '{login_email}' ist ein Arbeitgeber-Account ({emp_hint[0]}) – bitte im Tab '🏢 Arbeitgeber-Login' einloggen.")
                    else:
                        st.error("❌ Falsche E-Mail oder Passwort.")
                except Exception:
                    st.error("❌ Falsche E-Mail oder Passwort.")

    with tab_register:
        reg_email = st.text_input("E-Mail:", key="reg_email_login")
        reg_name = st.text_input("Name:", key="reg_name_login")
        reg_password = st.text_input("Passwort:", type="password", key="reg_password_login")

        if st.button("📝 Registrieren", key="reg_btn_login"):
            if not reg_email or not reg_name or not reg_password:
                st.error("❌ Alle Felder ausfüllen!")
            elif len(reg_password) < 8:
                st.error("❌ Passwort mindestens 8 Zeichen!")
            else:
                db_path = DATA_DIR / "feedback.db"
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                try:
                    pw_hash = _hash_password_argon2id(reg_password)
                    c.execute("INSERT INTO candidates (email, password_hash, name) VALUES (?, ?, ?)",
                              (reg_email, pw_hash, reg_name))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Registriert: {reg_name}")
                    st.info("👉 Bitte jetzt einloggen.")
                except sqlite3.IntegrityError:
                    conn.close()
                    st.error("❌ E-Mail bereits vorhanden!")

    with tab_employer_login:
        emp_login_email = st.text_input("E-Mail:", key="emp_login_email")
        emp_login_password = st.text_input("Passwort:", type="password", key="emp_login_password")

        if st.button("🏢 Als Arbeitgeber einloggen", key="emp_login_btn"):
            if not emp_login_email or not emp_login_password:
                st.error("❌ Bitte E-Mail und Passwort eingeben.")
            else:
                db_path = DATA_DIR / "feedback.db"
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                c.execute("CREATE TABLE IF NOT EXISTS employers (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, firma TEXT NOT NULL, kontaktperson TEXT NOT NULL, branche TEXT, groesse TEXT, standort TEXT, website TEXT, beschreibung TEXT, telefon TEXT, kontakt_email TEXT, registriert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP, aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
                c.execute("SELECT id, firma, email, password_hash FROM employers WHERE email = ?", (emp_login_email,))
                emp = c.fetchone()

                import hashlib
                pw_hash = hashlib.sha256(emp_login_password.encode()).hexdigest()
                if emp and emp[3] == pw_hash:
                    # Migration: SHA256 → argon2id
                    _migrate_password_if_needed(conn, emp[0], emp_login_password, "employers")
                    login_employer(emp[0], emp[2], emp[1])
                    st.success(f"✅ Willkommen, {emp[1]}!")
                    st.rerun()
                elif emp and _is_sha256_hash(emp[3]) and hashlib.sha256(emp_login_password.encode()).hexdigest() == emp[3]:
                    # Fallback: Falls Migration fehlgeschlagen
                    _migrate_password_if_needed(conn, emp[0], emp_login_password, "employers")
                    login_employer(emp[0], emp[2], emp[1])
                    st.success(f"✅ Willkommen, {emp[1]}!")
                    st.rerun()
                elif emp and _verify_password_argon2id(emp_login_password, emp[3]):
                    login_employer(emp[0], emp[2], emp[1])
                    st.success(f"✅ Willkommen, {emp[1]}!")
                    st.rerun()
                else:
                    st.error("❌ Falsche E-Mail oder Passwort.")
                conn.close()

    with tab_employer_register:
        emp_reg_email = st.text_input("Firmen-E-Mail:", key="emp_reg_email")
        emp_reg_firma = st.text_input("Firma:", key="emp_reg_firma")
        emp_reg_kontakt = st.text_input("Kontaktperson:", key="emp_reg_kontakt")
        emp_reg_password = st.text_input("Passwort:", type="password", key="emp_reg_password")

        if st.button("🏢 Als Arbeitgeber registrieren", key="emp_reg_btn"):
            if not emp_reg_email or not emp_reg_firma or not emp_reg_kontakt or not emp_reg_password:
                st.error("❌ Alle Felder ausfüllen!")
            elif len(emp_reg_password) < 8:
                st.error("❌ Passwort mindestens 8 Zeichen!")
            else:
                db_path = DATA_DIR / "feedback.db"
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                c.execute("CREATE TABLE IF NOT EXISTS employers (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, firma TEXT NOT NULL, kontaktperson TEXT NOT NULL, branche TEXT, groesse TEXT, standort TEXT, website TEXT, beschreibung TEXT, telefon TEXT, kontakt_email TEXT, registriert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP, aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
                try:
                    pw_hash = _hash_password_argon2id(emp_reg_password)
                    c.execute("INSERT INTO employers (email, password_hash, firma, kontaktperson) VALUES (?, ?, ?, ?)",
                              (emp_reg_email, pw_hash, emp_reg_firma, emp_reg_kontakt))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Arbeitgeber registriert: {emp_reg_firma}")
                    st.info("👉 Bitte jetzt einloggen.")
                except sqlite3.IntegrityError:
                    conn.close()
                    st.error("❌ E-Mail bereits vorhanden!")

    with tab_admin_login:
        # ── ADMIN-LOGIN (v4.5/v3.1, Option 2: admins-Tabelle) ──
        st.markdown("🛡️ Geschützter Admin-Zugang – Betrieb und Kontrolle der Agent-Ebene.")
        adm_email = st.text_input("Admin-E-Mail:", key="adm_login_email")
        adm_password = st.text_input("Passwort:", type="password", key="adm_login_password")
        if st.button("🛡️ Als Admin einloggen", key="adm_login_btn"):
            if not adm_email or not adm_password:
                st.error("❌ Bitte E-Mail und Passwort eingeben.")
            else:
                conn_adm = sqlite3.connect(str(DATA_DIR / "feedback.db"))
                ca = conn_adm.cursor()
                ca.execute("""CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT,
                    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
                ca.execute("SELECT COUNT(*) FROM admins")
                if ca.fetchone()[0] == 0:
                    # Seed-Admin (erster Start, Prototyp)
                    ca.execute("INSERT INTO admins (email, password_hash, name) VALUES (?, ?, ?)",
                               ("admin@km-hr-agent.local",
                                _hash_password_argon2id("admin-agent-2026"),
                                "Betreiber (Seed)"))
                    conn_adm.commit()
                ca.execute("SELECT id, email, password_hash FROM admins WHERE email = ?", (adm_email,))
                adm = ca.fetchone()
                conn_adm.close()
                import hashlib
                pw_hash = hashlib.sha256(adm_password.encode()).hexdigest()
                if adm and adm[2] == pw_hash:
                    # Migration: SHA256 → argon2id
                    conn_adm2 = sqlite3.connect(str(DATA_DIR / "feedback.db"))
                    _migrate_password_if_needed(conn_adm2, adm[0], adm_password, "admins")
                    conn_adm2.close()
                    login_admin(adm[0], adm[1])
                    st.success("✅ Admin-Login erfolgreich.")
                    st.rerun()
                elif adm and _is_sha256_hash(adm[2]) and hashlib.sha256(adm_password.encode()).hexdigest() == adm[2]:
                    # Fallback: Falls Migration fehlgeschlagen
                    conn_adm2 = sqlite3.connect(str(DATA_DIR / "feedback.db"))
                    _migrate_password_if_needed(conn_adm2, adm[0], adm_password, "admins")
                    conn_adm2.close()
                    login_admin(adm[0], adm[1])
                    st.success("✅ Admin-Login erfolgreich.")
                    st.rerun()
                elif adm and _verify_password_argon2id(adm_password, adm[2]):
                    login_admin(adm[0], adm[1])
                    st.success("✅ Admin-Login erfolgreich.")
                    st.rerun()
                else:
                    st.error("❌ Falsche Admin-E-Mail oder Passwort.")

    st.stop()  # ← Hier stoppt die App für unregistrierte User

# ─── Eingeloggt: App zeigt alles ──────────────────────────────────────

if check_admin_login():
    st.title("🤖 KM-HR-Agent – Admin-Bereich")
    st.caption(f"Eingeloggt als Admin: {st.session_state.admin_email} (Agent-Ebene sichtbar, v3.1)")
    # ── Passwort ändern (N5) ──
    with st.expander("🔒 Passwort ändern"):
        altes_pw = st.text_input("Aktuelles Passwort:", type="password", key="pw_alt_admin")
        neues_pw = st.text_input("Neues Passwort:", type="password", key="pw_neu_admin")
        neues_pw_wdh = st.text_input("Neues Passwort wiederholen:", type="password", key="pw_wdh_admin")
        if st.button("🔒 Passwort ändern", key="pw_change_admin"):
            if not altes_pw or not neues_pw or not neues_pw_wdh:
                st.error("❌ Bitte alle Felder ausfüllen.")
            elif neues_pw != neues_pw_wdh:
                st.error("❌ Passwörter stimmen nicht überein.")
            else:
                from webui.logic import change_password
                conn_admin = sqlite3.connect(str(DATA_DIR / "feedback.db"))
                admin_id = conn_admin.execute(
                    "SELECT id FROM admins WHERE email = ?", (st.session_state.admin_email,)
                ).fetchone()
                if admin_id:
                    ok, msg = change_password(conn_admin, "admins", admin_id[0], altes_pw, neues_pw)
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
                conn_admin.close()
elif check_employer_login():
    st.title("🤖 KM-HR-Agent – Arbeitgeber-Bereich")
    st.caption(f"Eingeloggt als Arbeitgeber: {st.session_state.employer_firma} ({st.session_state.employer_email})")
else:
    st.title("🤖 KM-HR-Agent – Prototyp")
    st.caption(f"Eingeloggt als: {st.session_state.user_name} ({st.session_state.user_email})")

# Logout-Button
if st.sidebar.button("🚪 Abmelden"):
    if check_admin_login():
        logout_admin()
    elif check_employer_login():
        logout_employer()
    else:
        logout_user()
    st.rerun()

# ─── Sidebar Navigation ───────────────────────────────────────────────

st.sidebar.title("🧭 Skills")

def _seiten_fuer_rolle(rolle):
    """Rollenbasierte Seitenliste (v4.5/v3.1, knowledge/system/access-control.md)."""
    if rolle == "candidate":
        return ["📤 Upload", "6️⃣ Pre-Screen", "7️⃣ Generate Onboarding", "👤 Candidate Portal", "💼 Stellenangebote"]
    if rolle == "employer":
        # v4.5: 9 Portal-Seiten – read-only Ergebnis-Sichten + Agent-Details + Dokumente
        return ["2️⃣ Match-Ergebnis", "3️⃣ Compliance-Ergebnis", "🔍 Agent-Details",
                "🗂️ Dokumente",
                "6️⃣ Pre-Screen", "7️⃣ Generate Onboarding", "8️⃣ Store Feedback",
                "💼 Stellenangebote", "🏢 Arbeitgeber-Portal"]
    if rolle == "admin":
        # v3.1 §2.4: ADMIN = v4.3-Vollansicht (Agent-Tools sichtbar + ausführbar)
        return ["📤 Upload", "1️⃣ Extract Profile", "2️⃣ Match Candidate", "3️⃣ Check Compliance",
                "4️⃣ Contact Candidate", "5️⃣ Assess Culture Fit", "6️⃣ Pre-Screen",
                "7️⃣ Generate Onboarding", "8️⃣ Store Feedback", "💼 Stellenangebote", "🏢 Arbeitgeber-Portal"]
    return []

_seiten = _seiten_fuer_rolle(current_role())
skill = st.sidebar.radio("Skill auswählen:", _seiten) if _seiten else None

# Session-Bindung für Skills 2–8 (nur die HR-Sicht hat den Kandidat-Selector)
selected_status = None
selected_cand_id = None
selected_kandidat = ""

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Status")
st.sidebar.markdown(f"**Profile:** {len(list_profiles())}")
st.sidebar.markdown(f"**Stellen:** {len(list_stellen())}")
st.sidebar.markdown(f"**Ergebnisse:** {len(list(ERGEBNISSE.glob('*.md')))}")

# Kandidat-Selector (nur HR-Sicht, nur für Skills 2-8)
if current_role() in ("employer", "admin") and skill not in ["📤 Upload", "1️⃣ Extract Profile", "💼 Stellenangebote", "🏢 Arbeitgeber-Portal"]:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👤 Kandidat")
    db_path = DATA_DIR / "feedback.db"
    conn_sel = sqlite3.connect(str(db_path))
    c_sel = conn_sel.cursor()
    c_sel.execute("SELECT id, name, status FROM candidates ORDER BY name")
    alle_kandidaten = c_sel.fetchall()
    conn_sel.close()

    if not alle_kandidaten:
        st.sidebar.warning("⚠️ Keine Kandidaten registriert")
    else:
        # Status-Farben
        status_emoji = {
            "registriert": "🔴",
            "profil_vollstaendig": "🟡",
            "lebenslauf_hochgeladen": "🟢",
            "profil_geprueft": "🟢",
            "match_berechnet": "🟢",
            "eingeladen": "🟢",
        }
        erlaubt = ["lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen"]

        optionen = []
        for k in alle_kandidaten:
            emoji = status_emoji.get(k[2], "⚪")
            optionen.append(f"{emoji} {k[1]} ({k[2]})")

        selected_kandidat = st.sidebar.selectbox("Kandidat:", optionen, key="sidebar_kandidat")

        # Gewählten Kandidaten-Status prüfen
        selected_idx = optionen.index(selected_kandidat)
        selected_status = alle_kandidaten[selected_idx][2]
        selected_cand_id = alle_kandidaten[selected_idx][0]

        if selected_status not in erlaubt:
            st.sidebar.error(f"❌ Status '{selected_status}' – Lebenslauf hochladen nötig")
        else:
            st.sidebar.success(f"✅ Status: {selected_status}")


# ═════════════════════════════════════════════════════════════════════
# SKILL 0: UPLOAD
# ═════════════════════════════════════════════════════════════════════

if skill == "📤 Upload" and current_role() in ("candidate", "admin"):
    st.header("📤 Datei-Upload")
    st.markdown("Lade Lebensläufe (PDF/TXT) oder Stellenprofile (TXT) hoch.")

    col1, col2 = st.columns(2)

    with col1:
        if current_role() == "candidate":
            st.subheader("Lebenslauf (eigener CV)")
            st.caption("🔒 Eigene-Datei-Bindung: Ihr Upload füllt direkt Ihr Profil und setzt Ihren Status auf 'lebenslauf_hochgeladen'.")
        else:
            st.subheader("Lebenslauf")
        cv_file = st.file_uploader(
            "PDF oder TXT",
            type=["pdf", "txt"],
            key="cv_upload"
        )
        if cv_file and current_role() == "candidate":
            # CANDIDATE: eigener CV -> direkt ins eigene Profil (wie Candidate Portal, Tab Lebenslauf)
            conn_up = sqlite3.connect(str(DATA_DIR / "feedback.db"))
            cu_up = conn_up.cursor()
            save_path = TESTDATEN / f"kandidat-{st.session_state.user_cand_id}-{cv_file.name}"
            save_path.write_bytes(cv_file.getvalue())
            if cv_file.type == "application/pdf":
                cv_text = extract_pdf_text(str(save_path))
            else:
                cv_text = cv_file.getvalue().decode("utf-8", errors="replace")
            cu_up.execute("""UPDATE candidates SET
                lebenslauf_datei=?, lebenslauf_text=?,
                status='lebenslauf_hochgeladen', aktualisiert_am=CURRENT_TIMESTAMP
                WHERE id=?""",
                (str(save_path), cv_text[:5000], st.session_state.user_cand_id))
            conn_up.commit()
            conn_up.close()
            # Phase 5 (Spec §3): CV-Upload → Agent extrahiert automatisch
            queue_agent_task("extract_profile", {"candidate_id": st.session_state.user_cand_id,
                                                 "cv_path": str(save_path)})
            st.success(f"✅ Eigener Lebenslauf gespeichert ({len(cv_text)} Zeichen). Status: lebenslauf_hochgeladen")
            with st.expander("📄 Vorschau"):
                st.text(cv_text[:2000])
        elif cv_file:
            save_path = TESTDATEN / cv_file.name
            save_path.write_bytes(cv_file.getvalue())
            st.success(f"✅ Gespeichert: `{save_path}`")

            # Vorschau
            if cv_file.type == "application/pdf":
                text = extract_pdf_text(str(save_path))
            else:
                text = cv_file.getvalue().decode("utf-8", errors="replace")

            with st.expander("📄 Vorschau"):
                st.text(text[:2000])

    with col2:
        st.subheader("Stellenprofil")
        if current_role() == "candidate":
            st.caption("ℹ️ Stellenprofil-Upload ist der HR-Sicht vorbehalten.")
        jd_file = st.file_uploader(
            "TXT",
            type=["txt"],
            key="jd_upload",
            disabled=current_role() == "candidate"
        )
        if jd_file:
            save_path = TESTDATEN / jd_file.name
            save_path.write_bytes(jd_file.getvalue())
            st.success(f"✅ Gespeichert: `{save_path}`")

            with st.expander("📄 Vorschau"):
                st.text(jd_file.getvalue().decode("utf-8", errors="replace")[:2000])

    # Vorhandene Dateien anzeigen
    st.markdown("---")
    st.subheader("📁 Vorhandene Dateien")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Profile:**")
        for f in list_profiles():
            st.markdown(f"- `{f.name}`")
    with col_b:
        st.markdown("**Stellen:**")
        for f in list_stellen():
            st.markdown(f"- `{f.name}`")


# ═════════════════════════════════════════════════════════════════════
# SKILL 1: EXTRACT PROFILE
# ═════════════════════════════════════════════════════════════════════

elif skill == "1️⃣ Extract Profile" and current_role() == "admin":
    st.header("1️⃣ Extract Profile")
    st.markdown("Extrahiert ein strukturiertes Profil aus einem Lebenslauf (PDF/TXT).")
    st.caption("🔒 DSGVO (v4.3): Anzeige anonymisiert – ohne Name, ohne Kontaktdaten. Freigabe erst nach Einladung.")

    # Datei auswählen
    all_files = list(TESTDATEN.glob("*.txt")) + list(TESTDATEN.glob("*.pdf"))
    cv_files = [f for f in all_files if "stellenprofil" not in f.name.lower()]

    if not cv_files:
        st.warning("⚠️ Keine Lebenslauf-Dateien gefunden. Lade zuerst eine Datei hoch (Skill 0: Upload).")
    else:
        selected = st.selectbox(
            "Lebenslauf auswählen:",
            cv_files,
            format_func=lambda x: x.name
        )

        if st.button("🔍 Profil extrahieren", key="extract_btn"):
            with st.spinner("Extrahiere Profil..."):
                # Datei lesen
                raw_text = read_file(str(selected))

                # Strukturierung (vereinfacht – in Produktion via LLM)
                profile = {
                    "quelle": selected.name,
                    "extrahiert_am": datetime.now().strftime("%d.%m.%Y %H:%M"),
                    "roh_text_length": len(raw_text),
                }

                # Einfache Extraktion
                lines = raw_text.split("\n")
                name = ""
                for line in lines[:20]:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("---") and len(line) > 3:
                        if not any(kw in line.lower() for kw in ["datum", "datum:", "erstellt", "stand", "kontakt"]):
                            name = line
                            break

                profile["name"] = name if name else "Unbekannt"

                # Ergebnis als Markdown
                md = f"# Profil: {profile['name']}\n\n"
                md += f"**Extrahiert am:** {profile['extrahiert_am']}\n"
                md += f"**Quelle:** {profile['quelle']}\n"
                md += f"**Methode:** PDF/TXT → Strukturierung\n\n"
                md += "---\n\n"
                md += "## Roher Text (Auszug)\n\n"
                md += f"```\n{raw_text[:3000]}\n```\n\n"
                md += "---\n\n"
                md += f"*Erstellt am {profile['extrahiert_am']} vom KM-HR-Agenten.*\n"

                # Speichern
                filename = f"profil-{profile['name'].lower().replace(' ', '-')}.md"
                path = save_result(filename, md, base_dir=TESTDATEN)

                st.success(f"✅ Profil gespeichert: `{path}`")

                # Anzeige
                st.markdown(md)

                # Download
                st.download_button(
                    "📥 Profil herunterladen",
                    md,
                    file_name=filename,
                    mime="text/markdown"
                )


# ═════════════════════════════════════════════════════════════════════
# SKILL 2: MATCH CANDIDATE
# ═════════════════════════════════════════════════════════════════════

elif skill == "2️⃣ Match Candidate" and current_role() == "admin":
    st.header("2️⃣ Match Candidate")
    st.markdown("Vergleicht Kandidatenprofil mit Stellenprofil und erstellt Match-Score.")

    # Profil-Check: Nur wenn Kandidat aus Sidebar erlaubt
    erlaubt = ["lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen"]
    if selected_status not in erlaubt:
        st.error(f"❌ Kandidat '{selected_kandidat.split(']')[1].strip() if ']' in selected_kandidat else selected_kandidat}' muss Lebenslauf hochladen. Aktueller Status: {selected_status}")
        st.info("💡 Gehe zu 👤 Candidate Portal → 📄 Lebenslauf")
    else:
        profiles = list_profiles()
        stellen = list_stellen()

        if not profiles or not stellen:
            st.warning("⚠️ Benötige mindestens 1 Profil und 1 Stellenprofil.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                sel_profile = st.selectbox("Kandidat:", profiles, format_func=lambda x: x.name)
            with col2:
                sel_stelle = st.selectbox("Stelle:", stellen, format_func=lambda x: x.name)

        if st.button("🎯 Match berechnen", key="match_btn"):
            with st.spinner("Berechne Match-Score..."):
                profil_text = read_file(str(sel_profile))
                stellen_text = read_file(str(sel_stelle))

                # Einfache Skill-Matching (vereinfacht – in Produktion via LLM)
                profil_lower = profil_text.lower()
                stellen_lower = stellen_text.lower()

                # Bekannte Skills prüfen
                common_skills = [
                    "aws", "kubernetes", "docker", "python", "java", "go",
                    "terraform", "ci/cd", "jenkins", "github actions", "argocd",
                    "postgresql", "mongodb", "redis", "typescript", "react",
                    "node.js", "scrum", "agil", "teamführung", "devops",
                    "cloud", "azure", "gcp", "helm", "microservices"
                ]

                matches = []
                gaps = []
                for skill_name in common_skills:
                    in_profil = skill_name in profil_lower
                    in_stelle = skill_name in stellen_lower
                    if in_profil and in_stelle:
                        matches.append(skill_name)
                    elif not in_profil and in_stelle:
                        gaps.append(skill_name)

                # Score berechnen
                match_count = len(matches)
                gap_count = len(gaps)
                total_skills = match_count + gap_count
                skill_score = int((match_count / max(total_skills, 1)) * 30)

                # Erfahrung prüfen
                erfahrung_score = 0
                if "jahre" in profil_lower or "2016" in profil_lower or "2018" in profil_lower:
                    erfahrung_score = 25
                elif "2020" in profil_lower or "2021" in profil_lower:
                    erfahrung_score = 20

                # Bildung prüfen
                bildung_score = 0
                if "master" in profil_lower or "m.sc" in profil_lower:
                    bildung_score = 15
                elif "bachelor" in profil_lower or "b.sc" in profil_lower:
                    bildung_score = 12

                # Standort
                standort_score = 8
                if "münchen" in profil_lower and "münchen" in stellen_lower:
                    standort_score = 10

                # Gesamt-Score
                total = skill_score + erfahrung_score + bildung_score + standort_score + 8
                total = min(total, 100)

                # Kategorie
                if total >= 90:
                    kategorie = "Hervorragend"
                    emoji = "🟢"
                elif total >= 75:
                    kategorie = "Gut"
                    emoji = "🟡"
                elif total >= 60:
                    kategorie = "Bedingt"
                    emoji = "🟠"
                else:
                    kategorie = "Nicht passend"
                    emoji = "🔴"

                # Ergebnis
                md = f"# Match-Bericht\n\n"
                md += f"**Kandidat:** `{sel_profile.name}`\n"
                md += f"**Stelle:** `{sel_stelle.name}`\n"
                md += f"**Datum:** {datetime.now().strftime('%d.%m.%Y')}\n\n"
                md += "---\n\n"
                md += f"## {emoji} Match-Score: {total}/100 ({kategorie})\n\n"
                md += "### Score-Verteilung\n\n"
                md += f"| Kategorie | Punkte |\n"
                md += f"|---|---|\n"
                md += f"| Kernkompetenzen | {skill_score}/30 |\n"
                md += f"| Berufserfahrung | {erfahrung_score}/25 |\n"
                md += f"| Bildung | {bildung_score}/15 |\n"
                md += f"| Standort | {standort_score}/10 |\n"
                md += f"| Branchenkenntnis | 8/10 |\n"
                md += f"| **Gesamt** | **{total}/100** |\n\n"
                md += "### Übereinstimmungen\n\n"
                for m in matches:
                    md += f"- ✅ {m}\n"
                if not matches:
                    md += "- (keine direkten Übereinstimmungen)\n"
                md += "\n### Fehlende Skills (Gaps)\n\n"
                for g in gaps:
                    md += f"- ❌ {g}\n"
                if not gaps:
                    md += "- (keine Lücken)\n"
                md += "\n### Empfehlung\n\n"
                if total >= 90:
                    md += "✅ **Sofort einladen** – Hervorragender Match.\n"
                elif total >= 75:
                    md += "✅ **Einladen** – Gut Qualifiziert.\n"
                elif total >= 60:
                    md += "⚠️ **Prüfung empfohlen** – Bedingter Match.\n"
                else:
                    md += "❌ **Ablehnen** – Nicht passend.\n"

                md += "\n---\n\n"
                md += f"*Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} vom KM-HR-Agenten.*\n"

                # Speichern
                kandidat_name = sel_profile.stem.replace("profil-", "")
                stelle_name = sel_stelle.stem.replace("stellenprofil-", "")
                filename = f"match-{kandidat_name}-{stelle_name}-{datetime.now().strftime('%Y-%m-%d')}.md"
                path = save_result(filename, md)
                st.success(f"✅ Match gespeichert: `{path}`")

                # Anzeige
                st.markdown(md)
                st.download_button("📥 Herunterladen", md, file_name=filename)


# ═════════════════════════════════════════════════════════════════════
# SKILL 3: CHECK COMPLIANCE
# ═════════════════════════════════════════════════════════════════════

elif skill == "3️⃣ Check Compliance" and current_role() == "admin":
    st.header("3️⃣ Check Compliance")
    st.markdown("Länderspezifische Compliance-Prüfung (DE/FR/CH + DSGVO).")

    erlaubt = ["lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen"]
    if selected_status not in erlaubt:
        st.error(f"❌ Kandidat muss Lebenslauf hochladen. Status: {selected_status}")
    else:
        profiles = list_profiles()
        stellen = list_stellen()

        if not profiles or not stellen:
            st.warning("⚠️ Benötige mindestens 1 Profil und 1 Stellenprofil.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                sel_profile = st.selectbox("Kandidat:", profiles, format_func=lambda x: x.name, key="compliance_profile")
            with col2:
                sel_stelle = st.selectbox("Stelle:", stellen, format_func=lambda x: x.name, key="compliance_stelle")

        laender = st.multiselect(
            "Länder prüfen:",
            ["🇩🇪 Deutschland", "🇫🇷 Frankreich", "🇨🇭 Schweiz"],
            default=["🇩🇪 Deutschland"]
        )

        if st.button("⚖️ Compliance prüfen", key="compliance_btn"):
            with st.spinner("Prüfe Compliance..."):
                profil_text = read_file(str(sel_profile))
                stellen_text = read_file(str(sel_stelle))

                md = "# Compliance-Bericht\n\n"
                md += f"**Kandidat:** `{sel_profile.name}`\n"
                md += f"**Stelle:** `{sel_stelle.name}`\n"
                md += f"**Datum:** {datetime.now().strftime('%d.%m.%Y')}\n\n"
                md += "---\n\n"

                # DSGVO Check
                md += "## 🔒 DSGVO (EU-weit)\n\n"
                md += "| Prüfpunkt | Status | Details |\n"
                md += "|---|---|---|\n"
                md += "| Art. 5 – Datenminimierung | ✅ COMPLIANT | Nur relevante Daten erfasst |\n"
                md += "| Art. 6 – Rechtsgrundlage | ✅ COMPLIANT | Art. 6(1)(b) – Vertragserfüllung |\n"
                md += "| Art. 13 – Informationspflicht | ⚠️ HINWEIS | Kandidat muss informiert werden |\n"
                md += "| Art. 17 – Recht auf Löschung | ✅ COMPLIANT | Nach Einstellungsprozess löschen |\n"
                md += "| Art. 22 – Automatisierte Entscheidung | ⚠️ HINWEIS | EU AI Act Transparenz nötig |\n\n"

                # DE Compliance
                if "🇩🇪 Deutschland" in laender:
                    md += "## 🇩🇪 Deutschland (AGG, BDSG, MiLoG)\n\n"
                    md += "| Gesetz | Prüfpunkt | Status |\n"
                    md += "|---|---|---|\n"

                    # AGG Check
                    profil_lower = profil_text.lower()
                    if any(w in profil_lower for w in ["männlich", "weiblich", "frau", "herr"]):
                        md += "| AGG §1 | Diskriminierungsverbot | ⚠️ WARNUNG – Geschlecht explizit genannt |\n"
                    else:
                        md += "| AGG §1 | Diskriminierungsverbot | ✅ COMPLIANT |\n"

                    # BDSG
                    md += "| BDSG §26 | Bewerberdaten | ✅ COMPLIANT – Datenverarbeitung erforderlich |\n"

                    # EU AI Act
                    md += "| EU AI Act Art. 50 | Transparenz KI | ⚠️ HINWEIS – KI-generierte Entscheidung kennzeichnen |\n"

                    # MiLoG
                    if "gehalt" in stellen_text.lower() or "75.000" in stellen_text or "95.000" in stellen_text:
                        md += "| MiLoG | Mindestlohn | ✅ COMPLIANT – Gehalt über Mindestlohn |\n"
                    else:
                        md += "| MiLoG | Mindestlohn | ⚠️ HINWEIS – Kein Gehalt angegeben |\n"
                    md += "\n"

                # FR Compliance
                if "🇫🇷 Frankreich" in laender:
                    md += "## 🇫🇷 Frankreich (Code du travail)\n\n"
                    md += "| Gesetz | Prüfpunkt | Status |\n"
                    md += "|---|---|---|\n"
                    md += "| Code du travail L.1132-1 | Diskriminierungsverbot | ✅ COMPLIANT |\n"
                    md += "| Loi L.3121-27 | 35h-Woche | ⚠️ HINWEIS – Arbeitszeit prüfen |\n"
                    md += "| RGPD | Datenschutz | ✅ COMPLIANT |\n\n"

                # CH Compliance
                if "🇨🇭 Schweiz" in laender:
                    md += "## 🇨🇭 Schweiz (OR, ArG)\n\n"
                    md += "| Gesetz | Prüfpunkt | Status |\n"
                    md += "|---|---|---|\n"
                    md += "| OR Art. 319 | Arbeitsvertrag | ✅ COMPLIANT |\n"
                    md += "| ArG Art. 9 | Arbeitszeit (45h/50h) | ⚠️ HINWEIS – Arbeitszeitmodell prüfen |\n"
                    md += "| DSG Art. 6 | Datenschutz | ✅ COMPLIANT |\n\n"

                # Gesamtbewertung
                md += "## Gesamtbewertung\n\n"
                md += "✅ **COMPLIANT** – Match kann fortgesetzt werden.\n"
                md += "\n---\n\n"
                md += f"*Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} vom KM-HR-Agenten.*\n"

                # Speichern
                kandidat_name = sel_profile.stem.replace("profil-", "")
                filename = f"compliance-{kandidat_name}-{datetime.now().strftime('%Y-%m-%d')}.md"
                path = save_result(filename, md)
                st.success(f"✅ Compliance-Bericht gespeichert: `{path}`")
                st.markdown(md)
                st.download_button("📥 Herunterladen", md, file_name=filename)


# ═════════════════════════════════════════════════════════════════════
# SKILL 4: CONTACT CANDIDATE
# ═════════════════════════════════════════════════════════════════════

elif skill == "4️⃣ Contact Candidate" and current_role() == "admin":
    st.header("4️⃣ Contact Candidate")
    st.markdown("Generiert personalisierte E-Mail-Einladungen für Kandidaten.")

    erlaubt = ["lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen"]
    if selected_status not in erlaubt:
        st.error(f"❌ Kandidat muss Lebenslauf hochladen. Status: {selected_status}")
    else:
        profiles = list_profiles()

        if not profiles:
            st.warning("⚠️ Keine Profile gefunden.")
        else:
            sel_profile = st.selectbox(
                "Kandidat:",
                profiles,
                format_func=lambda x: x.name,
                key="contact_profile"
            )

        col1, col2 = st.columns(2)
        with col1:
            stelle = st.text_input("Stelle:", "Senior Cloud/DevOps Engineer")
        with col2:
            unternehmen = st.text_input("Unternehmen:", "TechVision GmbH")

        if st.button("📧 E-Mail generieren", key="contact_btn"):
            with st.spinner("Generiere E-Mail..."):
                profil_text = read_file(str(sel_profile))

                # Name extrahieren
                name = sel_profile.stem.replace("profil-", "").replace("-", " ").title()

                # E-Mail-Adresse aus Profil lesen
                email = "kandidat@example.de"
                for line in profil_text.split("\n"):
                    if "@" in line and ("e-mail" in line.lower() or "email" in line.lower()):
                        parts = line.split(":")
                        if len(parts) > 1:
                            email = parts[1].strip()
                            break

                datum = (datetime.now() + timedelta(days=14)).strftime("%A, %d. %B %Y")
                uhrzeit = "10:00 Uhr"

                md = f"# E-Mail an {name}\n\n"
                md += f"**Von:** HR Team / {unternehmen}\n"
                md += f"**An:** {email}\n"
                md += f"**Betreff:** Einladung zum Vorstellungsgespräch – {stelle}\n\n"
                md += "---\n\n"
                md += f"Sehr geehrte(r) {name},\n\n"
                md += f"wir freuen uns, Ihnen unser Interesse an Ihrer Bewerbung mitteilen zu können.\n\n"
                md += f"Nach der Prüfung Ihres Lebenslaufs haben wir festgestellt, dass Ihre "
                md += f"Qualifikationen hervorragend zu unserer Position als **{stelle}** "
                md += f"bei **{unternehmen}** passen.\n\n"
                md += f"**Wir laden Sie herzlich ein zum:**\n\n"
                md += f"- **Datum:** {datum}\n"
                md += f"- **Uhrzeit:** {uhrzeit}\n"
                md += f"- **Format:** Online (Jitsi Meet – kostenlos)\n"
                md += f"- **Dauer:** ca. 45–60 Minuten\n\n"
                md += f"**Agenda:**\n"
                md += f"1. Vorstellung des Unternehmens (5 Min.)\n"
                md += f"2. Technische Fragen (20 Min.)\n"
                md += f"3. Kulturelles Fit (10 Min.)\n"
                md += f"4. Fragen des Kandidaten (10 Min.)\n\n"
                md += f"**Vorbereitung:**\n"
                md += f"Bitte bringen Sie folgende Unterlagen mit:\n"
                md += f"- Aktuellen Lebenslauf\n"
                md += f"- Zeugnisse\n"
                md += f"- Referenzen (falls vorhanden)\n\n"
                md += f"---\n\n"
                md += f"**Rechtliche Hinweise:**\n"
                md += f"- 🔒 DSGVO Art. 13: Ihre Daten werden gemäß Art. 6(1)(b) DSGVO verarbeitet.\n"
                md += f"- ⚖️ EU AI Act Art. 50: Diese Einladung wurde mit KI-Unterstützung erstellt.\n\n"
                md += f"Mit freundlichen Grüßen,\n"
                md += f"HR Team\n"
                md += f"{unternehmen}\n\n"
                md += f"---\n\n"
                md += f"*Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} vom KM-HR-Agenten.*\n"

                # Speichern
                kandidat_name = sel_profile.stem.replace("profil-", "")
                filename = f"email-{kandidat_name}-{datetime.now().strftime('%Y-%m-%d')}.md"
                path = save_result(filename, md)
                st.success(f"✅ E-Mail gespeichert: `{path}`")
                st.markdown(md)
                st.download_button("📥 Herunterladen", md, file_name=filename)


# ═════════════════════════════════════════════════════════════════════
# SKILL 5: ASSESS CULTURE FIT
# ═════════════════════════════════════════════════════════════════════

elif skill == "5️⃣ Assess Culture Fit" and current_role() == "admin":
    st.header("5️⃣ Assess Culture Fit")
    st.markdown("Bewertet den Kultur-Fit eines Kandidaten (0–100).")

    erlaubt = ["lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen"]
    if selected_status not in erlaubt:
        st.error(f"❌ Kandidat muss Lebenslauf hochladen. Status: {selected_status}")
    else:
        profiles = list_profiles()

        if not profiles:
            st.warning("⚠️ Keine Profile gefunden.")
        else:
            sel_profile = st.selectbox(
                "Kandidat:",
                profiles,
                format_func=lambda x: x.name,
                key="culture_profile"
            )

        if st.button("🎭 Kultur-Fit bewerten", key="culture_btn"):
            with st.spinner("Bewerte Kultur-Fit..."):
                profil_text = read_file(str(sel_profile))
                profil_lower = profil_text.lower()

                # Kriterien
                scores = {}

                # Sprache
                if "deutsch" in profil_lower and ("muttersprache" in profil_lower or "fließend" in profil_lower):
                    scores["Sprache (Deutsch)"] = 10
                elif "deutsch" in profil_lower:
                    scores["Sprache (Deutsch)"] = 7
                else:
                    scores["Sprache (Deutsch)"] = 3

                if "englisch" in profil_lower and "fließend" in profil_lower:
                    scores["Sprache (Englisch)"] = 10
                elif "englisch" in profil_lower:
                    scores["Sprache (Englisch)"] = 7
                else:
                    scores["Sprache (Englisch)"] = 4

                # Teamfähigkeit
                if any(w in profil_lower for w in ["teamführung", "team", "mentoring", "scrum"]):
                    scores["Teamfähigkeit"] = 9
                elif "zusammenarbeit" in profil_lower:
                    scores["Teamfähigkeit"] = 7
                else:
                    scores["Teamfähigkeit"] = 5

                # Kommunikation
                if any(w in profil_lower for w in ["dokumentation", "präsentation", "kommunikation"]):
                    scores["Kommunikation"] = 8
                else:
                    scores["Kommunikation"] = 6

                # Agilität
                if any(w in profil_lower for w in ["scrum", "agil", "kanban", "sprint"]):
                    scores["Agilität"] = 9
                else:
                    scores["Agilität"] = 5

                # Standort-Treue
                if "münchen" in profil_lower:
                    scores["Standort-Treue"] = 9
                elif "remote" in profil_lower or "hybrid" in profil_lower:
                    scores["Standort-Treue"] = 7
                else:
                    scores["Standort-Treue"] = 5

                total = sum(scores.values())
                max_score = len(scores) * 10
                pct = int((total / max_score) * 100)

                if pct >= 85:
                    empfehlung = "✅ Perfekter Kultur-Fit"
                elif pct >= 70:
                    empfehlung = "⚠️ Bedingt – Anpassung nötig"
                else:
                    empfehlung = "❌ Kultur-Fit nicht gegeben"

                # Ergebnis
                name = sel_profile.stem.replace("profil-", "").replace("-", " ").title()
                md = f"# Kultur-Fit: {name}\n\n"
                md += f"**Datum:** {datetime.now().strftime('%d.%m.%Y')}\n\n"
                md += "---\n\n"
                md += f"## Score: {pct}/100\n\n"
                md += f"**Empfehlung:** {empfehlung}\n\n"
                md += "### Bewertung nach Kriterien\n\n"
                md += "| Kriterium | Punkte | Max | Bewertung |\n"
                md += "|---|---|---|---|\n"
                for k, v in scores.items():
                    emoji = "✅" if v >= 8 else "⚠️" if v >= 6 else "❌"
                    md += f"| {k} | {v} | 10 | {emoji} |\n"
                md += f"| **Gesamt** | **{total}** | **{max_score}** | **{pct}%** |\n\n"

                md += "### Detailanalyse\n\n"
                md += f"- **Sprache:** {'Sehr gut' if scores.get('Sprache (Deutsch)', 0) >= 8 else 'Ausreichend'}\n"
                md += f"- **Teamarbeit:** {'Führungserfahrung' if scores.get('Teamfähigkeit', 0) >= 8 else 'Grundkenntnisse'}\n"
                md += f"- **Arbeitsstil:** {'Agil/Scrum' if scores.get('Agilität', 0) >= 8 else 'Strukturiert'}\n\n"
                md += "---\n\n"
                md += f"*Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} vom KM-HR-Agenten.*\n"

                # Speichern
                kandidat_name = sel_profile.stem.replace("profil-", "")
                filename = f"kultur-fit-{kandidat_name}-{datetime.now().strftime('%Y-%m-%d')}.md"
                path = save_result(filename, md)
                st.success(f"✅ Kultur-Fit gespeichert: `{path}`")
                st.markdown(md)
                st.download_button("📥 Herunterladen", md, file_name=filename)


# ═════════════════════════════════════════════════════════════════════
# SKILL 2R: MATCH-ERGEBNIS (v4.5 – read-only Sicht für EMPLOYER)
# Das Matching-TOOL läuft auf der Agent-Ebene (opencode/MCP) bzw. Admin;
# der Arbeitgeber sieht hier NUR das agent-generierte Ergebnis.
# ═════════════════════════════════════════════════════════════════════

elif skill == "2️⃣ Match-Ergebnis" and current_role() == "employer":
    st.header("2️⃣ Match-Ergebnis")
    st.caption("🔒 Read-only: Agent-generiertes Matching-Ergebnis. Das Tool selbst läuft auf der Agent-Ebene – kein Ausführen, keine Dateiauswahl.")
    if not selected_kandidat:
        st.info("ℹ️ Kein Kandidat gewählt (Sidebar → 👤 Kandidat).")
    else:
        cand_name = selected_kandidat.split(" (")[0].replace("🟢", "").replace("🔴", "").replace("🟡", "").replace("⚪", "").strip()
        st.markdown(f"**Gewählter Kandidat:** {cand_name}")

        # ── Live-Score: Berechne aktuelle Scores für diesen Kandidaten ──
        # (nicht nur den alten Agent-Snapshot, sondern live aus DB)
        _conn_ls = sqlite3.connect(str(DATA_DIR / "feedback.db"))
        _c_ls = _conn_ls.cursor()
        _c_ls.execute("""SELECT a.job_id, j.titel, j.hard_skills, j.soft_skills,
            j.berufserfahrung_jahre, j.deutsch_level, j.englisch_level,
            j.standort, j.stellentyp, e.branche, j.gehaltsrahmen_min, j.gehaltsrahmen_max
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN employers e ON j.employer_id = e.id
            WHERE a.candidate_id = ? AND a.status != 'zurückgezogen'
            ORDER BY a.erstellungsdatum DESC""", (selected_cand_id,))
        _jobs_fuer_kand = _c_ls.fetchall()
        _c_ls.execute("""SELECT hard_skills, soft_skills, berufserfahrung_jahre,
            abschluss, deutsch, englisch, standort, gehaltsvorstellung, lebenslauf_text
            FROM candidates WHERE id = ?""", (selected_cand_id,))
        _profil = _c_ls.fetchone()
        _conn_ls.close()

        if _profil and _jobs_fuer_kand:
            _k_data = {"hard_skills": _profil[0], "soft_skills": _profil[1],
                       "berufserfahrung_jahre": _profil[2], "abschluss": _profil[3],
                       "deutsch": _profil[4], "englisch": _profil[5],
                       "standort": _profil[6], "lebenslauf_text": _profil[8]}
            st.markdown("**📊 Aktueller Match-Score (live aus DB):**")
            _lc1, _lc2, _lc3 = st.columns(3)
            for _ji, _jf in enumerate(_jobs_fuer_kand[:3]):
                _j_data = {"hard_skills": _jf[2], "soft_skills": _jf[3],
                           "berufserfahrung_jahre": _jf[4], "deutsch_level": _jf[5],
                           "englisch_level": _jf[6], "standort": _jf[7],
                           "stellentyp": _jf[8], "branche": _jf[9]}
                _r_live = berechne_match_score(_k_data, _j_data)
                _col = [_lc1, _lc2, _lc3][_ji % 3]
                with _col:
                    st.metric(f"{_jf[1][:30]}", f"{_r_live['total']}/100", _r_live["kategorie"])
            st.markdown("---")

        # ── Agent-Bericht (Snapshot) ──
        kandidat_slug = cand_name.lower().replace(" ", "-")
        berichte = sorted(ERGEBNISSE.glob("**/match-*.md"))
        treffer = [b for b in berichte if kandidat_slug in b.name.lower()]
        if not treffer:
            st.warning(f"⚠️ Kein agent-generierter Match-Bericht für '{cand_name}' in ergebnisse/ gefunden.\n\nDas Matching läuft über den Agenten (opencode + MCP-Connectors). Das aktuelle Ranking pro Stelle sehen Sie im 🏢 Arbeitgeber-Portal → Tab '👥 Kandidaten' (DB-Scores, Phase 2–4.6).")
        else:
            for b in treffer[:3]:
                # Prüfe ob Agent-Score ≠ Live-Score
                _md_text = b.read_text(encoding="utf-8", errors="replace")
                import re as _re
                _agent_score_match = _re.search(r'Match-Score:\s*(\d+)/100', _md_text)
                if _agent_score_match and _jobs_fuer_kand and _profil:
                    _agent_score = int(_agent_score_match.group(1))
                    _jf0 = _jobs_fuer_kand[0]
                    _j_data0 = {"hard_skills": _jf0[2], "soft_skills": _jf0[3],
                                "berufserfahrung_jahre": _jf0[4], "deutsch_level": _jf0[5],
                                "englisch_level": _jf0[6], "standort": _jf0[7],
                                "stellentyp": _jf0[8], "branche": _jf0[9]}
                    _r_check = berechne_match_score(_k_data, _j_data0)
                    if abs(_agent_score - _r_check["total"]) > 2:
                        st.warning(f"⚠️ Score-Differenz: Agent-Bericht = {_agent_score}, Aktueller Score = {_r_check['total']} (Daten haben sich geändert)")
                with st.expander(f"📄 {b.name}", expanded=(b == treffer[0])):
                    st.markdown(_md_text)


# ═════════════════════════════════════════════════════════════════════
# SKILL 3R: COMPLIANCE-ERGEBNIS (v4.5 – read-only Sicht für EMPLOYER)
# ═════════════════════════════════════════════════════════════════════

elif skill == "3️⃣ Compliance-Ergebnis" and current_role() == "employer":
    st.header("3️⃣ Compliance-Ergebnis")
    st.caption("🔒 Read-only: Agent-generierte Compliance-Prüfung (DE/FR/CH + DSGVO). Das Tool selbst läuft auf der Agent-Ebene – keine Prüfung auslösbar.")
    if not selected_kandidat:
        st.info("ℹ️ Kein Kandidat gewählt (Sidebar → 👤 Kandidat).")
    else:
        cand_name = selected_kandidat.split(" (")[0].replace("🟢", "").replace("🔴", "").replace("🟡", "").replace("⚪", "").strip()
        st.markdown(f"**Gewählter Kandidat:** {cand_name}")
        kandidat_slug = cand_name.lower().replace(" ", "-")
        berichte = sorted(ERGEBNISSE.glob("**/compliance-*.md"))
        treffer = [b for b in berichte if kandidat_slug in b.name.lower()]
        if not treffer:
            st.warning(f"⚠️ Kein agent-generierter Compliance-Bericht für '{cand_name}' in ergebnisse/ gefunden.\n\nDie Compliance-Prüfung läuft über den Agenten (opencode + ansvar-Law-Connectors).")
        else:
            for b in treffer[:3]:
                with st.expander(f"📄 {b.name}", expanded=(b == treffer[0])):
                    st.markdown(b.read_text(encoding="utf-8", errors="replace"))


# ═════════════════════════════════════════════════════════════════════
# 🔍 AGENT-DETAILS (v6.2 – alle Agent-Ergebnisse für EMPLOYER)
# ═════════════════════════════════════════════════════════════════════

elif skill == "🔍 Agent-Details" and current_role() == "employer":
    st.header("🔍 Agent-Details")
    st.caption("🔒 Read-only: Alle Agent-generierten Ergebnisse fuer einen Kandidaten: "
               "Dokumenten-Verifizierung, Visum-Check, DSGVO, Match-Erklaerung.")
    if not selected_kandidat:
        st.info("ℹ️ Kein Kandidat gewählt (Sidebar → 👤 Kandidat).")
    else:
        cand_name = selected_kandidat.split(" (")[0].replace("🟢", "").replace("🔴", "").replace("🟡", "").replace("⚪", "").strip()
        st.markdown(f"**Gewählter Kandidat:** {cand_name}")
        kandidat_slug = cand_name.lower().replace(" ", "-")
        # Alle Agent-Dateien für diesen Kandidaten finden
        _agent_tasks = [
            ("📋 Extract Profile",    "extract_profile-*"),
            ("🎯 Match Candidate",    "match_candidate-*"),
            ("⚖️ Check Compliance",   "check_compliance-*"),
            ("🏢 Assess Culture-Fit", "assess_culture_fit-*"),
            ("📄 Verify Documents",   "verify_documents-*"),
            ("🛂 Check Visa",         "check_visa-*"),
            ("🔒 Check GDPR",         "check_gdpr-*"),
            ("💡 Explain Match",      "explain_match-*"),
            ("📧 Notify User",        "notify_user-*"),
        ]
        # Badge-Zeile: Wichtige Ergebnisse als Metriken
        _badges = []
        for _label, _glob in _agent_tasks:
            _files = sorted(ERGEBNISSE.glob(_glob))
            _match = [f for f in _files if kandidat_slug in f.name.lower()]
            if _match:
                _txt = _match[-1].read_text(encoding="utf-8", errors="replace").upper()
                if "AUFFAELLIG" in _txt or "AUFFÄLLIG" in _txt:
                    _badges.append(("🔴", _label.split(" ", 1)[1]))
                elif "NICHT ERFORDERLICH" in _txt or "KONFORM" in _txt or "COMPLIANT" in _txt:
                    _badges.append(("🟢", _label.split(" ", 1)[1]))
                elif "ERFORDERLICH" in _txt or "NICHT_COMPLIANT" in _txt or "NICHT_KONFORM" in _txt:
                    _badges.append(("🔴", _label.split(" ", 1)[1]))
                else:
                    _badges.append(("🟡", _label.split(" ", 1)[1]))
            else:
                _badges.append(("⚪", _label.split(" ", 1)[1]))
        if _badges:
            st.markdown("**⚡ Status-Übersicht:**")
            _badge_cols = st.columns(min(len(_badges), 6))
            for i, (_icon, _name) in enumerate(_badges[:6]):
                with _badge_cols[i]:
                    st.metric(_name, _icon)
            if len(_badges) > 6:
                _badge_cols2 = st.columns(min(len(_badges) - 6, 3))
                for i, (_icon, _name) in enumerate(_badges[6:9]):
                    with _badge_cols2[i]:
                        st.metric(_name, _icon)
        st.markdown("---")
        # Detaillierte Berichte
        for _label, _glob in _agent_tasks:
            _files = sorted(ERGEBNISSE.glob(_glob))
            _match = [f for f in _files if kandidat_slug in f.name.lower()]
            if _match:
                _latest = _match[-1]
                _content = _latest.read_text(encoding="utf-8", errors="replace")
                _upper = _content.upper()
                # Badge-Farbe bestimmen
                if "AUFFAELLIG" in _upper or "NICHT_ERFORDERLICH" in _upper:
                    _icon = "🔴"
                elif "ERFORDERLICH" in _upper or "NICHT_COMPLIANT" in _upper or "NICHT_KONFORM" in _upper:
                    _icon = "🔴"
                elif "PLAUSIBEL" in _upper or "COMPLIANT" in _upper or "KONFORM" in _upper or "NICHT ERFORDERLICH" in _upper:
                    _icon = "🟢"
                else:
                    _icon = "🟡"
                with st.expander(f"{_icon} {_label} ({_latest.name})"):
                    st.markdown(_content)
            else:
                st.caption(f"⚪ {_label}: Kein Bericht vorhanden")


# ═════════════════════════════════════════════════════════════════════
# 🗂️ DOKUMENTE (HR-Dokumenten-Ansicht, Phase 3)
# ═════════════════════════════════════════════════════════════════════

elif skill == "🗂️ Dokumente" and current_role() == "employer":
    st.header("🗂️ Dokumente")
    st.caption("🔒 DSGVO: Dokumente nur sichtbar nach Status 'eingeladen'. "
               "Zeugnisse, Zertifikate, Sprachtest-Ergebnisse, Video-Vorstellung.")
    if not selected_kandidat:
        st.info("ℹ️ Kein Kandidat gewählt (Sidebar → 👤 Kandidat).")
    else:
        cand_name = selected_kandidat.split(" (")[0].replace("🟢", "").replace("🔴", "").replace("🟡", "").replace("⚪", "").strip()
        st.markdown(f"**Gewählter Kandidat:** {cand_name}")

        # DSGVO-Check: Nur bei Status >= 'eingeladen'
        _conn_dsgvo = sqlite3.connect(str(DATA_DIR / "feedback.db"))
        _c_dsgvo = _conn_dsgvo.cursor()
        _c_dsgvo.execute("SELECT status FROM candidates WHERE id = ?", (selected_cand_id,))
        _cand_status = _c_dsgvo.fetchone()
        _cand_status = _cand_status[0] if _cand_status else ""
        _dsgvo_ok = _cand_status in ("eingeladen", "eingestellt")
        _conn_dsgvo.close()

        if not _dsgvo_ok:
            st.warning(f"🔒 DSGVO: Dokumente erst nach Status 'eingeladen' sichtbar. "
                       f"Aktueller Status: **{_cand_status}**")
        else:
            st.success(f"✅ Status: {_cand_status} – Dokumente sind freigegeben (DSGVO Art. 6(1)(b))")

            # ── 1. Kandidaten-Dokumente (candidate_documents) ──
            st.markdown("---")
            st.subheader("📄 Hochgeladene Dokumente")
            _conn_docs = sqlite3.connect(str(DATA_DIR / "feedback.db"))
            _c_docs = _conn_docs.cursor()
            _c_docs.execute("""SELECT id, datei_pfad, dokumententyp, hochgeladen_am
                FROM candidate_documents WHERE candidate_id = ?
                ORDER BY hochgeladen_am DESC""", (selected_cand_id,))
            _doks = _c_docs.fetchall()
            _conn_docs.close()

            if not _doks:
                st.info("ℹ️ Keine Dokumente hochgeladen.")
            else:
                for _d_id, _d_pfad, _d_typ, _d_dat in _doks:
                    with st.expander(f"📄 {_d_typ} ({_d_dat[:10] if _d_dat else '?'})"):
                        # PDF-Vorschau
                        if _d_pfad and _d_pfad.endswith(".pdf"):
                            try:
                                _d_text = extract_pdf_text(_d_pfad)
                                st.text_area("Inhalt:", _d_text[:3000], height=200, disabled=True,
                                             key=f"doc_preview_{_d_id}")
                            except Exception as e:
                                st.error(f"PDF-Vorschau fehlgeschlagen: {e}")
                        elif _d_pfad and _d_pfad.endswith(".txt"):
                            try:
                                _d_text = Path(_d_pfad).read_text(encoding="utf-8", errors="replace")
                                st.text_area("Inhalt:", _d_text[:3000], height=200, disabled=True,
                                             key=f"doc_preview_{_d_id}")
                            except Exception as e:
                                st.error(f"TXT-Vorschau fehlgeschlagen: {e}")
                        st.caption(f"📁 {_d_pfad}")

            # ── 2. Sprachtest-Ergebnisse (language_tests) ──
            st.markdown("---")
            st.subheader("🗣️ Sprachtest-Ergebnisse")
            _conn_lt = sqlite3.connect(str(DATA_DIR / "feedback.db"))
            _c_lt = _conn_lt.cursor()
            _c_lt.execute("""SELECT sprache, niveau, punkte, cefr_level, test_datum, details
                FROM language_tests WHERE candidate_id = ?
                ORDER BY test_datum DESC""", (selected_cand_id,))
            _sprachtests = _c_lt.fetchall()
            _conn_lt.close()

            if not _sprachtests:
                st.info("ℹ️ Keine Sprachtest-Ergebnisse vorhanden.")
            else:
                for _st_sprache, _st_niv, _st_pkt, _st_cefr, _st_dat, _st_details in _sprachtests:
                    _cefr_color = "🟢" if _st_cefr and _st_cefr >= "B1" else ("🟡" if _st_cefr == "A2" else "🔴")
                    with st.expander(f"{_cefr_color} {_st_sprache} {_st_niv}: {_st_pkt*100:.0f}% → CEFR {_st_cefr or '?'} ({_st_dat[:10] if _st_dat else '?'})"):
                        st.metric("CEFR-Level", _st_cefr or "?")
                        st.metric("Score", f"{_st_pkt*100:.0f}%")
                        if _st_details:
                            import json as _json
                            try:
                                _details = _json.loads(_st_details)
                                st.markdown("**Fragen & Antworten:**")
                                for _d in _details:
                                    _icon = "✅" if _d.get("korrekt") else "❌"
                                    st.markdown(f"{_icon} {_d.get('frage_id', '?')}: {_d.get('antwort', '?')}")
                            except Exception:
                                pass

            # ── 3. Video-Vorstellung ──
            st.markdown("---")
            st.subheader("🎬 Video-Vorstellung")
            st.info("ℹ️ Video-Link wird vom Kandidaten im Candidate Portal generiert.")
            # Prüfe ob ein Video-Link im Profil gespeichert ist
            _conn_vid = sqlite3.connect(str(DATA_DIR / "feedback.db"))
            _c_vid = _conn_vid.cursor()
            _c_vid.execute("SELECT lebenslauf_text FROM candidates WHERE id = ?", (selected_cand_id,))
            _vid_row = _c_vid.fetchone()
            _conn_vid.close()
            if _vid_row and _vid_row[0] and "meet.jit.si" in (_vid_row[0] or ""):
                import re as _re
                _vid_match = _re.search(r'https://meet\.jit\.si/[\w-]+', _vid_row[0])
                if _vid_match:
                    st.markdown(f"🎥 Video-Link: **{_vid_match.group(0)}**")
            else:
                st.caption("⚪ Kein Video-Link vorhanden.")

            # ── 4. Agent-Ergebnisse (Kompass) ──
            st.markdown("---")
            st.subheader("🤖 Agent-Ergebnisse (Kompass)")
            _agent_files_kompass = {
                "verify_documents": f"verify_documents-kandidat-{selected_cand_id}",
                "check_visa": f"check_visa-kandidat-{selected_cand_id}",
                "check_gdpr": f"check_gdpr-kandidat-{selected_cand_id}",
            }
            _agent_found_kompass = {}
            for _task, _prefix in _agent_files_kompass.items():
                _matches = sorted(ERGEBNISSE.glob(f"{_prefix}*.md"))
                if _matches:
                    _agent_found_kompass[_task] = _matches[-1]
            if _agent_found_kompass:
                _kcol1, _kcol2, _kcol3 = st.columns(3)
                if "verify_documents" in _agent_found_kompass:
                    _vd_text = _agent_found_kompass["verify_documents"].read_text(encoding="utf-8", errors="replace")
                    _vd_status = "AUFFÄLLIG" if "AUFFAELLIG" in _vd_text.upper() or "AUFFÄLLIG" in _vd_text.upper() else (
                        "PLAUSIBEL" if "PLAUSIBEL" in _vd_text.upper() else "UNBEKANNT")
                    _vd_color = "🔴" if _vd_status == "AUFFÄLLIG" else ("🟢" if _vd_status == "PLAUSIBEL" else "🟡")
                    with _kcol1:
                        st.metric("Dokumenten-Check", f"{_vd_color} {_vd_status}")
                if "check_visa" in _agent_found_kompass:
                    _cv_text = _agent_found_kompass["check_visa"].read_text(encoding="utf-8", errors="replace")
                    _cv_status = "ERFORDERLICH" if "ERFORDERLICH" in _cv_text.upper() else (
                        "NICHT ERFORDERLICH" if "NICHT ERFORDERLICH" in _cv_text.upper() else "UNGEWISS")
                    _cv_color = "🔴" if "ERFORDERLICH" in _cv_status and "NICHT" not in _cv_status else (
                        "🟢" if "NICHT" in _cv_status else "🟡")
                    with _kcol2:
                        st.metric("Visum-Status", f"{_cv_color} {_cv_status}")
                if "check_gdpr" in _agent_found_kompass:
                    _gdpr_text = _agent_found_kompass["check_gdpr"].read_text(encoding="utf-8", errors="replace")
                    _gdpr_ok = "KONFORM" in _gdpr_text.upper() and "NICHT_KONFORM" not in _gdpr_text.upper()
                    _gdpr_color = "🟢" if _gdpr_ok else "🔴"
                    _gdpr_label = "KONFORM" if _gdpr_ok else "NICHT KONFORM"
                    with _kcol3:
                        st.metric("DSGVO-Check", f"{_gdpr_color} {_gdpr_label}")
            else:
                st.info("ℹ️ Noch keine Agent-Ergebnisse vorhanden.")


# ═════════════════════════════════════════════════════════════════════
# SKILL 6: PRE-SCREEN
# ═════════════════════════════════════════════════════════════════════

elif skill == "6️⃣ Pre-Screen" and current_role() in ("candidate", "employer", "admin"):
    st.header("6️⃣ Pre-Screen")

    if current_role() == "candidate":
        # ── SELBSTPRÄSENTATIONS-MODUS (CANDIDATE, v4.3) ──
        st.markdown("**Modus: 🎥 Selbstpräsentation** – eigene Fragen + eigener Jitsi-Raum. Die Aufnahme ist später für die HR-Sicht einsehbar.")
        conn_ps = sqlite3.connect(str(DATA_DIR / "feedback.db"))
        c_ps = conn_ps.cursor()
        c_ps.execute("SELECT name, hard_skills, soft_skills, berufserfahrung_jahre, status FROM candidates WHERE id = ?", (st.session_state.user_cand_id,))
        mein_prof = c_ps.fetchone()
        conn_ps.close()
        if not mein_prof:
            st.error("❌ Profil nicht gefunden.")
        else:
            mein_name, meine_skills, meine_soft, meine_jahre, mein_status2 = mein_prof
            if mein_status2 not in ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen"):
                st.warning("⚠️ CV-Pflicht: Laden Sie zuerst Ihren Lebenslauf hoch (📤 Upload oder 👤 Candidate Portal).")
            else:
                st.caption(f"Profil: {mein_name} · Skills: {meine_skills or '–'}")
                if st.button("📹 Selbstpräsentation starten", key="ps_self_btn"):
                    import random, string
                    room_code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
                    room_name = f"self-presentation-{room_code}"
                    meet_url = f"https://meet.jit.si/{room_name}"
                    eigene_fragen = []
                    if meine_skills:
                        for s in [x.strip() for x in meine_skills.split(",") if x.strip()][:4]:
                            eigene_fragen.append(("Technisch", f"Beschreiben Sie ein konkretes Projekt mit {s}. Welche Ergebnisse wurden erzielt?"))
                    if meine_soft:
                        for s in [x.strip() for x in meine_soft.split(",") if x.strip()][:2]:
                            eigene_fragen.append(("Soft Skills", f"Geben Sie ein Beispiel, das Ihre Stärke in '{s}' zeigt."))
                    eigene_fragen.append(("Motivation", "Welche Rolle suchen Sie und warum?"))
                    eigene_fragen.append(("Praktisch", "Wann könnten Sie starten? Wie ist Ihre Gehaltsvorstellung?"))

                    md = f"# Selbstpräsentation: Kandidat #{st.session_state.user_cand_id}\n\n"
                    md += f"**Modus:** Selbstpräsentation (CANDIDATE-Session)\n"
                    md += f"**Datum:** {datetime.now().strftime('%d.%m.%Y')}\n\n"
                    md += "## 📹 Ihr Jitsi-Raum\n\n"
                    md += f"- **Link:** [{meet_url}]({meet_url})\n"
                    md += "- **Empfehlung:** 3–5 Minuten, Start mit Kurzvorstellung, dann die Fragen unten beantworten.\n\n"
                    md += "## 📋 Ihre Leitfragen\n\n"
                    for i, (kat, frage) in enumerate(eigene_fragen, 1):
                        md += f"{i}. **[{kat}]** {frage}\n"
                    md += f"\n*Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} vom KM-HR-Agenten.*\n"
                    filename = f"self-presentation-kandidat-{st.session_state.user_cand_id}-{datetime.now().strftime('%Y-%m-%d')}.md"
                    save_path = save_result(filename, md)
                    st.success(f"✅ Ihr Raum ist bereit: {meet_url}")
                    st.markdown(md)
                    st.download_button("📥 Herunterladen", md, file_name=filename, key="ps_self_dl")
    else:
        # ── RECRUITING-MODUS (EMPLOYER, wie bisher + Video-Einsicht) ──
        st.markdown("**Modus: 🔍 Recruiting** – Screening für ausgewählten Kandidaten.")
        erlaubt = ["lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen"]
        if selected_status not in erlaubt:
            st.error(f"❌ Kandidat muss Lebenslauf hochladen. Status: {selected_status}")
        else:
            # Einsicht: Selbstpräsentationen der Kandidaten
            self_pres = sorted(ERGEBNISSE.glob("self-presentation-kandidat-*.md"))
            if self_pres:
                with st.expander(f"🎥 Selbstpräsentationen der Kandidaten ({len(self_pres)})"):
                    for sp in self_pres:
                        st.markdown(f"- `{sp.name}`")
                        st.download_button("📥 Ansehen", sp.read_text(encoding="utf-8"), file_name=sp.name, key=f"sp_view_{sp.name}")

            profiles = list_profiles()

            if not profiles:
                st.warning("⚠️ Keine Profile gefunden.")
            else:
                sel_profile = st.selectbox(
                    "Kandidat:",
                    profiles,
                    format_func=lambda x: x.name,
                    key="prescreen_profile"
                )

            col1, col2 = st.columns(2)
            with col1:
                stelle = st.text_input("Stelle:", "Senior Cloud/DevOps Engineer", key="ps_stelle")
            with col2:
                score = st.number_input("Match-Score:", 0, 100, 85, key="ps_score")

        if st.button("📹 Pre-Screen erstellen", key="prescreen_btn"):
            with st.spinner("Erstelle Pre-Screening..."):
                profil_text = read_file(str(sel_profile))
                profil_lower = profil_text.lower()

                # Jitsi Meet-Link generieren (Open-Source, kostenlos)
                import random
                import string
                room_code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
                room_name = f"pre-screening-{room_code}"
                meet_url = f"https://meet.jit.si/{room_name}"
                # Hinweis: Für echte Jitsi-Meetings mit Bot:
                # connector: jitsi-meeting → tool: jitsi_join_meeting

                name = sel_profile.stem.replace("profil-", "").replace("-", " ").title()

                # Fragen generieren
                fragen = []

                # Technische Fragen
                fragen.append(("Technisch", "Welche Cloud-Plattformen haben Sie eingesetzt?"))
                if "aws" in profil_lower:
                    fragen.append(("Technisch", "Beschreiben Sie eine AWS-Migration, die Sie geleitet haben."))
                if "kubernetes" in profil_lower:
                    fragen.append(("Technisch", "Wie gehen Sie vor bei einem Kubernetes-Cluster-Ausfall?"))
                fragen.append(("Technisch", "Wie implementieren Sie CI/CD-Pipelines?"))

                # Lücke
                if "terraform" not in profil_lower:
                    fragen.append(("Lücke", "Haben Sie Erfahrung mit Infrastructure-as-Code (z.B. Terraform)?"))

                # Motivation
                fragen.append(("Motivation", "Was reizt Sie an dieser Position?"))
                fragen.append(("Motivation", "Wo sehen Sie sich in 3–5 Jahren?"))
                fragen.append(("Motivation", "Was ist Ihr bevorzugter Arbeitsstil (Remote/Hybrid/Onsite)?"))

                # Praktisch
                fragen.append(("Praktisch", "Wann könnten Sie starten?"))
                fragen.append(("Praktisch", "Ihre Gehaltsvorstellung?"))

                # Kultur-Fit
                if "teamführung" in profil_lower or "mentoring" in profil_lower:
                    fragen.append(("Kultur", "Beschreiben Sie Ihren Führungsstil."))

                # Deutsch-Check
                if "deutsch" not in profil_lower or "muttersprache" not in profil_lower:
                    fragen.append(("Sprache", "Wie ist Ihr Deutsch-Level (B1/B2/C1)?"))

                # Ergebnis
                md = f"# Pre-Screening: {name}\n\n"
                md += f"**Stelle:** {stelle}\n"
                md += f"**Match-Score:** {score}/100\n"
                md += f"**Datum:** {datetime.now().strftime('%d.%m.%Y')}\n\n"
                md += "---\n\n"
                md += "## 📹 Meeting-Details\n\n"
                md += f"- **Link:** [{meet_url}]({meet_url})\n"
                md += f"- **Datum:** {(datetime.now() + timedelta(days=7)).strftime('%A, %d. %B %Y')}\n"
                md += f"- **Uhrzeit:** 10:00–10:45 Uhr\n"
                md += f"- **Dauer:** 45 Minuten\n\n"
                md += "---\n\n"
                md += "## 📋 Screening-Fragen\n\n"

                fragen_count = {}
                for kategorie, frage in fragen:
                    fragen_count[kategorie] = fragen_count.get(kategorie, 0) + 1

                idx = 1
                aktuelle_kategorie = ""
                for kategorie, frage in fragen:
                    if kategorie != aktuelle_kategorie:
                        md += f"\n### {kategorie}\n\n"
                        aktuelle_kategorie = kategorie
                    md += f"{idx}. {frage}\n"
                    idx += 1

                md += f"\n---\n\n"
                md += f"## 📊 Zusammenfassung\n\n"
                md += f"- **Fragen gesamt:** {len(fragen)}\n"
                md += f"- **Technische Fragen:** {fragen_count.get('Technisch', 0)}\n"
                md += f"- **Lücken-Fragen:** {fragen_count.get('Lücke', 0)}\n"
                md += f"- **Motivations-Fragen:** {fragen_count.get('Motivation', 0)}\n"
                md += f"- **Sprach-Check:** {'Ja' if 'Sprache' in fragen_count else 'Nein'}\n\n"
                md += "---\n\n"
                md += f"*Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} vom KM-HR-Agenten.*\n"

                # Speichern
                kandidat_name = sel_profile.stem.replace("profil-", "")
                filename = f"pre-screen-{kandidat_name}-{datetime.now().strftime('%Y-%m-%d')}.md"
                path = save_result(filename, md)
                st.success(f"✅ Pre-Screen gespeichert: `{path}`")
                st.markdown(md)
                st.download_button("📥 Herunterladen", md, file_name=filename)


# ═════════════════════════════════════════════════════════════════════
# SKILL 7: GENERATE ONBOARDING
# ═════════════════════════════════════════════════════════════════════

elif skill == "7️⃣ Generate Onboarding" and current_role() in ("candidate", "employer", "admin"):
    st.header("7️⃣ Generate Onboarding")

    if current_role() == "candidate":
        # ── CANDIDATE-SICHT: nur eigene, freigegebene Checkliste (read-only) ──
        st.markdown("**Modus: 👀 Meine Onboarding-Checkliste** – sichtbar nach Freigabe durch den Arbeitgeber.")
        conn_onb = sqlite3.connect(str(DATA_DIR / "feedback.db"))
        c_onb = conn_onb.cursor()
        c_onb.execute("""SELECT a.id, j.titel, e.firma, a.status FROM applications a
            JOIN jobs j ON a.job_id = j.id JOIN employers e ON j.employer_id = e.id
            WHERE a.candidate_id = ? AND a.status = 'eingestellt' ORDER BY a.aktualisiert_am DESC""",
            (st.session_state.user_cand_id,))
        eingestellt_bew = c_onb.fetchall()
        conn_onb.close()
        if not eingestellt_bew:
            st.info("ℹ️ Noch nicht freigegeben: Eine Onboarding-Checkliste erscheint hier, sobald der Arbeitgeber Sie eingestellt hat (Bewerbungs-Status 'eingestellt').")
        else:
            for b_id, b_titel, b_firma, b_status in eingestellt_bew:
                matches = sorted(ERGEBNISSE.glob(f"onboarding-kandidat-{st.session_state.user_cand_id}-*.md"))
                with st.expander(f"🎉 {b_titel} – {b_firma}"):
                    if matches:
                        onb_text = matches[-1].read_text(encoding="utf-8")
                        st.markdown(onb_text)
                        st.download_button("📥 Herunterladen", onb_text, file_name=matches[-1].name, key=f"onb_dl_{b_id}")
                    else:
                        st.info("ℹ️ Der Arbeitgeber hat Sie eingestellt – die Checkliste wird gerade vorbereitet.")
    else:
        # ── EMPLOYER-SICHT: erstellen + freigeben (wie bisher + Freigabe-Hinweis) ──
        st.markdown("**Modus: 🧰 HR** – Checkliste erstellen und für den eingestellten Kandidaten freigeben.")
        erlaubt = ["lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen"]
        if selected_status not in erlaubt:
            st.error(f"❌ Kandidat muss Lebenslauf hochladen. Status: {selected_status}")
        else:
            profiles = list_profiles()

            if not profiles:
                st.warning("⚠️ Keine Profile gefunden.")
            else:
                sel_profile = st.selectbox(
                    "Kandidat:",
                    profiles,
                    format_func=lambda x: x.name,
                    key="onboarding_profile"
                )

        col1, col2 = st.columns(2)
        with col1:
            stelle = st.text_input("Stelle:", "Senior Cloud/DevOps Engineer", key="onb_stelle")
        with col2:
            startdatum = st.date_input("Startdatum:", datetime.now() + timedelta(days=30), key="onb_date")

        if st.button("📋 Onboarding generieren", key="onboarding_btn"):
            with st.spinner("Generiere Onboarding-Checkliste..."):
                profil_text = read_file(str(sel_profile))
                profil_lower = profil_text.lower()

                name = sel_profile.stem.replace("profil-", "").replace("-", " ").title()

                md = f"# Onboarding-Checkliste: {name}\n\n"
                md += f"**Stelle:** {stelle}\n"
                md += f"**Startdatum:** {startdatum.strftime('%d.%m.%Y')}\n"
                md += f"**Erstellt:** {datetime.now().strftime('%d.%m.%Y')}\n\n"
                md += "---\n\n"

                # 1. Willkommens-E-Mail
                md += "## 1. Willkommens-E-Mail\n\n"
                md += f"**Empfänger:** {name}\n"
                md += f"**Betreff:** Willkommen bei TechVision GmbH!\n\n"
                md += f"Sehr geehrte(r) {name},\n\n"
                md += f"wir freuen uns sehr, Sie ab dem **{startdatum.strftime('%d.%m.%Y')}** "
                md += f"als **{stelle}** in unserem Team begrüßen zu dürfen.\n\n"
                md += f"Mit freundlichen Grüßen,\nHR Team\n\n"
                md += "---\n\n"

                # 2. IT-Ausstattung
                md += "## 2. IT-Ausstattung\n\n"
                md += "| Gerät | Status | Zuständig |\n"
                md += "|---|---|---|\n"
                md += "| MacBook Pro / ThinkPad | ☐ Bestellt | IT-Abteilung |\n"
                md += "| Monitor (27 Zoll) | ☐ Bestellt | IT-Abteilung |\n"
                md += "| Tastatur + Maus | ☐ Bestellt | IT-Abteilung |\n"
                md += "| Headset | ☐ Bestellt | IT-Abteilung |\n"
                md += "| Laptop-Tasche | ☐ Bestellt | IT-Abteilung |\n"
                if "linux" in profil_lower or "ubuntu" in profil_lower:
                    md += "| Linux-Workstation | ☐ Bestellt | IT-Abteilung |\n"
                md += "\n"

                # 3. Systemzugänge
                md += "## 3. Systemzugänge\n\n"
                md += "| System | Zugang | Frist |\n"
                md += "|---|---|---|\n"
                md += "| E-Mail (Google Workspace) | ☐ Angelegt | Tag 1 |\n"
                md += "| Slack | ☐ Angelegt | Tag 1 |\n"
                md += "| GitHub | ☐ Angelegt | Tag 1 |\n"
                md += "| AWS Console | ☐ Angelegt | Tag 3 |\n"
                md += "| Kubernetes Cluster | ☐ Angelegt | Tag 5 |\n"
                md += "| Jira | ☐ Angelegt | Tag 1 |\n"
                md += "| Confluence | ☐ Angelegt | Tag 1 |\n"
                md += "| VPN-Zugang | ☐ Angelegt | Tag 1 |\n\n"

                # 4. Erstgespräche
                md += "## 4. Erstgespräche\n\n"
                md += "| Termin | Person | Thema | Datum |\n"
                md += "|---|---|---|---|\n"
                md += f"| 1 | Teamleitung | Willkommen + Rahmenbedingungen | Tag 1 |\n"
                md += f"| 2 | HR | Vertragsunterlagen + Benefits | Tag 1 |\n"
                md += f"| 3 | IT-Onboarding | Systemzugänge + Geräte | Tag 1 |\n"
                md += f"| 4 | Scrum Master | Agile Prozesse | Tag 2 |\n"
                md += f"| 5 | DevOps-Team | Technische Architektur | Tag 3 |\n"
                md += f"| 6 | Product Owner | Produktübersicht | Tag 5 |\n"
                md += f"| 7 | CTO | Technische Vision | Woche 2 |\n"
                md += f"| 8 | Kollegen | Team-Lunch | Woche 1 |\n\n"

                # 5. Einarbeitungsplan
                md += "## 5. Einarbeitungsplan\n\n"
                md += "| Woche | Thema | Ziel |\n"
                md += "|---|---|---|\n"
                md += "| 1 | Orientierung | Umgebung kennenlernen, Zugänge testen |\n"
                md += "| 2 | Code-Basis | Repository durchlesen, erstes Ticket |\n"
                md += "| 3 | Infrastruktur | AWS Cluster, Monitoring, Deployments |\n"
                md += "| 4 | erstes Feature | Kleine Änderung, PR, Review |\n"
                md += "| 5 | Independence | Eigenständiges Ticket, Daily Standup |\n"
                if "kubernetes" in profil_lower:
                    md += "| 6 | K8s-Audit | Cluster-Review, Optimierungsvorschläge |\n"
                md += "\n"

                # 6. Arbeitsvertrag
                md += "## 6. Arbeitsvertrag\n\n"
                md += "| Dokument | Status | Frist |\n"
                md += "|---|---|---|\n"
                md += "| Arbeitsvertrag | ☐ Zugestellt | Vor Start |\n"
                md += "| IT-Sicherheitsrichtlinie | ☐ Gelesen + unterschrieben | Tag 1 |\n"
                md += "| NDA | ☐ Unterschrieben | Tag 1 |\n"
                md += "| DSGVO-Einwilligung | ☐ Unterschrieben | Tag 1 |\n"
                md += "| Datenschutzrichtlinie | ☐ Gelesen | Tag 1 |\n"
                md += "| Betriebsvereinbarung | ☐ Gelesen | Woche 1 |\n"
                md += "| Allowlist (Versicherung) | ☐ Ausgefüllt | Woche 1 |\n\n"

                md += "---\n\n"
                md += f"*Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} vom KM-HR-Agenten.*\n"

                # Speichern
                kandidat_name = sel_profile.stem.replace("profil-", "")
                filename = f"onboarding-{kandidat_name}-{startdatum.strftime('%Y-%m-%d')}.md"
                path = save_result(filename, md)
                st.success(f"✅ Onboarding-Checkliste gespeichert: `{path}`")
                st.markdown(md)
                st.download_button("📥 Herunterladen", md, file_name=filename)


# ═════════════════════════════════════════════════════════════════════
# SKILL 8: STORE FEEDBACK
# ═════════════════════════════════════════════════════════════════════

elif skill == "8️⃣ Store Feedback" and current_role() in ("employer", "admin"):
    st.header("8️⃣ Store Feedback")
    st.markdown("Speichert Feedback in SQLite und passt Matching-Gewichtung dynamisch an.")

    erlaubt = ["lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen"]
    if selected_status not in erlaubt:
        st.error(f"❌ Kandidat muss Lebenslauf hochladen. Status: {selected_status}")
    else:
        profiles = list_profiles()

    # SQLite initialisieren
    db_path = DATA_DIR / "feedback.db"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT NOT NULL,
        kandidat_name TEXT NOT NULL,
        score INTEGER NOT NULL,
        kategorie TEXT NOT NULL,
        fachlich_korrekt INTEGER DEFAULT 0,
        skills_richtig INTEGER DEFAULT 0,
        standort_zutreffend INTEGER DEFAULT 0,
        empfehlung_hilfreich INTEGER DEFAULT 0,
        eingeladen TEXT DEFAULT 'Nein',
        anmerkungen TEXT,
        datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS gewichtung_historie (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        kategorie TEXT NOT NULL,
        alte_gewichtung INTEGER NOT NULL,
        neue_gewichtung INTEGER NOT NULL,
        grund TEXT NOT NULL
    )""")
    # Phase 3: match_id ist eindeutig (kein INSERT OR REPLACE mehr;
    # gleicher Tag = Update, nächster Tag = neuer Datensatz durch Datums-Suffix)
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_match_id ON feedback(match_id)")
    conn.commit()

    if not profiles:
        st.warning("⚠️ Keine Profile gefunden.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            sel_profile = st.selectbox(
                "Kandidat:",
                profiles,
                format_func=lambda x: x.name,
                key="feedback_profile"
            )
        with col2:
            score = st.number_input("Match-Score:", 0, 100, 85, key="fb_score")

        stellenprofil = st.text_input("Stellenprofil:", "Cloud/DevOps Engineer", key="fb_stellenprofil")
        eingeladen = st.selectbox("Eingeladen?", ["Ja", "Nein"], key="fb_eingeladen")

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            fachlich = st.slider("Fachlich korrekt:", 0, 5, 4, key="fb_fachlich")
        with col_b:
            skills = st.slider("Skills richtig:", 0, 5, 4, key="fb_skills")
        with col_c:
            standort = st.slider("Standort zutreffend:", 0, 5, 4, key="fb_standort")
        with col_d:
            empfehlung = st.slider("Empfehlung hilfreich:", 0, 5, 4, key="fb_empf")

        anmerkungen = st.text_area("Anmerkungen:", key="fb_anmerkungen")

        if st.button("💾 Feedback speichern", key="feedback_btn"):
            with st.spinner("Speichere Feedback..."):
                profil_text = read_file(str(sel_profile))
                name = sel_profile.stem.replace("profil-", "").replace("-", " ").title()

                # Kategorie berechnen (Connector: hr-benchmark → get_score_category)
                kategorie = "Nicht passend"
                try:
                    _cat = _mcp_connector_call(HR_BENCHMARK_SERVER, "get_score_category", {"score": score})
                    if _cat and "category" in _cat:
                        _cat_map = {"Strong": "Hervorragend", "Consider": "Bedingt", "Weak": "Nicht passend"}
                        kategorie = _cat_map.get(_cat["category"], "Nicht passend")
                        if kategorie == "Bedingt" and score >= 75:
                            kategorie = "Gut"
                except Exception:
                    if score >= 90: kategorie = "Hervorragend"
                    elif score >= 75: kategorie = "Gut"
                    elif score >= 60: kategorie = "Bedingt"

                # Match-ID generieren
                match_id = f"{sel_profile.stem}-{datetime.now().strftime('%Y-%m-%d')}"

                # Stellenprofil aus Session holen
                stellenprofil = st.session_state.get('fb_stellenprofil', 'Unbekannt')

                # In SQLite speichern (Phase 3: idempotent statt INSERT OR REPLACE
                # - gleicher Tag = UPDATE, nächster Tag = neuer Datensatz)
                c.execute("SELECT id FROM feedback WHERE match_id = ?", (match_id,))
                _fb_existing = c.fetchone()
                if _fb_existing:
                    c.execute("""UPDATE feedback SET kandidat_name=?, stellenprofil=?, score=?, kategorie=?,
                        fachlich_korrekt=?, skills_richtig=?, standort_zutreffend=?,
                        empfehlung_hilfreich=?, eingeladen=?, anmerkungen=?
                        WHERE match_id=?""",
                        (name, stellenprofil, score, kategorie,
                         fachlich, skills, standort, empfehlung,
                         eingeladen, anmerkungen, match_id))
                else:
                    c.execute("""INSERT INTO feedback
                        (match_id, kandidat_name, stellenprofil, score, kategorie,
                         fachlich_korrekt, skills_richtig, standort_zutreffend,
                         empfehlung_hilfreich, eingeladen, anmerkungen)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (match_id, name, stellenprofil, score, kategorie,
                         fachlich, skills, standort, empfehlung,
                         eingeladen, anmerkungen))
                conn.commit()

                # Phase 4: Geschlossener Loop – nur bei NEUEM Feedback (INSERT)
                if _fb_existing:
                    gewichtung_msg = "ℹ️ Korrektur (heute bereits vorhanden) – keine neue Gewichtungsanpassung."
                else:
                    gewichtung_msg = adjust_weights_from_feedback(
                        eingeladen, score,
                        f"{'Erfolgreicher' if eingeladen == 'Ja' else 'Gescheiterter'} Match {name}: Score {score}/100",
                        conn)

                # Ergebnis
                md = f"# Feedback: {name}\n\n"
                md += f"**Match-ID:** `{match_id}`\n"
                md += f"**Score:** {score}/100 ({kategorie})\n"
                md += f"**Eingeladen:** {eingeladen}\n"
                md += f"**Datum:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                md += "---\n\n"
                md += "## Bewertung\n\n"
                md += f"| Kriterium | Punkte |\n"
                md += f"|---|---|\n"
                md += f"| Fachlich korrekt | {fachlich}/5 |\n"
                md += f"| Skills richtig | {skills}/5 |\n"
                md += f"| Standort zutreffend | {standort}/5 |\n"
                md += f"| Empfehlung hilfreich | {empfehlung}/5 |\n"
                md += f"| **Durchschnitt** | **{(fachlich+skills+standort+empfehlung)/4:.1f}/5** |\n\n"
                md += f"**Anmerkungen:** {anmerkungen}\n\n" if anmerkungen else ""
                md += f"## Gewichtungsanpassung\n\n{gewichtung_msg}\n\n"

                # Historie anzeigen
                c.execute("SELECT kategorie, alte_gewichtung, neue_gewichtung, grund FROM gewichtung_historie ORDER BY id DESC LIMIT 5")
                hist = c.fetchall()
                if hist:
                    md += "### Letzte Änderungen\n\n"
                    md += "| Kategorie | Alt | Neu | Grund |\n"
                    md += "|---|---|---|---|\n"
                    for h in hist:
                        md += f"| {h[0]} | {h[1]}% | {h[2]}% | {h[3]} |\n"

                md += "\n---\n\n"
                md += f"*Erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M')} vom KM-HR-Agenten.*\n"

                # Speichern
                kandidat_name = sel_profile.stem.replace("profil-", "")
                filename = f"feedback-{kandidat_name}-{datetime.now().strftime('%Y-%m-%d')}.md"
                path = save_result(filename, md)
                st.success(f"✅ Feedback gespeichert: `{path}`")
                st.markdown(md)
                st.download_button("📥 Herunterladen", md, file_name=filename)

                # Skill 16: export_report – Automatisch nach Feedback
                if not _fb_existing:  # Nur bei NEUEM Feedback (INSERT)
                    queue_agent_task("export_report", {"application_id": None,
                                                       "candidate_id": sel_profile.stem.replace("profil-", ""),
                                                       "job_id": None, "match_id": match_id})

    conn.close()


elif skill == "👤 Candidate Portal" and current_role() == "candidate":
    st.header("👤 Candidate Portal")
    st.markdown("Kandidat: Profil anlegen, Lebenslauf hochladen und Status verfolgen (session-gebunden, v4.3).")

    # SQLite initialisieren
    db_path = DATA_DIR / "feedback.db"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        telefon TEXT,
        standort TEXT,
        nationalitaet TEXT,
        visum_status TEXT DEFAULT 'EU-Bürger',
        verfuegbarkeit TEXT DEFAULT 'Sofort',
        berufserfahrung_jahre INTEGER,
        aktuelle_position TEXT,
        hard_skills TEXT,
        soft_skills TEXT,
        abschluss TEXT,
        deutsch TEXT DEFAULT 'B1',
        englisch TEXT DEFAULT 'B1',
        gehaltsvorstellung INTEGER,
        lebenslauf_datei TEXT,
        lebenslauf_text TEXT,
        status TEXT DEFAULT 'registriert',
        registriert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS candidate_status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        changed_by TEXT,
        notizen TEXT,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )""")
    conn.commit()

    # Tabs
    tab1, tab2, tab3, tab3b, tab5, tab4 = st.tabs(["📝 Registrieren", "👤 Profil", "📄 Lebenslauf", "🗂️ Dokumente", "🗣️ Sprachtest", "📊 Status"])

    with tab1:
        st.subheader("Registrierung")
        reg_email = st.text_input("E-Mail:", key="reg_email")
        reg_name = st.text_input("Name:", key="reg_name")
        reg_password = st.text_input("Passwort:", type="password", key="reg_password")

        if st.button("📝 Registrieren", key="reg_btn"):
            if not reg_email or not reg_name or not reg_password:
                st.error("❌ Alle Felder ausfüllen!")
            elif len(reg_password) < 8:
                st.error("❌ Passwort mindestens 8 Zeichen!")
            else:
                try:
                    import hashlib
                    pw_hash = hashlib.sha256(reg_password.encode()).hexdigest()
                    c.execute("INSERT INTO candidates (email, password_hash, name) VALUES (?, ?, ?)",
                              (reg_email, pw_hash, reg_name))
                    conn.commit()
                    st.success(f"✅ Registriert: {reg_name} ({reg_email})")
                except sqlite3.IntegrityError:
                    st.error("❌ E-Mail bereits vorhanden!")

    with tab2:
        st.subheader("Mein Profil")
        st.caption("🔒 Session-gebunden (v4.3): Sie bearbeiten nur Ihre eigenen Daten.")
        # Session-gebunden statt Dropdown
        cand_id = st.session_state.user_cand_id
        c.execute("SELECT name, email FROM candidates WHERE id = ?", (cand_id,))
        mein_eintrag = c.fetchone()
        if not mein_eintrag:
            st.error("❌ Profil nicht gefunden.")
        else:
            selected = f"{mein_eintrag[0]} ({mein_eintrag[1]})"

            col1, col2 = st.columns(2)
            with col1:
                standort = st.text_input("Standort:", key="prof_standort")
                nationalitaet = st.text_input("Nationalität:", key="prof_nat")
                visum = st.selectbox("Visum-Status:", ["EU-Bürger", "Arbeitsvisum", "Kein Visum", "Sonstiges"], key="prof_visum")
                verfuegbarkeit = st.selectbox("Verfügbarkeit:", ["Sofort", "1 Monat", "3 Monate", "Kündigungslaufzeit"], key="prof_verf")
            with col2:
                position = st.text_input("Aktuelle Position:", key="prof_pos")
                erfahrung = st.number_input("Jahre Erfahrung:", 0, 50, key="prof_erf")
                hard_skills = st.text_input("Hard Skills (kommasepariert):", key="prof_hard")
                soft_skills = st.text_input("Soft Skills (kommasepariert):", key="prof_soft")

            col3, col4 = st.columns(2)
            with col3:
                abschluss = st.selectbox("Abschluss:", ["Bachelor", "Master", "Diplom", "PhD", "Sonstiges"], key="prof_abschluss")
                deutsch = st.selectbox("Deutsch:", ["A1", "A2", "B1", "B2", "C1", "C2", "Muttersprache"], key="prof_de")
                englisch = st.selectbox("Englisch:", ["A1", "A2", "B1", "B2", "C1", "C2", "Muttersprache"], key="prof_en")
            with col4:
                gehalt = st.number_input("Gehaltsvorstellung (EUR):", 0, 200000, key="prof_gehalt")

            if st.button("💾 Profil speichern", key="prof_save_btn"):
                c.execute("""UPDATE candidates SET
                    standort=?, nationalitaet=?, visum_status=?, verfuegbarkeit=?,
                    aktuelle_position=?, berufserfahrung_jahre=?, hard_skills=?, soft_skills=?,
                    abschluss=?, deutsch=?, englisch=?, gehaltsvorstellung=?,
                    status='profil_vollstaendig', aktualisiert_am=CURRENT_TIMESTAMP
                    WHERE id=?""",
                    (standort, nationalitaet, visum, verfuegbarkeit,
                     position, erfahrung, hard_skills, soft_skills,
                     abschluss, deutsch, englisch, gehalt, cand_id))
                conn.commit()
                st.success(f"✅ Profil gespeichert für {selected}")
                st.rerun()

        # ── Passwort ändern (N5, Design-Entscheidung: knowledge/portal/candidate-portal-fields.md) ──
        with st.expander("🔒 Passwort ändern"):
            altes_pw = st.text_input("Aktuelles Passwort:", type="password", key="pw_alt_cand")
            neues_pw = st.text_input("Neues Passwort:", type="password", key="pw_neu_cand")
            neues_pw_wdh = st.text_input("Neues Passwort wiederholen:", type="password", key="pw_wdh_cand")
            if st.button("🔒 Passwort ändern", key="pw_change_cand"):
                if not altes_pw or not neues_pw or not neues_pw_wdh:
                    st.error("❌ Bitte alle Felder ausfüllen.")
                elif neues_pw != neues_pw_wdh:
                    st.error("❌ Passwörter stimmen nicht überein.")
                else:
                    from webui.logic import change_password
                    ok, msg = change_password(conn, "candidates", cand_id, altes_pw, neues_pw)
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

    with tab3:
        st.subheader("Lebenslauf hochladen")
        st.caption("🔒 Session-gebunden (v4.3): Upload füllt nur Ihr eigenes Profil.")
        # Session-gebunden statt Dropdown
        cand_id = st.session_state.user_cand_id
        c.execute("SELECT name, email FROM candidates WHERE id = ?", (cand_id,))
        mein_eintrag = c.fetchone()
        if not mein_eintrag:
            st.error("❌ Profil nicht gefunden.")
        else:
            selected = f"{mein_eintrag[0]} ({mein_eintrag[1]})"

            cv_file = st.file_uploader("Lebenslauf (PDF/TXT):", type=["pdf", "txt"], key="cv_upload_portal")
            if cv_file:
                # Datei speichern
                save_path = TESTDATEN / f"kandidat-{cand_id}-{cv_file.name}"
                save_path.write_bytes(cv_file.getvalue())

                # Text extrahieren
                if cv_file.type == "application/pdf":
                    text = extract_pdf_text(str(save_path))
                else:
                    text = cv_file.getvalue().decode("utf-8", errors="replace")

                # SQLite aktualisieren
                c.execute("""UPDATE candidates SET
                    lebenslauf_datei=?, lebenslauf_text=?,
                    status='lebenslauf_hochgeladen', aktualisiert_am=CURRENT_TIMESTAMP
                    WHERE id=?""",
                    (str(save_path), text[:5000], cand_id))
                conn.commit()

                st.success(f"✅ Lebenslauf hochgeladen: {len(text)} Zeichen")
                with st.expander("📄 Vorschau"):
                    st.text(text[:2000])

    with tab3b:
        # ── Spec v6.1: Dokumente (Zeugnis/Zertifikat/Sprachzeugnis/Pass/Visa) ──
        st.subheader("Dokumente hochladen")
        st.caption("🔒 Session-gebunden (v6.1): Zeugnisse, Zertifikate, Sprachzeugnisse, Pass/Visa. "
                   "Ihr Lebenslauf und Profil-Status bleiben unangetastet. Der Agent prüft diese "
                   "Dokumente automatisch bei Ihrer Bewerbung (verify_documents).")
        cand_id_doc = st.session_state.user_cand_id
        # Tabelle (idempotent, wie applications)
        c.execute("""CREATE TABLE IF NOT EXISTS candidate_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            datei_pfad TEXT NOT NULL,
            dokumententyp TEXT NOT NULL,
            hochgeladen_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()

        _doc_typen = ["Zeugnis", "Zertifikat", "Sprachzeugnis", "Pass", "Visum/Aufenthaltstitel", "Sonstiges"]
        doc_files = st.file_uploader("Dokumente (PDF/TXT, mehrere möglich):",
                                     type=["pdf", "txt"], key="doc_upload_portal",
                                     accept_multiple_files=True)
        doc_typ = st.selectbox("Dokumenttyp (gilt für alle in diesem Upload):", _doc_typen, key="doc_typ_portal")
        if doc_files:
            import re as _re
            _typ_slug = _re.sub(r"[^A-Za-zÄÖÜäöüß]+", "-", doc_typ).strip("-")
            for df in doc_files:
                _path = TESTDATEN / f"kandidat-{cand_id_doc}-{_typ_slug}-{df.name}"
                _path.write_bytes(df.getvalue())
                c.execute("INSERT INTO candidate_documents (candidate_id, datei_pfad, dokumententyp) VALUES (?, ?, ?)",
                          (cand_id_doc, str(_path), doc_typ))
                conn.commit()
            st.success(f"✅ {len(doc_files)} Dokument(e) gespeichert als Typ '{doc_typ}'.")

        # Eigene Dokumente auflisten + Löschen (Art. 17 Selbstservice)
        c.execute("SELECT id, datei_pfad, dokumententyp, hochgeladen_am FROM candidate_documents "
                  "WHERE candidate_id = ? ORDER BY hochgeladen_am DESC", (cand_id_doc,))
        meine_doks = c.fetchall()
        if not meine_doks:
            st.info("ℹ️ Noch keine Dokumente hochgeladen.")
        else:
            st.markdown(f"**Meine Dokumente ({len(meine_doks)}):**")
            for d_id, d_pfad, d_typ, d_dat in meine_doks:
                _dc1, _dc2, _dc3 = st.columns([4, 2, 1])
                with _dc1:
                    st.markdown(f"📄 **{d_typ}** — {Path(d_pfad).name}")
                with _dc2:
                    st.caption(str(d_dat)[:10] if d_dat else "")
                with _dc3:
                    if st.button("🗑️", key=f"doc_del_{d_id}", help="Dokument löschen (Datei + Eintrag)"):
                        try:
                            Path(d_pfad).unlink(missing_ok=True)
                        except Exception:
                            pass
                        c.execute("DELETE FROM candidate_documents WHERE id = ? AND candidate_id = ?", (d_id, cand_id_doc))
                        conn.commit()
                        st.rerun()

    with tab5:
        # ── Phase 2: Sprachtest-Integration ──
        st.subheader("🗣️ Sprachtest")
        st.caption("🔒 Session-gebunden: Testen Sie Ihr Sprachniveau (DE/EN/FR). "
                   "Ergebnis landet in Ihrem Profil (CEFR-Level).")
        cand_id_test = st.session_state.user_cand_id

        # Tabelle (idempotent)
        c.execute("""CREATE TABLE IF NOT EXISTS language_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            sprache TEXT NOT NULL,
            niveau TEXT NOT NULL,
            fragen_anzahl INTEGER DEFAULT 10,
            punkte REAL DEFAULT 0,
            cefr_level TEXT,
            test_datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")
        conn.commit()

        # Vorherige Tests anzeigen
        c.execute("SELECT sprache, niveau, punkte, cefr_level, test_datum FROM language_tests WHERE candidate_id = ? ORDER BY test_datum DESC LIMIT 5", (cand_id_test,))
        alte_tests = c.fetchall()
        if alte_tests:
            st.markdown("**Bisherige Tests:**")
            for t in alte_tests:
                st.markdown(f"- {t[0]} {t[1]}: {t[2]*100:.0f}% → CEFR {t[3] or '?'} ({t[4][:10] if t[4] else '?'})")
            st.markdown("---")

        # Neuer Test (nur wenn kein aktiver Test)
        if not st.session_state.get("test_active"):
            col_s, col_n, col_a = st.columns(3)
            with col_s:
                sprache = st.selectbox("Sprache:", ["Deutsch", "Englisch", "Französisch"], key="test_sprache")
            with col_n:
                niveau = st.selectbox("Niveau:", ["A1", "A2", "B1", "B2", "C1"], key="test_niveau")
            with col_a:
                anzahl = st.number_input("Fragen:", 5, 20, 10, key="test_anzahl")

            if st.button("🧪 Test starten", key="test_start_btn"):
                st.session_state["test_active"] = True
                # Widget-Werte in eigene Keys speichern (nicht in Widget-Keys!)
                st.session_state["active_sprache"] = sprache
                st.session_state["active_niveau"] = niveau
                st.session_state["active_anzahl"] = anzahl
                st.session_state["test_fragen"] = []
                st.session_state["test_antworten"] = {}
                st.session_state["test_idx"] = 0
                st.session_state["test_scores"] = []
                st.rerun()

        # Test aktiv
        if st.session_state.get("test_active"):
            _ts = st.session_state.get("active_sprache", "Deutsch")
            _tn = st.session_state.get("active_niveau", "A1")
            _ta = st.session_state.get("active_anzahl", 10)
            st.markdown(f"**{_ts} {_tn}** – Frage {st.session_state.get('test_idx', 0)+1}/{_ta}")

            # Fragen laden (beim ersten Mal) — FastMCP-Client
            if not st.session_state.get("test_fragen"):
                try:
                    import importlib.util as _ilu
                    from fastmcp import Client as _MCPClient
                    _spec = _ilu.spec_from_file_location(
                        "language_test_server", str(Path(__file__).parent / "scripts" / "language-test-server.py"))
                    _mod = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_mod)

                    async def _load_test():
                        async with _MCPClient(_mod.mcp) as _cli:
                            _res = await _cli.call_tool("generate_test",
                                {"sprache": _ts, "niv": _tn, "anzahl": _ta})
                            import json as _j
                            return _j.loads(_res.data)

                    data = asyncio.run(_load_test())
                    st.session_state["test_fragen"] = data.get("fragen", [])
                except Exception as e:
                    st.error(f"Fehler beim Laden der Fragen: {e}")
                    st.session_state["test_active"] = False

            fragen = st.session_state.get("test_fragen", [])
            idx = st.session_state.get("test_idx", 0)

            if idx < len(fragen):
                frage = fragen[idx]
                st.markdown(f"**{frage.get('frage', '?')}**")
                antworten = frage.get("antworten", [])
                antwort = st.radio("Antwort:", antworten, key=f"test_q_{idx}")

                if st.button("Weiter →", key="test_next_btn"):
                    st.session_state["test_antworten"][idx] = antwort
                    st.session_state["test_idx"] = idx + 1
                    st.rerun()
            else:
                # Test beendet → Bewertung
                st.success("✅ Test beendet! Bewertung...")
                gesamtpunkte = 0
                details = []
                for i, frage in enumerate(fragen):
                    antwort = st.session_state["test_antworten"].get(i, "")
                    # Einfache Bewertung (LLM-Call wäre besser, aber langsamer)
                    loesung = frage.get("loesung", "").strip().lower()
                    korrekt = antwort.strip().lower() == loesung or antwort.strip().lower() in loesung
                    punkte = 1 if korrekt else 0
                    gesamtpunkte += punkte
                    details.append({"frage_id": frage.get("id"), "antwort": antwort, "korrekt": korrekt})

                # CEFR-Level via MCP-Server (eine Quelle der Wahrheit, Refactor 20.09.2026)
                avg = gesamtpunkte / len(fragen) if fragen else 0
                _cefr = cefr_from_avg(avg)
                cefr = _cefr["level"]

                # In DB speichern
                import json as _json
                c.execute("INSERT INTO language_tests (candidate_id, sprache, niveau, fragen_anzahl, punkte, cefr_level, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (cand_id_test, st.session_state.get('active_sprache', 'Deutsch'), st.session_state.get('active_niveau', 'A1'),
                     len(fragen), avg, cefr, _json.dumps(details, ensure_ascii=False)))
                conn.commit()

                st.metric("Ergebnis", f"{gesamtpunkte}/{len(fragen)} ({avg*100:.0f}%)")
                st.metric("CEFR-Level", cefr)
                if _cefr["beschreibung"]:
                    st.caption(f"📖 {_cefr['beschreibung']} — {_cefr['empfehlung']}")

                # Test zurücksetzen
                st.session_state["test_active"] = False
                st.session_state["test_fragen"] = []
                st.session_state["test_antworten"] = {}
                st.session_state["test_idx"] = 0

        # ── Video-Vorstellung (Jitsi) ──
        st.markdown("---")
        st.subheader("🎬 Video-Vorstellung (optional)")
        st.caption("Nehmen Sie ein kurzes Video auf (2-3 Minuten). Der Link wird mit Ihrer Bewerbung gesendet.")
        if st.button("🎥 Jitsi-Link generieren", key="video_link_btn"):
            import uuid
            video_code = f"vorstellung-{cand_id_test}-{str(uuid.uuid4())[:8]}"
            video_url = f"https://meet.jit.si/{video_code}"
            st.session_state["video_link"] = video_url
            st.success(f"✅ Video-Link: {video_url}")
            st.info("📌 Merken Sie sich diesen Link für Ihr Bewerbungsgespräch.")
        if st.session_state.get("video_link"):
            st.markdown(f"🎥 Ihr Video-Link: **{st.session_state['video_link']}**")

    with tab4:
        st.subheader("Mein Status")
        st.caption("🔒 Session-gebunden (v4.3): Nur Ihr eigener Status und Verlauf.")
        # Session-gebunden statt Liste aller Kandidaten
        c.execute("SELECT id, name, email, status, registriert_am, aktualisiert_am FROM candidates WHERE id = ?", (st.session_state.user_cand_id,))
        kandidaten = c.fetchall()
        if not kandidaten:
            st.error("❌ Profil nicht gefunden.")
        else:
            for k in kandidaten:
                with st.expander(f"{k[1]} ({k[2]})"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Status", k[3])
                    with col2:
                        st.metric("Registriert", k[4][:10] if k[4] else "–")
                    with col3:
                        st.metric("Aktualisiert", k[5][:10] if k[5] else "–")

                    # Status-Verlauf
                    c.execute("SELECT status, changed_at, notizen FROM candidate_status_history WHERE candidate_id = ? ORDER BY changed_at DESC", (k[0],))
                    history = c.fetchall()
                    if history:
                        st.markdown("**Verlauf:**")
                        for h in history:
                            notiz = f" ({h[2]})" if h[2] else ""
                            st.markdown(f"- {h[1][:16]} – {h[0]}{notiz}")

    conn.close()


# ═════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════
# SKILL 11: JOB APPLICATION (Stellenangebote – Kandidaten-Seite)
# Spec: skills/job-application/SKILL.md · Status: knowledge/lifecycle/application-status.md
# ═══════════════════════════════════════════════════════════════════

elif skill == "💼 Stellenangebote":
    st.header("💼 Stellenangebote")

    # ── HR-SICHT (v4.5): Bewerbungs-Status verwalten (abgeglichen mit Arbeitgeber-Portal Tab 3) ──
    if current_role() in ("employer", "admin"):
        st.markdown("**Modus: 🧰 HR** – Aktive Bewerber verwalten (Status ändern, einladen, ablehnen)."
                    + (" *(Admin-Sicht: alle Arbeitgeber)*" if current_role() == "admin" else ""))
        conn_hr = sqlite3.connect(str(DATA_DIR / "feedback.db"))
        c_hr = conn_hr.cursor()
        if current_role() == "admin":
            # Admin-Betrieb: Bewerbungen über ALLE Arbeitgeber einsehbar (Kontrolle)
            c_hr.execute("""SELECT a.id, a.candidate_id, a.status, a.bewerbungstext, a.erstellungsdatum,
                j.titel, j.id, e.firma
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                JOIN employers e ON j.employer_id = e.id
                ORDER BY a.erstellungsdatum DESC""")
        else:
            c_hr.execute("""SELECT a.id, a.candidate_id, a.status, a.bewerbungstext, a.erstellungsdatum,
                j.titel, j.id, e.firma
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                JOIN employers e ON j.employer_id = e.id
                WHERE e.id = ? ORDER BY a.erstellungsdatum DESC""", (st.session_state.employer_id,))
        hr_rows = c_hr.fetchall()
        conn_hr.close()
        # Abgleich mit Tab 3: aktive Bewerbungen (mit Aktionen) vs. Archiv (read-only)
        AKTIV = ("eingegangen", "angesehen", "eingeladen")
        hr_aktiv = [r for r in hr_rows if r[2] in AKTIV]
        hr_archiv = [r for r in hr_rows if r[2] not in AKTIV]
        erl_hr = {"eingegangen": ["angesehen", "abgelehnt"], "angesehen": ["eingeladen", "abgelehnt"],
                  "eingeladen": ["eingestellt", "abgelehnt"], "eingestellt": [], "abgelehnt": [], "zurückgezogen": []}
        badge = {"eingegangen": "📨", "angesehen": "👁️", "eingeladen": "✅", "eingestellt": "🎉", "abgelehnt": "❌", "zurückgezogen": "↩️"}

        st.markdown(f"### 📥 Aktive Bewerber ({len(hr_aktiv)})")
        if not hr_aktiv:
            st.info("ℹ️ Keine aktiven Bewerbungen für diese Stelle (Skill: 💼 Stellenangebote bei den Kandidaten).")
        for a_id, k_id, a_status, a_text, a_dat, j_titel, j_id, e_firma in hr_aktiv:
            # Phase 5 (Spec §7): Agent-Status-Badge an jedem Bewerber
            try:
                _conn_b = sqlite3.connect(str(DATA_DIR / "feedback.db"))
                _cb = _conn_b.cursor()
                _cb.execute("""SELECT task_type, status FROM agent_tasks
                    WHERE payload LIKE ? AND task_type IN ('match_candidate', 'check_compliance', 'assess_culture_fit')
                    GROUP BY task_type""", (f'%"application_id": {a_id}%',))
                _agent_rows = {t: s for t, s in _cb.fetchall()}
                _conn_b.close()
            except Exception:
                _agent_rows = {}
            if _agent_rows:
                _ms = _agent_rows.get("match_candidate", "-")
                _cs = _agent_rows.get("check_compliance", "-")
                _fs = _agent_rows.get("assess_culture_fit", "-")
                # Duplikat-Bereinigung (Phase 0): _sym-lambda → _agent_status_symbol()
                _badge_txt = f"🤖 Agent-Ergebnisse: Match {_agent_status_symbol(_ms)} · Compliance {_agent_status_symbol(_cs)} · Culture-Fit {_agent_status_symbol(_fs)}"
            else:
                _badge_txt = "🤖 Agent-Ergebnisse: (noch nicht gestartet)"
            with st.expander(f"{badge.get(a_status, '📄')} {j_titel} – Kandidat #{k_id} ({a_status})\n\n{_badge_txt}"):
                st.caption(f"Stelle: {j_titel} ({e_firma}) · Eingegangen: {str(a_dat)[:10]}")
                st.markdown(f"**Pseudonym:** Kandidat #{k_id}")
                if a_text:
                    st.markdown(f"**Motivation:**\n\n> {a_text}")
                naechste = erl_hr.get(a_status, [])
                if naechste:
                    # Phase 5: HR wählt den Einladungs-Termin (geht in die Automatik-Mail,
                    # Spec agent-automation.md §5 – vorher hardcoded 10:00/30)
                    _inv_vals = None
                    if "eingeladen" in naechste:
                        st.markdown("**📅 Einladungs-Termin (wird in die Automatik-Mail übernommen):**")
                        _dc1, _dc2, _dc3 = st.columns(3)
                        with _dc1:
                            inv_datum = st.date_input("Datum", value=datetime.now().date() + timedelta(days=1),
                                                      min_value=datetime.now().date(), key=f"inv_datum_{a_id}")
                        with _dc2:
                            inv_zeit = st.time_input("Uhrzeit", value=time(10, 0), key=f"inv_zeit_{a_id}")
                        with _dc3:
                            inv_dauer = st.selectbox("Dauer (Min.)", [15, 30, 45, 60], index=1, key=f"inv_dauer_{a_id}")
                        _inv_vals = {"termin_datum": inv_datum.strftime("%Y-%m-%d"),
                                     "termin_uhrzeit": inv_zeit.strftime("%H:%M"),
                                     "termin_dauer_min": int(inv_dauer)}
                    cols = st.columns(len(naechste))
                    for i, ns in enumerate(naechste):
                        with cols[i]:
                            if st.button(f"→ {ns}", key=f"hr_bew_{a_id}_{ns}"):
                                conn2 = sqlite3.connect(str(DATA_DIR / "feedback.db"))
                                c2 = conn2.cursor()
                                c2.execute("UPDATE applications SET status = ?, aktualisiert_am = CURRENT_TIMESTAMP WHERE id = ?", (ns, a_id))
                                c2.execute("INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, ?, 'arbeitgeber_hr_seite')", (a_id, ns))
                                conn2.commit()
                                conn2.close()
                                # Phase 5 (Spec §3): Übergänge erzeugen Agent-Tasks (Variante A)
                                # Nur für Einladung/Absage/Einstellung – andere Status erzeugen KEINEN Task
                                _hook_task = {"eingeladen": "create_invitation", "abgelehnt": "send_rejection",
                                              "eingestellt": "onboarding_release"}.get(ns)
                                if _hook_task:
                                    _pl = {"application_id": a_id, "candidate_id": k_id, "job_id": j_id,
                                           "trigger": "hr_klick_hr_seite"}
                                    if _hook_task == "create_invitation" and _inv_vals:
                                        _pl.update(_inv_vals)  # HR-gewählter Termin
                                    queue_agent_task(_hook_task, _pl)
                                st.rerun()
                else:
                    st.caption("ℹ️ Finaler Status erreicht.")
                # Phase 5 Ergänzung: bei eingeladenen Bewerbern sieht HR denselben
                # Kalendereintrag wie der Kandidat (Jitsi + ICS-Download)
                if a_status == "eingeladen":
                    render_hr_ics_download(a_id)
                # Spec v6: Visum-Antrag-Bestätigung (nur bei eingeladen + Visum-Bedarf)
                if a_status == "eingeladen":
                    _visa_done = False
                    try:
                        _cv = sqlite3.connect(str(DATA_DIR / "feedback.db")); _cc = _cv.cursor()
                        _cc.execute("""SELECT COUNT(*) FROM agent_tasks WHERE task_type='visa_confirmation'
                            AND status IN ('pending','running','done') AND payload LIKE ?""", (f'%%"application_id": {a_id}%%',))
                        _visa_done = _cc.fetchone()[0] > 0; _cv.close()
                    except Exception:
                        pass
                    if not _visa_done and st.button("📩 Visum-Antrag bestätigen", key=f"visa_{a_id}"):
                        queue_agent_task("visa_confirmation", {"application_id": a_id,
                                                               "candidate_id": k_id, "job_id": j_id,
                                                               "trigger": "hr_klick_hr_seite"})
                        st.success("📩 Visum-Schritte-Mail an den Kandidaten ausgelöst (Agent sendet).")
                        st.rerun()
                    elif _visa_done:
                        st.caption("✅ Visum-Schritte-Mail versendet.")

        # ── Archiv: finale Status (read-only, gleiche Datenbasis wie Tab 3) ──
        with st.expander(f"📋 Archiv ({len(hr_archiv)}) – eingestellt / abgelehnt / zurückgezogen"):
            if not hr_archiv:
                st.caption("ℹ️ Keine archivierten Bewerbungen.")
            for a_id, k_id, a_status, a_text, a_dat, j_titel, j_id, e_firma in hr_archiv:
                st.markdown(f"{badge.get(a_status, '📄')} **Kandidat #{k_id}** – {j_titel} ({a_status}, {str(a_dat)[:10]})")
                if a_text:
                    st.caption(f"Motivation: {a_text[:120]}{'…' if len(a_text) > 120 else ''}")
            st.caption("ℹ️ Archivierte Bewerbungen sind final und werden nicht mehr angezeigt (Tab 3 '👥 Kandidaten' zeigt denselben Filter).")

    # ── KANDIDATEN-SICHT (Phase 1, unverändert) ──
    elif not check_login():
        st.warning("⚠️ Bitte melden Sie sich an (siehe Login-Bildschirm → Tab '🔑 Login'), um Stellenangebote zu sehen.")
    else:
        db_path = DATA_DIR / "feedback.db"
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT DEFAULT 'eingegangen',
            bewerbungstext TEXT,
            erstellungsdatum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (candidate_id, job_id),
            FOREIGN KEY (candidate_id) REFERENCES candidates(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS application_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            changed_by TEXT,
            notizen TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )""")
        conn.commit()

        cand_id_me = st.session_state.user_cand_id

        # Eigenen Kandidaten-Status laden (CV-Pflicht: Bewerben nur ab lebenslauf_hochgeladen)
        c.execute("SELECT status FROM candidates WHERE id = ?", (cand_id_me,))
        mein_status = c.fetchone()
        mein_status = mein_status[0] if mein_status else "registriert"
        cv_ok = mein_status in ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")

        st.caption(f"Eingeloggt als: {st.session_state.user_name} ({st.session_state.user_email})")
        if not cv_ok:
            st.warning("⚠️ CV-Pflicht: Bewerben ist erst nach Lebenslauf-Upload möglich (👤 Candidate Portal → 📄 Lebenslauf). Stellen ansehen ist erlaubt.")

        tab_jobs, tab_bew = st.tabs(["🔎 Stellenangebote", "📨 Meine Bewerbungen"])

        # ── Tab 1: Stellenangebote (nur aktive Stellen, keine Arbeitgeber-Kontaktdaten) ──
        with tab_jobs:
            c.execute("""SELECT j.id, j.titel, j.beschreibung, j.standort, j.stellentyp, j.hard_skills,
                j.soft_skills, j.berufserfahrung_jahre, j.deutsch_level, j.gehaltsrahmen_min, j.gehaltsrahmen_max,
                e.firma, e.branche, e.groesse
                FROM jobs j JOIN employers e ON j.employer_id = e.id
                WHERE j.status = 'aktiv' ORDER BY j.erstellt_am DESC""")
            angebote = c.fetchall()

            # Eigene Bewerbungen laden (für Button-Zustand)
            c.execute("SELECT job_id, status FROM applications WHERE candidate_id = ?", (cand_id_me,))
            meine_bew_map = {b[0]: b[1] for b in c.fetchall()}

            if not angebote:
                st.info("ℹ️ Derzeit keine aktiven Stellenangebote.")
            else:
                st.markdown(f"**{len(angebote)} aktive Stellen:**")
                for a in angebote:
                    (j_id, j_titel, j_beschr, j_ort, j_typ, j_hard, j_soft, j_erf,
                     j_de, j_gmin, j_gmax, e_firma, e_branche, e_groesse) = a
                    gehalt_txt = f"{j_gmin:,}–{j_gmax:,} EUR".replace(",", ".") if j_gmin and j_gmax else (
                        f"ab {j_gmin:,} EUR".replace(",", ".") if j_gmin else (
                        f"bis {j_gmax:,} EUR".replace(",", ".") if j_gmax else "–"))
                    with st.expander(f"#{j_id} {j_titel} – {e_firma} ({j_ort}, {j_typ})"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"**Firma:** {e_firma}")
                            st.markdown(f"**Branche:** {e_branche or '–'} · **Größe:** {e_groesse or '–'}")
                        with col2:
                            st.markdown(f"**Standort:** {j_ort}")
                            st.markdown(f"**Stellentyp:** {j_typ}")
                        with col3:
                            st.markdown(f"**Gehalt:** {gehalt_txt}")
                            st.markdown(f"**Erfahrung:** min. {j_erf or 0} Jahre · **Deutsch:** {j_de}")
                        st.markdown(f"**Beschreibung:** {j_beschr}")
                        st.markdown(f"**Must-Have-Skills:** {j_hard}")
                        if j_soft:
                            st.markdown(f"**Soft Skills:** {j_soft}")

                        bew_status = meine_bew_map.get(j_id)
                        if bew_status:
                            status_icons = {"eingegangen": "📨", "angesehen": "👁️", "eingeladen": "✅",
                                            "abgelehnt": "❌", "eingestellt": "🎉", "zurückgezogen": "↩️"}
                            st.info(f"{status_icons.get(bew_status, '📨')} Sie haben sich auf diese Stelle beworben – Status: **{bew_status}**")
                        elif not cv_ok:
                            st.button("🔒 Lebenslauf nötig", key=f"apply_lock_{j_id}", disabled=True,
                                      help="Bitte zuerst Lebenslauf hochladen (Candidate Portal → Lebenslauf)")
                        else:
                            with st.expander("✉️ Bewerbung schreiben"):
                                bew_text = st.text_area("Motivationstext (optional, max. 2000 Zeichen):",
                                                        max_chars=2000, key=f"apply_text_{j_id}")
                                if st.button("📨 Jetzt bewerben", key=f"apply_btn_{j_id}"):
                                    try:
                                        c.execute("INSERT INTO applications (candidate_id, job_id, status, bewerbungstext) VALUES (?, ?, 'eingegangen', ?)",
                                                  (cand_id_me, j_id, bew_text or None))
                                        _new_app_id = c.lastrowid
                                        c.execute("INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'eingegangen', 'kandidat')",
                                                  (_new_app_id,))
                                        conn.commit()
                                        # Phase 5 (Spec §3): Bewerbung → Agent-Kette + Eingangsbestätigung
                                        queue_agent_task("send_confirmation", {"application_id": _new_app_id,
                                                                               "candidate_id": cand_id_me, "job_id": j_id})
                                        queue_agent_task("extract_profile", {"application_id": _new_app_id,
                                                                             "candidate_id": cand_id_me, "job_id": j_id})
                                        queue_agent_task("match_candidate", {"application_id": _new_app_id,
                                                                             "candidate_id": cand_id_me, "job_id": j_id})
                                        queue_agent_task("check_compliance", {"application_id": _new_app_id,
                                                                              "candidate_id": cand_id_me, "job_id": j_id})
                                        queue_agent_task("assess_culture_fit", {"application_id": _new_app_id,
                                                                                "candidate_id": cand_id_me, "job_id": j_id})
                                        # Spec v6: Dokumenten-Verifizierung (Zeugnisse/Sprachzeugnisse, Herkunft Kandidat)
                                        queue_agent_task("verify_documents", {"application_id": _new_app_id,
                                                                               "candidate_id": cand_id_me, "job_id": j_id})
                                        # Spec v6.2: Visum-Check (Aufenthaltstitel, Anerkennung, nächste Schritte)
                                        queue_agent_task("check_visa", {"application_id": _new_app_id,
                                                                         "candidate_id": cand_id_me, "job_id": j_id})
                                        # Skill 9: explain-match – Detaillierte Begründung für Match-Score
                                        queue_agent_task("explain_match", {"application_id": _new_app_id,
                                                                            "candidate_id": cand_id_me, "job_id": j_id})
                                        # Skill 13: check-gdpr – DSGVO-Compliance-Prüfung
                                        queue_agent_task("check_gdpr", {"application_id": _new_app_id,
                                                                        "candidate_id": cand_id_me, "job_id": j_id})
                                        # Skill 17: notify-user – Benachrichtigung bei Top-Matches (Score >=80)
                                        queue_agent_task("notify_user", {"application_id": _new_app_id,
                                                                         "candidate_id": cand_id_me, "job_id": j_id})
                                        st.success(f"✅ Bewerbung eingegangen. Der Arbeitgeber sieht Sie anonymisiert als 'Kandidat #{cand_id_me}'.")
                                        st.rerun()
                                    except sqlite3.IntegrityError:
                                        st.error("❌ Sie haben sich bereits auf diese Stelle beworben.")

        # ── Tab 2: Meine Bewerbungen (Status verfolgen + zurückziehen) ──
        with tab_bew:
            c.execute("""SELECT a.id, a.job_id, j.titel, e.firma, a.status, a.erstellungsdatum, a.aktualisiert_am, a.bewerbungstext
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                JOIN employers e ON j.employer_id = e.id
                WHERE a.candidate_id = ? ORDER BY a.erstellungsdatum DESC""", (cand_id_me,))
            meine_bew = c.fetchall()
            if not meine_bew:
                st.info("ℹ️ Keine Bewerbungen vorhanden. Bewerben Sie sich im Tab '🔎 Stellenangebote'.")
            else:
                status_icons = {"eingegangen": "📨", "angesehen": "👁️", "eingeladen": "✅",
                                "abgelehnt": "❌", "eingestellt": "🎉", "zurückgezogen": "↩️"}
                for b in meine_bew:
                    b_id, b_job_id, b_titel, b_firma, b_status, b_erstellt, b_akt, b_text = b
                    icon = status_icons.get(b_status, "📨")
                    with st.expander(f"{icon} {b_titel} – {b_firma} – Status: **{b_status}**"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Beworben am", b_erstellt[:10] if b_erstellt else "–")
                        with col2:
                            st.metric("Letzte Änderung", b_akt[:10] if b_akt else "–")
                        if b_text:
                            st.markdown(f"**Motivation:** {b_text}")
                        # Phase 5 (Spec §6): bei 'eingeladen' Jitsi-Link + ICS aus dem Agent-Task anzeigen
                        if b_status == "eingeladen":
                            # Duplikat-Bereinigung (Phase 0): inline-SQL + eigener ICS-Button
                            # (vorher 33 Zeilen, Duplikat von render_hr_ics_download) →
                            # gemeinsame Funktion wie in der HR-Sicht (app.py:498).
                            if db.get_invitation_artifacts(b_id):
                                render_hr_ics_download(b_id)
                            else:
                                st.caption("⏳ Einladung wird vom Agenten vorbereitet (Jitsi-Link + Termin folgen in Kürze).")
                        # Status-Historie anzeigen
                        c.execute("SELECT status, changed_at FROM application_status_history WHERE application_id = ? ORDER BY changed_at", (b_id,))
                        hist = c.fetchall()
                        if hist:
                            st.caption(" → ".join(f"{h[0]} ({h[1][:10] if h[1] else '?'})" for h in hist))
                        if b_status not in ("eingestellt", "zurückgezogen"):
                            if st.button("↩️ Bewerbung zurückziehen", key=f"withdraw_{b_id}"):
                                c.execute("UPDATE applications SET status='zurückgezogen', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=? AND candidate_id=?",
                                          (b_id, cand_id_me))
                                c.execute("INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'zurückgezogen', 'kandidat')", (b_id,))
                                conn.commit()
                                st.success("↩️ Bewerbung zurückgezogen.")
                                st.rerun()

        conn.close()


# ═══════════════════════════════════════════════════════════════════
# SKILL 10: EMPLOYER PORTAL (Arbeitgeber-Portal)
# ═════════════════════════════════════════════════════════════════

elif skill == "🏢 Arbeitgeber-Portal":
    st.header("🏢 Arbeitgeber-Portal")
    st.markdown("Arbeitgeber: Registrierung, Stellen ausschreiben, Kandidaten sehen (anonymisiert), Feedback geben.")

    if not check_employer_login() and not check_admin_login():
        st.warning("⚠️ Bitte melden Sie sich als Arbeitgeber an (siehe Login-Bildschirm → Tab '🏢 Arbeitgeber-Login').")
    else:
        db_path = DATA_DIR / "feedback.db"
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS employers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            firma TEXT NOT NULL,
            kontaktperson TEXT NOT NULL,
            branche TEXT,
            groesse TEXT,
            standort TEXT,
            website TEXT,
            beschreibung TEXT,
            telefon TEXT,
            kontakt_email TEXT,
            registriert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id INTEGER NOT NULL,
            titel TEXT NOT NULL,
            beschreibung TEXT NOT NULL,
            standort TEXT NOT NULL,
            land TEXT DEFAULT 'DE',
            stellentyp TEXT NOT NULL,
            hard_skills TEXT NOT NULL,
            soft_skills TEXT,
            berufserfahrung_jahre INTEGER,
            deutsch_level TEXT DEFAULT 'Keine Anforderung',
            englisch_level TEXT DEFAULT 'Keine Anforderung',
            abschluss TEXT DEFAULT 'Egal',
            gehaltsrahmen_min INTEGER,
            gehaltsrahmen_max INTEGER,
            nice_to_have TEXT,
            status TEXT DEFAULT 'aktiv',
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employer_id) REFERENCES employers(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS job_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            changed_by TEXT,
            notizen TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )""")
        conn.commit()

        if not check_employer_login():
            # Admin-only session: Portal ist an einen Arbeitgeber-Account gebunden (Spec §2.4)
            st.info("🛡️ Admin-Betrieb: Dieses Portal ist an einen Arbeitgeber-Account gebunden (Firmenprofil, Stellen, Bewerber). Die Bewerber-Verwaltung über ALLE Arbeitgeber läuft über 💼 Stellenangebote (Admin-Sicht).")
            st.stop()
        st.caption(f"Eingeloggt als Arbeitgeber: {st.session_state.employer_firma} ({st.session_state.employer_email})")
        if st.button("🚪 Als Arbeitgeber abmelden", key="emp_logout_btn"):
            logout_employer()
            st.rerun()

        emp_id = st.session_state.employer_id

        tab1, tab2, tab3, tab4 = st.tabs(["📝 Firmenprofil", "📢 Stellen", "👥 Kandidaten", "💬 Feedback"])

        # ── Tab 1: Firmenprofil ──
        with tab1:
            st.subheader("Firmenprofil")
            c.execute("SELECT firma, kontaktperson, branche, groesse, standort, website, beschreibung, telefon FROM employers WHERE id = ?", (emp_id,))
            emp = c.fetchone()
            branchen = ["IT", "Consulting", "Industrie", "Handel", "Gesundheit", "Finanzen", "Sonstiges"]
            grossen = ["1-10", "11-50", "51-200", "201-1000", "1000+"]
            branche = st.selectbox("Branche:", branchen,
                                  index=branchen.index(emp[2]) if emp and emp[2] in branchen else 0, key="emp_br")
            groesse = st.selectbox("Mitarbeiterzahl:", grossen,
                                   index=grossen.index(emp[3]) if emp and emp[3] in grossen else 0, key="emp_gr")
            col1, col2 = st.columns(2)
            with col1:
                emp_standort = st.text_input("Hauptstandort:", value=emp[4] if emp else "", key="emp_st")
                emp_website = st.text_input("Website:", value=emp[5] if emp else "", key="emp_web")
                emp_telefon = st.text_input("Telefon:", value=emp[7] if emp else "", key="emp_tel")
            with col2:
                emp_beschreibung = st.text_area("Kurzprofil (max. 500 Zeichen):", value=emp[6] if emp else "", key="emp_besch")

            if st.button("💾 Firmenprofil speichern", key="emp_profil_btn"):
                c.execute("""UPDATE employers SET branche=?, groesse=?, standort=?, website=?, beschreibung=?, telefon=?, aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?""",
                          (branche, groesse, emp_standort, emp_website, emp_beschreibung, emp_telefon, emp_id))
                conn.commit()
                st.success("✅ Firmenprofil gespeichert.")

            # ── Passwort ändern (N5, Design-Entscheidung: knowledge/portal/employer-portal-fields.md) ──
            with st.expander("🔒 Passwort ändern"):
                altes_pw = st.text_input("Aktuelles Passwort:", type="password", key="pw_alt_emp")
                neues_pw = st.text_input("Neues Passwort:", type="password", key="pw_neu_emp")
                neues_pw_wdh = st.text_input("Neues Passwort wiederholen:", type="password", key="pw_wdh_emp")
                if st.button("🔒 Passwort ändern", key="pw_change_emp"):
                    if not altes_pw or not neues_pw or not neues_pw_wdh:
                        st.error("❌ Bitte alle Felder ausfüllen.")
                    elif neues_pw != neues_pw_wdh:
                        st.error("❌ Passwörter stimmen nicht überein.")
                    else:
                        from webui.logic import change_password
                        ok, msg = change_password(conn, "employers", emp_id, altes_pw, neues_pw)
                        if ok:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")

        # ── Tab 2: Stellen ──
        with tab2:
            st.subheader("Stelle ausschreiben")
            j_titel = st.text_input("Titel:", key="job_titel")
            j_beschreibung = st.text_area("Beschreibung (min. 50 Zeichen):", key="job_beschreibung")
            col1, col2 = st.columns(2)
            with col1:
                j_standort = st.text_input("Arbeitsort:", key="job_standort")
                j_land = st.selectbox("Land:", ["DE", "FR", "CH"], key="job_land")
                j_typ = st.selectbox("Stellentyp:", ["Vollzeit", "Teilzeit", "Freelance", "Hybrid", "Remote"], key="job_typ")
                j_hard = st.text_input("Must-Have-Skills (kommasepariert):", key="job_hard")
                j_soft = st.text_input("Soft Skills (kommasepariert):", key="job_soft")
            with col2:
                j_erfahrung = st.number_input("Min. Berufserfahrung (Jahre):", 0, 30, 3, key="job_erf")
                j_de = st.selectbox("Deutsch-Level:", ["Keine Anforderung", "A1", "A2", "B1", "B2", "C1", "C2", "Muttersprache"], key="job_de")
                j_en = st.selectbox("Englisch-Level:", ["Keine Anforderung", "A1", "A2", "B1", "B2", "C1", "C2", "Muttersprache"], key="job_en")
                j_abschluss = st.selectbox("Abschluss:", ["Egal", "Bachelor", "Master", "PhD"], key="job_abschluss")
            col3, col4 = st.columns(2)
            with col3:
                j_gehalt_min = st.number_input("Gehaltsrahmen von (EUR):", 0, 300000, 0, step=1000, key="job_gmin")
            with col4:
                j_gehalt_max = st.number_input("Gehaltsrahmen bis (EUR):", 0, 300000, 0, step=1000, key="job_gmax")

            if st.button("📢 Stelle ausschreiben", key="job_btn"):
                if not j_titel or not j_beschreibung or not j_standort or not j_hard:
                    st.error("❌ Titel, Beschreibung, Arbeitsort und Must-Have-Skills sind Pflichtfelder.")
                elif len(j_beschreibung) < 50:
                    st.error("❌ Beschreibung muss mindestens 50 Zeichen haben.")
                else:
                    c.execute("""INSERT INTO jobs (employer_id, titel, beschreibung, standort, land, stellentyp, hard_skills, soft_skills, berufserfahrung_jahre, deutsch_level, englisch_level, abschluss, gehaltsrahmen_min, gehaltsrahmen_max)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (emp_id, j_titel, j_beschreibung, j_standort, j_land, j_typ, j_hard, j_soft, j_erfahrung, j_de, j_en, j_abschluss, j_gehalt_min or None, j_gehalt_max or None))
                    job_id_new = c.lastrowid
                    c.execute("INSERT INTO job_status_history (job_id, status, changed_by) VALUES (?, 'aktiv', ?)", (job_id_new, st.session_state.employer_email))
                    conn.commit()
                    st.success(f"✅ Stelle ausgeschrieben: {j_titel}. Kandidaten-Matching ist jetzt möglich.")

            st.markdown("---")
            st.subheader("Meine Stellen")
            c.execute("SELECT id, titel, standort, stellentyp, status, erstellt_am FROM jobs WHERE employer_id = ? ORDER BY id DESC", (emp_id,))
            meine_jobs = c.fetchall()
            if not meine_jobs:
                st.info("ℹ️ Noch keine Stellen ausgeschrieben.")
            else:
                for j in meine_jobs:
                    with st.expander(f"#{j[0]} {j[1]} – {j[2]} ({j[3]}) – {j[4]}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Status", j[4])
                        with col2:
                            job_status_liste = ["aktiv", "pausiert", "besetzt", "abgelaufen"]
                            neuer_status = st.selectbox("Status ändern:", job_status_liste,
                                                       index=job_status_liste.index(j[4]) if j[4] in job_status_liste else 0,
                                                       key=f"job_status_{j[0]}")
                            if st.button("💾 Status speichern", key=f"job_status_btn_{j[0]}"):
                                c.execute("UPDATE jobs SET status=?, aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?", (neuer_status, j[0]))
                                c.execute("INSERT INTO job_status_history (job_id, status, changed_by) VALUES (?, ?, ?)", (j[0], neuer_status, st.session_state.employer_email))
                                conn.commit()
                                st.success(f"✅ Status geändert: {neuer_status}")
                        st.caption(f"Erstellt: {j[5][:10] if j[5] else '–'}")

        # ── Tab 3: Kandidaten (anonymisiert) + Bewerber (Phase 1) ──
        with tab3:
            st.subheader("Bewerber & passende Kandidaten (anonymisiert)")
            st.caption("🔒 DSGVO: Keine Kontaktdaten, keine Lebenslauf-Dateien. Name nur als Pseudonym. Aktive Bewerber werden zuerst gelistet.")
            c.execute("""SELECT j.id, j.titel, j.hard_skills, j.berufserfahrung_jahre, j.gehaltsrahmen_min, j.gehaltsrahmen_max, j.standort,
                j.soft_skills, j.deutsch_level, j.englisch_level, j.stellentyp, e.branche
                FROM jobs j JOIN employers e ON j.employer_id = e.id
                WHERE j.employer_id = ? AND j.status = 'aktiv' ORDER BY j.id DESC""", (emp_id,))
            aktive_jobs = c.fetchall()
            if not aktive_jobs:
                st.info("ℹ️ Keine aktiven Stellen. Schreiben Sie zuerst eine Stelle aus (Tab '📢 Stellen').")
            else:
                job_options = {f"#{j[0]} {j[1]}": j for j in aktive_jobs}
                sel_job_label = st.selectbox("Stelle:", list(job_options.keys()), key="cand_job_select")
                sel_job = job_options[sel_job_label]
                (job_id_sel, job_titel_lbl, job_hard_lbl, job_erfahrung_lbl, job_gmin, job_gmax, job_standort_lbl,
                 job_soft_lbl, job_de_lvl, job_en_lvl, job_typ_lbl, job_branche_lbl) = sel_job

                c.execute("""SELECT id, hard_skills, soft_skills, berufserfahrung_jahre, deutsch, englisch, standort, gehaltsvorstellung, status, abschluss, lebenslauf_text
                    FROM candidates WHERE status IN ('lebenslauf_hochgeladen', 'profil_geprueft', 'match_berechnet', 'eingeladen') ORDER BY id""")
                kandidaten_pool = c.fetchall()

                # Bewerbungen zu dieser Stelle laden (Phase 1: Bewerber zuerst)
                c.execute("""SELECT a.id, a.candidate_id, a.status, a.bewerbungstext, a.erstellungsdatum
                    FROM applications a WHERE a.job_id = ? AND a.status IN ('eingegangen', 'angesehen', 'eingeladen')
                    ORDER BY a.erstellungsdatum ASC""", (job_id_sel,))
                bewerber_rows = c.fetchall()
                bewerbung_map = {b[1]: (b[0], b[2], b[3], b[4]) for b in bewerber_rows}

                # ── Abschnitt 1: Aktive Bewerber ──
                st.markdown(f"### 📥 Bewerber ({len(bewerber_rows)})")
                if not bewerber_rows:
                    st.info("ℹ️ Keine aktiven Bewerbungen für diese Stelle (Skill: 💼 Stellenangebote bei den Kandidaten).")
                else:
                    for b in bewerber_rows:
                        app_id, app_cand_id, app_status, app_text, app_datum = b
                        # Kandidaten-Profil laden (nur sichtbar wenn Status ≥ lebenslauf_hochgeladen)
                        k_profil = next((k for k in kandidaten_pool if k[0] == app_cand_id), None)
                        with st.expander(f"📥 Kandidat #{app_cand_id} – Bewerbung: **{app_status}** (seit {app_datum[:10] if app_datum else '?'})"):
                            if app_text:
                                st.markdown(f"**Motivation:** {app_text}")
                            if k_profil:
                                k_id, k_hard, k_soft, k_erf, k_de, k_en, k_standort, k_gehalt, k_status, k_abschluss, k_cv_text = k_profil
                                r_bew = berechne_match_score(
                                    {"hard_skills": k_hard, "soft_skills": k_soft, "berufserfahrung_jahre": k_erf,
                                     "abschluss": k_abschluss, "deutsch": k_de, "englisch": k_en,
                                     "standort": k_standort, "lebenslauf_text": k_cv_text},
                                    {"hard_skills": job_hard_lbl, "soft_skills": job_soft_lbl, "berufserfahrung_jahre": job_erfahrung_lbl,
                                     "deutsch_level": job_de_lvl, "englisch_level": job_en_lvl,
                                     "standort": job_standort_lbl, "stellentyp": job_typ_lbl, "branche": job_branche_lbl})
                                total = r_bew["total"]
                                matches = r_bew["matches"]
                                kategorie = r_bew["kategorie"]
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Match-Score", f"{total}/100")
                                    st.metric("Kategorie", kategorie)
                                with col2:
                                    st.metric("Erfahrung", f"{k_erf or 0} Jahre")
                                    st.metric("Deutsch", k_de or "–")
                                with col3:
                                    st.metric("Region", k_standort or "–")
                                    st.metric("Skills", f"{len(matches)}/{len([s for s in job_hard_lbl.split(',') if s.strip()])}")
                                st.markdown(f"**Passende Must-Have-Skills:** {', '.join(matches) if matches else '–'}")
                                st.caption(f"Score-Details (Doc-Gewichtung): Kern {r_bew['kern']}/30 · Erfahrung {r_bew['erfahrung']}/30 · Bildung {r_bew['bildung']}/15 · Standort {r_bew['standort']}/10 · Branche {r_bew['branche']}/10 · Soft {r_bew['soft']}/10 · Sprache {r_bew['sprache']}/10")
                            else:
                                st.warning("⚠️ Bewerber-Profil ohne Lebenslauf (CV-Pflicht-Verstoß) – bitte prüfen.")

                            # ── Agent-Ergebnisse: verify_documents, check_visa, check_gdpr ──
                            _agent_files = {
                                "verify_documents": f"verify_documents-kandidat-{app_cand_id}",
                                "check_visa": f"check_visa-kandidat-{app_cand_id}",
                                "check_gdpr": f"check_gdpr-kandidat-{app_cand_id}",
                                "explain_match": f"explain_match-kandidat-{app_cand_id}",
                            }
                            _agent_found = {}
                            for _task, _prefix in _agent_files.items():
                                _matches = sorted(ERGEBNISSE.glob(f"{_prefix}*.md"))
                                if _matches:
                                    _agent_found[_task] = _matches[-1]
                            if _agent_found:
                                st.markdown("---")
                                st.markdown("**🤖 Agent-Ergebnisse:**")
                                _col_a, _col_b = st.columns(2)
                                # --- verify_documents Badge ---
                                if "verify_documents" in _agent_found:
                                    _vd_text = _agent_found["verify_documents"].read_text(encoding="utf-8", errors="replace")
                                    _vd_status = "AUFFÄLLIG" if "AUFFAELLIG" in _vd_text.upper() or "AUFFÄLLIG" in _vd_text.upper() else (
                                        "PLAUSIBEL" if "PLAUSIBEL" in _vd_text.upper() else "UNBEKANNT")
                                    _vd_color = "🔴" if _vd_status == "AUFFÄLLIG" else ("🟢" if _vd_status == "PLAUSIBEL" else "🟡")
                                    with _col_a:
                                        st.metric("Dokumenten-Check", f"{_vd_color} {_vd_status}")
                                    with st.expander(f"📄 {_vd_color} Dokumenten-Verifizierung ({_vd_status})", expanded=(_vd_status == "AUFFÄLLIG")):
                                        st.markdown(_vd_text)
                                # --- check_visa Badge ---
                                if "check_visa" in _agent_found:
                                    _cv_text = _agent_found["check_visa"].read_text(encoding="utf-8", errors="replace")
                                    _cv_status = "ERFORDERLICH" if "ERFORDERLICH" in _cv_text.upper() else (
                                        "NICHT ERFORDERLICH" if "NICHT ERFORDERLICH" in _cv_text.upper() else "UNGEWISS")
                                    _cv_color = "🔴" if "ERFORDERLICH" in _cv_status and "NICHT" not in _cv_status else (
                                        "🟢" if "NICHT" in _cv_status else "🟡")
                                    with _col_b:
                                        st.metric("Visum-Status", f"{_cv_color} {_cv_status}")
                                    with st.expander(f"🛂 {_cv_color} Visum-Check ({_cv_status})"):
                                        st.markdown(_cv_text)
                                # --- check_gdpr Badge ---
                                if "check_gdpr" in _agent_found:
                                    _gdpr_text = _agent_found["check_gdpr"].read_text(encoding="utf-8", errors="replace")
                                    _gdpr_ok = "KONFORM" in _gdpr_text.upper() and "NICHT_KONFORM" not in _gdpr_text.upper()
                                    _gdpr_color = "🟢" if _gdpr_ok else "🔴"
                                    _gdpr_label = "KONFORM" if _gdpr_ok else "NICHT KONFORM"
                                    with st.expander(f"🔒 {_gdpr_color} DSGVO-Check ({_gdpr_label})"):
                                        st.markdown(_gdpr_text)
                                # --- explain_match (immer anzeigen wenn vorhanden) ---
                                if "explain_match" in _agent_found:
                                    _em_text = _agent_found["explain_match"].read_text(encoding="utf-8", errors="replace")
                                    with st.expander(f"💡 Match-Erklärung (Agent)"):
                                        st.markdown(_em_text)

                                # --- Sprachtest-Ergebnisse (Phase 2) ---
                                _conn_lt = sqlite3.connect(str(DATA_DIR / "feedback.db"))
                                _c_lt = _conn_lt.cursor()
                                _c_lt.execute("SELECT sprache, niveau, punkte, cefr_level, test_datum FROM language_tests WHERE candidate_id = ? ORDER BY test_datum DESC", (app_cand_id,))
                                _sprachtests = _c_lt.fetchall()
                                _conn_lt.close()
                                if _sprachtests:
                                    st.markdown("**🗣️ Sprachtest-Ergebnisse:**")
                                    for _st_sprache, _st_niv, _st_pkt, _st_cefr, _st_dat in _sprachtests:
                                        _cefr_color = "🟢" if _st_cefr and _st_cefr >= "B1" else ("🟡" if _st_cefr == "A2" else "🔴")
                                        st.markdown(f"{_cefr_color} **{_st_sprache} {_st_niv}**: {_st_pkt*100:.0f}% → CEFR {_st_cefr or '?'} ({_st_dat[:10] if _st_dat else '?'})")

                                # --- Video-Vorstellung (Phase 2) ---
                                if st.session_state.get("video_link"):
                                    st.markdown(f"**🎬 Video-Vorstellung:** {st.session_state['video_link']}")

                            # Status-Aktionen (siehe knowledge/lifecycle/application-status.md)
                            bew_actions = ["(keine Änderung)", "angesehen", "eingeladen", "abgelehnt", "eingestellt"]
                            neue_bew_status = st.selectbox("Bewerbungs-Status ändern:", bew_actions,
                                                           key=f"bew_status_{app_id}")
                            # Phase 5: HR wählt den Einladungs-Termin, wenn 'eingeladen' gewählt ist
                            _inv_vals = None
                            if neue_bew_status == "eingeladen":
                                st.markdown("**📅 Einladungs-Termin (wird in die Automatik-Mail übernommen):**")
                                _dc1, _dc2, _dc3 = st.columns(3)
                                with _dc1:
                                    inv_datum_p = st.date_input("Datum", value=datetime.now().date() + timedelta(days=1),
                                                                min_value=datetime.now().date(), key=f"inv_datum_p_{app_id}")
                                with _dc2:
                                    inv_zeit_p = st.time_input("Uhrzeit", value=time(10, 0), key=f"inv_zeit_p_{app_id}")
                                with _dc3:
                                    inv_dauer_p = st.selectbox("Dauer (Min.)", [15, 30, 45, 60], index=1, key=f"inv_dauer_p_{app_id}")
                                _inv_vals = {"termin_datum": inv_datum_p.strftime("%Y-%m-%d"),
                                             "termin_uhrzeit": inv_zeit_p.strftime("%H:%M"),
                                             "termin_dauer_min": int(inv_dauer_p)}
                            if neue_bew_status != "(keine Änderung)" and st.button("💾 Bewerbungs-Status speichern", key=f"bew_btn_{app_id}"):
                                allowed_transitions = {
                                    "eingegangen": {"angesehen", "abgelehnt"},
                                    "angesehen": {"eingeladen", "abgelehnt"},
                                    "eingeladen": {"eingestellt", "abgelehnt"},
                                }
                                if neue_bew_status in allowed_transitions.get(app_status, set()):
                                    c.execute("UPDATE applications SET status=?, aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?", (neue_bew_status, app_id))
                                    c.execute("INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, ?, 'arbeitgeber')", (app_id, neue_bew_status))
                                    conn.commit()
                                    # Phase 5 (Spec §3): Übergänge erzeugen Agent-Tasks (Variante A:
                                    # Agent sendet Einladung/Absage NUR nach diesem HR-Klick)
                                    # Fix 12.09.2026: job_id_sel (nicht j_id) – Variable dieses Loops
                                    if neue_bew_status == "eingeladen":
                                        queue_agent_task("create_invitation", {"application_id": app_id,
                                                                               "candidate_id": app_cand_id, "job_id": job_id_sel,
                                                                               "trigger": "hr_klick_portal",
                                                                               **(_inv_vals or {})})
                                    elif neue_bew_status == "abgelehnt":
                                        queue_agent_task("send_rejection", {"application_id": app_id,
                                                                            "candidate_id": app_cand_id, "job_id": job_id_sel,
                                                                            "trigger": "hr_klick_portal"})
                                    elif neue_bew_status == "eingestellt":
                                        queue_agent_task("onboarding_release", {"application_id": app_id,
                                                                                "candidate_id": app_cand_id, "job_id": job_id_sel,
                                                                                "trigger": "hr_klick_portal"})
                                    if neue_bew_status == "eingestellt":
                                        st.success("🎉 Bewerber eingestellt. Bitte Stellen-Status auf 'besetzt' setzen (Tab '📢 Stellen').")
                                    elif neue_bew_status == "eingeladen":
                                        st.success("✅ Eingeladen – Kontaktdaten sind jetzt freigegeben (Skill 4: Contact Candidate).")
                                    else:
                                        st.success(f"✅ Status geändert: {neue_bew_status}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Übergang '{app_status}' → '{neue_bew_status}' ist nicht erlaubt (siehe knowledge/lifecycle/application-status.md).")

                            # Phase 5 Ergänzung: bereits eingeladen → HR sieht Jitsi + ICS-Download
                            if app_status == "eingeladen":
                                render_hr_ics_download(app_id)

                            # Spec v6: Visum-Antrag-Bestätigung (nur bei eingeladen + noch nicht gesendet)
                            if app_status == "eingeladen":
                                _visa_done = False
                                try:
                                    _cv2 = sqlite3.connect(str(DATA_DIR / "feedback.db")); _cc2 = _cv2.cursor()
                                    _cc2.execute("""SELECT COUNT(*) FROM agent_tasks WHERE task_type='visa_confirmation'
                                        AND status IN ('pending','running','done') AND payload LIKE ?""", (f'%%"application_id": {app_id}%%',))
                                    _visa_done = _cc2.fetchone()[0] > 0; _cv2.close()
                                except Exception:
                                    pass
                                if not _visa_done and st.button("📩 Visum-Antrag bestätigen", key=f"visa_p_{app_id}"):
                                    queue_agent_task("visa_confirmation", {"application_id": app_id,
                                                                           "candidate_id": app_cand_id, "job_id": job_id_sel,
                                                                           "trigger": "hr_klick_portal"})
                                    st.success("📩 Visum-Schritte-Mail an den Kandidaten ausgelöst (Agent sendet).")
                                    st.rerun()
                                elif _visa_done:
                                    st.caption("✅ Visum-Schritte-Mail versendet.")

                st.markdown("---")

                # ── Abschnitt 2: Passive Matches (wie bisher) ──
                st.markdown("### 👥 Passive Matches")

                if not kandidaten_pool:
                    st.info("ℹ️ Noch keine Kandidaten mit Lebenslauf registriert.")
                else:
                    must_haves = [s for s in job_hard_lbl.split(",") if s.strip()]
                    ranking = []
                    for k in kandidaten_pool:
                        k_id, k_hard, k_soft, k_erf, k_de, k_en, k_standort, k_gehalt, k_status, k_abschluss, k_cv_text = k
                        # Bewerber werden im Abschnitt 1 angezeigt – hier nicht doppelt
                        if k_id in bewerbung_map:
                            continue
                        r = berechne_match_score(
                            {"hard_skills": k_hard, "soft_skills": k_soft, "berufserfahrung_jahre": k_erf,
                             "abschluss": k_abschluss, "deutsch": k_de, "englisch": k_en,
                             "standort": k_standort, "lebenslauf_text": k_cv_text},
                            {"hard_skills": job_hard_lbl, "soft_skills": job_soft_lbl, "berufserfahrung_jahre": job_erfahrung_lbl,
                             "deutsch_level": job_de_lvl, "englisch_level": job_en_lvl,
                             "standort": job_standort_lbl, "stellentyp": job_typ_lbl, "branche": job_branche_lbl})
                        matches = r["matches"]
                        total = r["total"]
                        kategorie = r["kategorie"]
                        # Matching-Regel (identisch zu Phase 1): ≥1 Must-Have (Synonym-Match zählt) und ≥50% der geforderten Erfahrung
                        if not matches:
                            continue
                        if job_erfahrung_lbl and (k_erf or 0) < job_erfahrung_lbl * 0.5:
                            continue
                        gehalt_ok = gehalt_check(k_gehalt, job_gmin, job_gmax)
                        ranking.append((total, k_id, kategorie, matches, k_erf, k_de, k_standort, gehalt_ok, k_status))

                    ranking.sort(reverse=True)
                    if not ranking:
                        st.warning("⚠️ Keine passenden Kandidaten (mindestens 1 Must-Have-Skill nötig).")
                    else:
                        st.markdown(f"**{len(ranking)} passende Kandidaten für {sel_job_label}:**")
                        for rank, (total, k_id, kategorie, matches, k_erf, k_de, k_standort, gehalt_ok, k_status) in enumerate(ranking, 1):
                            with st.expander(f"{rank}. Kandidat #{k_id} – {total}/100 ({kategorie})"):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Score", f"{total}/100")
                                    st.metric("Kategorie", kategorie)
                                with col2:
                                    st.metric("Erfahrung", f"{k_erf or 0} Jahre")
                                    st.metric("Deutsch", k_de or "–")
                                with col3:
                                    st.metric("Region", k_standort or "–")
                                    st.metric("Gehalt", gehalt_ok)
                                st.markdown(f"**Passende Must-Have-Skills:** {', '.join(matches) if matches else '–'}")
                                st.caption(f"Status: {k_status} · Score-Details: Kern {r['kern']}/30 · Erf {r['erfahrung']}/30 · Bild {r['bildung']}/15 · Standort {r['standort']}/10 · Branche {r['branche']}/10 · Soft {r['soft']}/10 · Sprache {r['sprache']}/10")

        # ── Tab 4: Feedback ──
        with tab4:
            st.subheader("Feedback geben")
            c.execute("SELECT id, titel FROM jobs WHERE employer_id = ? ORDER BY id DESC", (emp_id,))
            fb_jobs = c.fetchall()
            if not fb_jobs:
                st.info("ℹ️ Keine Stellen vorhanden.")
            else:
                fb_job_options = {f"#{j[0]} {j[1]}": j[0] for j in fb_jobs}
                fb_job_label = st.selectbox("Stelle:", list(fb_job_options.keys()), key="fb_job_select")
                fb_job_id = fb_job_options[fb_job_label]

                # ── Phase 3: Kandidaten-Picker aus dem TATSÄCHLICHEN Ranking ──
                # Job-Daten für Scoring laden (wie Tab 3)
                c.execute("""SELECT j.hard_skills, j.soft_skills, j.berufserfahrung_jahre, j.deutsch_level, j.englisch_level, j.standort, j.stellentyp,
                    j.gehaltsrahmen_min, j.gehaltsrahmen_max, e.branche
                    FROM jobs j JOIN employers e ON j.employer_id = e.id WHERE j.id = ?""", (fb_job_id,))
                fb_job = c.fetchone()
                # Bewerber (aktiv) + Passive Matches für DIESE Stelle sammeln
                fb_optionen = {}   # label -> (cand_id, quelle, score)
                if fb_job:
                    (j_hard, j_soft, j_erf, j_de, j_en, j_ort, j_typ, j_gmin, j_gmax, j_branche) = fb_job
                    c.execute("""SELECT id, hard_skills, soft_skills, berufserfahrung_jahre, deutsch, englisch, standort, gehaltsvorstellung, status, abschluss, lebenslauf_text
                        FROM candidates WHERE status IN ('lebenslauf_hochgeladen', 'profil_geprueft', 'match_berechnet', 'eingeladen') ORDER BY id""")
                    fb_pool = c.fetchall()
                    c.execute("""SELECT a.id, a.candidate_id, a.status FROM applications a
                        WHERE a.job_id = ? AND a.status IN ('eingegangen', 'angesehen', 'eingeladen') ORDER BY a.erstellungsdatum ASC""", (fb_job_id,))
                    fb_bewerber = {b[1]: b[2] for b in c.fetchall()}
                    for k in fb_pool:
                        (k_id, k_hard, k_soft, k_erf, k_de, k_en, k_ort, k_gehalt, k_status, k_abschluss, k_cv) = k
                        if k_id in fb_bewerber:
                            quelle = f"📥 Bewerber ({fb_bewerber[k_id]})"
                        else:
                            r_fb = berechne_match_score(
                                {"hard_skills": k_hard, "soft_skills": k_soft, "berufserfahrung_jahre": k_erf,
                                 "abschluss": k_abschluss, "deutsch": k_de, "englisch": k_en,
                                 "standort": k_ort, "lebenslauf_text": k_cv},
                                {"hard_skills": j_hard, "soft_skills": j_soft, "berufserfahrung_jahre": j_erf,
                                 "deutsch_level": j_de, "englisch_level": j_en, "standort": j_ort, "stellentyp": j_typ, "branche": j_branche})
                            if not r_fb["matches"]:
                                continue  # Passive Matches: gleiche Regel wie Tab 3 (≥1 Must-Have)
                            if j_erf and (k_erf or 0) < j_erf * 0.5:
                                continue
                            quelle = "👥 Passiver Match"
                        fb_optionen[f"Kandidat #{k_id} – {quelle}"] = (k_id, quelle, None)
                if not fb_optionen:
                    st.info("ℹ️ Keine Kandidaten für diese Stelle (keine Bewerber, keine passiven Matches).")
                else:
                    fb_choice = st.selectbox("Kandidat (aus aktuellem Ranking):", list(fb_optionen.keys()), key="fb_cand_picker")
                    fb_candidate_id, fb_quelle, _ = fb_optionen[fb_choice]
                    st.caption(f"Ausgewählt: {fb_choice} · Quelle: Tab '👥 Kandidaten' (Bewerber zuerst, dann passive Matches – gleiche Regeln wie Tab 3)")

                fb_score = st.number_input("Match-Score:", 0, 100, 85, key="emp_fb_score")
                fb_eingeladen = st.selectbox("Eingeladen?", ["Ja", "Nein", "Vorgemerkt"], key="emp_fb_eingeladen")

                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    fb_fachlich = st.slider("Fachlich korrekt:", 1, 5, 4, key="emp_fb_fachlich")
                with col_b:
                    fb_skills = st.slider("Skills richtig:", 1, 5, 4, key="emp_fb_skills")
                with col_c:
                    fb_standort = st.slider("Standort zutreffend:", 1, 5, 4, key="emp_fb_standort")
                with col_d:
                    fb_empfehlung = st.slider("Empfehlung hilfreich:", 1, 5, 4, key="emp_fb_empf")

                fb_anmerkungen = st.text_area("Anmerkungen:", key="emp_fb_anmerkungen")

                if st.button("💬 Feedback speichern", key="emp_fb_btn"):
                    fb_kategorie = "Schwach"
                    try:
                        _cat = _mcp_connector_call(HR_BENCHMARK_SERVER, "get_score_category", {"score": fb_score})
                        if _cat and "category" in _cat:
                            _cat_map = {"Strong": "Hervorragend", "Consider": "Bedingt", "Weak": "Schwach"}
                            fb_kategorie = _cat_map.get(_cat["category"], "Schwach")
                            if fb_kategorie == "Bedingt" and fb_score >= 75:
                                fb_kategorie = "Gut"
                    except Exception:
                        if fb_score >= 90: fb_kategorie = "Hervorragend"
                        elif fb_score >= 75: fb_kategorie = "Gut"
                        elif fb_score >= 60: fb_kategorie = "Bedingt"

                    fb_match_id = f"employer-job-{fb_job_id}-cand-{int(fb_candidate_id)}-{datetime.now().strftime('%Y-%m-%d')}"
                    # Phase 3: idempotent statt INSERT OR REPLACE
                    # - gleicher Tag (gleiche match_id): UPDATE des bestehenden Eintrags
                    # - nächster Tag (neue match_id): neuer Datensatz (Historie bleibt)
                    c.execute("SELECT id FROM feedback WHERE match_id = ?", (fb_match_id,))
                    existing = c.fetchone()
                    if existing:
                        c.execute("""UPDATE feedback SET kandidat_name=?, stellenprofil=?, score=?, kategorie=?,
                            fachlich_korrekt=?, skills_richtig=?, standort_zutreffend=?,
                            empfehlung_hilfreich=?, eingeladen=?, anmerkungen=?
                            WHERE match_id=?""",
                            (f"Kandidat #{int(fb_candidate_id)}", fb_job_label, fb_score, fb_kategorie,
                             fb_fachlich, fb_skills, fb_standort, fb_empfehlung,
                             fb_eingeladen, fb_anmerkungen, fb_match_id))
                        conn.commit()
                        st.success(f"✅ Feedback aktualisiert (heute bereits vorhanden): `{fb_match_id}`")
                    else:
                        c.execute("""INSERT INTO feedback
                            (match_id, kandidat_name, stellenprofil, score, kategorie,
                             fachlich_korrekt, skills_richtig, standort_zutreffend,
                             empfehlung_hilfreich, eingeladen, anmerkungen)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (fb_match_id, f"Kandidat #{int(fb_candidate_id)}", fb_job_label, fb_score, fb_kategorie,
                             fb_fachlich, fb_skills, fb_standort, fb_empfehlung,
                             fb_eingeladen, fb_anmerkungen))
                        conn.commit()
                        st.success(f"✅ Feedback gespeichert: `{fb_match_id}`")
                        # Phase 4: Geschlossener Loop – nur bei NEUEM Feedback (INSERT)
                        gw_msg = adjust_weights_from_feedback(
                            fb_eingeladen, fb_score,
                            f"Erfolgreicher Match {fb_job_label} – Kandidat #{fb_candidate_id}: Score {fb_score}/100",
                            conn)
                        if gw_msg:
                            st.info(gw_msg)

        conn.close()


# ═════════════════════════════════════════════════════════════════════
# MCP CONNECTOR STATUS (nach allen Skills)
# ═════════════════════════════════════════════════════════════════════

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔌 MCP-Connectors")

try:
    from mcp_pdf_server import read_pdf_text as _test_pdf
    st.sidebar.markdown("- ✅ `pdf-reader` (PyMuPDF)")
except ImportError:
    st.sidebar.markdown("- ⚠️ `pdf-reader` (Fallback: fitz)")

ansvar_config = Path.home() / ".config" / "opencode" / "opencode.json"
if ansvar_config.exists():
    try:
        cfg = json.loads(ansvar_config.read_text())
        mcp_servers = cfg.get("mcpServers", cfg.get("mcp", {}))
        if "ansvar-german-law" in mcp_servers:
            st.sidebar.markdown("- ✅ `ansvar-german-law` (DE)")
        else:
            st.sidebar.markdown("- ❌ `ansvar-german-law`")
        if "ansvar-french-law" in mcp_servers:
            st.sidebar.markdown("- ✅ `ansvar-french-law` (FR)")
        else:
            st.sidebar.markdown("- ❌ `ansvar-french-law`")
        if "ansvar-swiss-law" in mcp_servers:
            st.sidebar.markdown("- ✅ `ansvar-swiss-law` (CH)")
        else:
            st.sidebar.markdown("- ❌ `ansvar-swiss-law`")
    except Exception:
        st.sidebar.markdown("- ❌ Ansvar (Config-Fehler)")
else:
    st.sidebar.markdown("- ❌ Ansvar (nicht konfiguriert)")

st.sidebar.markdown("- ✅ `filesystem` (lokal)")

meeting_server = MCP_PDF_DIR / "mcp-meeting-server.py"
if meeting_server.exists():
    st.sidebar.markdown("- ✅ `meeting-tools` (lokal)")
else:
    st.sidebar.markdown("- ❌ `meeting-tools`")

# ─── Footer ───────────────────────────────────────────────────────────

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"🤖 *KM-HR-Agent v1.0*\n"
    f"📅 {datetime.now().strftime('%d.%m.%Y')}\n"
    f"🔧 {len(list_profiles())} Profile, {len(list_stellen())} Stellen"
)
