"""E2E Hiring-Board Passiv-Filter (S5, Iteration „Hiring-Board Passiv-Filter", 16.10.2026).

Seite /employer/board (Codemark `_page_board` in webui/pages/employer.py), Reiter
„Passiv" (Codemark `_pf_*`): ui.select „Stelle" (Default „Alle Stellen" = bester Job
je Kandidat, Score DESC), „Score" (Alle/90+/75+/60+/40+), „Erfahrung" (Alle/ab 2/5/10
Jahren), „Sprache" (Alle Sprachen/Deutsch/Englisch/Französisch). Gate 1:1-Parität `_passive_best`
(matching-filter.md (g)): >=1 Must-Have UND >=50 % der geforderten Erfahrung — OHNE
Gate-Treffer erscheint der Kandidat NICHT.

Login-/Restore-/residue-Muster: tests/e2e_einladen_flow.py (nur LESEND, keine
Fixture-Schreibungen — der Passiv-Filter schreibt nichts, daher kein Restore noetig;
residue=0 faellt ohnehin 0 aus). Navigation OHNE hartes goto (Hang-Falle §5):
Login -> Sidebar-Klick „Hiring-Board" -> Reiter „Passiv".

Behauptungen (Erwartung IM Skript unabhaengig aus dem ISOLATIONS-Spiegel berechnet,
read-only `sqlite3.connect('file:<spiegel>?mode=ro', uri=True)`):
1) Gate-Negativ + Erwartungsberechnung: ERWARTETE Menge = CV-Pool (CAND_CV_STATUS)
   minus Bewerber (applications JOIN jobs, employer 1, status != 'zurückgezogen'),
   pro Kandidat bester Job ueber alle 4 aktiven Jobs mit Gate (`logic.berechne_match_score`:
   `matches` nicht leer UND `k_exp or 0 >= j_exp * 0.5`), Score DESC. UI-Gegenprobe:
   (a) jede angezeigte Karte traegt Pseudonym einer ERWARTETEN id; (b) jede erwartete
   id OHNE Gate-Treffer (Gate-negative) darf NICHT auf der Seite vorkommen; (c) die
   UI-„Passung X/100"-Werte stimmen je Karte mit dem berechneten Score ueberein.
2) Score-DESC relativ: die X/100-Reihe ist monoton fallend.
3) Filter ⊆ Menge ohne Filter: Score „60+" (Teilmenge, jeder Score >= 60); „Erfahrung:
   ab 10 Jahren" (Teilmenge, jede Karte „Erfahrung: >= 10"); „Sprache: Deutsch"
   (Teilmenge, alle mit deutschem Level aus der Spiegel-DB belegt); „Sprache:
   Französisch" (Teilmenge, alle mit franzoesischem Level; FR-Fixture-Kandidat
   e2e-fr-passiv@example.invalid muss erscheinen). Jeder Filterwechsel
   wird gegen eine unabhaengig berechnete Zielmenge geprueft.
4) Stellen-Waehler: EIN konkreter Job MIT Gate-Treffer -> Teilmenge der Basismenge;
   ein Job OHNE Gate-Treffer -> leer (ein Kandidat, der fuer DIESEN Job keinen
   Gate-Treffer hat, erscheint nicht — negativ aus der Spiegel-DB belegt).
5) residue=0 am Ende; die Live-sha256-Gleichheit liefert der Isolations-Lauf
   (tests/e2e_isolation.py, summary.txt).
"""
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import BASE, DB, seed_email  # noqa: E402

# Erwartungsberechnung: 1:1 dieselben Quellen wie `_pf_berechne`/`_passive_best`.
from webui.pages.employer import CAND_CV_STATUS, anzeige_name  # noqa: E402
from webui import logic  # noqa: E402

EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"
EMPLOYER_ID = 1
# Passiver FR-Fixture-Kandidat aus scripts/seed_ci_db.py (Marker fuer den
# „Sprache: Französisch"-Nachweis unten).
FR_EMAIL = "e2e-fr-passiv@example.invalid"


def _ro():
    """Read-only Verbindung auf den ISOLATIONS-Spiegel (nie Live-DB)."""
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2500)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(700)
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I))
    ).first
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I)).click()
    page.wait_for_url("**/employer**", timeout=15000)


