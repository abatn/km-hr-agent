"""P1 (07.10.2026): Sprach-Transport-Kette, Variante B — Teil P1.

Spec: `knowledge/system/i18n-runner-chain.md` §7.1. Umsetzung von:
  * `webui/i18n_core.py::tr()` — framework-freie gettext-Kernschicht
    (4 Sprachen, Fallback Original, `de` = Identität, `**fmt`).
  * `webui/db.py::queue_agent_task` — injiziert die Session-Sprache über den
    Resolver-Hook `set_language_resolver`; `language` beeinflusst den
    Dedupe-Vergleich im Zweig ohne `application_id` NICHT.

NOCH NICHT Teil von P1 (P2/P3, anderer Auftrag): Runner-Mails/Reports.

Isolation: `tests/conftest.py` leitet `data/feedback.db` in einen
prozesseigenen Spiegel um — die Live-DB wird NIE beschrieben. Der Verbindungs-
pfad wird per `PRAGMA database_list` fail-closed nachgewiesen
(Muster `tests/test_gatekeeper_memo.py`).
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from webui import db
from webui.i18n_core import DEFAULT, SUPPORTED, tr

LANGS = ("de", "en", "fr", "ar")

# Erwartete msgstr je Sprache (Quelle: webui/locales/*/messages.po, ⓘ07.10.2026).
ERWARTET = {
    "Profil gespeichert!": {
        "de": "Profil gespeichert!",
        "en": "Profile saved!",
        "fr": "Profil enregistré !",
        "ar": "تم حفظ الملف الشخصي!",
    },
    "Neue Bewerbung": {
        "de": "Neue Bewerbung",
        "en": "New application",
        "fr": "Nouvelle candidature",
        "ar": "طلب جديد",
    },
}


@pytest.fixture(autouse=True)
def _resolver_isolieren():
    """Resolver-Zustand je Test sichern/wiederherstellen.

    Wichtig: der Import von `webui.i18n` (z. B. in anderen Testmodulen)
    registriert global den echten Session-Resolver -> Tests setzen ihn selbst
    auf None und stellen den Vorzustand danach wieder her.
    """
    prev = db._language_resolver
    db._language_resolver = None
    yield
    db._language_resolver = prev


def _mirror_conn() -> sqlite3.Connection:
    """Verbindung auf die Queue-Tabelle; erzwingt den Spiegel (fail-closed)."""
    conn = sqlite3.connect(str(db.AGENT_TASKS_DB), timeout=10)
    real = conn.execute("PRAGMA database_list").fetchone()[2]
    assert "kmhr-mirror" in real, f"KEIN Spiegel — Verbindung zeigt auf: {real}"
    return conn


def _cleanup(task_type: str) -> None:
    conn = _mirror_conn()
    try:
        conn.execute("DELETE FROM agent_tasks WHERE task_type = ?", (task_type,))
        conn.commit()
    finally:
        conn.close()


def _count(task_type: str) -> int:
    conn = _mirror_conn()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM agent_tasks WHERE task_type = ?",
            (task_type,)).fetchone()[0]
    finally:
        conn.close()


def _payload_of(tid: int) -> dict:
    conn = _mirror_conn()
    try:
        row = conn.execute(
            "SELECT payload FROM agent_tasks WHERE id = ?", (tid,)).fetchone()
    finally:
        conn.close()
    assert row is not None, f"Task #{tid} nicht gefunden"
    return json.loads(row[0])


# ─── tr(): 4 Sprachen, Fallback, Identität, Format ──────────────────────────

def test_tr_bekannte_msgids_in_allen_sprachen():
    for msgid, per_lang in ERWARTET.items():
        for lang in LANGS:
            assert tr(msgid, lang) == per_lang[lang], f"{msgid!r}/{lang}"


def test_tr_de_ist_identitaet():
    assert tr("Profil gespeichert!", "de") == "Profil gespeichert!"
    assert tr("Neue Bewerbung", DEFAULT) == "Neue Bewerbung"


def test_tr_unbekannter_msgid_faellt_auf_original_zurueck():
    assert tr("DIESER-MSGID-EXISTIERT-NICHT", "en") == "DIESER-MSGID-EXISTIERT-NICHT"


def test_tr_unbekannte_sprache_faellt_auf_default():
    # nicht in SUPPORTED -> DEFAULT 'de' -> Identität
    assert "xx" not in SUPPORTED
    assert tr("Profil gespeichert!", "xx") == "Profil gespeichert!"


def test_tr_format_mit_benannten_platzhaltern():
    # Namens-Platzhalter (nicht {0}) — passt zu **fmt / .format(**fmt)
    assert tr("Willkommen, {name}!", "en", name="Anna") == "Welcome, Anna!"
    assert tr("Willkommen, {name}!", "fr", name="Anna") == "Bienvenue, Anna !"
    assert tr("Willkommen, {name}!", "de", name="Anna") == "Willkommen, Anna!"


# ─── queue_agent_task: Transport ────────────────────────────────────────────

def test_queue_ohne_resolver_kein_language_key():
    task = "p1_i18n_ohne_resolver"
    try:
        db._language_resolver = None
        tid = db.queue_agent_task(task, {"marker": "a"})
        assert tid is not None
        assert "language" not in _payload_of(tid)
    finally:
        _cleanup(task)


def test_queue_mit_resolver_injiziert_language():
    task = "p1_i18n_mit_resolver"
    try:
        db._language_resolver = lambda: "fr"
        tid = db.queue_agent_task(task, {"marker": "a"})
        assert tid is not None
        assert _payload_of(tid).get("language") == "fr"
    finally:
        _cleanup(task)


def test_queue_resolver_fehler_bleibt_ohne_language():
    task = "p1_i18n_resolver_fehler"

    def _boom():
        raise RuntimeError("keine Session")

    try:
        db._language_resolver = _boom
        tid = db.queue_agent_task(task, {"marker": "a"})
        assert tid is not None
        assert "language" not in _payload_of(tid)
    finally:
        _cleanup(task)


def test_queue_mutiert_uebergebenes_payload_nicht():
    task = "p1_i18n_keine_mutation"
    original = {"marker": "a"}
    try:
        db._language_resolver = lambda: "ar"
        assert db.queue_agent_task(task, original) is not None
        assert original == {"marker": "a"}, "Payload wurde mutiert!"
    finally:
        _cleanup(task)


# ─── Dedupe: language darf den Vergleich NICHT beeinflussen ─────────────────

def test_dedupe_ignoriert_language_beide_richtungen():
    task = "p1_i18n_dedupe"
    try:
        # erst OHNE language, dann MIT language -> nur EIN Insert
        db._language_resolver = None
        assert db.queue_agent_task(task, {"marker": "x"}) is not None
        db._language_resolver = lambda: "en"
        assert db.queue_agent_task(task, {"marker": "x"}) is None, \
            "language hat den Dedupe-Vergleich verfaelscht (ohne->mit)"
        assert _count(task) == 1

        # Gegenrichtung: erst MIT language, dann OHNE
        _cleanup(task)
        db._language_resolver = lambda: "ar"
        assert db.queue_agent_task(task, {"marker": "y"}) is not None
        db._language_resolver = None
        assert db.queue_agent_task(task, {"marker": "y"}) is None, \
            "language hat den Dedupe-Vergleich verfaelscht (mit->ohne)"
        assert _count(task) == 1
    finally:
        _cleanup(task)


def test_anderes_payload_wird_weiter_gequeued():
    """Gegenprobe: unterschiedlicher Payload (ohne application_id) deduped NICHT."""
    task = "p1_i18n_verschieden"
    try:
        db._language_resolver = None
        assert db.queue_agent_task(task, {"marker": "a"}) is not None
        assert db.queue_agent_task(task, {"marker": "b"}) is not None
        assert _count(task) == 2
    finally:
        _cleanup(task)


# ─── webui/i18n.py: _() delegiert an i18n_core ──────────────────────────────

def test_i18n_delegiert_an_i18n_core(monkeypatch):
    from webui import i18n
    from webui import i18n_core
    assert i18n.LOCALES_DIR == i18n_core.LOCALES_DIR
    monkeypatch.setattr(i18n, "get_language", lambda: "fr")
    assert i18n._("Profil gespeichert!") == "Profil enregistré !"
    monkeypatch.setattr(i18n, "get_language", lambda: "de")
    assert i18n._("Profil gespeichert!") == "Profil gespeichert!"


# ═══════════════════════════════════════════════════════════════════════════
# P2/P3 (07.10.2026): Runner-Mails/Reports in Payload-Sprache.
# Spec: knowledge/system/i18n-runner-chain.md §7.1 Punkt 3–5.
# ═══════════════════════════════════════════════════════════════════════════
import importlib.util
import gettext
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOCALES = BASE / "webui" / "locales"
RUNNER = BASE / "scripts" / "agent-runner.py"
_RUNNER_CACHE: dict = {}


def _load_runner():
    """Runner per importlib laden (Muster tests/e2e_contract_preflight.py)."""
    if "mod" not in _RUNNER_CACHE:
        spec = importlib.util.spec_from_file_location("agent_runner_i18n_unit", RUNNER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _RUNNER_CACHE["mod"] = mod
    return _RUNNER_CACHE["mod"]


def _catalog(lang: str) -> gettext.GNUTranslations:
    return gettext.translation("messages", str(LOCALES), languages=[lang], fallback=True)


# ─── (a) _lang(): Prioritaet gueltig/ungueltig/fehlt ─────────────────────────

@pytest.mark.parametrize("payload,erwartet", [
    ({"language": "en"}, "en"),
    ({"language": "fr"}, "fr"),
    ({"language": "ar"}, "ar"),
    ({"language": "de"}, "de"),
    ({"language": "xx"}, "de"),   # nicht in SUPPORTED
    ({}, "de"),                   # fehlt (Alt-Task)
    ({"language": None}, "de"),
    (None, "de"),
])
def test_lang_prioritaet(payload, erwartet):
    assert _load_runner()._lang(payload) == erwartet


def test_lang_default_ist_de():
    assert DEFAULT == "de"
    assert _load_runner()._lang({"language": "de"}) == "de"


# ─── (b) Mail-Betreffe/Bausteine ueber tr() in en/fr/ar ─────────────────────

def test_runner_mail_bausteine_in_en_fr_ar():
    """Stichproben: 3 Betreffe + Body-Bausteine (Design-Entscheidung-Erstfassung)."""
    erwartet = {
        "Ihre Bewerbung ist eingegangen": (
            "Your application has been received",
            "Votre candidature a été reçue",
            "تم استلام طلبك",
        ),
        "Willkommen im Team – Ihre Einstellung": (
            "Welcome to the team – your hiring",
            "Bienvenue dans l'équipe – votre embauche",
            "مرحبًا بك في الفريق – تم تعيينك",
        ),
        "Rückmeldung zu Ihrer Bewerbung": (
            "Feedback on your application",
            "Retour sur votre candidature",
            "رد بشأن طلبك",
        ),
        "WAS: {0}": ("WHAT: {0}", "QUOI : {0}", "ماذا: {0}"),
        "Wir freuen uns auf die Zusammenarbeit!": (
            "We look forward to working with you!",
            "Nous nous réjouissons de collaborer avec vous !",
            "نتطلع إلى العمل معك!",
        ),
    }
    for key, (en, fr, ar) in erwartet.items():
        got = {"en": _catalog("en").gettext(key),
               "fr": _catalog("fr").gettext(key),
               "ar": _catalog("ar").gettext(key)}
        assert got == {"en": en, "fr": fr, "ar": ar}, f"{key!r}: {got}"


def test_runner_mail_betreff_wird_formatiert():
    # Betreff mit Platzhaltern (nicht in Katalog -> Fallback; Kern = Sprachwahl)
    assert tr("Ihre Bewerbung ist eingegangen", "en") == "Your application has been received"
    assert tr("Ihre Bewerbung ist eingegangen", "de") == "Ihre Bewerbung ist eingegangen"


# ─── (c) Katalog-Vollstaendigkeit: alle neuen Runner-msgids in allen 4 .po ──

RUNNER_NEW_KEYS = (
    'Diese Nachricht wurde im Rahmen des Bewerbungsverfahrens mit Unterstützung eines KI-Systems (EU AI Act Art. 50) erstellt.',
    'Ihre neue Position',
    '⚠️ sekundär belegt',
    'siehe Katalog',
    '## 1. Gehalts-Check (MiLoG)',
    '## 2. Formfall-Hinweise (HR wählt vor Versand)',
    '## 3. NachwG-Pflichtangaben (§ 2 Abs. 1 Nr. 1–15) – HR prüft',
    '- [ ] 1 Name/Anschrift · 2 Beginn/Dauer · 3 Arbeitsort · 4 Tätigkeit',
    '- [ ] 5 Einstufung (tarifgebunden) · 6 Vergütung · 7 Arbeitszeit',
    '- [ ] 8 Urlaub · 9 Kündigungsfristen · 10 Tarifvertrag/BV',
    '- [ ] 11 Vorrang-Regeln · 12 E-Kommunikation · 13 Genehmigung',
    '- [ ] 14 Entsendung/Auslandsrecht · 15 besondere Vertragsbestandteile',
    '## 4. Vertragsskelett',
    '## 5. Quellen (aus knowledge/legal/contract-sources.md, keine Hartkodierung)',
    '*Erstellt von Skill contract-management (Preflight). Der Agent prüft und berichtet – er erstellt keinen Vertrag und signiert nicht (Variante A). Signatur-Optionen A–F: knowledge/legal/contract-management.md §4.*',
    'Ihre Bewerbung ist eingegangen',
    'Ihre Visum-Schritte zur Arbeitsaufnahme',
    'Willkommen im Team – Ihre Einstellung',
    'Rückmeldung zu Ihrer Bewerbung',
    'Online-Interview im Rahmen des Bewerbungsverfahrens.',
    'Online-Interview (HR/Director-Ansicht).',
    'Kein Gehaltsrahmen in der Stelle hinterlegt – HR ergänzt Gehalt vor Vertragsübergabe (HINWEIS, kein FEHLER, Parität app.py MiLoG-Logik)',
    'Unbefristet, unstrittig',
    'formfrei; Nachweis Textform (§ 2 NachwG, E-Mail genügt)',
    'Befristet',
    'Schriftform; elektronisch nur mit QES',
    'Kündigung / Aufhebungsvertrag',
    'Schriftform, elektronische Form ausgeschlossen',
    'QES allgemein',
    'qualifizierte elektronische Signatur = handschriftliche Wirkung',
    '**DSGVO (Spec §6):** Meldebestätigung/Meldeschein enthält die vollständige Wohnanschrift = Stammdaten (Löschfrist 6 Monate, `gdpr-policy.md:48`); in Agent-Berichten nur Status speichern („Meldebestätigung: ja/nein/Offen“, „Wohnungsgeberbestätigung: vorliegend/ja“), **keine** Adresse, **keine** Meldeschein-/Pass-/eAT-Nummern (Art. 5 Abs. 1 c DSGVO); Meldeadresse nie in E-Mails an Dritte.',
    'Guten Tag {name},',
    'vielen Dank für Ihre Bewerbung. Sie ist bei uns eingegangen und wird in Kürze geprüft (Lebenslauf-Analyse, Match- und Compliance-Prüfung).',
    'Wir melden uns, sobald ein Ergebnis vorliegt.',
    'Ihr KM-HR-Agent-Team',
    'Der Agent stellt keinen Antrag – die Antragstellung obliegt dem Kandidaten.',
    'Guten Tag,',
    'Die ausführlichen Berichte (Match / Compliance / Culture-Fit / Dokumente) finden Sie im Portal: 2️⃣ Match-Ergebnis · 3️⃣ Compliance-Ergebnis.',
    'Entscheiden Sie im Portal (💼 Stellenangebote), ob Sie den Kandidaten einladen möchten – der Agent versendet keine Einladung von sich aus.',
    'Ihr KM-HR-Agent (automatische Benachrichtigung)',
    'Ihre Bewerbung war erfolgreich – für Ihren Arbeitsantritt benötigt Ihre Aufenthaltsgenehmigung Ihre Aufmerksamkeit. Hier die Schritte (agent-generiert, bitte verifizieren Sie die Angaben bei der zuständigen Stelle):',
    'Der Agent stellt keinen Antrag – die Antragstellung obliegt Ihnen.',
    'Ihr KM-HR-Agent',
    'Dein Ansprechpartner (Mentor): {0}',
    'wir freuen uns, Sie offiziell bei uns begrüßen zu dürfen – herzlichen Glückwunsch zu Ihrer Einstellung!',
    'Ihr Onboarding im Überblick:',
    '- Vertragliche Dokumente: Arbeitsvertrag (vor Eintritt), Datenschutzeinwilligung und Arbeitszeitkonto (Tag 1)',
    '- IT-Ausstattung: Laptop, E-Mail-Account, VPN und Chat-Zugang (bereitgestellt von der IT-Abteilung)',
    '- Einarbeitung Woche 1: Tag 1 Begrüßung & IT-Übergabe → Tag 2 Tools und Team-Vorstellung → Tag 3 Prozess-Überblick → Tag 5 Rückfragen und erstes Feedback',
    'Die vollständige Onboarding-Checkliste erhalten Sie über das Candidate-Portal (Tab Onboarding).',
    'Wir freuen uns auf die Zusammenarbeit!',
    'vielen Dank für Ihre Bewerbung und Ihr Interesse.',
    'Nach sorgfältiger Prüfung aller Unterlagen haben wir uns entschlossen, in diesem Verfahren anderenorts fortzufahren. Dies ist keine Bewertung Ihrer Fähigkeiten und Persönlichkeit.',
    'Wir wünschen Ihnen für Ihre berufliche und persönliche Zukunft alles Gute.',
    '{0} Uhr ({1} Min.)',
    'Stellenland {0} – Mindestlohn-Check DE (MiLoG) nicht anwendbar; Landesrecht prüfen',
    '(Volltext prüfen)',
    '# Contract Preflight – Bewerbung #{0}',
    'Datum:',
    'Trigger:',
    'Befund',
    'Mindestlohn-Wert (Stand 2026):',
    'Quelle (aus Link-Katalog):',
    'Rechtsgrundlage',
    'Volltext: {0} (Key `nachwg_2` im Link-Katalog)',
    '- Vorlage: `{0}` (Skelett, HR füllt aus – Agent erstellt NICHT den Vertrag)',
    'Key',
    'Neues Agent-Ergebnis: Kandidat #{0} – Score {1}/100',
    'Vorstellungsgespräch: {0}',
    'Vorstellungsgespräch: {0} (HR)',
    'Variante A: HR-Klick',
    'Quellenstatus:',
    'Vergleichsbasis (Design-Entscheidung, 24.09.2026):',
    'Jahresgehalt ÷ {0} h (40 h/Woche × 52) → Stundenlohn',
    'Stellenrahmen: min={0} max={1} €/Jahr',
    'der Agent hat die Bewerbung von Kandidat #{0} geprüft (Bewerbung #{1}).',
    'Match-Score: {0}/100 ({1})',
    'Dokumente: siehe Bericht verify_documents-kandidat-{0}.md',
    'Stelle: {0}',
    'Mindestgehalt {0} €/Jahr ≈ {1:.2f} €/h ≥ {2:.2f} €/h Mindestlohn (Stand 2026)',
    'Mindestgehalt {0} €/Jahr ≈ {1:.2f} €/h < {2:.2f} €/h Mindestlohn (Stand 2026) – VOR Vertragsübergabe korrigieren',
    'Form',
    '- §5.6 Trigger/Task-Zeitpunkt des relocation-Checks (Design-Entscheidung) – **offen**.',
    'WO: {0}',
    'Checkliste via 7️⃣ Generate Onboarding freigeben (HR)',
    'Fall',
    '- §5.5 MD-Korrektur `knowledge/legal/visa-rules.md:144` – **offen**.',
    '- Der Agent sucht keine Angebote und stellt keine Mietanfragen (Variante A).',
    'WIE: {0}',
    "*Task automatisch erzeugt beim Statuswechsel 'eingestellt'.*",
    'WAS: {0}',
    '- §5.4 ansvar-Query-Test `search("Bundesmeldegesetz Anmeldung 17")` – **offen**.',
    '*Ausgelöst durch HR-Klick ({0}) – Variante A.*',
    '- **Portale (nur Link, manuell):** ImmoScout24 · Kleinanzeigen · wg-gesucht · immowelt (AGB untersagt automatisiertes Scraping)',
    'Visum-Hinweis (aus der Dokumenten-Prüfung, agent-generiert):',
    '📋 Visum-Schritte (aus der Dokumenten-Prüfung, agent-generiert):',
    '- §5.3 Skill `relocation` (Agent-Ebene, analog `check-visa`) – **offen**.',
    '- Mail: {0}',
    '- **Freie Quellen:** BMWSB-Ratgeber »Auf Wohnungssuche in Deutschland« · Handbook Germany (9 Sprachen) · Statistikportal/Destatis Open Data · kommunale Wohnungsämter',
    '- **WO:** {0}',
    '## 🤝 Patenschaft (Mentoring)',
    '- **Mentor/Ansprechpartner:** {0}',
    '- §5.2 Relocation-Abschnitt in `knowledge/onboarding-default.md` + den 3 Land-Templates – **offen**.',
    '- ICS (HR/Director): {0}',
    '- **Checkliste:** Zielstadt + Einzugstermin festlegen → Bewerbungsmappe (Selbstauskunft, SCHUFA, Einkommensnachweise) → Mietpreis-Range via Open-Data-Mietspiegel prüfen → freie Quellen nutzen → Angebote manuell auf Portalen (Browser) ansehen',
    '- **WIE:** {0}',
    '- §5.1 Behörden-Infos live & kostenlos (Fristen/Öffnungen/Formulare) via `fetch` + `anysearch` → knowledge-MD – **offen**.',
    '- ICS (Kandidat/Gast): {0}',
    '## 🏠 Wohnungssuche (Checkliste + freie Quellen)',
    '## 📋 Visum-Schritt (agent-generiert)',
    '- **WAS:** {0}',
    'Kandidat #{0} eingestellt – HR erstellt die Checkliste mit 7️⃣ Generate Onboarding und gibt sie frei.',
    '**Offen (Spec §5 – was NEU kommen müsste, noch nicht umgesetzt):**',
    '- Termin: {0}',
    '# Onboarding-Freigabe – Bewerbung #{0}',
    '- Meeting (Kandidat/Gast, Gate 8): {0}',
    '- **Variante A (Spec §3):** Der Agent lädt, meldet und beantragt nie bei einer Behörde – nur Information, Checkliste, E-Mail-Hinweis nach HR-Freigabe.',
    '- Meeting (HR/Director): {0}',
    '- **FR/CH (Design-Entscheidung, Spec §2):** FR Mairie → numéro fiscal → sécurité sociale; CH Einwohnerkontrolle/Gemeinde → AHV-Nummer → Krankenkasse – Details nicht recherchiert.',
    '# Einladung – Bewerbung #{0}',
    '- **Schritte 4–6 (Spec §2):** Steuer-ID erst **nach** Schritt 3 (IdNr bei Zuzug aus dem Ausland zwingend) · Krankenkasse: Kandidat wählt GKV, Arbeitgeber meldet Beschäftigung spätestens 6 Wochen nach Beginn · ELStAM: IdNr + Geburtsdatum, ohne IdNr Steuerklasse VI (max. 3 Monate).',
    '- **Schritt 3 Bürgeramt (Spec §2):** Anmeldung **innerhalb von 2 Wochen nach Einzug**; Unterlagen: Meldeschein + Personalausweis/Pass/Passersatz + Wohnungsgeberbestätigung (Mietvertrag ersetzt sie NICHT); Nicht-EU: Anmeldung **vor** dem Aufenthaltstitel, eAT mit Nationalpass (BMG § 17/§ 23).',
    '- **Reihenfolge (bindend, Spec §2):** 1 Visum/Aufenthalt (`check_visa`) → 2 Wohnung suchen/beziehen → 3 Bürgeramt-Anmeldung (Meldebehörde) → 4 Steuer-ID → 5 Krankenkasse → 6 ELStAM.',
    '## 🏛️ Relocation / Umzug, Behörden, Anmeldung',
)


def test_runner_neue_msgids_in_allen_katalogen():
    """Alle 124 neuen P2/P3-Keys liegen je Sprache im Katalog (nicht leer);
    DE = Identitaet. Zaehlung wie tests/test_i18n.py."""
    assert len(RUNNER_NEW_KEYS) == len(set(RUNNER_NEW_KEYS)) == 124, \
        "P2/P3-Keyliste muss 124 eindeutige Keys haben"
    for key in RUNNER_NEW_KEYS:
        for lang in LANGS:
            cat = _catalog(lang)
            assert key in cat._catalog, f"{lang}: Key {key!r} fehlt im Katalog (P2/P3)"
            assert str(cat._catalog[key]).strip(), f"{lang}: msgstr fuer {key!r} leer"
        assert _catalog("de").gettext(key) == key, f"DE: msgstr != msgid fuer {key!r}"


def test_runner_msgids_im_po_texte():
    """Gegenprobe: die Keys stehen auch in der .po-Quelle (nicht nur .mo)."""
    for lang in LANGS:
        po = (LOCALES / lang / "LC_MESSAGES" / "messages.po").read_text(encoding="utf-8")
        fehlend = [k for k in RUNNER_NEW_KEYS if f'msgid "{k}"' not in po and f'msgid "{_po_esc(k)}"' not in po]
        assert not fehlend, f"{lang}: {len(fehlend)} Keys fehlen in messages.po: {fehlend[:3]}"


def _po_esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ─── (d) Sprach-Beweis: DRY_RUN-Mails sprechen die Payload-Sprache ──────────

def test_dry_run_mail_betreff_sprachabhaengig(monkeypatch):
    """send_confirmation/send_rejection im DRY_RUN (kein echter Versand):
    der Betreff ist EN, wenn payload.language == 'en'; ohne language DE."""
    mod = _load_runner()
    mod.DRY_RUN = True
    aufrufe: list[dict] = []

    def _fake_mcp(server, tool, args):
        aufrufe.append({"tool": tool, "args": args})
        return "DRY-RUN"

    monkeypatch.setattr(mod, "mcp_call", _fake_mcp)

    conn = sqlite3.connect(str(db.AGENT_TASKS_DB))
    try:
        # Kandidat mit E-Mail (Spiegel-DB) fuer send_confirmation
        cid = conn.execute(
            "SELECT id FROM candidates WHERE email IS NOT NULL AND email <> '' "
            "ORDER BY id LIMIT 1").fetchone()[0]
        # abgelehnte Bewerbung fuer send_rejection
        rej = conn.execute(
            "SELECT a.id, a.candidate_id FROM applications a JOIN candidates cd "
            "ON a.candidate_id = cd.id WHERE a.status = 'abgelehnt' "
            "AND cd.email IS NOT NULL AND cd.email <> '' ORDER BY a.id LIMIT 1").fetchone()
    finally:
        conn.close()
    assert rej is not None, "Testdaten fehlen: keine abgelehnte Bewerbung im Spiegel"

    # 1) send_confirmation mit language=en -> englischer Betreff/Body
    mod.send_confirmation({"candidate_id": cid, "language": "en"})
    mail = aufrufe[-1]["args"]
    assert mail["subject"] == "Your application has been received", mail["subject"]
    assert "Thank you for your application" in mail["body"]
    assert "Ihre Bewerbung ist eingegangen" not in aufrufe[-1]["args"]["subject"]

    # 2) send_confirmation OHNE language -> deutscher Betreff (Alt-Task-Fallback)
    mod.send_confirmation({"candidate_id": cid})
    assert aufrufe[-1]["args"]["subject"] == "Ihre Bewerbung ist eingegangen"

    # 3) send_rejection mit language=en -> englischer Betreff, kein Versand
    mod.send_rejection({"application_id": rej[0], "candidate_id": rej[1],
                        "trigger": "hr_klick_portal", "language": "en"})
    assert aufrufe[-1]["args"]["subject"] == "Feedback on your application"

    # 4) send_rejection mit language=ar -> arabischer Betreff
    mod.send_rejection({"application_id": rej[0], "candidate_id": rej[1],
                        "trigger": "hr_klick_portal", "language": "ar"})
    assert aufrufe[-1]["args"]["subject"] == "رد بشأن طلبك"


# ═══════════════════════════════════════════════════════════════════════════
# P2b (07.10.2026): Pre-Screen-Mail + Screening-Fragen in Payload-Sprache.
# Spec: knowledge/system/i18n-runner-chain.md §7.1; betroffen:
#   mcp-email-server.py::send_pre_screen_invitation
#   mcp-meeting-server.py::generate_screening_questions
#   scripts/agent-runner.py::create_invitation (language-Attribut)
# ═══════════════════════════════════════════════════════════════════════════

EMAIL_SERVER_PY = BASE / "mcp-email-server.py"
MEETING_SERVER_PY = BASE / "mcp-meeting-server.py"
_MCP_CACHE: dict = {}


def _load_mcp(name: str, path: Path):
    """MCP-Server in-process laden (Dateiname mit Bindestrich -> importlib)."""
    if name not in _MCP_CACHE:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MCP_CACHE[name] = mod
    return _MCP_CACHE[name]


# 42 neue P2b-msgids (Quelle: webui/locales/*/messages.po, ⓘ07.10.2026).
P2B_NEUE_KEYS = (
    # mcp-email-server.py :: send_pre_screen_invitation (8)
    "Pre-Screening: {position}",
    "wir möchten Sie herzlich zu einem kurzen Pre-Screening für die "
    "Position als **{position}** einladen.",
    "**Meeting-Details:**",
    "- **Link:** {meet_url}",
    "- **Uhrzeit:** {uhrzeit}",
    "- **Dauer:** ca. 30 Minuten",
    "**Themen:**",
    "Bitte bestätigen Sie Ihre Teilnahme kurz per Rück-Mail.",
    # mcp-meeting-server.py :: generate_screening_questions (34)
    "Hervorragend – Fokus auf Leadership & Vision",
    "Gut – Fokus auf Skills & Kultur",
    "Bedingt – Fokus auf Lücken klären",
    "Schwach – Grundlegende Eignung prüfen",
    "{i}. **{s}:** Beschreiben Sie ein konkretes Projekt, in dem Sie {s} "
    "eingesetzt haben. Welche Ergebnisse wurden erzielt?",
    "{i}. **{g}:** Inwieweit haben Sie Erfahrung mit {g}? "
    "Wie würden Sie sich hier einarbeiten?",
    "1. Warum interessiert Sie die Position als {position}?",
    "2. Was sind Ihre beruflichen Ziele für die nächsten 3 Jahre?",
    "3. Wie beschreiben Sie Ihren idealen Arbeitsstil?",
    "4. Welche Erwartungen haben Sie an das Gehalt?",
    "1. Wann könnten Sie starten?",
    "2. Sind Sie bereit, nach München zu ziehen / remote zu arbeiten?",
    "3. Haben Sie Fragen an uns?",
    "=== SCREENING-FRAGEN: {candidate_name} ===",
    "**Kultur-Fit:** {cultural_fit_score}/100",
    "**Kategorie:** {kategorie}",
    "## A. Technische Kompetenz (15 Min.)",
    "## B. Lücken klären (10 Min.)",
    "## C. Motivation & Kultur (10 Min.)",
    "## D. Praktische Details (5 Min.)",
    "## Interviewer-Checkliste",
    "- [ ] Profil-Check vor dem Gespräch",
    "- [ ] Technische Fragen vorbereitet",
    "- [ ] Kultur-Fit-Fragen notiert",
    "- [ ] Nächste Schritte besprochen",
    "- [ ] Feedback-Formular ausgefüllt",
    "## Bewertungsbogen",
    "| Bereich | Score (1–5) | Notizen |",
    "| Technische Kompetenz | | |",
    "| Erfahrungs-Relevanz | | |",
    "| Motivation & Kultur | | |",
    "| Kommunikation | | |",
    "| **Gesamt** | /20 | |",
    "**Empfehlung:** ✅ Weiter / ⚠️ Klärungsbedarf / ❌ Absage",
)


def test_p2b_neue_msgids_in_allen_katalogen():
    """Alle 42 neuen P2b-Keys liegen je Sprache im Katalog (nicht leer);
    DE = Identitaet. Zaehlung wie tests/test_i18n.py."""
    assert len(P2B_NEUE_KEYS) == len(set(P2B_NEUE_KEYS)) == 42, \
        "P2b-Keyliste muss 42 eindeutige Keys haben"
    for key in P2B_NEUE_KEYS:
        for lang in LANGS:
            cat = _catalog(lang)
            assert key in cat._catalog, f"{lang}: Key {key!r} fehlt im Katalog (P2b)"
            assert str(cat._catalog[key]).strip(), f"{lang}: msgstr fuer {key!r} leer"
        assert _catalog("de").gettext(key) == key, f"DE: msgstr != msgid fuer {key!r}"


def test_p2b_msgids_im_po_texte():
    """Gegenprobe: die Keys stehen auch in der .po-Quelle (nicht nur .mo)."""
    for lang in LANGS:
        po = (LOCALES / lang / "LC_MESSAGES" / "messages.po").read_text(encoding="utf-8")
        fehlend = [k for k in P2B_NEUE_KEYS
                   if f'msgid "{k}"' not in po and f'msgid "{_po_esc(k)}"' not in po]
        assert not fehlend, f"{lang}: {len(fehlend)} Keys fehlen in messages.po: {fehlend[:3]}"


def test_p2b_uebersetzungen_en_fr_ar():
    """Stichproben der P2b-Uebersetzungen (Design-Entscheidung-Erstfassung)."""
    erwartet = {
        "Pre-Screening: {position}": (
            "Pre-screening: {position}",
            "Pré-sélection : {position}",
            "الفرز الأولي: {position}",
        ),
        "**Meeting-Details:**": (
            "**Meeting details:**",
            "**Détails de la réunion :**",
            "**تفاصيل الاجتماع:**",
        ),
        "## A. Technische Kompetenz (15 Min.)": (
            "## A. Technical competence (15 min)",
            "## A. Compétence technique (15 min)",
            "## أ. الكفاءة التقنية (15 دقيقة)",
        ),
        "Hervorragend – Fokus auf Leadership & Vision": (
            "Excellent – focus on leadership & vision",
            "Excellent – focus sur le leadership et la vision",
            "ممتاز – التركيز على القيادة والرؤية",
        ),
        "**Empfehlung:** ✅ Weiter / ⚠️ Klärungsbedarf / ❌ Absage": (
            "**Recommendation:** ✅ Proceed / ⚠️ Clarification needed / ❌ Reject",
            "**Recommandation :** ✅ Poursuivre / ⚠️ Clarification nécessaire / ❌ Refuser",
            "**التوصية:** ✅ المتابعة / ⚠️ بحاجة إلى توضيح / ❌ رفض",
        ),
    }
    for key, (en, fr, ar) in erwartet.items():
        got = {"en": _catalog("en").gettext(key),
               "fr": _catalog("fr").gettext(key),
               "ar": _catalog("ar").gettext(key)}
        assert got == {"en": en, "fr": fr, "ar": ar}, f"{key!r}: {got}"


def test_p2b_generate_screening_questions_sprachabhaengig():
    """generate_screening_questions(language=…) liefert Kopf/Block-Titel in
    der Zielsprache; de = Identitaet (Default). KEIN Netz/LLM."""
    mod = _load_mcp("mcp_meeting_p2b", MEETING_SERVER_PY)
    args = ("Anna", "DevOps Engineer", 82, 75, "AWS, Docker", "Kubernetes")

    de = mod.generate_screening_questions(*args)  # Default de (Altverhalten)
    assert "=== SCREENING-FRAGEN: Anna ===" in de
    assert "## A. Technische Kompetenz (15 Min.)" in de
    assert "Gut – Fokus auf Skills & Kultur" in de

    en = mod.generate_screening_questions(*args, language="en")
    assert "=== SCREENING QUESTIONS: Anna ===" in en
    assert "## A. Technical competence (15 min)" in en
    assert "Describe a concrete project" in en
    assert "**Category:** Good – focus on skills & culture" in en
    assert "=== SCREENING-FRAGEN" not in en

    fr = mod.generate_screening_questions(*args, language="fr")
    assert "=== QUESTIONS DE PRÉSÉLECTION : Anna ===" in fr
    assert "## A. Compétence technique (15 min)" in fr
    assert "Décrivez un projet concret" in fr

    ar = mod.generate_screening_questions(*args, language="ar")
    assert "=== أسئلة الفرز: Anna ===" in ar
    assert "## أ. الكفاءة التقنية (15 دقيقة)" in ar
    assert "صف مشروعًا ملموسًا" in ar


def test_p2b_send_pre_screen_invitation_sprachabhaengig(monkeypatch):
    """send_pre_screen_invitation baut Betreff+Body ueber tr(). send_email wird
    gemockt (KEIN echter Versand); Rueckgabeformat bleibt das von send_email."""
    mod = _load_mcp("mcp_email_p2b", EMAIL_SERVER_PY)
    captured: dict = {}

    def _fake_send(to, subject, body, **kw):
        captured.update(to=to, subject=subject, body=body)
        return "OK|fake"

    monkeypatch.setattr(mod, "send_email", _fake_send)
    args = ("cand@example.org", "Anna", "DevOps Engineer",
            "https://vdo.ninja/?room=prescreeningabc&record=off", "2026-10-10", "10:00", "F1")

    out = mod.send_pre_screen_invitation(*args, language="en")
    assert out == "OK|fake", "Rueckgabeformat von send_email muss unveraendert sein"
    assert captured["subject"] == "Pre-screening: DevOps Engineer"
    assert "**Meeting details:**" in captured["body"]
    assert "**Topics:**" in captured["body"]
    assert "Please briefly confirm your participation by reply e-mail." in captured["body"]

    mod.send_pre_screen_invitation(*args, language="fr")
    assert captured["subject"] == "Pré-sélection : DevOps Engineer"
    assert "**Détails de la réunion :**" in captured["body"]
    assert "Cordialement," in captured["body"]

    mod.send_pre_screen_invitation(*args, language="ar")
    assert captured["subject"] == "الفرز الأولي: DevOps Engineer"
    assert "**تفاصيل الاجتماع:**" in captured["body"]

    # Default/ungueltig -> de (Altverhalten)
    mod.send_pre_screen_invitation(*args)
    assert captured["subject"] == "Pre-Screening: DevOps Engineer"
    mod.send_pre_screen_invitation(*args, language="xx")
    assert captured["subject"] == "Pre-Screening: DevOps Engineer"


def test_p2b_runner_create_invitation_traegt_language():
    """Quelltext-Regression: der Runner uebergibt `language` an beide
    MCP-Calls in create_invitation (Spec §7.1) und uebersetzt die
    Bericht-Platzhalter strengths/gaps (M2, 07.10.2026) — sie landen
    woertlich im Kandidaten-Pre-Screen-Mail-Body."""
    src = (BASE / "scripts" / "agent-runner.py").read_text(encoding="utf-8")
    assert '"questions_summary": fragen[:400], "language": lang}' in src, \
        "send_pre_screen_invitation ohne language"
    assert '"strengths": tr("siehe Match-Bericht", lang),\n' \
           '                       "gaps": tr("siehe Match-Bericht", lang),\n' \
           '                       "language": lang})' in src, \
        "generate_screening_questions ohne language / strengths+gaps nicht uebersetzt (M2)"


# ═══════════════════════════════════════════════════════════════════════════
# P4c (07.10.2026): deterministischer Report-Generator export_report
# (Skill 16, ergebnisse/export-kandidat-*.md) in Payload-Sprache.
# Spec: knowledge/system/i18n-runner-chain.md §7.4.
# ═══════════════════════════════════════════════════════════════════════════

def test_p4c_export_report_sprachabhaengig(tmp_path, monkeypatch):
    """export_report schreibt nutzersichtbare Texte in der Payload-Sprache;
    technische Tokens + Dateiname unveraendert. Isoliert auf tmp_path
    (ERGEBNISSE-Spiegel) — kein Netz, keine DB."""
    mod = _load_runner()
    monkeypatch.setattr(mod, "ERGEBNISSE", tmp_path)

    res = mod.export_report({"candidate_id": 7, "job_id": 3, "language": "en"})
    text = Path(res["result_path"]).read_text(encoding="utf-8")
    assert text.startswith("# Match export – candidate #7 / job #3"), text.splitlines()[0]
    assert "## Categories" in text
    assert "| Category | Status |" in text
    assert "| Core competencies | see match report |" in text
    assert "| Sprache | see match report |" not in text
    assert "*Exported on " in text
    # technischer Token bleibt (COMPLIANT/NICHT COMPLIANT), Dateiname technisch
    assert "COMPLIANT" in text
    assert Path(res["result_path"]).name.startswith("export-kandidat-7-job-3-")

    # Alt-Task ohne language -> de (Identitaet), Kategorie-Zeile deutsch
    res_de = mod.export_report({"candidate_id": 7, "job_id": 3})
    text_de = Path(res_de["result_path"]).read_text(encoding="utf-8")
    assert text_de.startswith("# Match-Export – Kandidat #7 / Stelle #3")
    assert "| Kernkompetenzen | siehe Match-Bericht |" in text_de
    assert "## Kategorien" in text_de



# ═══════════════════════════════════════════════════════════════════════════
# P9.5b (07.10.2026, Nutzer-GO "Mituebersetzen" + "Prompt-Haertung"):
# LLM-Berichts-Header ueber tr() + Status-Token-Anweisung im Prompt.
# Spec: knowledge/system/i18n-runner-chain.md §2/§7.1 (Punkt 5),
#       knowledge/system/i18n.md (Badge-Risiko -> gehaertet).
# ═══════════════════════════════════════════════════════════════════════════

def test_p9_5b_header_de_byteidentisch():
    """Bei lang='de' ist der Header byte-identisch mit dem Altbestand.
    Beweis: tests/e2e_admin_downloads.py erwartet "Extract Profile" im
    Report-Content (de = Identitaet von tr, i18n_core §7.1 Punkt 1)."""
    mod = _load_runner()
    erwartet = (f"# Extract Profile – Kandidat #13 / Stelle #6\n\n"
                f"> Agent-Task (Phase 5, live 2026-09-24), Modell: {mod.LLM_MODEL}\n\n")
    assert mod.llm_report_header("extract_profile", 13, 6, "2026-09-24", "de") == erwartet
    # ohne job_id: kein " / Stelle #"-Teil
    ohne_jid = mod.llm_report_header("check_gdpr", 13, None, "2026-09-24", "de")
    assert ohne_jid.startswith("# Check Gdpr – Kandidat #13\n\n> Agent-Task")
    assert "Stelle" not in ohne_jid


def test_p9_5b_header_payload_sprache():
    """Task-Titel bleibt englisch; nur die Prosa-Zeile in der Payload-Sprache.

    **Korrektur P9.5b für parse-kritische Marker (Design-Entscheidung 09.10.2026):**
    die Titel-Struktur-Marker „Kandidat #<id>" / „Stelle #<id>" sind
    sprachstabile Identifier (maschinell geparst von `_BERICHT_STELLE` in
    `webui/pages/employer.py` + `tests/test_r33_compliance_reports.py`) und
    werden daher IMMER deutsch geschrieben — nur die `>`-Prosa-Zeile läuft
    über `tr()`. Spec: `knowledge/system/i18n-runner-chain.md` §2/§7.1.
    """
    mod = _load_runner()
    fr = mod.llm_report_header("extract_profile", 13, 6, "2026-10-07", "fr")
    assert fr.startswith("# Extract Profile – Kandidat #13 / Stelle #6\n")
    assert "Tâche d'agent (phase 5, du 2026-10-07)" in fr
    assert "Agent-Task" not in fr

    ar = mod.llm_report_header("match_candidate", 13, None, "2026-10-07", "ar")
    assert ar.startswith("# Match Candidate – Kandidat #13\n")
    assert "مهمة الوكيل" in ar

    en = mod.llm_report_header("match_candidate", 13, None, "2026-10-07", "en")
    assert en.startswith("# Match Candidate – Kandidat #13\n")
    assert "Agent task (Phase 5, live 2026-10-07), model:" in en


def test_p9_5b_prompt_token_haertung():
    """Quelltext-Regression (Muster test_p2b_runner_create_invitation_...):
    die Status-Token-Anweisung steht NACH dem Sprach-Suffix "Antworte in
    <Klarname>." — sonst faellt jedes Badge in FR/AR-Berichten auf den
    🟡-Default (_badge_icon liest die Tokens aus dem LLM-Text)."""
    src = (BASE / "scripts" / "agent-runner.py").read_text(encoding="utf-8")
    i_sprache = src.index("Antworte in {LANG_NAMES")
    i_token = src.index("Die Status-Tokens COMPLIANT, NICHT_COMPLIANT")
    assert i_token > i_sprache, "Token-Anweisung muss NACH dem Sprach-Suffix stehen"
    fenster = src[i_token:i_token + 700]
    for tok in ("KONFORM", "NICHT_KONFORM", "PLAUSIBEL", "AUFFAELLIG",
                "UNBEKANNT", "UNGEWISS", "ERFORDERLICH", "NICHT ERFORDERLICH"):
        assert tok in fenster, f"Token {tok} fehlt in der Prompt-Haertung"


def test_p9_5b_agent_task_msgid_in_katalogen():
    """Die neue Header-msgid liegt in allen 4 Katalogen mit nicht-leerem
    msgstr; nur de darf der msgid selbst entsprechen (Identitaet)."""
    key = "Agent-Task (Phase 5, live {0}), Modell: {1}"
    for lang in LANGS:
        cat = gettext.translation("messages", str(LOCALES), languages=[lang], fallback=True)
        val = cat.gettext(key)
        assert val.strip(), f"{lang}: leerer msgstr für {key!r}"
        if lang != "de":
            assert val != key, f"{lang}: Fallback auf msgid statt Übersetzung"


# ═══════════════════════════════════════════════════════════════════════════
# O1 (11.10.2026): Prompt-Struktur-Labels in der Payload-Sprache.
# Spec: knowledge/system/i18n-runner-chain.md §7.1 Punkt 5 (Ergänzung O1).
#   scripts/agent-runner.py: `_gewichts_prompt_zeile(lang)` +
#   `tr('Kategorie', lang)` in `match_candidate` + Sektionsliste im
#   `extract_profile`-Prompt (Codemarken, gemessen 11.10.2026).
# Beweis ueber Prompt-Fang: `requests.post` wird gemockt (kein Netz/LLM),
# `ERGEBNISSE` -> pytest-`tmp_path` (kein Schreiben nach ergebnisse/);
# Gewichte deterministisch auf die Baseline gepinnt (unabhaengig von der
# Live-`gewichtung_historie`). `de` = Altbestand (byte-identisch).
# ═══════════════════════════════════════════════════════════════════════════

BASELINE_GEWICHTE = {"kern": 30, "erfahrung": 25, "bildung": 15, "standort": 10,
                     "branche": 10, "soft": 10, "sprache": 0}

# Erwartete Struktur-Labels je Sprache (Quelle: webui/locales/*/messages.po,
# ⓘ11.10.2026 — Sektions-/Kategorie-Labels Altbestand, 7 Gewichte O1).
SEKTIONEN = {
    "de": "Sektionen: Profil,\nKernkompetenzen, Berufserfahrung, Bildung, Sprache, Standort).",
    "en": "Sektionen: Profile,\nCore competencies, Professional experience, Education, Language, Location).",
    "fr": "Sektionen: Profil,\nCompétences clés, Expérience professionnelle, Formation, Langue, Lieu).",
    "ar": "Sektionen: الملف الشخصي,\nالكفاءات الأساسية, الخبرة المهنية, التعليم, اللغة, الموقع).",
}
KATEGORIE = {
    "de": "'Kategorie: <Name>'",
    "en": "'Category: <Name>'",
    "fr": "'Catégorie: <Name>'",
    "ar": "'الفئة: <Name>'",
}
GEWICHTSZEILE = {
    "de": "kern 30.0 / erfahrung 25.0 / bildung 15.0 / standort 10.0 / branche 10.0 / soft 10.0 / sprache 0.0",
    "en": "core 30.0 / experience 25.0 / education 15.0 / location 10.0 / industry 10.0 / soft skills 10.0 / language 0.0",
    "fr": "cœur 30.0 / expérience 25.0 / formation 15.0 / lieu 10.0 / secteur 10.0 / compétences comportementales 10.0 / langue 0.0",
    "ar": "الجوهري 30.0 / الخبرة 25.0 / التعليم 15.0 / الموقع 10.0 / القطاع 10.0 / المهارات الناعمة 10.0 / اللغة 0.0",
}


def _capture_prompt_and_result(monkeypatch, tmp_path, task_type: str, payload: dict) -> dict:
    """Wie `_capture_prompt`, liefert zusaetzlich den `run_llm_task`-Rueckgabewert.

    Faengt den an die LLM-API gesendeten Prompt (`requests.post` gemockt).
    Kein Netz, kein LLM: der Fake liefert 200 + >100 Zeichen Text, damit
    `run_llm_task` den Bericht nach `tmp_path` schreibt und regulaer zurueckkehrt.
    """
    mod = _load_runner()
    monkeypatch.setattr(mod, "DRY_RUN", False)
    monkeypatch.setattr(mod, "ERGEBNISSE", tmp_path)
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key-o1")
    from webui import logic as _logic
    monkeypatch.setattr(_logic, "get_current_weights", lambda: dict(BASELINE_GEWICHTE))
    gefangen: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "L" * 200}}]}

    def _fake_post(url, headers=None, json=None, timeout=None):
        gefangen["prompt"] = (json or {}).get("messages", [{}])[0].get("content", "")
        return _Resp()

    monkeypatch.setattr(mod.requests, "post", _fake_post)
    gefangen["result"] = mod.run_llm_task(task_type, payload)
    return gefangen


def _capture_prompt(monkeypatch, tmp_path, task_type: str, payload: dict) -> str:
    """Wie `_capture_prompt_and_result`, liefert aber nur den Prompt-String."""
    gefangen = _capture_prompt_and_result(monkeypatch, tmp_path, task_type, payload)
    assert gefangen.get("prompt"), "kein requests.post-Aufruf gefangen (Prompt leer)"
    return gefangen["prompt"]


def test_o1_gewichtszeile_de_byteidentisch(monkeypatch):
    """`de` == Altbestand-Formel: rohe Keys + Wert (z. B. `kern 30.0 …`).

    Gegenprobe mit Nicht-Baseline-Werten beweist, dass `de` nichts uebersetzt
    (nur Reihenfolge/Rundung zaehlen) — identisch zur alten `f"{k} {wert}"`-Zeile.
    """
    mod = _load_runner()
    from webui import logic as _logic
    monkeypatch.setattr(_logic, "get_current_weights", lambda: dict(BASELINE_GEWICHTE))
    assert mod._gewichts_prompt_zeile("de") == GEWICHTSZEILE["de"]

    w = {"kern": 23.076923076923077, "erfahrung": 30.76923076923077,
         "bildung": 11.538461538461538, "standort": 7.6923076923076925,
         "branche": 7.6923076923076925, "soft": 7.6923076923076925,
         "sprache": 11.538461538461538}
    monkeypatch.setattr(_logic, "get_current_weights", lambda: dict(w))
    erwartet = " / ".join(f"{k} {round(float(v), 1)}" for k, v in w.items())
    assert mod._gewichts_prompt_zeile("de") == erwartet, \
        "de weicht von der Altbestands-Formel ab"


@pytest.mark.parametrize("lang", LANGS)
def test_o1_prompt_struktur_labels_lokalisiert(lang, monkeypatch, tmp_path):
    """Sektionsliste (extract_profile) + Gewichtszeile + Kategorie (match_candidate)
    erscheinen in der Payload-Sprache."""
    ep = _capture_prompt(monkeypatch, tmp_path, "extract_profile",
                         {"candidate_id": None, "language": lang})
    assert SEKTIONEN[lang] in ep, \
        f"extract_profile/{lang}: Sektionsliste nicht lokalisiert: {ep[:400]}"

    mc = _capture_prompt(monkeypatch, tmp_path, "match_candidate",
                         {"candidate_id": None, "job_id": None, "language": lang})
    assert GEWICHTSZEILE[lang] in mc, \
        f"match_candidate/{lang}: Gewichtszeile nicht lokalisiert"
    assert KATEGORIE[lang] in mc, \
        f"match_candidate/{lang}: Kategorie-Label nicht lokalisiert"
    if lang != "de":
        assert "Sektionen: Profil,\nKernkompetenzen" not in ep, \
            f"{lang}: deutscher Altbestand taucht weiter auf"


def test_o1_de_prompt_byteidentisch_altbestand(monkeypatch, tmp_path):
    """`de`-Prompt enthaelt die alten Struktur-Zeilen verbatim (Altbestand)."""
    ep = _capture_prompt(monkeypatch, tmp_path, "extract_profile",
                         {"candidate_id": None, "language": "de"})
    assert SEKTIONEN["de"] in ep
    mc = _capture_prompt(monkeypatch, tmp_path, "match_candidate",
                         {"candidate_id": None, "job_id": None, "language": "de"})
    assert GEWICHTSZEILE["de"] in mc
    assert KATEGORIE["de"] in mc


# ═══════════════════════════════════════════════════════════════════════════
# F1 (12.10.2026): Sprach-Bypass-Fix — die drei direkten `INSERT INTO
# agent_tasks` tragen jetzt die Payload-Sprache (`language`).
# Spec: knowledge/system/i18n-runner-chain.md §7.1.
#   * Auto-Refresh match_candidate (`_c_ar.execute(...)`)
#   * gatekeeper_eval-Marker (`VALUES ('gatekeeper_eval', 'done', ?)`)
#   * notify_hr (`VALUES ('notify_hr', ?)`)
# Quelltext-Regression (Muster test_p2b_runner_create_invitation_traegt_language):
# Marker-Substring + 400-Zeichen-Fenster gegen Format-Drift gepuffert.
# ═══════════════════════════════════════════════════════════════════════════

def _runner_src() -> str:
    return RUNNER.read_text(encoding="utf-8")


def _fenster(src: str, marker: str, n: int = 400) -> str:
    """400-Zeichen-Fenster ab dem Marker; fail-closed, wenn der Marker fehlt."""
    assert marker in src, f"Marker fehlt im Runner-Quelltext: {marker!r}"
    i = src.index(marker)
    return src[i:i + n]


def test_f1_auto_refresh_match_candidate_insert_traegt_language():
    """Auto-Refresh-Match: `_c_ar.execute("INSERT INTO agent_tasks...` mit language."""
    fenster = _fenster(_runner_src(), '_c_ar.execute("INSERT INTO agent_tasks')
    assert '"language"' in fenster, \
        "Auto-Refresh match_candidate-Insert ohne language (Sprach-Bypass)"
    assert "_langval" in fenster, \
        "Auto-Refresh match_candidate-Insert ohne Payload-Sprachwert"


def test_f1_gatekeeper_eval_insert_traegt_language():
    """gatekeeper_eval-Marker-Insert traegt `language` / `_lang(`."""
    fenster = _fenster(_runner_src(), "VALUES ('gatekeeper_eval', 'done', ?)")
    assert '"language"' in fenster, \
        "gatekeeper_eval-Insert ohne language (Sprach-Bypass)"
    assert "_lang(" in fenster, \
        "gatekeeper_eval-Insert ohne _lang(payload)-Aufruf"


def test_f1_notify_hr_insert_traegt_language():
    """notify_hr-Insert traegt `language` / `_lang(`."""
    fenster = _fenster(_runner_src(), "VALUES ('notify_hr', ?)")
    assert '"language"' in fenster, \
        "notify_hr-Insert ohne language (Sprach-Bypass)"
    assert "_lang(" in fenster, \
        "notify_hr-Insert ohne _lang(payload)-Aufruf"


# ─── S4a (12.10.2026): `run_llm_task` gibt die Bericht-Sprache mit zurueck ───

@pytest.mark.parametrize("lang", LANGS)
def test_s4a_run_llm_task_result_traegt_language(monkeypatch, tmp_path, lang):
    """`run_llm_task`-Rueckgabe traegt `language` (`_langval`), damit der Aufrufer
    sie ueber `finish_task` in `result_json` persistieren kann (keine Schema-Aenderung)."""
    gefangen = _capture_prompt_and_result(
        monkeypatch, tmp_path, "extract_profile",
        {"candidate_id": None, "language": lang})
    result = gefangen["result"]
    assert isinstance(result, dict), f"S4a: kein result-Dict: {result!r}"
    assert result.get("language") == lang, \
        f"S4a: result ohne/mit falscher language: {result.get('language')!r}"


# ─── F2: _body_sprache_ok() — Heuristik, Default True bei Unsicherheit ───────

def test_f2_body_sprache_ok_de():
    """Umlaute/Stopwoerter -> True; klar englischer Body -> False."""
    ok = _load_runner()._body_sprache_ok
    de = ("Dieses Profil enthält eine ausführliche Übersicht über die Erfahrung "
          "und die Qualifikation. Die Kenntnisse wurden geprüft und bestätigt.")
    en = ("This profile contains a detailed overview of the experience and "
          "qualifications. The skills were reviewed and verified by the team.")
    assert ok(de, "de") is True
    assert ok(en, "de") is False


def test_f2_body_sprache_ok_ar():
    """Arabische Zeichen -> True; reiner Latin-Body (lang genug) -> False."""
    ok = _load_runner()._body_sprache_ok
    ar = ("مرحبا بكم في هذه الشركة، نتمنى لكم يوما سعيدا وموفقا في العمل معنا. "
          "نتطلع إلى رؤية إنجازاتكم قريبا في الفريق.")
    la = "This is a plain Latin body without any Arabic characters at all."
    assert ok(ar, "ar") is True
    assert ok(la, "ar") is False


def test_f2_body_sprache_ok_fr():
    """Akzente/Stopwoerter -> True; klar deutscher Body -> False."""
    ok = _load_runner()._body_sprache_ok
    fr = ("Nous vous remercions pour votre candidature et nous vous contacterons "
          "dans les plus brefs délais concernant votre dossier.")
    de = ("Wir danken Ihnen für Ihre Bewerbung und melden uns in Kürze mit "
          "einem Ergebnis bei Ihnen zurück.")
    assert ok(fr, "fr") is True
    assert ok(de, "fr") is False


def test_f2_body_sprache_ok_en():
    """Englischer Body -> True fuer 'en'."""
    ok = _load_runner()._body_sprache_ok
    en = ("Thank you for your application. We will review the documents and "
          "contact you with the results in that process.")
    assert ok(en, "en") is True


@pytest.mark.parametrize("lang", LANGS + ("xx",))
def test_f2_body_sprache_ok_kurz_default_true(lang):
    """Sehr kurzer/mehrdeutiger Text (<40 Zeichen) -> True (Unsicherheit)."""
    ok = _load_runner()._body_sprache_ok
    assert ok("Kurz und knapp", lang) is True
    assert ok("", lang) is True
    assert ok(None, lang) is True
