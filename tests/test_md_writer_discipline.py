"""Schreiber-Disziplin für Markdown (md-Disziplin, 21.10.2026).

Deckt die Regeln R4 (Schreiber-Statik über Quelltext), R1.1 (Struktur) und
R2 (Linkform) aus `knowledge/system/md-schreib-konvention.md` ab.

Muster: `tests/test_status_guards_md.py` — reiner Quelltext-/MD-Parse, **keine DB,
kein UI-Start**, keine Schreibzugriffe auf `data/feedback.db` oder `ergebnisse/`.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = (ROOT / "webui" / "pages" / "candidate.py").read_text(encoding="utf-8")
COMP = (ROOT / "webui" / "components.py").read_text(encoding="utf-8")
LOGIC = (ROOT / "webui" / "logic.py").read_text(encoding="utf-8")
RUNNER = (ROOT / "scripts" / "agent-runner.py").read_text(encoding="utf-8")
SPEC = (ROOT / "knowledge" / "system" / "md-schreib-konvention.md").read_text(encoding="utf-8")
ALL_WRITERS = {"candidate.py": CAND, "components.py": COMP,
                "logic.py": LOGIC, "agent-runner.py": RUNNER}


def _fn_seg(src: str, name: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"Funktion {name} nicht gefunden")


# ── R4.1: kein Schreiber wählt „neueste existierende" als Ziel ─────────────
def test_r4_1_kein_neueste_existierende_als_ziel():
    for name, src in ALL_WRITERS.items():
        for m in re.finditer(r"dateien\[-1\]|files\[-1\]", src):
            zeile = src[:m.start()].count("\n") + 1
            raise AssertionError(f"R4.1 {name}:{zeile} wählt 'neueste existierende' als Ziel")


# ── R4.2: kein Laufzeit-Schreibzugriff auf knowledge/** oder skills/** ────
def test_r4_2_kein_schreiben_in_knowledge_oder_skills():
    """Prüft SCHREIB-Calls (AST), nicht Kommentare/Docstrings/Leser.

    Erlaubt bleibt das Lesen aus `knowledge/**` (z. B. `_load_contract_sources`).
    """
    schreiber = {"write_text", "write_bytes", "open"}
    for name, src in ALL_WRITERS.items():
        for m in re.finditer(r"write_text\([^)]*(knowledge|skills)", src):
            zeile = src[:m.start()].count("\n") + 1
            raise AssertionError(f"R4.2 {name}:{zeile} schreibt nach knowledge/**/skills/**")
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            fname = getattr(func, "attr", None) or getattr(func, "id", None)
            if fname not in schreiber:
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    if sub.value in ("knowledge", "skills") or sub.value.startswith("knowledge/"):
                        raise AssertionError(
                            f"R4.2 {name}:{getattr(sub, 'lineno', 0)} schreibt nach "
                            f"'{sub.value}' (normativer Bereich)")


# ── R4.3: kein Carry-over (Abschnitt aus einer anderen MD-Datei) ──────────
def test_r4_3_kein_carry_over():
    for name, src in ALL_WRITERS.items():
        for m in re.finditer(r"find_video_section\(", src):
            if "def find_video_section" in src[max(0, m.start() - 80):m.start()]:
                continue
            zeile = src[:m.start()].count("\n") + 1
            raise AssertionError(f"R4.3 {name}:{zeile} übernimmt einen Abschnitt aus einer anderen Datei")


# ── R4.4: keine Truncation eines bestehenden Abschnitts ─────────────────
def test_r4_4_keine_truncation():
    for name, src in ALL_WRITERS.items():
        for m in re.finditer(r"\.split\(VIDEO_HEADING\)\[0\]", src):
            zeile = src[:m.start()].count("\n") + 1
            raise AssertionError(f"R4.4 {name}:{zeile} schneidet Inhalt ab (split(VIDEO_HEADING)[0])")


# ── R4.5: Zielverzeichnis wird vor dem Schreiben angelegt ────────────────
def test_r4_5_ergebnisverzeichnis_wird_angelegt():
    assert "_ergebnis_pfad(" in RUNNER
    assert "ERGEBNISSE.mkdir(parents=True, exist_ok=True)" in RUNNER
    # Jede Schreibstelle nutzt den Helfer (nicht direkt ERGEBNISSE / ...).
    for m in re.finditer(r"ERGEBNISSE\s*/\s*f?\"", RUNNER):
        zeile = RUNNER[:m.start()].count("\n") + 1
        raise AssertionError(f"R4.5 agent-runner.py:{zeile} schreibt direkt nach ERGEBNISSE ohne mkdir")


# ── R5.1: Leser wählen den neuesten Report (sorted + [::-1]) ─────────────
def test_r5_1_leser_waehlen_den_neuesten_report():
    """R5.1: die Report-Leser wählen den **neuesten** Report
    (`sorted(...)[::-1]`); `export_report` (Kultur-Fit) ebenso explizit."""
    for marker in ("_compliance_from_ergebnisse",
                   "_visum_auswertung_from_ergebnisse"):
        seg = _fn_seg(RUNNER, marker)
        schleife = re.search(r"for p in sorted\((.*?)\)\s*(\[[^\]]*\])?:", seg, flags=re.S)
        assert schleife, f"{marker}: keine sorted()-Schleife gefunden"
        assert "[::-1]" in schleife.group(0) or "reversed(" in schleife.group(0), (
            f"{marker}: wählt nicht den neuesten Report (Spec R5.1)")
    # _score_from_ergebnisse (21.10.2026, job-genau): neueste-zuerst sortieren
    # und auf die passende Stelle eingrenzen.
    seg = _fn_seg(RUNNER, "_score_from_ergebnisse")
    assert re.search(r"sorted\([^)]*glob\([^)]*\)\)\[::-1\]", seg, flags=re.S), (
        "_score_from_ergebnisse: wählt nicht den neuesten Report (Spec R5.1)")
    assert "_report_stelle" in seg, (
        "_score_from_ergebnisse: grenzt den Report nicht auf die Stelle ein (job-Parameter)")
    # Kultur-Fit-Leser in export_report: explizit „neuester" (21.10.2026).
    seg = _fn_seg(RUNNER, "export_report")
    assert "assess_culture_fit" in seg
    assert re.search(r"for p in sorted\(.*?\)\[::-1\]:", seg, flags=re.S), (
        "export_report: Kultur-Fit-Leser wählt nicht explizit den neuesten Report (R5.1)")


# ── R1.1: keine doppelten H2-Überschriften in einem Artefakt ────────────
def test_r1_1_keine_doppelten_h2_ueberschriften():
    for datei in ("2026-10-21",):
        for p in (ROOT / "ergebnisse").glob(f"self-presentation-kandidat-*-{datei}.md"):
            h2 = re.findall(r"^## (.+)$", p.read_text(encoding="utf-8"), flags=re.M)
            doppelt = {h for h in h2 if h2.count(h) > 1}
            assert not doppelt, f"R1.1 {p.name}: doppelte Überschriften {sorted(doppelt)}"


# ── R2: Linkformen in neuen Artefakten ───────────────────────────────────
def test_r2_linkformen_der_neuen_artefakte():
    for p in (ROOT / "ergebnisse").glob("self-presentation-kandidat-*-2026-10-21.md"):
        text = p.read_text(encoding="utf-8")
        assert "?director=" not in text, f"R2.2 {p.name}: ?director= in der Selbstpräsentation"
        for m in re.finditer(r"\?push=([A-Za-z0-9_-]+)", text):
            assert "-" not in m.group(1), f"R2.1 {p.name}: ?push=-ID mit Bindestrich: {m.group(1)}"


# ── R1.2: Konflikt-ID Kandidat+Tag genau eine Datei ──────────────────────
def test_r1_2_kandidat_und_tag_eindeutig():
    gruppen: dict[tuple[str, str], list[str]] = {}
    for p in (ROOT / "ergebnisse").glob("self-presentation-kandidat-*-*.md"):
        m = re.match(r"self-presentation-kandidat-(\d+)-(\d{4}-\d{2}-\d{2})", p.name)
        if m:
            gruppen.setdefault((m.group(1), m.group(2)), []).append(p.name)
    for (cid, tag), namen in gruppen.items():
        assert len(namen) == 1, f"R1.2 Kandidat {cid} + {tag}: {len(namen)} Dateien {sorted(namen)}"


# ── Spec: die Regeln sind dokumentiert (Doku-first) ─────────────────────
def test_spec_enthaelt_die_regeln():
    for regel in ("R-S1", "R-S2", "R-S3", "R-S4", "R-S5", "R-S6",
                  "R1.1", "R2.1", "R3.1", "R4.1", "R5.1"):
        assert regel in SPEC, f"Spec nennt {regel} nicht"
    assert "mdguard" in SPEC
