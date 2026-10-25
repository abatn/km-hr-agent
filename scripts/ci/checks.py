#!/usr/bin/env python3
"""CI-Prüfungen je Verantwortungsbereich (Aufruf: python3 scripts/ci/checks.py <bereich>).

Bereiche: docs | legal | mcp | i18n | schema | mdguard
Exit 0 = OK, Exit 1 = Fehler (mit Klartext-Meldungen).

Lab-Prinzip: prüft NUR Struktur/Konsistenz — erfindet keine Regeln und keine
juristische Freigabe. Hinweise, die menschliche Prüfung brauchen, werden als
WARNUNG ausgegeben (Exit bleibt 0), harte Fehler als FEHLER (Exit 1).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FEHLER: list[str] = []
WARNUNG: list[str] = []


def fehler(msg: str) -> None:
    FEHLER.append(msg)


def warnung(msg: str) -> None:
    WARNUNG.append(msg)


# ── docs: interne Links in knowledge/ + skills/ ──────────────────────────
def check_docs() -> None:
    dateien = list((ROOT / "knowledge").rglob("*.md")) + list((ROOT / "skills").rglob("*.md"))
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for f in dateien:
        for ziel in link_re.findall(f.read_text(encoding="utf-8", errors="replace")):
            if ziel.startswith(("http://", "https://", "#", "mailto:", "/")):
                continue  # "/agb" & Co. sind Web-Routen, keine Dateipfade
            pfad = ziel.split("#")[0].strip()
            if not pfad:
                continue
            ziel_pfad = (f.parent / pfad).resolve()
            if not ziel_pfad.exists() and not (ROOT / pfad).exists():
                warnung(f"{f.relative_to(ROOT)}: toter interner Link → {ziel}")


# ── legal: Mehrsprachigkeit + 'deutsche Fassung gilt' ────────────────────
def check_legal() -> None:
    legal = ROOT / "knowledge" / "legal"
    seiten = ["impressum", "datenschutz", "agb", "kontakt"]
    # Hinweis „deutsche Fassung gilt" nur bei echten Rechtstexten (nicht Kontakt-Seite).
    rechtstexte = {"impressum", "datenschutz", "agb"}
    # Konzept mehrsprachig: „prevail(s)" / „gilt" / „prévaut" / „الألمانية"
    hinweis_re = re.compile(r"prevail|gilt|prévaut|الألمانية|deutsche", re.I)
    for name in seiten:
        if not (legal / f"{name}.md").is_file():
            fehler(f"Rechts-Seite fehlt: knowledge/legal/{name}.md (DE-Fallback)")
        for lang in ("en", "fr", "ar"):
            p = legal / f"{name}.{lang}.md"
            if not p.is_file():
                fehler(f"Rechts-Übersetzung fehlt: knowledge/legal/{name}.{lang}.md")
            elif name in rechtstexte:
                kopf = p.read_text(encoding="utf-8", errors="replace")[:800]
                if not hinweis_re.search(kopf):
                    warnung(f"{p.relative_to(ROOT)}: Hinweis 'deutsche Fassung gilt' fehlt")
    # recording-consent: Gate-Status muss explizit sein
    rc = legal / "recording-consent.md"
    if rc.is_file():
        t = rc.read_text(encoding="utf-8", errors="replace")
        if "kein aufnahme-aktivierender Parameter" not in t.lower() and "record=off" not in t.lower():
            warnung("recording-consent.md: Gate-Status (kein Aufnahme-Parameter) nicht klar benannt")


# ── mcp: opencode.json + lokale Server-Handshake ─────────────────────────
def check_mcp() -> None:
    cfg = ROOT / "opencode.json"
    if not cfg.is_file():
        fehler("opencode.json fehlt"); return
    try:
        d = json.loads(cfg.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fehler(f"opencode.json: ungültiges JSON — {e}"); return
    server = d.get("mcp", {})
    if not server:
        fehler("opencode.json: kein 'mcp'-Block"); return
    for name, s in server.items():
        if s.get("type") == "local":
            cmd = s.get("command")
            if not cmd:
                fehler(f"MCP '{name}': lokaler Server ohne 'command'")
                continue
            # Pfad-Prüfung (absolute/relative Datei-Argumente)
            for arg in (s.get("args") or []):
                if isinstance(arg, str) and arg.endswith(".py"):
                    if not (ROOT / arg).exists() and not Path(arg).exists():
                        fehler(f"MCP '{name}': Skript fehlt → {arg}")
    print(f"opencode.json gültig: {len(server)} Server")


# ── i18n: PO-Syntax, Platzhalter, PO↔MO ──────────────────────────────────
def check_i18n() -> None:
    import gettext
    loc = ROOT / "webui" / "locales"
    langs = ["de", "en", "fr", "ar"]
    cats = {}
    for l in langs:
        po = loc / l / "LC_MESSAGES" / "messages.po"
        mo = loc / l / "LC_MESSAGES" / "messages.mo"
        if not po.is_file() or not mo.is_file():
            fehler(f"i18n: {l}: messages.po/.mo fehlt"); continue
        with open(mo, "rb") as f:
            cats[l] = {k: v for k, v in gettext.GNUTranslations(f)._catalog.items() if k}
        # PO-Syntax grob: msgid/msgstr-Paare
        txt = po.read_text(encoding="utf-8", errors="replace")
        if txt.count("msgid ") != txt.count("msgstr "):
            fehler(f"i18n {l}: msgid/msgstr-Anzahl ungleich")
        # MO frischer als PO?
        if po.stat().st_mtime > mo.stat().st_mtime + 1:
            warnung(f"i18n {l}: messages.mo älter als .po (neu kompilieren?)")
    if "de" in cats:
        base = set(cats["de"])
        for l in langs:
            if l in cats and set(cats[l]) != base:
                fehler(f"i18n {l}: Key-Menge != DE ({len(set(cats[l]) ^ base)} Abweichungen)")
        # Platzhalter-Parität
        fmt = re.compile(r"\{(\d+)(?::[^}]*)?\}")
        for l in langs:
            if l not in cats:
                continue
            for k, v in cats[l].items():
                if set(fmt.findall(k)) != set(fmt.findall(v)):
                    fehler(f"i18n {l}: Platzhalter-Mismatch bei {k!r}")
    print(f"i18n geprüft: {len(cats)} Kataloge")


# ── schema: DB-Tabellen vs. erwartete 17 ─────────────────────────────────
ERWARTETE_TABELLEN = {
    "admins", "agent_tasks", "application_status_history", "applications",
    "candidate_documents", "candidate_status_history", "candidates",
    "compliance_protokoll", "employers", "feedback", "gewichtung_historie",
    "job_status_history", "jobs", "language_tests", "mentoring", "notifications",
    "password_resets",
}


def check_schema() -> None:
    import sqlite3
    db = ROOT / "tests" / "fixtures" / "seed.db"
    if not db.is_file():
        warnung("tests/fixtures/seed.db fehlt — Schema-Check übersprungen"); return
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        haben = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    finally:
        conn.close()
    if haben != ERWARTETE_TABELLEN:
        fehler(f"DB-Schema: Tabellen weichen ab (fehlt: {ERWARTETE_TABELLEN - haben}, "
               f"extra: {haben - ERWARTETE_TABELLEN})")
    else:
        print(f"DB-Schema OK: {len(haben)} Tabellen")


# ── mdguard: Markdown-Schreib-Konvention (knowledge/system/md-schreib-konvention.md) ──
# Rein lesend: Quelltext-/MD-Prüfung, KEIN DB-Write, kein UI-Start.
# Stand 21.10.2026. Allowlisten: Alt-Bestand < MDGUARD_STICHTAG, Changelog-Append,
# datumsfreie Muster, Startdatum-Muster (Datumsrollen-Tabelle in der Spec).
MDGUARD_STICHTAG = "2026-10-21"          # Artefakte vor diesem Datum: nicht rot
MDGUARD_ERGEBNISSE = ROOT / "ergebnisse"
# V-10 (21.10.2026): getrackte Fixtures — `ergebnisse/` ist gitignored, in der
# CI existiert der Ordner nicht ⇒ die artefaktbezogenen Regeln liefen nie. Die
# Fixtures unter tests/fixtures/md-guard/ sind versioniert und werden in der CI
# mitgeprueft (1 gueltige + 1 verstoessende Datei je Regel-Gruppe).
MDGUARD_FIXTURES = ROOT / "tests" / "fixtures" / "md-guard"
MDGUARD_HTML_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
# Muster ohne Datum im Dateinamen bzw. mit Startdatum (Datumsrollen: Vorgangs-ID
# bzw. Fachdatum) — by design, im Code umgesetzt (Spec §3, 21.10.2026).
MDGUARD_UNDATUM = ("einladung-bewerbung-", "onboarding-freigabe-bewerbung-",
                   "contract-preflight-bewerbung-", "onboarding-")
# Paritäts-Referenz: Schreiber dort sind nicht produktiv (Spec §3) — werden
# seit V-07 (21.10.2026) **mitgeprüft** (der Code ist real, nur der Start ist
# abgeschaltet).
MDGUARD_PARITAET = ()
# Schreiber-Codemarken, die der Wächter statisch prüft (Quelle: Teil-0-Inventar).
MDGUARD_WRITER_DATEIEN = (
    ROOT / "webui" / "pages" / "candidate.py",
    ROOT / "webui" / "components.py",
    ROOT / "webui" / "logic.py",
    ROOT / "scripts" / "agent-runner.py",
)
# Auto-Discovery: weitere Produktiv-Schreiber werden mitgeprüft (21.10.2026).
# V-07 (21.10.2026): die **Repo-Wurzel** ist mit enthalten ⇒ `mcp-*.py` und
# `app.py` (Paritäts-Referenz) werden erfasst. `tests/**` bleibt bewusst
# ausgenommen (dort wird bewusst nach ergebnisse/ geschrieben — E2E-Fixtures);
# die Ausnahme ist in der Spec (knowledge/system/md-schreib-konvention.md §3)
# begruendet.
MDGUARD_AUTO_GLOBE = (ROOT / "webui", ROOT / "scripts", ROOT / "connectors", ROOT)
MDGUARD_AUTO_AUSSCHLUSS = ("tests", "scripts/ci", "scripts/seed_ci_db.py",
                           "scripts/agent-test.sh", "scripts/agent-runner.py",
                           "scripts/visual_audit.py", ".venv", ".git",
                           "node_modules", "ergebnisse", "testdaten", "data")
# Leser, die „neuesten" behaupten (R5.1) — Datei → Marker.
MDGUARD_LESER = {
    "agent-runner.py": ("_score_from_ergebnisse", "_compliance_from_ergebnisse",
                        "_visum_auswertung_from_ergebnisse", "export_report"),
    "admin.py": ("tool_result_section",),
}
# Append-only-Protokolle: Anhängen ist hier **by design** (jede Zeile = ein neuer
# Eintrag, kein Abschnitts-Ersetzen) — Ausnahme von R-S1 (Spec §1/§3, 21.10.2026).
MDGUARD_APPEND_ERLAUBT = ("error-statistik-", "pushstate-protokoll-")
# Marker, deren **Aufruf** ein Carry-over ist (R4.3) — die Definition ist erlaubt.
MDGUARD_CARRY_OVER_MARKER = ("find_video_section", "extract_from_other_file")
# Standard-/Fremd-Begriffe, die keine Codemarke sind (R3.1-Rückfall).
MDGUARD_STANDARD_MARKER = {
    "mdguard", "mkdir", "mcp", "sqlite_master", "FileNotFoundError", "Path",
    "write_text", "write_bytes", "open", "sorted", "reversed", "json", "os",
    "knowledge", "skills", "results", "content", "payload", "text", "name",
    "value", "line", "lines", "id", "url", "date", "time", "lang", "score",
    "kategorie", "ja", "nein", "true", "false", "none", "und", "oder",
    "nicht", "kein", "keine", "mit", "ohne", "für", "zum", "zur", "von",
    "im", "in", "an", "auf", "ist", "sind", "war", "werden", "wird", "kann",
    "muss", "soll", "darf", "Datum", "Uhrzeit", "Link", "Sprache", "Status",
}


def _mdguard_quellen() -> dict[str, str]:
    """Alle Produktiv-Schreiber (feste Liste + Auto-Discovery), read-only."""
    out: dict[str, str] = {}
    for p in MDGUARD_WRITER_DATEIEN:
        if p.is_file():
            # V-07 (21.10.2026): Schluessel = **relativer Pfad** (nicht der
            # Basisname) — sonst kollidierten `webui/__init__.py` und
            # `webui/pages/__init__.py` und eine Datei wurde nie geprueft.
            out[_mdguard_schluessel(p)] = p.read_text(encoding="utf-8", errors="replace")
    for basis in MDGUARD_AUTO_GLOBE:
        if not basis.is_dir():
            continue
        for p in sorted(basis.rglob("*.py")):
            rel = _mdguard_schluessel(p)
            if any(rel.startswith(x) or rel == x for x in MDGUARD_AUTO_AUSSCHLUSS):
                continue
            if rel in out:
                continue
            if "__pycache__" in rel:
                continue
            out[rel] = p.read_text(encoding="utf-8", errors="replace")
    return out


def _mdguard_schluessel(p: Path) -> str:
    """Relativer Pfad als Schluessel (ausserhalb des Repo-Wurzelbaums: absoluter Pfad)."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _mdguard_neu(p: Path) -> bool:
    """Nur Artefakte mit Datum >= Stichtag werden geprueft.

    Alt-Bestand (Datum < Stichtag), datumslose Muster (Vorgangs-ID) und
    historische Reports ohne Datum bleiben unangetastet (Allowlist Spec §3).
    """
    name = p.name
    if name.startswith(MDGUARD_UNDATUM):
        return False
    m = MDGUARD_HTML_DATE.search(name)
    if not m:
        return False  # historischer Report ohne Datum -> nicht rot
    return m.group(1) >= MDGUARD_STICHTAG