# ── Erwartungsberechnung aus dem Spiegel (read-only) ─────────────────────────
def _jobs(conn):
    return conn.execute(
        "SELECT j.id, j.titel, j.hard_skills, j.soft_skills, j.berufserfahrung_jahre, "
        "j.deutsch_level, j.englisch_level, j.standort, j.stellentyp, e.branche "
        "FROM jobs j JOIN employers e ON e.id = j.employer_id "
        "WHERE j.employer_id = ? AND j.status = 'aktiv'",
        (EMPLOYER_ID,)).fetchall()


def _app_ids(conn):
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT a.candidate_id FROM applications a "
        "JOIN jobs j ON a.job_id = j.id "
        "WHERE j.employer_id = ? AND a.status != 'zurückgezogen'",
        (EMPLOYER_ID,)).fetchall()}


def _pool(conn):
    ph = ",".join("?" * len(CAND_CV_STATUS))
    return conn.execute(
        "SELECT id, name, hard_skills, soft_skills, berufserfahrung_jahre, "
        "abschluss, deutsch, englisch, standort, lebenslauf_text, franzoesisch "
        f"FROM candidates WHERE status IN ({ph})", list(CAND_CV_STATUS)).fetchall()


def erwarte(job_id="alle", min_score=0, min_exp=0, sprache="alle") -> list[dict]:
    """Erwartete Passiv-Menge unter Filtern — 1:1 nachbau von `_pf_berechne`.

    Pro Kandidat: Job-Menge (alle aktiven Jobs oder die gewaehlte Stelle), je Job
    `logic.berechne_match_score` mit dem Dict-Aufbau des Passiv-Blocks; Skip ohne
    >=1 Must-Have (`matches`) und bei <50 % der geforderten Erfahrung; bester Treffer
    je Kandidat. Danach Score-/Erfahrungs-/Sprach-Filter, Ergebnis Score DESC.
    """
    conn = _ro()
    try:
        jobs = _jobs(conn)
        aus = _app_ids(conn)
        pool = _pool(conn)
        menge = jobs if job_id == "alle" else [j for j in jobs if str(j[0]) == str(job_id)]
        erg: list[dict] = []
        for pk in pool:
            if pk[0] in aus:
                continue
            best = None
            for pj in menge:
                try:
                    r = logic.berechne_match_score(
                        {"hard_skills": pk[2], "soft_skills": pk[3],
                         "berufserfahrung_jahre": pk[4], "abschluss": pk[5],
                         "deutsch": pk[6], "englisch": pk[7], "standort": pk[8],
                         "lebenslauf_text": pk[9] or ""},
                        {"hard_skills": pj[2], "soft_skills": pj[3],
                         "berufserfahrung_jahre": pj[4], "deutsch_level": pj[5],
                         "englisch_level": pj[6], "standort": pj[7], "stellentyp": pj[8],
                         "branche": pj[9]})
                except Exception:
                    continue
                if not r["matches"]:
                    continue
                if pj[4] and (pk[4] or 0) < pj[4] * 0.5:
                    continue
                if best is None or r["total"] > best[0]:
                    best = (r["total"], pj[1] or "")
            if best is None:
                continue  # Gate-Negativ: kein Treffer ueber das Gate
            if min_score and best[0] < min_score:
                continue
            if min_exp and (pk[4] or 0) < min_exp:
                continue
            if sprache == "de" and not str(pk[6] or "").strip():
                continue
            if sprache == "en" and not str(pk[7] or "").strip():
                continue
            if sprache == "fr" and not str(pk[10] or "").strip():
                continue
            erg.append({"id": pk[0], "score": best[0], "titel": best[1],
                        "exp": pk[4] or 0, "de": pk[6] or "", "en": pk[7] or "",
                        "fr": pk[10] or ""})
        return sorted(erg, key=lambda t: t["score"], reverse=True)
    finally:
        conn.close()


def gate_negative_ids(ziel_ids: set) -> list[int]:
    """CV-Pool-Kandidaten OHNE Bewerbung, die keinen Gate-Treffer ueber die
    aktiven Jobs haben — duerfen im Passiv-Filter NICHT erscheinen."""
    conn = _ro()
    try:
        aus = _app_ids(conn)
        pool = _pool(conn)
        jobs = _jobs(conn)
        neg = []
        for pk in pool:
            if pk[0] in aus or pk[0] in ziel_ids:
                continue
            treffer = False
            for pj in jobs:
                try:
                    r = logic.berechne_match_score(
                        {"hard_skills": pk[2], "soft_skills": pk[3],
                         "berufserfahrung_jahre": pk[4], "abschluss": pk[5],
                         "deutsch": pk[6], "englisch": pk[7], "standort": pk[8],
                         "lebenslauf_text": pk[9] or ""},
                        {"hard_skills": pj[2], "soft_skills": pj[3],
                         "berufserfahrung_jahre": pj[4], "deutsch_level": pj[5],
                         "englisch_level": pj[6], "standort": pj[7], "stellentyp": pj[8],
                         "branche": pj[9]})
                except Exception:
                    continue
                if r["matches"] and not (pj[4] and (pk[4] or 0) < pj[4] * 0.5):
                    treffer = True
                    break
            if not treffer:
                neg.append(pk[0])
        return neg
    finally:
        conn.close()


