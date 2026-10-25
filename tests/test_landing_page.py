"""
Tests fuer die Landingpage (webui/pages/landing.py) – ohne Server/Browser.

Prueft die lab-relevanten Zusagen der Nutzerentscheidungen 02.10.2026:
* Three.js liegt LOKAL im Projekt (kein CDN, offline-faehig).
* Der Import-Map-Pfad zeigt auf die lokale Datei.
* Jede Kapitel-Zahl der Animation traegt eine Quellenangabe (Codemarke +
  Messdatum) oder ist als Design-Entscheidung markiert.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LANDING = BASE / "webui" / "pages" / "landing.py"
THREE_DIR = BASE / "webui" / "static" / "three"


def test_threejs_liegt_lokal():
    """Nutzerentscheidung 02.10.2026: Three.js lokal, KEIN externes CDN."""
    assert (THREE_DIR / "three.module.js").is_file()
    assert (THREE_DIR / "three.core.js").is_file()
    assert (THREE_DIR / "LICENSE").is_file()  # MIT


def test_threejs_per_url_import_keine_eigene_importmap():
    """02.10.2026: Three.js per Relative Import Reference (URL) laden — KEINE eigene
    Import-Map. Grund: NiceGUI setzt bereits eine Import-Map (vue/sass/...); laut
    HTML-Spec ist nur EINE erlaubt, eine zweite (three) wird ignoriert
    (bare-specifier-Fehler). Quellen: spidermonkey.dev "Import maps, Part 2"
    (only one map allowed), sbcode.net "Module Specifiers Versus Relative Import
    References" (URL-Import braucht keine Map)."""
    src = LANDING.read_text(encoding="utf-8")
    # Relative Import Reference (URL) statt bare specifier
    assert "import * as THREE from '/static/three/three.module.js'" in src
    # Keine eigene Import-Map mehr im Head-HTML (sonst Konflikt mit NiceGUI)
    head = src.split("_HEAD_HTML", 1)[1]
    assert 'type="importmap"' not in head
    # Kein bare specifier mehr
    assert "from 'three'" not in src
    # Kein CDN (offline-Pflicht)
    for cdn in ("cdn.jsdelivr", "unpkg.com", "cdnjs", "esm.sh", "googleapis"):
        assert cdn not in head


def test_quellen_nicht_im_besucher_ui():
    """02.10.2026 (Nutzerbefehl): Der technische Quellen-Block wurde aus der Landingpage
    entfernt — er wirkte im Besucher-UI unprofessionell (Dateipfade, Code-Namen).
    Lab-Nachweis liegt in ergebnisse/entscheidungen.md; die Zahlen selbst prüft
    test_zahlen_gegen_quellcode_gezaehlt gegen den Code."""
    import importlib.util
    src = LANDING.read_text(encoding="utf-8")
    assert "_SOURCES_HTML" not in src                     # Block entfernt
    assert 'ui.expansion(_("So funktioniert\'s")' in src
    spec = importlib.util.spec_from_file_location("landing_mod3", LANDING)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Die 7 sichtbaren Schritte enthalten KEINE internen Pfade/Code-Namen
    for z in mod._STEP_LINES:
        for bad in ("knowledge/", "webui/", ".py", "KATEGORIE", "_upload", "ALLOWED"):
            assert bad not in z, f"interner Token im sichtbaren Schritt: {z}"


def test_vdo_ninja_statt_jitsi():
    """Zoom 5 zeigt VDO.Ninja (Nutzerentscheidung, Migration 27.09.2026)."""
    src = LANDING.read_text(encoding="utf-8")
    assert "VDO.Ninja" in src
    assert "jit.si" not in src


# ─── Ergänzungen aus der Prüfung 02.10.2026 (Schritt 4 des Auftrags) ───

def _js_ch_windows(src):
    import re
    return [(float(a), float(b)) for a, b in
            re.findall(r"t0:\s*([\d.]+),\s*t1:\s*([\d.]+)", src)]


def test_dauer_exakt_30_sekunden():
    """Pkt. 1: TOTAL = 30.0; 5 Fenster liegen in 0–30 s, sortiert, ohne Überlappung."""
    import re
    src = LANDING.read_text(encoding="utf-8")
    assert re.search(r"const TOTAL = 30\.0;", src)
    assert "TOTAL = 32" not in src
    w = _js_ch_windows(src)
    assert len(w) == 5
    assert w[0][0] == 0.0 and w[-1][1] == 30.0
    for (a0, a1), (b0, b1) in zip(w, w[1:]):
        assert a0 < a1 <= b0 < b1
    # kein Widerspruch zur Dauer im Text/Quellen-Block
    assert "32 s" not in src and "≈ 32" not in src and "≈32" not in src


def test_ueberschrift_konsistent():
    """Pkt. 5: Die Animation erklärt das Agenten-Prinzip in 30 Sekunden."""
    src = LANDING.read_text(encoding="utf-8")
    assert 'ui.label(_("Das Agenten-Prinzip – in 30 Sekunden"))' in src
    assert "30 Sekunden erklärt" not in src