def _mdguard_normativ(ziel: str) -> bool:
    """Zielt der Schreibvorgang in den normativen Bereich (knowledge/**/skills/**)?

    V-04 (21.10.2026): Der Pfad wird **normalisiert** — auch `BASE / "knowledge" /
    "x.md"` und `base = Path("knowledge"); base / "x.md"` (dort steht "knowledge"
    nur in einer Zuweisung) werden erkannt.
    """
    if not ziel:
        return False
    z = ziel.replace("\\", "/").replace("'", '"')
    for teil in (t.strip().strip('"') for t in z.split("/")):
        if teil in ("knowledge", "skills"):
            return True
    return ("knowledge/" in z) or ("skills/" in z)


def _mdguard_schreibziele(src: str) -> list[tuple[int, str, str]]:
    """AST: alle Schreib-Calls als (Zeile, Ziel-Ausdruck, Inhalt-Ausdruck).

    `Path(x).write_text(t)` → Ziel = `Path(x)`, Inhalt = `t`;
    `p.write_text(t)` → Ziel = `p`, Inhalt = `t`;
    `open(p, "w"/"a")` → Ziel = `p`, Inhalt = Modus (V-04, 21.10.2026: der `open()`-
    Zweig fehlte in der aktiven Fassung — er steckte nur in einer **toten**
    Doppel-Definition).
    Die Zielauflösung löst **mehrere** Ebenen auf (`ziel = p`, `p = pfade[-1]`).
    """
    import ast
    treffer: list[tuple[int, str, str]] = []
    try:
        baum = ast.parse(src)
    except SyntaxError:
        return treffer
    zuweisungen = _mdguard_zuweisungen(src)
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        func = knoten.func
        fname = getattr(func, "attr", None) or getattr(func, "id", None)
        if fname in ("write_text", "write_bytes"):
            ziel = ast.unparse(func.value) if isinstance(func, ast.Attribute) else ""
            inhalt = ast.unparse(knoten.args[0]) if knoten.args else ""
        elif fname == "open":
            # V-04/V-07 (21.10.2026): nur **schreibende** Modi (w/a/x/+) sind
            # Schreibvorgänge — `open(pfad, "rb")` ist reines Lesen.
            modus = ast.unparse(knoten.args[1]) if len(knoten.args) > 1 else ""
            if not re.search(r"[\"'][wax+]", modus):
                continue
            ziel = ast.unparse(knoten.args[0]) if knoten.args else ""
            inhalt = modus
        else:
            continue
        # Zielaufloesung: `ziel = Path("knowledge/x.md")` -> Pfad steht in der
        # Zuweisung, nicht im Call (21.10.2026, E5-Probefund).
        for _ebene in range(3):
            if ziel and ziel in zuweisungen:
                ziel = f"{ziel} = {zuweisungen[ziel]}"
        treffer.append((getattr(knoten, "lineno", 0), ziel, inhalt))
    return treffer