# ── UI-Lesehelfer (sichtbarer Passiv-Reiter) ─────────────────────────────────
def lese_karten(page) -> list[dict]:
    """Liest die sichtbaren Passiv-Karten (Reiter „Passiv") aus: Pseudonym-ID,
    Score (X/100), Erfahrung (N Jahre), DE/EN-Level."""
    karten = page.locator(".q-tab-panel:visible .q-card")
    n = karten.count()
    out = []
    for i in range(n):
        txt = karten.nth(i).inner_text()
        m_id = re.search(r"Kandidat #(\d+)", txt)
        m_sc = re.search(r"(\d+)/100", txt)
        m_ex = re.search(r"Erfahrung:\s*(\d+)\s*Jahre", txt)
        m_de = re.search(r"DE\s*(\S+)\s*·\s*EN\s*(\S+)", txt)
        out.append({
            "cid": int(m_id.group(1)) if m_id else None,
            "score": int(m_sc.group(1)) if m_sc else None,
            "exp": int(m_ex.group(1)) if m_ex else None,
            "de": m_de.group(1) if m_de else None,
            "en": m_de.group(2) if m_de else None,
        })
    return out


def setze_auswahl(page, label: str, option: str) -> None:
    """Waehlt eine Option in einem ui.select mit schwebendem Label `label`.

    Muster e2e_sprachtest_flow/e2e_feedback_filter: .q-select (Label-Filter) klicken,
    Option im offenen .q-menu gescoped klicken, auf Menü-Schluss + Refresh warten.
    """
    sel = page.locator(".q-select").filter(has_text=label).first
    sel.click()
    page.wait_for_timeout(600)
    menue_opt = page.locator(".q-menu").get_by_role("option", name=option, exact=True)
    menue_opt.wait_for(timeout=6000)
    menue_opt.first.click()
    try:
        page.wait_for_selector(".q-menu", state="detached", timeout=4000)
    except Exception:
        page.keyboard.press("Escape")
    page.wait_for_timeout(1500)  # `_pf_view.refresh()` + Server-Roundtrip


def setze_defaults(page) -> None:
    """Setzt alle vier Filter zurueck (job/score/exp/sprache = alle)."""
    setze_auswahl(page, "Stelle", "Alle Stellen")
    setze_auswahl(page, "Score", "Alle")
    setze_auswahl(page, "Erfahrung", "Alle")
    setze_auswahl(page, "Sprache", "Alle Sprachen")


def ids(karten) -> set:
    return {k["cid"] for k in karten}


