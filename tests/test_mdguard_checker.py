"""Nachweis: der Wächter `mdguard` erkennt echte Verstöße (Positiv-/Negativproben).

21.10.2026, E5(k): der Wächter wird **über den echten Checker** geprüft
(`importlib`-Laden von `scripts/ci/checks.py`, Konstanten nur im Speicher umgebogen)
— nicht über eine Nachbildung. Der Repo wird dabei **nicht** verändert.
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _checker():
    """Echter Checker (frisch geladen, damit keine globalen Fehler zurueckbleiben).

    V-08 (21.10.2026): Die Quellen-Suche wird hier **abgeschaltet**
    (`MDGUARD_AUTO_GLOBE = ()`) — die Proben pruefen jeweils genau einen
    Abschnitt (Artefakt-Regeln oder Schreiber-Statik). Ohne diese Trennung
    scannt jeder Test den ganzen Repo-Baum (~15 s pro Test).
    """
    spec = importlib.util.spec_from_file_location("checks_md", ROOT / "scripts" / "ci" / "checks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.FEHLER.clear()
    mod.WARNUNG.clear()
    mod.MDGUARD_AUTO_GLOBE = ()
    mod.MDGUARD_WRITER_DATEIEN = ()
    return mod


def _probe(snippet: str, *, schreiber: str = "probe.py") -> list[str]:
    """Snippet als Schreiber-Datei prüfen; liefert die Fehlermeldungen.

    V-08 (21.10.2026): Die Probe läuft **isoliert** in einem temporären
    Verzeichnis — die Artefakt-Verzeichnisse (`MDGUARD_ERGEBNISSE`,
    `MDGUARD_FIXTURES`) werden auf **leere** Verzeichnisse gesetzt, damit die
    getrackten Fixtures (inkl. der absichtlich verstoßenden) das Probenergebnis
    nicht verfälschen.
    """
    mod = _checker()
    with tempfile.TemporaryDirectory(prefix="kmhr-mdguard-") as tmpdir:
        tmp = Path(tmpdir)
        ziel = tmp / schreiber
        ziel.write_text(snippet, encoding="utf-8")
        mod.MDGUARD_WRITER_DATEIEN = (ziel,)
        mod.MDGUARD_AUTO_GLOBE = (tmp,)
        mod.MDGUARD_AUTO_AUSSCHLUSS = ()
        mod.MDGUARD_ERGEBNISSE = tmp / "leer-ergebnisse"
        mod.MDGUARD_FIXTURES = tmp / "leer-fixtures"
        mod.MDGUARD_ERGEBNISSE.mkdir(parents=True, exist_ok=True)
        mod.MDGUARD_FIXTURES.mkdir(parents=True, exist_ok=True)
        mod.check_mdguard()
        return list(mod.FEHLER)


# ── R4.1: Ziel „neueste existierende" ────────────────────────────────────
def test_r4_1_erkennt_end_index_als_ziel():
    fehler = _probe('''
ERGEBNISSE = Path("ergebnisse")

def schreibe():
    dateien = sorted(ERGEBNISSE.glob("x-*.md"))
    ziel = dateien[-1]
    ziel.write_text("x")
''')
    assert any("R4.1" in f for f in fehler), fehler


def test_r4_1_erste_auswahl_ist_erlaubt():
    fehler = _probe('''
ERGEBNISSE = Path("ergebnisse")

def schreibe():
    dateien = sorted(ERGEBNISSE.glob("x-*.md"))
    ziel = dateien[0]
    ziel.write_text("x")
''')
    assert not any("R4.1" in f for f in fehler), fehler


# ── R4.2: Schreibziel im normativen Bereich ──────────────────────────────
def test_r4_2_erkennt_schreiben_in_knowledge():
    fehler = _probe('''
def schreibe():
    ziel = Path("knowledge/error-statistics.md")
    ziel.write_text("x")
''')
    assert any("R4.2" in f for f in fehler), fehler


def test_r4_2_kein_falsch_positiv_bei_inhalt():
    """Der Pfad zählt, nicht der Inhalt (alte Prüfung meldete Inhalte)."""
    fehler = _probe('''
def schreibe():
    ziel = Path("ergebnisse/x.md")
    ziel.write_text("knowledge ist wichtig")
''')
    assert not any("R4.2" in f for f in fehler), fehler


# ── R4.3: Carry-over — Aufruf ja, Definition nein ────────────────────────
def test_r4_3_erkennt_carry_over_aufruf():
    fehler = _probe('''
def find_video_section(p):
    return p.read_text()

def schreibe():
    teil = find_video_section(Path("ergebnisse/x.md"))
    Path("ergebnisse/y.md").write_text(teil)
''')
    assert any("R4.3" in f for f in fehler), fehler


def test_r4_3_definition_ist_kein_verstoss():
    fehler = _probe('''
def find_video_section(p):
    return p.read_text()
''')
    assert not any("R4.3" in f for f in fehler), fehler


# ── R4.4: Truncation am Schreibziel ──────────────────────────────────────
def test_r4_4_erkennt_abschneiden():
    fehler = _probe('''
def schreibe():
    text = Path("ergebnisse/x.md").read_text()
    Path("ergebnisse/y.md").write_text(text[:500])
''')
    assert any("R4.4" in f for f in fehler), fehler


def test_r4_4_kein_falsch_positiv_bei_anzeige_slice():
    fehler = _probe('''
def schreibe():
    Path("ergebnisse/y.md").write_text("ok")
    teil = "ein langer Text"[:200]
''')
    assert not any("R4.4" in f for f in fehler), fehler


# ── R4.5: Zielverzeichnis anlegen ────────────────────────────────────────
def test_r4_5_erkennt_fehlendes_mkdir():
    fehler = _probe('''
ERGEBNISSE = Path("ergebnisse")

def schreibe():
    ziel = ERGEBNISSE / "x.md"
    ziel.write_text("x")
''')
    assert any("R4.5" in f for f in fehler), fehler


def test_r4_5_mkdir_ist_erlaubt():
    fehler = _probe('''
ERGEBNISSE = Path("ergebnisse")

def schreibe():
    ERGEBNISSE.mkdir(parents=True, exist_ok=True)
    ziel = ERGEBNISSE / "x.md"
    ziel.write_text("x")
''')
    assert not any("R4.5" in f for f in fehler), fehler


# ── R-S1: blindes Anhängen vs. Anker-Replace ─────────────────────────────
def test_rs1_erkennt_read_modify_write_ohne_anker():
    fehler = _probe('''
def schreibe():
    ziel = Path("ergebnisse/x.md")
    text = ziel.read_text()
    text = text + "\\nneue Zeile\\n"
    ziel.write_text(text)
''')
    assert any("R-S1" in f for f in fehler), fehler


def test_rs1_anker_replace_ist_erlaubt():
    fehler = _probe('''
def schreibe():
    ziel = Path("ergebnisse/x.md")
    text = ziel.read_text()
    text = replace_video_section(text, "neu")
    ziel.write_text(text)
''')
    assert not any("R-S1" in f for f in fehler), fehler


# ── R-S6: Schreiber liefert die Resultatdatei zurück ──────────────────────
def test_rs6_erkennt_fehlende_rueckgabe():
    fehler = _probe('''
def write_artifact(text):
    ziel = Path("ergebnisse/x.md")
    ziel.write_text(text)
''')
    assert any("R-S6" in f for f in fehler), fehler


def test_rs6_rueckgabe_ist_erlaubt():
    fehler = _probe('''
def write_artifact(text):
    ziel = Path("ergebnisse/x.md")
    ziel.write_text(text)
    return ziel
''')
    assert not any("R-S6" in f for f in fehler), fehler


# ── R5.1: Leser wählt „neuesten" ─────────────────────────────────────────
def test_r5_1_erkennt_aeltesten_leser():
    fehler = _probe('''
ERGEBNISSE = Path("ergebnisse")

def _score_from_ergebnisse(cand):
    for p in sorted(ERGEBNISSE.glob(f"x-{cand}-*.md")):
        return p.read_text()
    return ""
''')
    assert any("R5.1" in f for f in fehler), fehler


def test_r5_1_neuester_leser_ist_erlaubt():
    fehler = _probe('''
ERGEBNISSE = Path("ergebnisse")

def _score_from_ergebnisse(cand):
    for p in sorted(ERGEBNISSE.glob(f"x-{cand}-*.md"))[::-1]:
        return p.read_text()
    return ""
''')
    assert not any("R5.1" in f for f in fehler), fehler


# ── Artefakt-Regeln (R1.1/R2.1) auf getrackten Fixtures ─────────────────
def _stichtag(mod) -> str:
    """V-09 (21.10.2026): der Stichtag kommt aus dem Checker — die Tests sind
    damit **nicht** auf ein festes Datum verdrahtet."""
    return mod.MDGUARD_STICHTAG


def test_r1_1_doppelte_ueberschrift_wird_erkannt(tmp_path):
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = tmp_path
    mod.MDGUARD_FIXTURES = tmp_path / "leer"
    (tmp_path / f"x-{_stichtag(mod)}.md").write_text(
        "# T\n\n## Abschnitt\n\n## Abschnitt\n", encoding="utf-8")
    mod.check_mdguard()
    assert any("R1.1" in f for f in mod.FEHLER), list(mod.FEHLER)


def test_r2_1_push_id_mit_bindestrich_wird_erkannt(tmp_path):
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = tmp_path
    mod.MDGUARD_FIXTURES = tmp_path / "leer"
    (tmp_path / f"y-{_stichtag(mod)}.md").write_text(
        "https://vdo.ninja/?push=mit-bindestrich\n", encoding="utf-8")
    mod.check_mdguard()
    assert any("R2.1" in f for f in mod.FEHLER), list(mod.FEHLER)


def test_altbestand_bleibt_gruen(tmp_path):
    """Alt-Bestand (Datum < Stichtag) wird nicht rot."""
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = tmp_path
    (tmp_path / "z-2026-01-01.md").write_text(
        "# T\n\n## Abschnitt\n\n## Abschnitt\n", encoding="utf-8")
    mod.check_mdguard()
    assert not any("R1.1" in f for f in mod.FEHLER), list(mod.FEHLER)


# ── V-08 (21.10.2026): die bisher unprobenen Regeln R1.2, R2.2, R2.3,
# R3.1, R3.2 und R4.6 — je eine Positiv- und eine Negativprobe.
def test_r1_2_konflikt_id_kandidat_und_tag_wird_erkannt(tmp_path):
    """Zwei Dateien mit derselben Konflikt-ID (Kandidat + Tag) ⇒ rot."""
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = tmp_path
    mod.MDGUARD_FIXTURES = tmp_path / "leer"
    tag = _stichtag(mod)
    (tmp_path / f"self-presentation-kandidat-7-{tag}.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / f"self-presentation-kandidat-7-{tag}-kopie.md").write_text("# B\n", encoding="utf-8")
    mod.check_mdguard()
    assert any("R1.2" in f for f in mod.FEHLER), list(mod.FEHLER)


def test_r1_2_eindeutige_id_bleibt_gruen(tmp_path):
    """Verschiedene Kandidaten am selben Tag ⇒ grün."""
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = tmp_path
    mod.MDGUARD_FIXTURES = tmp_path / "leer"
    tag = _stichtag(mod)
    (tmp_path / f"self-presentation-kandidat-7-{tag}.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / f"self-presentation-kandidat-8-{tag}.md").write_text("# B\n", encoding="utf-8")
    mod.check_mdguard()
    assert not any("R1.2" in f for f in mod.FEHLER), list(mod.FEHLER)


def test_r2_2_director_link_in_selbstpraesentation_wird_erkannt(tmp_path):
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = tmp_path
    mod.MDGUARD_FIXTURES = tmp_path / "leer"
    (tmp_path / f"self-presentation-kandidat-9-{_stichtag(mod)}.md").write_text(
        "https://vdo.ninja/?director=abc\n", encoding="utf-8")
    mod.check_mdguard()
    assert any("R2.2" in f for f in mod.FEHLER), list(mod.FEHLER)


def test_r2_2_push_link_ist_erlaubt(tmp_path):
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = tmp_path
    mod.MDGUARD_FIXTURES = tmp_path / "leer"
    (tmp_path / f"self-presentation-kandidat-9-{_stichtag(mod)}.md").write_text(
        "https://vdo.ninja/?push=abc123\n", encoding="utf-8")
    mod.check_mdguard()
    assert not any("R2.2" in f for f in mod.FEHLER), list(mod.FEHLER)


def test_r2_3_alter_anbieter_wird_erkannt(tmp_path):
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = tmp_path
    mod.MDGUARD_FIXTURES = tmp_path / "leer"
    (tmp_path / f"z-{_stichtag(mod)}.md").write_text(
        "https://meet.jit.si/abc\n", encoding="utf-8")
    mod.check_mdguard()
    assert any("R2.3" in f for f in mod.FEHLER), list(mod.FEHLER)


def test_r2_3_neuer_anbieter_ist_erlaubt(tmp_path):
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = tmp_path
    mod.MDGUARD_FIXTURES = tmp_path / "leer"
    (tmp_path / f"z-{_stichtag(mod)}.md").write_text(
        "https://vdo.ninja/?room=abc\n", encoding="utf-8")
    mod.check_mdguard()
    assert not any("R2.3" in f for f in mod.FEHLER), list(mod.FEHLER)


def _checker_mit_eigenem_root(tmp_path: Path):
    """Checker mit umgebogenem ROOT (Spec-Prüfungen R3.1/R3.2 lesen ROOT)."""
    mod = _checker()
    mod.ROOT = tmp_path
    (tmp_path / "knowledge" / "system").mkdir(parents=True, exist_ok=True)
    (tmp_path / "webui").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    mod.MDGUARD_ERGEBNISSE = tmp_path / "leer-ergebnisse"
    mod.MDGUARD_FIXTURES = tmp_path / "leer-fixtures"
    mod.MDGUARD_ERGEBNISSE.mkdir(parents=True, exist_ok=True)
    mod.MDGUARD_FIXTURES.mkdir(parents=True, exist_ok=True)
    return mod


def test_r3_1_unbekannte_codemarke_gibt_warnung(tmp_path):
    """R3.1: eine in der Spec zitierte Codemarke, die im Code fehlt ⇒ Warnung."""
    mod = _checker_mit_eigenem_root(tmp_path)
    spec = tmp_path / "knowledge" / "system" / "md-schreib-konvention.md"
    spec.write_text("Marker `quatsch_marke_xyz_42`\n", encoding="utf-8")
    mod.check_mdguard()
    assert any("R3.1" in w for w in mod.WARNUNG), list(mod.WARNUNG)


def test_r3_1_existierende_codemarke_bleibt_ohne_warnung(tmp_path):
    """R3.1-Negativprobe: die Codemarke existiert im Code ⇒ keine Warnung."""
    mod = _checker_mit_eigenem_root(tmp_path)
    spec = tmp_path / "knowledge" / "system" / "md-schreib-konvention.md"
    spec.write_text("Marker `quatsch_marke_xyz_42`\n", encoding="utf-8")
    (tmp_path / "webui" / "modul.py").write_text(
        "def quatsch_marke_xyz_42():\n    return 1\n", encoding="utf-8")
    mod.check_mdguard()
    assert not any("R3.1" in w for w in mod.WARNUNG), list(mod.WARNUNG)


def test_r3_2_abweichender_zaehlwert_wird_erkannt(tmp_path):
    """R3.2: die Knowledge-MD-Zahl in der Spec weicht vom Live-Wert ab ⇒ Fehler."""
    mod = _checker_mit_eigenem_root(tmp_path)
    spec = tmp_path / "knowledge" / "system" / "md-schreib-konvention.md"
    spec.write_text("Knowledge-MD = **9999**\n", encoding="utf-8")
    mod.check_mdguard()
    assert any("R3.2" in f for f in mod.FEHLER), list(mod.FEHLER)


def test_r3_2_richtiger_zaehlwert_bleibt_gruen(tmp_path):
    """R3.2-Negativprobe: die Zahl stimmt ⇒ kein Fehler."""
    mod = _checker_mit_eigenem_root(tmp_path)
    spec = tmp_path / "knowledge" / "system" / "md-schreib-konvention.md"
    spec.write_text("Knowledge-MD = **1**\n", encoding="utf-8")
    mod.check_mdguard()
    assert not any("R3.2" in f for f in mod.FEHLER), list(mod.FEHLER)


def test_r4_6_erfolgsversprechen_wird_erkannt():
    """R4.6: verschluckter Schreibfehler + konstante Erfolgs-Rückgabe ⇒ rot."""
    fehler = _probe('''
def schreibe(text):
    try:
        Path("ergebnisse/x.md").write_text(text)
    except Exception:
        pass
    return {"logged": True}
''')
    assert any("R4.6" in f for f in fehler), fehler


def test_r4_6_korrekte_statusrueckgabe_ist_erlaubt():
    """R4.6-Negativprobe: der Status folgt dem tatsächlichen Schreibvorgang."""
    fehler = _probe('''
def schreibe(text):
    ok = False
    try:
        Path("ergebnisse/x.md").write_text(text)
        ok = True
    except Exception as e:
        print(e)
    return {"logged": ok}
''')
    assert not any("R4.6" in f for f in fehler), fehler


def test_r4_6_loggender_fehler_mit_konstanter_erfolgsrueckgabe_wird_erkannt():
    """R4.6: breiter except + konstante Erfolgs-Rückgabe ⇒ auch mit Log rot."""
    fehler = _probe('''
def schreibe(text):
    try:
        Path("ergebnisse/x.md").write_text(text)
    except Exception as e:
        print(f"Fehler: {e}")
    return {"logged": True}
''')
    assert any("R4.6" in f for f in fehler), fehler


def test_r4_6_spezifischer_except_ohne_erfolgsversprechen_bleibt_gruen():
    """R4.6-Negativprobe: ein **spezifischer** Fehler (kein `except Exception`)."""
    fehler = _probe('''
def schreibe(text):
    try:
        Path("ergebnisse/x.md").write_text(text)
    except FileNotFoundError as e:
        print(f"Fehler: {e}")
    return {"logged": True}
''')
    assert not any("R4.6" in f for f in fehler), fehler


def test_getrackte_fixtures_erfuellen_ihre_erwartung():
    """V-10: `gueltig-*` muss grün, `verstoss-*` muss rot sein (CI-Nachweis)."""
    mod = _checker()
    mod.MDGUARD_ERGEBNISSE = ROOT / "ergebnisse"
    mod.MDGUARD_FIXTURES = ROOT / "tests" / "fixtures" / "md-guard"
    mod.check_mdguard()
    assert not any("Fixture-Erwartung" in f for f in mod.FEHLER), list(mod.FEHLER)