def _mdguard_zuweisungen(src: str) -> dict[str, str]:
    """AST: name → Ausdruck (transitiv aufgelöst, max. 3 Ebenen) je Datei.

    V-04 (21.10.2026): `ziel = p`, `p = pfade[-1]` ⇒ ohne Transitivitaet blieb
    die negative Index-Auswahl unsichtbar.
    """
    import ast
    erg: dict[str, str] = {}
    try:
        baum = ast.parse(src)
    except SyntaxError:
        return erg
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Assign) and len(knoten.targets) == 1 \
                and isinstance(knoten.targets[0], ast.Name):
            erg[knoten.targets[0].id] = ast.unparse(knoten.value)
    for _ebene in range(3):
        for name, wert in list(erg.items()):
            for ziel in list(erg):
                if ziel != name and wert == ziel:
                    erg[name] = erg[ziel]
    return erg


def _mdguard_schreibbereiche(src: str) -> list[tuple[int, int]]:
    """Zeilenbereiche (von, bis) der Funktionen, die in eine Datei schreiben.

    R4.x sind **Schreiber**-Regeln (Spec §1) — sie gelten nur im Kontext eines
    Schreibvorgangs (sonst würde z. B. ein Anzeige-Slice `text[:200]` als
    Truncation gemeldet).
    """
    import ast
    bereiche: list[tuple[int, int]] = []
    try:
        baum = ast.parse(src)
    except SyntaxError:
        return bereiche
    for funktion in [k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)]:
        schreibt = False
        for knoten in ast.walk(funktion):
            if isinstance(knoten, ast.Call):
                fname = getattr(knoten.func, "attr", None) or getattr(knoten.func, "id", None)
                if fname in ("write_text", "write_bytes"):
                    schreibt = True
        if schreibt:
            bereiche.append((funktion.lineno, funktion.end_lineno or funktion.lineno))
    return bereiche


