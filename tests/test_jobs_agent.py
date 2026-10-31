"""Job-Akquise-Agent: Filter, Eignung, Beleg-Namen, Mail-Rendering.

Die Tests laufen ohne Netz: Suche/Playwright werden nicht beruehrt.
Spec: knowledge/system/jobs-agent.md
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("jobs_agent", ROOT / "scripts" / "jobs_agent.py")
mod = importlib.util.module_from_spec(_spec)
sys.modules["jobs_agent"] = mod  # Dataclasses loesen Annotationen ueber sys.modules auf
_spec.loader.exec_module(mod)


# ── Eignung ────────────────────────────────────────────────────────────

def test_visum_und_anerkennung_erhoehen_score():
    text = ("Wir unterstuetzen Sie beim Visum und bei der Anerkennung Ihres "
            "Abschlusses. Deutschkenntnisse B1 genuegen. Relocation-Hilfe vorhanden.")
    score, gruende = mod.suitability(text)
    assert score >= 80, (score, gruende)
    assert any("visum" in g for g in gruende)
    assert any("anerkennung" in g for g in gruende)


def test_kurzer_text_wird_abgewertet():
    score, gruende = mod.suitability("Kurz.")
    assert score <= 20, (score, gruende)
    assert any("ohne verwertbaren Text" in g for g in gruende)


def test_eu_only_wird_abgewertet():
    text = ("Nur mit deutscher Berufszulassung. " * 20)
    score, _ = mod.suitability(text)
    assert score < 40, score


def test_score_bleibt_im_bereich():
    for text in ("", "x" * 5000, "Visum " * 500):
        score, _ = mod.suitability(text)
        assert 0 <= score <= 100


# ── E-Mail ─────────────────────────────────────────────────────────────

def test_find_email_nimmt_veroeffentlichte_adresse():
    assert mod.find_email("Kontakt: personal@klinik-beispiel.de") == "personal@klinik-beispiel.de"


def test_find_email_ignoriert_platzhalter():
    assert mod.find_email("mail@example.com logo.png") == ""


def test_find_email_ohne_treffer():
    assert mod.find_email("Kein Kontakt vorhanden.") == ""


# ── Aggregatoren ───────────────────────────────────────────────────────

def test_aggregator_boersen_werden_erkannt():
    lang = "x" * 400
    assert mod.is_aggregator("Job", "https://de.indeed.com/viewjob?jk=1", lang)
    assert mod.is_aggregator("Job", "https://www.stepstone.de/stellenangebote", lang)
    assert mod.is_aggregator("Jobs in Todesfelde", "https://lkw-fahrer-gesucht.de/x", lang)


def test_arbeitgeberseite_ist_kein_aggregator():
    text = "St. Irmgardis-Krankenhaus sucht eine Pflegefachkraft. " * 10
    assert not mod.is_aggregator("Ausbildung zur Pflegefachkraft", "https://jobs.st-franziskus-stiftung.de/de/x", text)


def test_kurzer_text_gilt_als_aggregator():
    assert mod.is_aggregator("Stelle", "https://example.org/job", "kurz")


# ── Namen und Slug ─────────────────────────────────────────────────────

def test_employer_aus_titel():
    assert mod.employer_from("Klinikum Nord - Pflegefachkraft", "") == "Klinikum Nord"


def test_employer_aus_text():
    text = "Unternehmen: TechVision GmbH\nStandort: Berlin"
    assert mod.employer_from("Pflegefachkraft", text) == "TechVision GmbH"


def test_location_aus_text():
    assert mod.location_from("Standort: Viersen\nRest", "DE") == "Viersen"


def test_slug_ist_stabil_und_dateisicher():
    a = mod.Job(title="Pflegefachkraft (m/w/d) – Süchteln", url="https://example.org/a", country="DE", industry="Krankenpflege")
    b = mod.Job(title="Pflegefachkraft (m/w/d) – Süchteln", url="https://example.org/a", country="DE", industry="Krankenpflege")
    assert a.slug == b.slug
    assert "/" not in a.slug and " " not in a.slug
    assert a.slug.startswith(a.key)


# ── Mail ───────────────────────────────────────────────────────────────

def test_mail_de_ohne_platzhalter():
    job = mod.Job(title="Pflegefachkraft", url="https://x", country="DE", industry="Krankenpflege",
                  employer="Klinikum Nord", location="Berlin")
    betreff, body = mod.render_mail("de", job, {"arbeitgeber": "Klinikum Nord"})
    assert "{{" not in body and "{{" not in betreff
    assert "Klinikum Nord" in body and "Pflegefachkraft" in body
    assert "jobs.hanibal-ai.com" in body
    assert "kostenlos" in body.lower()


def test_mail_fr_und_en():
    job = mod.Job(title="Infirmier", url="https://x", country="FR", industry="Krankenpflege",
                  employer="Clinique Lyon", location="Lyon")
    for lang, wort in (("fr", "gratuite"), ("en", "free")):
        betreff, body = mod.render_mail(lang, job, {"arbeitgeber": "Clinique Lyon"})
        assert wort in body.lower(), lang
        assert "{{" not in body


def test_mail_empfaenger_ohne_stelle():
    betreff, body = mod.render_mail("de", None, {"arbeitgeber": "AmeSol Akademie"})
    assert "AmeSol Akademie" in betreff or "AmeSol Akademie" in body
    assert "{{" not in body