def test_loop_replay_und_countdown():
    """Pkt. 2+3: Loop, Replay-Button, sichtbarer Countdown 30 → 0 + Fortschrittsbalken."""
    src = LANDING.read_text(encoding="utf-8")
    assert "Nochmal ansehen" in src
    assert "S.loops" in src and "S.startTime += n * TOTAL * 1000" in src  # automatischer Neustart
    assert 'id="kmhr-count-n"' in src
    assert "Math.round(TOTAL - t)" in src
    assert 'id="kmhr-progress-fill"' in src


def test_minimalismus_details_aufklappbar():
    """Pkt. 4: 7 Schritte im ui.expansion; kein Quellen-Text im Caption-Overlay.
    02.10.2026: Expansion heißt jetzt „So funktioniert's" (Quellen-Block entfernt)."""
    src = LANDING.read_text(encoding="utf-8")
    assert 'ui.expansion(_("So funktioniert\'s")' in src
    assert "kmhr-cap-src" not in src                      # keine Quelle in der Animation
    assert "_STEP_LINES" in src
    import importlib.util
    spec = importlib.util.spec_from_file_location("landing_mod", LANDING)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert len(mod._STEP_LINES) == 5
    assert all(len(z) <= 100 for z in mod._STEP_LINES)    # eine kurze Zeile je Schritt


def test_kapitelstruktur_synchron():
    """5 Kapitel: JS-CH, Python-_CHAPTERS, _STEP_LINES und builders bleiben synchron.
    Schützt vor der stillen Desynchronisierung (deutsche Restkapitel/leere Kamera)."""
    import importlib.util
    import re
    src = LANDING.read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location("landing_mod_sync", LANDING)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert len(mod._CHAPTERS) == 5
    assert len(mod._STEP_LINES) == 5
    ch_ids = re.findall(r"\{ id: '(\w+)', zi: (\d+), t0:", src)
    assert len(ch_ids) == 5
    assert [int(zi) for _, zi in ch_ids] == list(range(5))
    builders = re.search(r"const builders = \[(.*?)\];", src, re.S).group(1)
    assert len([b for b in builders.split(",") if b.strip()]) == 5
    # Jedes injizierte 3D-Label wird im JS auch als L.<key> gelesen.
    for key in mod._LABELS:
        assert f"L.{key}" in src or f"__KMHR_LABELS__ || {{}}).{key}" in src


def test_zahlen_gegen_quellcode_gezaehlt():
    """10 Tasks (webui/db.py) und 7 Kategorien (KATEGORIE_MAX) stimmen mit dem Code überein."""
    import re
    from webui import logic
    assert len(logic.KATEGORIE_MAX) == 7
    src = LANDING.read_text(encoding="utf-8")
    jsk = re.search(r"const KATEGORIEN = \[(.*?)\];", src, re.S).group(1)
    assert re.findall(r"\['(\w+)', (\d+)\]", jsk) == [(k, str(v)) for k, v in logic.KATEGORIE_MAX.items()]
    tasks = re.search(r"const TASKS = \[(.*?)\];", src, re.S).group(1)
    names = re.findall(r"'(\w+)'", tasks)
    assert len(names) == 10
    doc = (BASE / "webui" / "db.py").read_text(encoding="utf-8")
    seg = doc.split("def apply_to_job", 1)[1].split('"""', 2)[1]
    for n in names:
        assert n in seg


def test_vorteile_zahlen_gegen_code():
    """02.10.2026: Jede Zahl in „Warum KM-HR-Agent?" (_VORTEILE) ist im Projekt
    belegt — kein erfundener Wert (Lab-Prinzip)."""
    import importlib.util
    from webui import logic
    spec = importlib.util.spec_from_file_location("landing_mod_v", LANDING)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert len(mod._VORTEILE) == 6
    titel = [t for _, t, _ in mod._VORTEILE]
    assert any("10 Agent" in t for t in titel)
    assert any("7 Matching" in t for t in titel)
    # 7 Kategorien gegen den Code
    assert len(logic.KATEGORIE_MAX) == 7
    # 10 Tasks gegen den Code (db.py-Docstring der Bewerbungs-Kette)
    doc = (BASE / "webui" / "db.py").read_text(encoding="utf-8")
    seg = doc.split("def apply_to_job", 1)[1].split('"""', 2)[1]
    tasks = ("send_confirmation", "extract_profile", "match_candidate", "check_compliance",
             "assess_culture_fit", "verify_documents", "check_visa", "explain_match",
             "check_gdpr", "notify_user")
    assert sum(1 for n in tasks if n in seg) == 10
    # 183 Tage (DSGVO) gegen den Code
    assert "183" in (BASE / "webui" / "logic.py").read_text(encoding="utf-8")