def _mdguard_index_auswahl(src: str) -> list[int]:
    """R4.1: das **Schreibziel** wird per negativer Index-Auswahl gewählt (`x[-1]`)."""
    treffer: list[int] = []
    zuweisungen = _mdguard_zuweisungen(src)
    for zeile, ziel, _inhalt in _mdguard_schreibziele(src):
        ausdruck = zuweisungen.get(ziel, ziel)
        if "[-1]" in ausdruck or "[ -1 ]" in ausdruck:
            treffer.append(zeile)
    return treffer


def _mdguard_truncation(src: str) -> list[int]:
    """R4.4: das **Schreibziel** (oder sein Inhalt) wird abgeschnitten
    (`x[:n]`, `x[0:n]`, `x.split(...)[0]`)."""
    treffer: list[int] = []
    zuweisungen = _mdguard_zuweisungen(src)
    for zeile, ziel, inhalt in _mdguard_schreibziele(src):
        for ausdruck in (ziel, zuweisungen.get(ziel, ziel), inhalt,
                         zuweisungen.get(inhalt, inhalt)):
            # V-04 (21.10.2026): auch `text[0:500]` (obere Grenze) erfassen.
            if re.search(r"\[\s*\d*\s*:\s*\d+\s*\]", ausdruck):
                treffer.append(zeile)
                break
            if re.search(r"\.split\([^)]*\)\s*\[\s*0\s*\]", ausdruck):
                treffer.append(zeile)
                break
    return treffer


def _mdguard_carry_over(src: str) -> list[tuple[int, str]]:
    """R4.3: Carry-over — Inhalt einer **anderen** Markdown-Datei fliesst in eine
    geschriebene Datei.

    V-05 (21.10.2026): **markerbasiert** (bewusste Grenze, in der Spec
    dokumentiert): erkannt werden
      (a) Aufrufe der Marker-Funktionen `MDGUARD_CARRY_OVER_MARKER`
          (Pflege-Liste; die Definition selbst ist erlaubt — nur der Aufruf zaehlt),
      (b) ein **direktes** `read_text()`/`read_bytes()` einer *anderen* Datei, dessen
          Ergebnis in den geschriebenen Inhalt einfliesst.
    Erlaubt (Allowlist): der Zustand aus der **Zieldatei selbst** (Lesen und
    Ersetzen eines Abschnitts derselben Datei) sowie reine Anzeige-Leser.
    Bewusst nicht generisch: eine selbstdefinierte Hilfsfunktion ohne Marker-Namen
    wird nicht erkannt (Variablen-Propagation erzeugte False Positives — Beleg:
    `i` aus `text.find(...)` wurde zum Carry-over-Indikator). Pflege deshalb über
    `MDGUARD_CARRY_OVER_MARKER`.
    """
    import ast
    treffer: list[tuple[int, str]] = []
    try:
        baum = ast.parse(src)
    except SyntaxError:
        return treffer
    definitionen = [(k.name, k.lineno, k.end_lineno or k.lineno)
                    for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)]
    # (a) Marker-Aufrufe (Definition erlaubt).
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        func = knoten.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if not name or name not in MDGUARD_CARRY_OVER_MARKER:
            continue
        zeile = getattr(knoten, "lineno", 0)
        if any(dname == name and von <= zeile <= bis for dname, von, bis in definitionen):
            continue
        treffer.append((zeile, name))
    # (b) Direktes read_text()/read_bytes() einer ANDEREN Datei fliesst in einen Write.
    gelesen: list[tuple[int, str]] = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Attribute) \
                and knoten.func.attr in ("read_text", "read_bytes"):
            gelesen.append((getattr(knoten, "lineno", 0),
                            ast.unparse(knoten.func.value)[:160]))
    for zeile, ziel, inhalt in _mdguard_schreibziele(src):
        for _zl, quelle in gelesen:
            if not quelle:
                continue
            if quelle in ziel:
                continue  # Zustand aus der Zieldatei selbst -> erlaubt
            if quelle not in inhalt:
                continue  # fliesst nicht in den geschriebenen Inhalt
            treffer.append((zeile, f"read_text() aus {quelle!r} fliesst in den Write"))
            break
    return treffer
