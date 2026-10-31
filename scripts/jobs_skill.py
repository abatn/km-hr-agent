#!/usr/bin/env python3
"""Skill-Lattice, Transfer-Test und Form-Designer für die Job-Akquise.

Prinzip (Skill-Induktion): Jeder erfolgreiche Lauf wird zu einem
wiederverwendbaren Skill (Quelle + Land + Query-Mapping + Nachweis). Neue
Aufgaben (Land/Branche/Stadt) werden zuerst mit vorhandenen Skills versucht
(Zero-Shot-Transfer); scheitert das, wird der Skill erweitert oder als Lücke
dokumentiert.

Aufrufe:
    python3 scripts/jobs_skill.py list
    python3 scripts/jobs_skill.py probe  --skill ba-search --industry Krankenpflege
    python3 scripts/jobs_skill.py transfer --industry Krankenpflege
    python3 scripts/jobs_skill.py forms
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402
import jobs_api as ba  # noqa: E402
import jobs_ch as ch  # noqa: E402
import jobs_eures as eu  # noqa: E402
import jobs_jdp as jdp  # noqa: E402
import jobs_lhr as lhr  # noqa: E402

ROOT = ja.ROOT
SKILLS = ROOT / "jobs" / "skills"
ARBEITNOW = "https://www.arbeitnow.com/api/job-board-api"
EXTRA_INDUSTRIES = ["Logistik"]  # Form-Designer testet bewusst neue Branchen


def load_skills() -> dict[str, dict]:
    out = {}
    for p in sorted(SKILLS.glob("*.json")):
        if p.stem == "lattice":
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        if (isinstance(data, dict) and data.get("id")
                and data.get("country") and data.get("industries") is not None):
            out[p.stem] = data
    return out


def save_skill(skill: dict) -> None:
    (SKILLS / f"{skill['id']}.json").write_text(
        json.dumps(skill, ensure_ascii=False, indent=2), encoding="utf-8")


def _arbeitnow_cache() -> list[dict]:
    if not hasattr(_arbeitnow_cache, "daten"):
        req = urllib.request.Request(ARBEITNOW)
        req.add_header("User-Agent", "KMHR-JobsAgent/1.0")
        with urllib.request.urlopen(req, timeout=30) as r:
            _arbeitnow_cache.daten = json.loads(r.read().decode("utf-8", "replace")).get("data", [])
    return _arbeitnow_cache.daten


def probe(skill: dict, industry: str, city: str = "", country: str = "") -> dict:
    """Ein Zero-Shot-Versuch: liefert {ok, count, sample, error}."""
    q = ((skill.get("queries_by_country") or {}).get((country or "").lower()) or {}
         ).get(industry) or (skill.get("queries") or {}).get(industry) or industry
    sid = skill["id"]
    try:
        if sid == "ba-search":
            treffer = ba.suche(q, city or "Berlin", "1", size=10)
            return {"ok": len(treffer) > 0, "count": len(treffer),
                    "sample": (treffer[0].get("firma") if treffer else ""), "error": ""}
        if sid == "jobroom-search":
            treffer = ch.suche([q], size=20)
            name = ""
            if treffer:
                content = (treffer[0].get("jobAdvertisement") or {}).get("jobContent") or {}
                name = (content.get("company") or {}).get("name", "")
            return {"ok": len(treffer) > 0, "count": len(treffer), "sample": name, "error": ""}
        if sid == "arbeitnow-search":
            treffer = [j for j in _arbeitnow_cache()
                       if q.lower() in (j.get("title") or "").lower()]
            return {"ok": len(treffer) > 0, "count": len(treffer),
                    "sample": (treffer[0].get("company_name") if treffer else ""), "error": ""}
        if sid == "france-travail-search":
            if not (os.environ.get("FT_CLIENT_ID") and os.environ.get("FT_CLIENT_SECRET")):
                return {"ok": False, "count": 0, "sample": "", "error": "credentials fehlen"}
            return {"ok": False, "count": 0, "sample": "", "error": "nicht getestet (Creds gesetzt)"}
        if sid == "lhr-search":
            karten = lhr.liste("cuisinier")
            return {"ok": len(karten) > 0, "count": len(karten),
                    "sample": (karten[0].get("title") if karten else ""), "error": ""}
        if sid == "jdp-search":
            fr = [e for e in jdp.feed() if e.get("country") == "France"]
            return {"ok": len(fr) > 0, "count": len(fr),
                    "sample": (fr[0].get("society") if fr else ""), "error": ""}
        if sid == "eures-search":
            treffer = eu.suche(q, (country or "de").lower(), 10)
            return {"ok": len(treffer) > 0, "count": len(treffer),
                    "sample": ((treffer[0].get("employer") or {}).get("name") if treffer else ""),
                    "error": ""}
        if sid == "websearch-fallback":
            treffer, _ = ja.search(f"{q} {city}".strip(), 5)
            return {"ok": len(treffer) > 0, "count": len(treffer),
                    "sample": (treffer[0].get("title") if treffer else ""), "error": ""}
    except Exception as e:  # noqa: BLE001 — Probe-Fehler sind das Ergebnis
        return {"ok": False, "count": 0, "sample": "", "error": type(e).__name__}
    return {"ok": False, "count": 0, "sample": "", "error": "unbekannter Skill"}


def cmd_list(_: argparse.Namespace) -> int:
    skills = load_skills()
    print(f"{'Skill':24} {'Land':5} {'Branchen':42} {'Letzter Erfolg'}")
    for s in skills.values():
        print(f"{s['id']:24} {s['country']:5} {','.join(s['industries'])[:42]:42} {s.get('last_success') or '-'}")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    skills = load_skills()
    s = skills.get(args.skill)
    if not s:
        print(f"Unbekannter Skill: {args.skill}")
        return 2
    r = probe(s, args.industry, args.city)
    print(f"{s['id']} / {args.industry}: ok={r['ok']} count={r['count']} "
          f"sample={r['sample']!r} error={r['error']}")
    return 0 if r["ok"] else 1


def cmd_transfer(args: argparse.Namespace) -> int:
    """Zero-Shot: gleiche Branche, anderer Skill/Land."""
    skills = load_skills()
    zeilen = []
    for s in skills.values():
        if args.country and s["country"] not in (args.country, "*"):
            continue
        r = probe(s, args.industry, args.city)
        zeilen.append((s["country"], s["id"], r))
        time.sleep(0.3)
    print("| Land | Skill | Ergebnis | Anzahl | Beispiel | Fehler |")
    print("|---|---|---|---|---|---|")
    erfolge = 0
    for land, sid, r in zeilen:
        erfolge += 1 if r["ok"] else 0
        print(f"| {land} | {sid} | {'OK' if r['ok'] else 'FAIL'} | {r['count']} "
              f"| {r['sample'][:30]} | {r['error']} |")
    print(f"\nZero-Shot-Erfolg: {erfolge}/{len(zeilen)}")
    return 0


def cmd_forms(args: argparse.Namespace) -> int:
    """Form-Designer: kombiniert Land x Branche x Stadt und lernt bei Erfolg."""
    skills = load_skills()
    tag = date.today().isoformat()
    ziel = ROOT / "jobs" / "belege" / f"skills-{tag}"
    ziel.mkdir(parents=True, exist_ok=True)
    zeilen = ["| Land | Branche | Stadt | Skill | Ergebnis | Anzahl | Gelernt |",
              "|---|---|---|---|---|---|---|"]
    gelernt = 0
    for land in ("DE", "CH", "FR"):
        kandidaten = [s for s in skills.values() if s["country"] in (land, "*")]
        kandidaten.sort(key=lambda x: (x["country"] == "*", x.get("last_success") is None, x["id"]))
        if not kandidaten:
            zeilen.append(f"| {land} | - | - | - | FAIL | 0 | keine Quelle |")
            continue
        for branche in list({i for s in kandidaten for i in s["industries"]})[:8]:
            skill = kandidaten[0]
            stadt = (skill.get("cities") or [""])[0]
            r = probe(skill, branche, stadt)
            neu = ""
            if r["ok"] and branche not in skill["industries"]:
                skill["industries"].append(branche)
                skill["last_success"] = tag
                save_skill(skill)
                gelernt += 1
                neu = "ja"
            zeilen.append(f"| {land} | {branche} | {stadt} | {skill['id']} | "
                          f"{'OK' if r['ok'] else 'FAIL'} | {r['count']} | {neu} |")
            time.sleep(0.2)
    # Neue Branchen erzwingen (Skill-Induktion)
    for land in ("DE", "CH"):
        kandidaten = [x for x in skills.values() if x["country"] == land]
        kandidaten.sort(key=lambda x: (x.get("last_success") is None, x["id"]))
        skill = kandidaten[0]
        for branche in EXTRA_INDUSTRIES:
            r = probe(skill, branche, (skill.get("cities") or [""])[0])
            neu = ""
            if r["ok"] and branche not in skill["industries"]:
                skill["industries"].append(branche)
                skill["last_success"] = tag
                save_skill(skill)
                gelernt += 1
                neu = "ja"
            zeilen.append(f"| {land} | {branche} | {(skill.get('cities') or [''])[0]} | "
                          f"{skill['id']} | {'OK' if r['ok'] else 'FAIL'} | {r['count']} | {neu} |")
    bericht = ziel / "report.md"
    bericht.write_text(
        f"# Skill-Induktion – {tag}\n\n"
        f"Form-Designer: {len(zeilen) - 2} Kombinationen getestet, "
        f"{gelernt} neue Branchen gelernt.\n\n" + "\n".join(zeilen) + "\n",
        encoding="utf-8")
    print("\n".join(zeilen))
    print(f"\nGelernt: {gelernt} -> {bericht.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Skill-Lattice und Form-Designer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(func=cmd_list)
    p = sub.add_parser("probe")
    p.add_argument("--skill", required=True)
    p.add_argument("--industry", required=True)
    p.add_argument("--city", default="")
    p.set_defaults(func=cmd_probe)
    t = sub.add_parser("transfer")
    t.add_argument("--industry", required=True)
    t.add_argument("--country", default="")
    t.add_argument("--city", default="")
    t.set_defaults(func=cmd_transfer)
    sub.add_parser("forms").set_defaults(func=cmd_forms)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
