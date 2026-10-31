#!/usr/bin/env python3
"""Automatische Skill-Induktion, Transfer-Matrix und Form-Designer.

Ablauf:
1. `induce`  – liest alle Beleg-Läufe (`jobs/belege/*/index.md`), leitet daraus
   generalisierte Skills je (Land, Branche, Quelle) ab und schreibt
   `jobs/skills/lattice.json`.
2. `transfer` – testet live, welche Branchen in welchem Land mit den vorhandenen
   Skills erreichbar sind, und schreibt `jobs/skills/transfer.md`.
3. `forms`   – generiert neue Suchformen (Land × Branche × Stadt), prüft sie und
   erweitert Skills automatisch, wenn eine neue Branche erfolgreich ist.
   Ergebnis: `jobs/skills/self_improvement.md`.

Aufruf:
    python3 scripts/jobs_induce.py induce
    python3 scripts/jobs_induce.py transfer
    python3 scripts/jobs_induce.py forms
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402
import jobs_skill as sk  # noqa: E402

ROOT = ja.ROOT
SKILLS = ROOT / "jobs" / "skills"
BELEGE = ROOT / "jobs" / "belege"
LATTICE = SKILLS / "lattice.json"

QUELLEN = {
    "eures": "eures-search", "ba": "ba-search", "jobroom": "jobroom-search",
    "lhr": "lhr-search", "jdp": "jdp-search", "fr": "france-travail-search",
}
BRANCHEN = ("Krankenpflege", "LKW", "Handwerk", "Hotellerie")
STAEDTE = {"DE": "Berlin", "CH": "Zürich", "FR": "Lyon"}


def _quelle_aus_pfad(p: Path) -> str:
    name = p.parent.name
    if "eures" in name:
        return "eures-search"
    if "lhr" in name:
        return "lhr-search"
    if "jdp" in name:
        return "jdp-search"
    if "fr" in name:
        return "france-travail-search"
    if name.endswith("-ch"):
        return "jobroom-search"
    return "ba-search"


def evidence() -> list[dict]:
    """Alle belegten Stellen aus den Index-Tabellen (Land, Branche, Quelle)."""
    rows = []
    for idx in sorted(BELEGE.glob("*/index.md")):
        sid = _quelle_aus_pfad(idx)
        for zeile in idx.read_text(encoding="utf-8").splitlines():
            if not zeile.startswith("| ") or "---" in zeile or "Arbeitgeber" in zeile:
                continue
            f = [x.strip() for x in zeile.split("|")]
            if len(f) < 9:
                continue
            land, branche = f[4], f[5]
            if land not in ("DE", "CH", "FR") or branche not in BRANCHEN:
                continue
            rows.append({"country": land, "industry": branche, "source": sid,
                         "employer": f[1], "evidence": str(idx.parent.relative_to(ROOT))})
    return rows


def cmd_induce(_: argparse.Namespace) -> int:
    rows = evidence()
    gruppen: dict[tuple[str, str, str], int] = defaultdict(int)
    for r in rows:
        gruppen[(r["country"], r["industry"], r["source"])] += 1
    lattice = []
    for (land, branche, sid), n in sorted(gruppen.items()):
        lattice.append({"country": land, "industry": branche, "source": sid,
                        "count": n, "last_success": date.today().isoformat(),
                        "evidence": f"jobs/belege/"})
    LATTICE.write_text(json.dumps(lattice, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[induce] Belege: {len(rows)} | Skills: {len(lattice)} -> {LATTICE.relative_to(ROOT)}")
    for e in lattice:
        print(f"  {e['country']} {e['industry']:14} {e['source']:22} n={e['count']}")
    return 0


def _bester_skill(skills: dict, land: str, branche: str) -> dict | None:
    kandidaten = [s for s in skills.values()
                  if s["country"] in (land, "*") and branche in s["industries"]]
    kandidaten.sort(key=lambda s: (s.get("last_success") is None, s["country"] == "*", s["id"]))
    return kandidaten[0] if kandidaten else None


def cmd_transfer(_: argparse.Namespace) -> int:
    skills = sk.load_skills()
    zeilen = ["| Land | Branche | Skill | Ergebnis | Treffer | Beispiel |",
              "|---|---|---|---|---|---|"]
    erfolge = 0
    gesamt = 0
    for land in ("DE", "CH", "FR"):
        for branche in BRANCHEN:
            gesamt += 1
            s = _bester_skill(skills, land, branche)
            if not s:
                zeilen.append(f"| {land} | {branche} | – | FAIL | 0 | kein Skill |")
                continue
            r = sk.probe(s, branche, STAEDTE[land], land)
            erfolge += 1 if r["ok"] else 0
            zeilen.append(f"| {land} | {branche} | {s['id']} | {'OK' if r['ok'] else 'FAIL'} "
                          f"| {r['count']} | {r['sample'][:30]} |")
            time.sleep(0.2)
    ziel = SKILLS / "transfer.md"
    ziel.write_text("# Zero-Shot-Transfer (Land × Branche)\n\n"
                    + "\n".join(zeilen)
                    + f"\n\n**Erfolg: {erfolge}/{gesamt}**\n", encoding="utf-8")
    print("\n".join(zeilen))
    print(f"\nTransfer: {erfolge}/{gesamt} -> {ziel.relative_to(ROOT)}")
    return 0


def cmd_forms(_: argparse.Namespace) -> int:
    skills = sk.load_skills()
    zeilen = ["| Land | Branche | Stadt | Skill | Ergebnis | Treffer | Gelernt |",
              "|---|---|---|---|---|---|---|"]
    gelernt = []
    for land in ("DE", "CH", "FR"):
        for branche in BRANCHEN:
            stadt = STAEDTE[land]
            s = _bester_skill(skills, land, branche)
            if not s:
                zeilen.append(f"| {land} | {branche} | {stadt} | – | FAIL | 0 | Lücke |")
                continue
            r = sk.probe(s, branche, stadt)
            neu = ""
            if r["ok"] and branche not in s["industries"]:
                s["industries"].append(branche)
                s["last_success"] = date.today().isoformat()
                sk.save_skill(s)
                neu = "ja"
                gelernt.append(f"{s['id']} + {branche}")
            zeilen.append(f"| {land} | {branche} | {stadt} | {s['id']} | "
                          f"{'OK' if r['ok'] else 'FAIL'} | {r['count']} | {neu} |")
            time.sleep(0.2)
    ziel = SKILLS / "self_improvement.md"
    ziel.write_text("# Selbstverbesserung (Form-Designer)\n\n"
                    + "\n".join(zeilen)
                    + f"\n\n**Neu gelernt: {len(gelernt)}**"
                    + (": " + ", ".join(gelernt) if gelernt else "") + "\n",
                    encoding="utf-8")
    print("\n".join(zeilen))
    print(f"\nGelernt: {len(gelernt)} -> {ziel.relative_to(ROOT)}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    """Fehlende Kombination (Land/Branche) autonom erschliessen und Skill induzieren."""
    skills = sk.load_skills()
    eures = skills.get("eures-search")
    if not eures:
        print("[discover] keine Basisquelle (eures-search) vorhanden")
        return 2
    r = sk.probe(eures, args.industry, "", args.country)
    print(f"[discover] {args.country}/{args.industry}: ok={r['ok']} count={r['count']} "
          f"sample={r['sample']!r}")
    if not r["ok"]:
        print("[discover] keine Quelle gefunden -> Luecke dokumentiert")
        return 2
    sid = f"eures-{args.country.lower()}"
    neu = {"id": sid, "name": f"EURES {args.country.upper()}", "country": args.country.upper(),
           "source": "EURES public jv-search", "endpoint": eures["endpoint"], "auth": "keine",
           "industries": [args.industry], "queries": {}, "cities": [],
           "evidence": "", "last_success": date.today().isoformat(),
           "transferable_to": ["DE", "FR", "CH"],
           "notes": (f"Automatisch induziert am {date.today().isoformat()}: "
                     f"{r['count']} Treffer, Beispiel {r['sample']!r}.")}
    (SKILLS / f"{sid}.json").write_text(json.dumps(neu, ensure_ascii=False, indent=2), encoding="utf-8")
    ziel = SKILLS / "self_improvement.md"
    with ziel.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## Autonome Erschliessung {date.today().isoformat()}\n\n"
                 f"- Luecke: {args.country}/{args.industry}\n"
                 f"- Probe ueber `eures-search`: {r['count']} Treffer (z. B. {r['sample']})\n"
                 f"- Neuer Skill: `{sid}` (automatisch geschrieben)\n")
    print(f"[discover] neuer Skill: {sid} -> jobs/skills/{sid}.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Skill-Induktion und Transfer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("induce").set_defaults(func=cmd_induce)
    sub.add_parser("transfer").set_defaults(func=cmd_transfer)
    sub.add_parser("forms").set_defaults(func=cmd_forms)
    d = sub.add_parser("discover")
    d.add_argument("--country", required=True)
    d.add_argument("--industry", required=True)
    d.set_defaults(func=cmd_discover)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