def _mdguard_erfolgsversprechen(src: str) -> list[tuple[int, str]]:
    """R4.6: Ein Schreiber meldet **Erfolg**, obwohl der Schreibvorgang fehlschlagen
    kann (Erfolgsversprechen).

    Erkannt (AST, 21.10.2026): eine Funktion, die selbst schreibt **und**
    (a) einen **breiten** Fehlerhandler hat (`except Exception`,
    `except BaseException` oder ein nacktes `except:`) **und**
    (b) einen **konstanten** Erfolgswert zurückgibt (`True`, `"done"`, `"ok"`,
    `"erfolgreich"` — auch als Dict-Wert wie `{"logged": True}`).
    Die korrekte Form (`ok = False` … `ok = True` … `return {"logged": ok}`)
    wird **nicht** gemeldet — der Rückgabewert folgt dort dem Schreibvorgang.
    """
    import ast
    treffer: list[tuple[int, str]] = []
    try:
        baum = ast.parse(src)
    except SyntaxError:
        return treffer
    schreibzeilen = {z for z, _ziel, _inhalt in _mdguard_schreibziele(src)}
    erfolg_werte = (True, "done", "ok", "erfolgreich")
    for funktion in [k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)]:
        if not any(funktion.lineno <= z <= (funktion.end_lineno or 0) for z in schreibzeilen):
            continue
        # (a) breiter Fehlerhandler
        breit = False
        for handler in [n for n in ast.walk(funktion) if isinstance(n, ast.ExceptHandler)]:
            typ = handler.type
            if typ is None:
                breit = True
            elif isinstance(typ, ast.Name) and typ.id in ("Exception", "BaseException"):
                breit = True
            elif isinstance(typ, ast.Tuple) and any(
                    isinstance(t, ast.Name) and t.id in ("Exception", "BaseException")
                    for t in typ.elts):
                breit = True
        if not breit:
            continue
        # (b) konstante Erfolgs-Rueckgabe
        for knoten in ast.walk(funktion):
            if not isinstance(knoten, ast.Return) or knoten.value is None:
                continue
            wert = knoten.value
            gefunden = False
            if isinstance(wert, ast.Dict):
                for _k, v in zip(wert.keys, wert.values):
                    if isinstance(v, ast.Constant) and v.value in erfolg_werte:
                        gefunden = True
                        break
            elif isinstance(wert, ast.Constant) and wert.value in erfolg_werte:
                gefunden = True
            if gefunden:
                treffer.append((getattr(knoten, "lineno", 0),
                                f"{funktion.name}: breiter except + konstante Erfolgs-Rückgabe"))
    return treffer


def _mdguard_ohne_mkdir(src: str) -> list[int]:
    """R4.5: Schreibt nach `ergebnisse/`, ohne dass im Repo ein mkdir dafuer
    existiert (eigene Funktion **oder** Helfer wie `_ergebnis_pfad`)."""
    import ast
    treffer: list[int] = []
    try:
        baum = ast.parse(src)
    except SyntaxError:
        return treffer
    hat_mkdir = any(isinstance(k, ast.Call)
                     and (getattr(k.func, "attr", None) or getattr(k.func, "id", None)) == "mkdir"
                     for k in ast.walk(baum))
    if hat_mkdir:
        return treffer
    schreibzeilen = _mdguard_schreibziele(src)
    for funktion in [k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)]:
        for zeile, ziel, _inhalt in schreibzeilen:
            if zeile < funktion.lineno or zeile > (funktion.end_lineno or 0):
                continue
            if "ergebnisse" in ziel.lower() or "ergebnis_pfad" in ziel.lower():
                treffer.append(funktion.lineno)
                break
    return treffer


