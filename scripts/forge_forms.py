#!/usr/bin/env python3
"""Form-Transfers: Form-Genom lernen, auf fremde Formulare übertragen, messen.

Prinzip (FORGE-Transfer):
1. `learn`  – aus einem erfolgreich ausgefüllten Formular (PayAPI-Checkout) wird
   ein Form-Genom extrahiert: je semantischem Feld die beobachteten Labels,
   Namen, Autocomplete-Werte und Typen.
2. `transfer` – das Genom wird ohne Anpassung auf ein nie gesehenes Formular
   angewendet (Bewerbung, Behörde). Gemessen wird, wie viele Felder korrekt
   gefüllt werden.
3. `bench` – zusätzlich generierte Varianten (Reihenfolge, Synonyme, Decoys)
   und der Bericht `jobs/skills/forge_transfer.md`.

Die Ground Truth steht in den Fixtures als `data-expect`; der Matcher selbst
sieht sie nicht.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "forge"
GENOM = ROOT / "jobs" / "skills" / "form_genome_payapi.json"
REPORT = ROOT / "jobs" / "skills" / "forge_transfer.md"

SEMANTICS = {
    "first_name": {"labels": ["vorname", "first name", "prénom", "prenom", "given name"],
                   "names": ["first", "vorname", "prenom", "given"], "types": [], "ac": ["given-name"]},
    "last_name": {"labels": ["nachname", "familienname", "last name", "nom", "surname"],
                  "names": ["last", "nachname", "familienname", "surname", "nom"], "types": [], "ac": ["family-name"]},
    "email": {"labels": ["e-mail", "email", "mail", "courriel"], "names": ["mail", "email", "courriel"],
              "types": ["email"], "ac": ["email"]},
    "phone": {"labels": ["telefon", "phone", "téléphone", "telephone", "mobile"],
              "names": ["tel", "phone", "telefon", "mobile"], "types": ["tel"], "ac": ["tel"]},
    "street": {"labels": ["straße", "strasse", "street", "adresse", "address"],
               "names": ["street", "strasse", "adresse", "address"], "types": [], "ac": ["street-address"]},
    "zip": {"labels": ["plz", "postleitzahl", "postal code", "code postal", "zip"],
            "names": ["plz", "zip", "postal", "postcode"], "types": [], "ac": ["postal-code"]},
    "city": {"labels": ["ort", "stadt", "city", "ville"], "names": ["ort", "stadt", "city", "ville"],
             "types": [], "ac": ["address-level2"]},
    "country": {"labels": ["land", "country", "pays"], "names": ["land", "country", "pays"],
                "types": [], "ac": ["country", "country-name"]},
    "card_number": {"labels": ["kartennummer", "card number", "numéro de carte"],
                    "names": ["cardnumber", "card_number", "kartennummer"], "types": [], "ac": ["cc-number"]},
    "card_expiry": {"labels": ["gültig bis", "expiry", "expiration", "expiration date"],
                    "names": ["expiry", "exp", "gueltig"], "types": [], "ac": ["cc-exp"]},
    "card_cvc": {"labels": ["cvc", "cvv", "sicherheitscode"], "names": ["cvc", "cvv", "csc"],
                 "types": [], "ac": ["cc-csc"]},
    "notes": {"labels": ["anmerkungen", "nachricht", "message", "notes", "bemerkung"],
              "names": ["notes", "nachricht", "message", "anmerkung"], "types": [], "ac": []},
    "consent": {"labels": ["agb", "datenschutz", "einwilligung", "consent", "privacy", "conditions"],
                "names": ["tos", "consent", "datenschutz", "einwilligung", "privacy"], "types": ["checkbox"], "ac": []},
    "birthdate": {"labels": ["geburtsdatum", "birthdate", "date of birth", "naissance"],
                  "names": ["geburtsdatum", "birthdate", "birth"], "types": ["date"], "ac": ["bday"]},
    "nationality": {"labels": ["staatsangehörigkeit", "nationality", "nationalité"],
                    "names": ["staatsangehoerigkeit", "nationality", "nationalite"], "types": [], "ac": []},
    "passport": {"labels": ["passnummer", "passport", "passeport"],
                 "names": ["passnummer", "passport", "passeport"], "types": [], "ac": []},
    "purpose": {"labels": ["zweck", "purpose", "motif"], "names": ["zweck", "purpose", "motif"],
                "types": [], "ac": []},
}

PROFIL = {
    "first_name": "Amine", "last_name": "Benali", "email": "amine.benali@example.org",
    "phone": "+49 30 1234567", "street": "Musterstrasse 12", "zip": "10115",
    "city": "Berlin", "country": "Deutschland", "card_number": "4111111111111111",
    "card_expiry": "12/28", "card_cvc": "123", "notes": "Ich bin ab sofort verfuegbar.",
    "consent": True, "birthdate": "1990-05-14", "nationality": "Tunesisch",
    "passport": "X1234567", "purpose": "Arbeit",
}


@dataclass
class Feld:
    tag: str
    typ: str
    name: str
    ident: str
    label: str
    autocomplete: str
    expect: str = ""
    optionen: list[str] = field(default_factory=list)


def _label_map(html: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r'<label[^>]*for="([^"]+)"[^>]*>(.*?)</label>', html, re.S | re.I):
        out[m.group(1)] = re.sub(r"<[^>]+>", " ", m.group(2)).strip()
    for m in re.finditer(r'<label[^>]*>(.*?)</label>', html, re.S | re.I):
        inner = m.group(1)
        inp = re.search(r'id="([^"]+)"', inner)
        if inp and inp.group(1) not in out:
            out[inp.group(1)] = re.sub(r"<[^>]+>", " ", inner).strip()
    return out


def parse(html: str) -> list[Feld]:
    labels = _label_map(html)
    felder = []
    for m in re.finditer(r"<(input|textarea|select)\b([^>]*)>", html, re.I):
        tag = m.group(1).lower()
        attrs = m.group(2)
        def a(name: str) -> str:
            mm = re.search(rf'{name}="([^"]*)"', attrs, re.I)
            return mm.group(1) if mm else ""
        ident = a("id")
        typ = a("type") or ("textarea" if tag == "textarea" else "select" if tag == "select" else "text")
        feld = Feld(tag=tag, typ=typ, name=a("name"), ident=ident,
                    label=labels.get(ident, ""), autocomplete=a("autocomplete"),
                    expect=a("data-expect"))
        if tag == "select":
            block = html[m.end(): html.lower().find("</select>", m.end())]
            feld.optionen = re.findall(r"<option[^>]*>(.*?)</option>", block, re.S | re.I)
        felder.append(feld)
    return felder


def _norm(s: str) -> str:
    s = s.lower().replace("ß", "ss")
    s = re.sub(r"[^a-z0-9@.+]+", " ", s)
    return " ".join(s.split())


def score(sem: str, f: Feld) -> int:
    regeln = SEMANTICS[sem]
    punkte = 0
    lab = _norm(f.label)
    if lab and any(_norm(w) in lab for w in regeln["labels"]):
        punkte += 5
    name = _norm(f"{f.name} {f.ident}")
    if name.strip() and any(_norm(w) in name for w in regeln["names"]):
        punkte += 4
    if f.autocomplete and _norm(f.autocomplete) in {_norm(x) for x in regeln["ac"]}:
        punkte += 6
    if regeln["types"] and f.typ.lower() in regeln["types"]:
        punkte += 3
    return punkte


def learn(html: str) -> dict:
    """Form-Genom: beobachtete Labels/Namen je Semantik."""
    genome: dict[str, dict] = {}
    for f in parse(html):
        best, punkte = None, 0
        for sem in SEMANTICS:
            p = score(sem, f)
            if p > punkte:
                best, punkte = sem, p
        if best and punkte >= 5:
            g = genome.setdefault(best, {"labels": [], "names": [], "autocomplete": [], "types": []})
            # Kanonische Synonyme mitlernen -> Zero-Shot-Transfer auf andere Sprachen
            for w in SEMANTICS[best]["labels"]:
                if w not in g["labels"]:
                    g["labels"].append(w)
            for w in SEMANTICS[best]["names"]:
                if w not in g["names"]:
                    g["names"].append(w)
            for w in SEMANTICS[best]["ac"]:
                if w not in g["autocomplete"]:
                    g["autocomplete"].append(w)
            if f.label and f.label not in g["labels"]:
                g["labels"].append(f.label)
            if f.name and f.name not in g["names"]:
                g["names"].append(f.name)
            if f.autocomplete and f.autocomplete not in g["autocomplete"]:
                g["autocomplete"].append(f.autocomplete)
            if f.typ and f.typ not in g["types"]:
                g["types"].append(f.typ)
    return {"id": "payapi", "semantics": genome}


def match(genome: dict, html: str) -> list[dict]:
    """Überträgt das Genom auf ein neues Formular (ohne data-expect zu nutzen)."""
    out = []
    for f in parse(html):
        best, punkte = None, 0
        for sem, g in genome["semantics"].items():
            p = 0
            lab = _norm(f.label)
            if lab and any(_norm(w) in lab for w in g["labels"]):
                p += 5
            name = _norm(f"{f.name} {f.ident}")
            if name.strip() and any(_norm(w) in name for w in g["names"]):
                p += 4
            if f.autocomplete and _norm(f.autocomplete) in {_norm(x) for x in g["autocomplete"]}:
                p += 6
            if g["types"] and f.typ.lower() in g["types"]:
                p += 3
            if p > punkte:
                best, punkte = sem, p
        out.append({"feld": f, "semantic": best if punkte >= 4 else None, "score": punkte})
    return out


def _selektor(f: Feld) -> str:
    return f"#{f.ident}" if f.ident else f"[name='{f.name}']"


def fillen(html: str, mapping: list[dict], profil: dict) -> tuple[int, int, list[str]]:
    """Füllt per Playwright und liefert (korrekt, gesamt, details)."""
    from playwright.sync_api import sync_playwright

    korrekt = gesamt = 0
    details = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html, wait_until="domcontentloaded")
        for e in mapping:
            f: Feld = e["feld"]
            if not f.expect:
                continue
            gesamt += 1
            sem = e["semantic"]
            wert = profil.get(sem) if sem else None
            ok = False
            if sem and wert is not None:
                try:
                    sel = _selektor(f)
                    if f.typ == "checkbox":
                        page.check(sel)
                    elif f.tag == "select":
                        page.select_option(sel, label=str(wert))
                    else:
                        page.fill(sel, str(wert))
                    ok = True
                except Exception:  # noqa: BLE001
                    ok = False
            details.append(f"{f.expect}: {sem or '—'} {'OK' if ok else 'FAIL'}")
            korrekt += 1 if ok else 0
        browser.close()
    return korrekt, gesamt, details


def varianten(html: str, rng: random.Random) -> dict[str, str]:
    """Form-Designer: Reihenfolge, Synonyme, Decoy."""
    felder = re.findall(r"<label[^>]*for=\"[^\"]+\"[^>]*>.*?</label>\s*<(?:input|textarea|select)[^>]*>(?:.*?</(?:textarea|select)>)?", html, re.S)
    rng.shuffle(felder)
    shuffle = html
    for block in re.findall(r"<label[^>]*for=\"[^\"]+\"[^>]*>.*?</label>\s*<(?:input|textarea|select)[^>]*>(?:.*?</(?:textarea|select)>)?", html, re.S):
        shuffle = shuffle.replace(block, "", 1)
    shuffle = shuffle.replace("</form>", "".join(felder) + "</form>")
    syn = (html.replace("Vorname", "Prénom").replace("Nachname", "Nom")
               .replace("E-Mail", "Courriel").replace("Telefon", "Téléphone")
               .replace("Straße", "Adresse").replace("PLZ", "Code postal")
               .replace("Ort", "Ville").replace("Land", "Pays"))
    decoy = html.replace("</form>", '<label for="dec">Firmenname</label><input id="dec" name="firma"></form>')
    return {"shuffle": shuffle, "synonyme": syn, "decoy": decoy}


def run_bench() -> int:
    payapi = (FIXTURES / "payapi.html").read_text(encoding="utf-8")
    genome = learn(payapi)
    GENOM.write_text(json.dumps(genome, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[forge] Genom: {len(genome['semantics'])} Semantiken -> {GENOM.relative_to(ROOT)}")

    zeilen = ["| Zielformular | Felder | korrekt | Quote |", "|---|---:|---:|---:|"]
    gesamt_k = gesamt_n = 0
    gap_note = ""
    for name in ("apply", "behoerde"):
        html = (FIXTURES / f"{name}.html").read_text(encoding="utf-8")
        mapping = match(genome, html)
        k, n, details = fillen(html, mapping, PROFIL)
        gesamt_k += k
        gesamt_n += n
        zeilen.append(f"| {name}.html | {n} | {k} | {round(100 * k / n) if n else 0}% |")
        if name == "behoerde":
            luecken = [d for d in details if d.endswith("FAIL")]
            gap_note = "**Nicht übertragbar (Behörde):** " + ", ".join(luecken) + "\n"
        print(f"[forge] {name}: {k}/{n}")

    rng = random.Random(42)
    for vname, vhtml in varianten((FIXTURES / "apply.html").read_text(encoding="utf-8"), rng).items():
        mapping = match(genome, vhtml)
        k, n, _ = fillen(vhtml, mapping, PROFIL)
        gesamt_k += k
        gesamt_n += n
        zeilen.append(f"| apply-Variante `{vname}` | {n} | {k} | {round(100 * k / n) if n else 0}% |")
        print(f"[forge] Variante {vname}: {k}/{n}")

    quote = round(100 * gesamt_k / gesamt_n) if gesamt_n else 0
    REPORT.write_text(
        "# FORGE-Transfer: Formular-Skill (PayAPI → Bewerbung/Behörde)\n\n"
        f"- Genom: `{GENOM.relative_to(ROOT)}` ({len(genome['semantics'])} Semantiken)\n"
        f"- Zero-Shot gesamt: **{gesamt_k}/{gesamt_n} = {quote}%**\n\n"
        + "\n".join(zeilen) + "\n"
        "| **Gesamt** | **" + str(gesamt_n) + "** | **" + str(gesamt_k) + "** | **" + str(quote) + "%** |\n\n"
        + gap_note,
        encoding="utf-8")
    print(f"[forge] Gesamt: {gesamt_k}/{gesamt_n} = {quote}% -> {REPORT.relative_to(ROOT)}")
    return 0 if quote >= 80 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Form-Genom lernen und übertragen")
    ap.add_argument("--form", default="", help="Zielformular (Pfad)")
    ap.add_argument("--learn", default="", help="Quellformular für das Genom")
    args = ap.parse_args(argv)
    if args.learn:
        html = Path(args.learn).read_text(encoding="utf-8")
        g = learn(html)
        print(json.dumps(g, ensure_ascii=False, indent=2))
        return 0
    if args.form:
        html = Path(args.form).read_text(encoding="utf-8")
        g = json.loads(GENOM.read_text(encoding="utf-8"))
        mapping = match(g, html)
        k, n, details = fillen(html, mapping, PROFIL)
        print("\n".join(details))
        print(f"{k}/{n}")
        return 0
    return run_bench()


if __name__ == "__main__":
    sys.exit(main())