def main():
    check_server()
    if "e2e-iso-" not in str(DB):
        print(f"ABORT: kein Isolations-Spiegel (DB={DB}) — Lauf nur isoliert")
        sys.exit(1)
    task_base = pre_max_tasks()

    # ── unabhaengige Erwartung aus dem Spiegel ────────────────────────────
    basis = erwarte()  # ohne Filter (alle Stellen)
    basis_ids = {e["id"] for e in basis}
    neg_ids = gate_negative_ids(basis_ids)
    print(f"ERWARTET (ohne Filter): {len(basis)} Karten -> "
          f"{[(anzeige_name(None, e['id'], None), e['score']) for e in basis]}")
    print(f"GATE-NEGATIVE (duerfen NICHT erscheinen): {neg_ids}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        try:
            login_employer(page)
            # KLICK 1: Sidebar „Hiring-Board" (kein hartes goto — Hang-Falle §5)
            page.get_by_role("button", name=re.compile("Hiring-Board", re.I)).first.click()
            page.wait_for_timeout(2500)
            assert "/employer/board" in page.url, f"Route verfehlt: {page.url}"

            # KLICK 2: Reiter „Passiv"
            page.get_by_role("tab", name="Passiv", exact=True).click()
            page.wait_for_timeout(1500)

            # ── (1) Basismenge: Gate 1:1 + Erwartungsberechnung ──────────
            karten = lese_karten(page)
            zeig_ids = ids(karten)
            # (a) jede angezeigte Karte = erwartete id, und alle erwarteten id erscheinen
            assert zeig_ids <= basis_ids, \
                f"UI zeigt unerwartete id: {zeig_ids - basis_ids}"
            assert basis_ids <= zeig_ids, \
                f"UI zeigt nicht alle erwarteten id: {basis_ids - zeig_ids}"
            # (c) Score je Karte == berechneter bester Score
            score_map = {e["id"]: e["score"] for e in basis}
            for k in karten:
                assert k["score"] == score_map.get(k["cid"]), \
                    f"Score-Karte #{k['cid']}: UI {k['score']} != erwartet {score_map.get(k['cid'])}"
            # Karten-Struktur: Pseudonym + Jobtitel + „Passung" + X/100 + Profil-Button
            for i in range(page.locator(".q-tab-panel:visible .q-card").count()):
                karte = page.locator(".q-tab-panel:visible .q-card").nth(i)
                assert karte.locator("text=Passung").count() >= 1, "Karte ohne „Passung\""
                assert karte.locator("button:has-text('Im Kandidaten-Profil öffnen')").count() == 1, \
                    "Karte ohne Profil-Button"
            # (b) Gate-Negativ: Pseudonym der Gate-negativen id darf NICHT vorkommen
            for gid in neg_ids:
                treffer = page.get_by_text(re.compile(rf"Kandidat #{gid}(?!\d)")).count()
                assert treffer == 0, f"Gate-negative id #{gid} erscheint auf der Seite ({treffer}x)"
            print(f"BASE: {len(karten)} Karten, ids={sorted(zeig_ids)} == erwartet "
                  f"{sorted(basis_ids)}; Scores geprueft; Gate-negativ {neg_ids} abwesend")

            # ── (2) Score-DESC relativ ───────────────────────────────────
            reihenfolge = [k["score"] for k in karten]
            for a, b in zip(reihenfolge, reihenfolge[1:]):
                assert a >= b, f"Score nicht monoton fallend: {reihenfolge}"
            print(f"DESC: {reihenfolge} monoton fallend")

            # ── (3) Filter ⊆ Menge ohne Filter ───────────────────────────
            # Score „60+"
            setze_auswahl(page, "Score", "60+")
            ziel60 = erwarte(min_score=60)
            k60 = lese_karten(page)
            assert ids(k60) == {e["id"] for e in ziel60}, \
                f"Score 60+: UI {sorted(ids(k60))} != erwartet {sorted(e['id'] for e in ziel60)}"
            assert ids(k60) <= basis_ids, "Score 60+ nicht Teilmenge der Basismenge"
            assert all(k["score"] >= 60 for k in k60), f"Score 60+ zeigt {k60}"
            print(f"FILTER Score 60+: {sorted(ids(k60))} ⊆ Basis, jeder Score >= 60")

            # „Erfahrung: ab 10 Jahren" (Score zurueck auf Alle, unabhaengig pruefen)
            setze_defaults(page)
            setze_auswahl(page, "Erfahrung", "ab 10 Jahren")
            ziel10 = erwarte(min_exp=10)
            k10 = lese_karten(page)
            assert ids(k10) == {e["id"] for e in ziel10}, \
                f"Erfahrung 10+: UI {sorted(ids(k10))} != erwartet {sorted(e['id'] for e in ziel10)}"
            assert ids(k10) <= basis_ids, "Erfahrung 10+ nicht Teilmenge der Basismenge"
            assert all((k["exp"] or 0) >= 10 for k in k10), f"Erfahrung 10+ zeigt {k10}"
            print(f"FILTER Erfahrung ab 10: {sorted(ids(k10))} ⊆ Basis, jede Karte Erfahrung >= 10")

            # „Sprache: Deutsch"
            setze_defaults(page)
            setze_auswahl(page, "Sprache", "Deutsch")
            zielde = erwarte(sprache="de")
            kde = lese_karten(page)
            assert ids(kde) == {e["id"] for e in zielde}, \
                f"Sprache Deutsch: UI {sorted(ids(kde))} != erwartet {sorted(e['id'] for e in zielde)}"
            assert ids(kde) <= basis_ids, "Sprache Deutsch nicht Teilmenge der Basismenge"
            de_map = {e["id"]: e["de"] for e in zielde}
            for k in kde:
                assert str(de_map.get(k["cid"]) or "").strip(), \
                    f"Karte #{k['cid']} ohne deutsches Level in der Spiegel-DB"
            print(f"FILTER Sprache Deutsch: {sorted(ids(kde))} ⊆ Basis, alle mit deutschem Level")

            # „Sprache: Französisch" — Teilmenge, jede Karte mit franzoesischem
            # Level aus der Spiegel-DB; der FR-Fixture-Kandidat (Marker-E-Mail
            # FR_EMAIL, scripts/seed_ci_db.py) MUSS erscheinen.
            setze_defaults(page)
            setze_auswahl(page, "Sprache", "Französisch")
            zielfr = erwarte(sprache="fr")
            kfr = lese_karten(page)
            assert len(kfr) >= 1, "Sprache Französisch: keine Karten — FR-Fixture fehlt im Seed?"
            assert ids(kfr) == {e["id"] for e in zielfr}, \
                f"Sprache Französisch: UI {sorted(ids(kfr))} != erwartet {sorted(e['id'] for e in zielfr)}"
            assert ids(kfr) <= basis_ids, "Sprache Französisch nicht Teilmenge der Basismenge"
            conn_fr = _ro()
            try:
                fr_ids = {r[0] for r in conn_fr.execute(
                    "SELECT id FROM candidates WHERE email=?", (FR_EMAIL,))}
            finally:
                conn_fr.close()
            assert fr_ids and fr_ids <= ids(kfr), \
                f"FR-Fixture {sorted(fr_ids)} erscheint nicht unter {sorted(ids(kfr))}"
            fr_map = {e["id"]: e["fr"] for e in zielfr}
            for k in kfr:
                assert str(fr_map.get(k["cid"]) or "").strip(), \
                    f"Karte #{k['cid']} ohne franzoesischen Wert in der Spiegel-DB"
            print(f"FILTER Sprache Französisch: {sorted(ids(kfr))} ⊆ Basis, "
                  f"FR-Fixture {sorted(fr_ids)} enthalten")

            # ── (4) Stellen-Waehler: Job MIT und OHNE Gate-Treffer ───────
            setze_defaults(page)
            conn = _ro()
            try:
                alle_jobs = _jobs(conn)
            finally:
                conn.close()
            mit = ohne = None
            for j in alle_jobs:
                m = erwarte(job_id=str(j[0]))
                if m and mit is None:
                    mit = (str(j[0]), j[1], m)
                if not m and ohne is None:
                    ohne = (str(j[0]), j[1])
            assert mit is not None, "kein Job mit Gate-Treffer gefunden (Datenlage?)"
            assert ohne is not None, "kein Job ohne Gate-Treffer gefunden (Datenlage?)"

            # Job MIT Treffer: Teilmenge der Basismenge, unabh. Zielmenge gleich
            setze_auswahl(page, "Stelle", mit[1])
            kjob = lese_karten(page)
            assert ids(kjob) == {e["id"] for e in mit[2]}, \
                f"Job {mit[1]!r}: UI {sorted(ids(kjob))} != erwartet {sorted(e['id'] for e in mit[2])}"
            assert ids(kjob) <= basis_ids, "Job-Treffer nicht Teilmenge der Basismenge"
            print(f"STELLE {mit[1]!r}: {sorted(ids(kjob))} ⊆ Basis, == unabh. Zielmenge")

            # Job OHNE Treffer: leer — Kandidaten mit Basis-Treffer, aber ohne
            # Treffer fuer DIESEN Job, duerfen nicht erscheinen (Gate-Negativ je Job)
            setze_auswahl(page, "Stelle", ohne[1])
            ziel_ohne = erwarte(job_id=ohne[0])
            kohne = lese_karten(page)
            assert ziel_ohne == [], f"Job {ohne[1]!r} sollte keinen Gate-Treffer haben, hat {ziel_ohne}"
            assert ids(kohne) == set(), f"Job {ohne[1]!r} zeigt Karten ohne Gate-Treffer: {kohne}"
            verschwunden = basis_ids - ids(kohne)
            assert verschwunden == basis_ids, \
                f"Basis-Kandidaten erscheinen trotz fehlendem Job-Gate-Treffer: {ids(kohne)}"
            print(f"STELLE {ohne[1]!r}: leer — Basis-Kandidaten {sorted(basis_ids)} "
                  f"verschwinden (Gate-Negativ je Job)")
        finally:
            ctx.close()
            browser.close()

    residue = db_residue_report(task_base)
    print(f"OK board-passiv-filter residue={residue}")
    sys.exit(0 if residue == 0 else 1)


if __name__ == "__main__":
    main()