def _mdguard_blind_anhaengen(src: str) -> list[tuple[int, str]]:
    """R-S1: Read-Modify-Write auf einer bestehenden Markdown-Datei **ohne**
    Abschnitts-Anker (Anhaengen statt Ersetzen).

    Erkannt: dieselbe Variable wird gelesen (`read_text`), per `+=`/Konkatenation
    veraendert und zurueckgeschrieben — ohne dass ein Anker (`## …`) beteiligt ist.
    Reine String-Aufbaut (z. B. `prompt += …` ohne vorheriges Lesen) sind erlaubt.
    """
    import ast
    treffer: list[tuple[int, str]] = []
    try:
        baum = ast.parse(src)
    except SyntaxError:
        return treffer
    for funktion in [k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)]:
        gelesen: set[str] = set()
        veraendert: dict[str, int] = {}
        geschrieben: list[str] = []
        for knoten in ast.walk(funktion):
            if isinstance(knoten, ast.Assign) and len(knoten.targets) == 1 \
                    and isinstance(knoten.targets[0], ast.Name) \
                    and isinstance(knoten.value, ast.Call) \
                    and getattr(knoten.value.func, "attr", None) == "read_text":
                gelesen.add(knoten.targets[0].id)
            if isinstance(knoten, ast.AugAssign) and isinstance(knoten.op, ast.Add) \
                    and isinstance(knoten.target, ast.Name):
                veraendert[knoten.target.id] = getattr(knoten, "lineno", 0)
            if isinstance(knoten, ast.Assign) and len(knoten.targets) == 1 \
                    and isinstance(knoten.targets[0], ast.Name) \
                    and isinstance(knoten.value, ast.BinOp) and isinstance(knoten.value.op, ast.Add):
                ziel = knoten.targets[0].id
                if ziel in gelesen:
                    veraendert[ziel] = getattr(knoten, "lineno", 0)
            if isinstance(knoten, ast.Call) \
                    and getattr(knoten.func, "attr", None) in ("write_text", "write_bytes") \
                    and knoten.args:
                geschrieben.append(ast.unparse(knoten.args[0]))
        if not (gelesen and veraendert and geschrieben):
            continue
        block = ast.unparse(funktion)
        hat_anker = bool(re.search(r"^##\s", block, flags=re.M)) or "replace_" in block
        if hat_anker:
            continue  # Abschnitts-Anker genutzt => kein blinder Anhang
        if any(muster in block for muster in MDGUARD_APPEND_ERLAUBT):
            continue  # Append-only-Protokoll (by design)
        for name, zeile in veraendert.items():
            if any(name in inhalt for inhalt in geschrieben):
                treffer.append((zeile, f"{name} = {name} + ... (Read-Modify-Write ohne Anker)"))
    return treffer


def _mdguard_ohne_rueckgabe(src: str) -> list[tuple[int, str]]:
    """R-S6: Ein **dedizierter** Schreiber (Name-Muster write_/save_/persist_/create_)
    muss den Zielpfad zurueckgeben (Return mit Pfad-Ausdruck)."""
    import ast
    treffer: list[tuple[int, str]] = []
    try:
        baum = ast.parse(src)
    except SyntaxError:
        return treffer
    for funktion in [k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)]:
        if not re.match(r"^(write|save|persist|create)_", funktion.name):
            continue
        schreibt = False
        schreibt_ergebnis = False
        for zeile, ziel, _inhalt in _mdguard_schreibziele(src):
            if zeile < funktion.lineno or zeile > (funktion.end_lineno or 0):
                continue
            schreibt = True
            if "ergebnisse" in ziel.lower() or ziel.lower().endswith(".md") \
                    or "ergebnis_pfad" in ziel.lower():
                schreibt_ergebnis = True
        if not (schreibt and schreibt_ergebnis):
            continue  # R-S6 gilt fuer Ergebnis-/MD-Dateien (nicht fuer PID-/Logdateien)
        ret = False
        for knoten in ast.walk(funktion):
            if isinstance(knoten, ast.Return) and knoten.value is not None:
                ret = True
        annotation = ast.unparse(funktion.returns) if funktion.returns else ""
        if not ret and "Path" not in annotation:
            treffer.append((funktion.lineno, funktion.name))
    return treffer


def _mdguard_leser_auswahl(src: str, marker: str) -> list[tuple[int, bool]]:
    """R5.1: Leser wählt „neuesten"? → (Zeile, verstoßen) je Treffer."""
    import ast
    treffer: list[tuple[int, bool]] = []
    try:
        baum = ast.parse(src)
    except SyntaxError:
        return treffer
    for funktion in [k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)
                      and k.name == marker]:
        for knoten in ast.walk(funktion):
            if isinstance(knoten, ast.For) and isinstance(knoten.iter, ast.Call):
                call = knoten.iter
                if isinstance(call.func, ast.Name) and call.func.id == "sorted":
                    kopf = ast.unparse(knoten.iter)
                    if "[::-1]" in kopf or "reversed(" in kopf:
                        continue  # explizit „neuester"
                    # Rückgabe **innerhalb** der Schleife ⇒ erster Treffer = ältester
                    for inner in ast.walk(knoten):
                        if isinstance(inner, ast.Return):
                            treffer.append((funktion.lineno, True))
                            break
    return treffer


_MDGUARD_FIXTUR_FUNDE: dict[str, list[str]] = {}


def _mdguard_fund(regel: str, datei: str, text: str, ist_fixture: bool) -> None:
    """Meldet einen Artefakt-Fund — bei Fixtures als **Erwartung**, nicht als Fehler.

    V-10 (21.10.2026): `verstoss-*` in tests/fixtures/md-guard/ MUSS auffallen,
    `gueltig-*` MUSS sauber sein. Abweichungen sind echte Fehler (der Lauf
    bleibt dann rot ⇒ der Nachweis ist belastbar).
    """
    if not ist_fixture:
        fehler(f"{regel} {datei}: {text}")
        return
    _MDGUARD_FIXTUR_FUNDE.setdefault(datei, []).append(f"{regel}: {text}")


