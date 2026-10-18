#!/usr/bin/env python3
"""CI-Prüfungen je Verantwortungsbereich (Aufruf: python3 scripts/ci/checks.py <bereich>).

Bereiche: docs | legal | mcp | i18n | schema
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


BEREICHE = {"docs": check_docs, "legal": check_legal, "mcp": check_mcp,
            "i18n": check_i18n, "schema": check_schema}


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