def check_mdguard() -> None:
    """R1.1/R1.2, R2.1–R2.3, R3.1/R3.2, R4.1–R4.5, R5.1, R-S1, R-S6 (Spec §2)."""
    quellen = _mdguard_quellen()

    # ── R4: Schreiber-Statik über Quelltext (AST, generisch) ────────────
    for name, src in sorted(quellen.items()):
        if name in MDGUARD_PARITAET:
            continue  # Paritäts-Referenz, nicht produktiv (Spec §3)
        # R4.1: Ziel „neueste existierende" (negative Index-Auswahl, generisch)
        for zeile in _mdguard_index_auswahl(src):
            fehler(f"R4.1 {name}: Schreiber wählt 'neueste existierende' als Ziel "
                   f"(negative Index-Auswahl, Zeile {zeile}) — Spec R-S3 "
                   f"(md-schreib-konvention.md)")
        # R4.2: Schreibziel im normativen Bereich (knowledge/**/skills/**)
        for zeile, ziel, _inhalt in _mdguard_schreibziele(src):
            if _mdguard_normativ(ziel):
                fehler(f"R4.2 {name}: Schreibziel im normativen Bereich "
                       f"({ziel!r}, Zeile {zeile}) — Spec R-S4 "
                       f"(md-schreib-konvention.md)")
        # R4.3: Carry-over — Abschnitt aus einer ANDEREN Datei übernehmen
        # (AST: Aufruf, nicht Definition; die Definition ist erlaubt)
        for zeile, aufruf in _mdguard_carry_over(src):
            fehler(f"R4.3 {name}: Carry-over (Abschnitt aus anderer MD-Datei, "
                   f"Aufruf {aufruf!r}, Zeile {zeile}) — Spec R-S2 "
                   f"(md-schreib-konvention.md)")
        # R4.4: Truncation (x[:n] / split(...)[0])
        for zeile in _mdguard_truncation(src):
            fehler(f"R4.4 {name}: Truncation (Inhalt abgeschnitten, Zeile {zeile}) "
                   f"— Spec R-S5 (md-schreib-konvention.md)")
        # R4.5: Zielverzeichnis vor dem Schreiben anlegen
        for zeile in _mdguard_ohne_mkdir(src):
            fehler(f"R4.5 {name}: schreibt nach ergebnisse/ ohne mkdir "
                   f"(Zeile {zeile}) — Spec §1 Ergänzend (md-schreib-konvention.md)")
        # R-S1: Anhängen statt Ersetzen (Blind-Anhang an einen Altinhalt)
        for zeile, muster in _mdguard_blind_anhaengen(src):
            fehler(f"R-S1 {name}: blindes Anhängen statt Anker-Replace "
                   f"({muster}, Zeile {zeile}) — Spec R-S1 (md-schreib-konvention.md)")
        # R4.6: kein Erfolgsversprechen (konstante Erfolgs-Rückgabe trotz
        # verschlucktem Schreibfehler)
        for zeile, hinweis in _mdguard_erfolgsversprechen(src):
            fehler(f"R4.6 {name}: Erfolgsversprechen ({hinweis}, Zeile {zeile}) — "
                   f"Spec R4.6 (md-schreib-konvention.md)")
        # R-S6: Schreiber liefert die Resultatdatei zurück
        for zeile, funktion in _mdguard_ohne_rueckgabe(src):
            fehler(f"R-S6 {name}: Schreiber {funktion} gibt die Resultatdatei nicht "
                   f"zurück (Zeile {zeile}) — Spec R-S6 (md-schreib-konvention.md)")

    # ── R5.1: „neueste" vs. „heutige" explizit (Leser-Marker-Liste) ──
    alle_marker = sorted({mk for marker in MDGUARD_LESER.values() for mk in marker})
    for datei, src in sorted(quellen.items()):
        if datei in MDGUARD_PARITAET:
            continue
        for mk in alle_marker:
            for zeile, gefunden in _mdguard_leser_auswahl(src, mk):
                if gefunden:
                    fehler(f"R5.1 {datei}::{mk} wählt den ältesten Report "
                           f"(sorted + return in der Schleife, Zeile {zeile}) "
                           f"— Spec R5.1 (md-schreib-konvention.md)")

    # ── R1/R2: Artefakt-Dateien (nur neue; ergebnisse/ + getrackte Fixtures) ──
    # V-10 (21.10.2026): Die getrackten Fixtures unter tests/fixtures/md-guard/
    # sind **Erwartungsträger**: `gueltig-*` muss gruen sein, `verstoss-*` muss
    # rot sein. Der Lauf bleibt dadurch rc=0 und beweist in der CI, dass die
    # artefaktbezogenen Regeln wirklich greifen (vorher liefen sie nie, weil
    # `ergebnisse/` gitignored ist).
    for _artefaktbasis, _ist_fixture in ((MDGUARD_ERGEBNISSE, False),
                                         (MDGUARD_FIXTURES, True)):
      if _artefaktbasis.is_dir():
        for p in sorted(_artefaktbasis.rglob("*.md")):
            if not _mdguard_neu(p):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            # R1.1: doppelte Überschriften (H1/H2/H3)
            doppelt: set[str] = set()
            for ebene in (1, 2, 3):
                _h = re.findall(rf"^#{{{ebene}}} (.+)$", text, flags=re.M)
                doppelt |= {h for h in _h if _h.count(h) > 1}
            if doppelt:
                _mdguard_fund("R1.1", p.name, f"doppelte Überschrift(en): {sorted(doppelt)}",
                              _ist_fixture)
            # R2.1: ?push=-ID ohne Bindestrich
            for m in re.finditer(r"\?push=([A-Za-z0-9_-]+)", text):
                if "-" in m.group(1):
                    _mdguard_fund("R2.1", p.name,
                                  f"?push=-ID mit Bindestrich: {m.group(1)}", _ist_fixture)
            # R2.2: kein ?director= in Selbstpräsentation (Dateiname **enthaelt**
            # "self-presentation-" — die Fixture heisst "verstoss-self-presentation-…")
            if "self-presentation-" in p.name and "?director=" in text:
                _mdguard_fund("R2.2", p.name,
                              "?director= in der Selbstpräsentation "
                              "— Spec R2.2 (vdo-ninja-migration.md §2.3)", _ist_fixture)
            # R2.3: kein meet.jit.si in neuen Artefakten
            if "meet.jit.si" in text:
                _mdguard_fund("R2.3", p.name,
                              "meet.jit.si in neuem Artefakt "
                              "— Providerwechsel 27.09.2026 abgeschlossen", _ist_fixture)
        # R1.2: Konflikt-ID Kandidat+Tag genau eine Datei (alle Task-Familien)
        _seen: dict[tuple[str, str], list[str]] = {}
        for p in MDGUARD_ERGEBNISSE.rglob("*.md"):
            m = re.match(r"(.*?)-kandidat-(\d+)-(\d{4}-\d{2}-\d{2})", p.name)
            if not m:
                continue
            _seen.setdefault((f"{m.group(1)}#{m.group(2)}", m.group(3)), []).append(p.name)
        for (cid, tag), namen in sorted(_seen.items()):
            if len(namen) > 1:
                fehler(f"R1.2 {cid} + {tag}: {len(namen)} Dateien: {sorted(namen)}")

    # V-10: Fixture-Erwartungen pruefen (gruen = kein Fund, rot = Fund erwartet).
    if MDGUARD_FIXTURES.is_dir():
        for p in sorted(MDGUARD_FIXTURES.rglob("*.md")):
            funde = _MDGUARD_FIXTUR_FUNDE.get(p.name, [])
            if "verstoss" in p.name:
                if not funde:
                    fehler(f"Fixture-Erwartung: {p.name} sollte einen Verstoß "
                           f"auslösen, aber es gab keinen — die Regel greift nicht")
            elif funde:
                fehler(f"Fixture-Erwartung: {p.name} sollte sauber sein, "
                       f"aber es gab {len(funde)} Fund(e): {funde}")

    # ── R3.1: in der Spec genannte Codemarken existieren ──────────────
    spec = ROOT / "knowledge" / "system" / "md-schreib-konvention.md"
    if spec.is_file():
        spec_text = spec.read_text(encoding="utf-8", errors="replace")
        code_text = "\n".join(quellen.values())
        for marker in sorted(set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]{2,})`", spec_text))):
            if marker in MDGUARD_STANDARD_MARKER:
                continue
            if marker in code_text:
                continue
            if any(marker in p.read_text(encoding="utf-8", errors="replace")
                   for p in list((ROOT / "webui").rglob("*.py"))
                   + list((ROOT / "scripts").rglob("*.py"))
                   + list((ROOT / "tests").rglob("*.py"))
                   if "__pycache__" not in str(p)):
                continue
            warnung(f"R3.1 md-schreib-konvention.md zitiert Codemarke "
                    f"'{marker}', die im Code nicht gefunden wurde")

    # ── R3.2: Zählwerte live ───────────────────────────────────────────
    md_count = len(list((ROOT / "knowledge").rglob("*.md")))
    try:
        import json as _json
        mcp_count = len((_json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
                         .get("mcp") or {}))
    except Exception:
        mcp_count = None
    if spec.is_file():
        spec_text = spec.read_text(encoding="utf-8", errors="replace")
        if mcp_count is not None and f"`opencode.json`-`mcp` = **{mcp_count}**" not in spec_text:
            fehler(f"R3.2 md-schreib-konvention.md: MCP-Server-Zahl weicht ab "
                   f"(live {mcp_count})")
        if f"= **{md_count}**" not in spec_text:
            fehler(f"R3.2 md-schreib-konvention.md: Knowledge-MD-Zahl weicht ab "
                   f"(live {md_count})")

    print(f"mdguard: {len(FEHLER)} Fehler, {len(WARNUNG)} Warnungen "
          f"(Stichtag {MDGUARD_STICHTAG}, Knowledge-MD {md_count}, "
          f"MCP-Server {mcp_count}, Schreiber geprüft: {len(quellen)})")


BEREICHE = {"docs": check_docs, "legal": check_legal, "mcp": check_mcp,
            "i18n": check_i18n, "schema": check_schema, "mdguard": check_mdguard}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in BEREICHE:
        sys.exit(f"Usage: {sys.argv[0]} {'|'.join(BEREICHE)}")
    BEREICHE[sys.argv[1]]()
    for w in WARNUNG:
        print(f"WARNUNG: {w}")
    for f in FEHLER:
        print(f"FEHLER: {f}")
    print(f"→ {sys.argv[1]}: {len(FEHLER)} Fehler, {len(WARNUNG)} Warnungen")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    raise SystemExit(main())
