"""N-S2 (01.10.2026): Stellen-Guard == Match-Guard — MD ↔ employer ↔ admin.

Befund: ergebnisse/ui-analyse-2026-09-29.md:64 („Guard inkonsistent zu Match“).
Vorher DREI Kopien der Whitelist (employer `_page_stellen` erl-Dict, employer
ALLOWED_TRANSITIONS, admin erl-Dict) — inhaltlich gleich, aber ohne Mechanismus,
der Gleichheit erzwingt, und OHNE DB-Check beim Klick auf beiden Stellen-Seiten.

Nutzer-Entscheid (ask_user, 01.10.2026):
  (1) Variante B: ALLOWED_TRANSITIONS (employer.py, Modulebene) ist die EINZIGE
      Python-Quelle; beide Stellen-Seiten lesen sie via _legal_actions().
  (2) Klick-Guard JA: beide Stellen-Seiten prüfen beim Klick den aktuellen
      DB-Status (Match-Muster `_legal`), kein UPDATE bei Verstoss.
  (3) admin.py angleichen (Import der Konstante + DB-Check).

Lab-Prinzip Schritt 3 (MD ↔ Code): Quelle ist die Tabelle
knowledge/lifecycle/application-status.md „Erlaubte Übergänge“ — dieser Test
parst sie und erzwingt Gleichheit mit dem Code. Reine MD-/Quelltext-Inspektion,
KEINE DB-Zugriffe, KEIN UI-Start.
"""
import ast
from pathlib import Path

from webui.pages import employer as emp

ROOT = Path(__file__).resolve().parents[1]
EMP_SRC = (ROOT / "webui" / "pages" / "employer.py").read_text(encoding="utf-8")
ADM_SRC = (ROOT / "webui" / "pages" / "admin.py").read_text(encoding="utf-8")
MD_PATH = ROOT / "knowledge" / "lifecycle" / "application-status.md"


# ─── MD parsen: Zeilen „✅ + Durch = Arbeitgeber“ ────────────────────────────

def _md_employer_rows() -> dict:
    """{von: {nach, ...}} aus der MD-Tabelle, nur erlaubte HR-Übergänge."""
    text = MD_PATH.read_text(encoding="utf-8")
    assert "## Erlaubte Übergänge" in text, "MD-Abschnitt „Erlaubte Übergänge“ fehlt"
    sec = text.split("## Erlaubte Übergänge", 1)[1]
    if "\n## " in sec:
        sec = sec.split("\n## ", 1)[0]
    out: dict = {}
    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 4:
            continue
        von, nach, erlaubt, durch = cells
        if "✅" not in erlaubt or durch != "Arbeitgeber":
            continue  # Kandidaten-Zeilen (zurückgezogen), Endstatus ❌, Header, ──
        out.setdefault(von.replace("`", "").strip(), set()).add(
            nach.replace("`", "").strip())
    return out


def _fn_segment(src: str, name: str) -> str:
    """Quelltext-Segment der Modul-Level-def `name` (sonst AssertionError)."""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            seg = ast.get_source_segment(src, node)
            assert seg, f"Segment von {name} leer"
            return seg
    raise AssertionError(f"Modul-Level def {name} nicht gefunden")


def test_md_tabelle_liefert_alle_sechs_hr_zeilen():
    rows = _md_employer_rows()
    assert len(rows) == 3, f"MD-Parser fand nur {rows}"
    assert sum(len(v) for v in rows.values()) == 6, f"MD-Parser: {rows}"
    assert rows == {
        "eingegangen": {"angesehen", "abgelehnt"},
        "angesehen": {"eingeladen", "abgelehnt"},
        "eingeladen": {"eingestellt", "abgelehnt"},
    }, rows


def test_md_und_allowed_transitions_stimmen_ueberein():
    """Lab-Prinzip Schritt 3: MD-Quelle == Python-Quelle (sonst MD korrigieren)."""
    assert _md_employer_rows() == emp.ALLOWED_TRANSITIONS


def test_kandidatenzeilen_sind_nicht_in_der_hr_whitelist():
    """Nur „Durch = Arbeitgeber“: zurückgezogen ist Kandidaten-Recht, kein HR-Ziel."""
    rows = _md_employer_rows()
    assert "zurückgezogen" not in emp.ALLOWED_TRANSITIONS
    for ziele in rows.values():
        assert "zurückgezogen" not in ziele


def test_legal_actions_folgt_der_md_liste():
    for von, ziele in _md_employer_rows().items():
        assert set(emp._legal_actions(von)) == ziele, von
    for final in ("eingestellt", "abgelehnt", "zurückgezogen"):
        assert emp._legal_actions(final) == [], final


# ─── Quelltext: EIN Quelle, beide Stellen-Seiten ─────────────────────────────

def test_stellen_seiten_ohne_eigenes_erl_dict():
    """(1) Variante B: weder employer._page_stellen noch admin._page_stellen
    tragen noch eine eigene Übergangs-Map — beide lesen _legal_actions()."""
    for src, name in ((EMP_SRC, "employer"), (ADM_SRC, "admin")):
        seg = _fn_segment(src, "_page_stellen")
        assert "erl = {" not in seg, f"{name}._page_stellen trägt noch ein erl-Dict"
        assert "naechste = _legal_actions(a_status)" in seg, name
    # Quelle ist die Modulebene von employer.py (ast: literal, unverändert B2-5a)
    tree = ast.parse(EMP_SRC)
    matrices = [ast.literal_eval(n.value) for n in ast.walk(tree)
                if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name)
                and t.id == "ALLOWED_TRANSITIONS"]
    assert matrices == [{
        "eingegangen": {"angesehen", "abgelehnt"},
        "angesehen": {"eingeladen", "abgelehnt"},
        "eingeladen": {"eingestellt", "abgelehnt"},
    }], matrices


def test_admin_importiert_die_whitelist_aus_employer():
    """(3) admin.py hat KEINE eigene Kopie mehr, sondern importiert die Quelle."""
    assert "from webui.pages.employer import ALLOWED_TRANSITIONS, _legal_actions" in ADM_SRC
    tree = ast.parse(ADM_SRC)
    names = [t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
             for t in n.targets if isinstance(t, ast.Name)]
    assert "ALLOWED_TRANSITIONS" not in names, "admin definiert die Matrix selbst"
    assert "erl" not in names, "admin definiert noch ein erl-Dict"


def test_klick_guard_prueft_db_status_vor_update():
    """(2) Klick-Guard beider Stellen-Seiten: Ausgangsstatus live aus der DB,
    gegen ALLOWED_TRANSITIONS, VOR dem UPDATE (Match-Muster `_legal`)."""
    for src, name in ((EMP_SRC, "employer"), (ADM_SRC, "admin")):
        seg = _fn_segment(src, "_page_stellen")
        assert "SELECT status FROM applications WHERE id = ?" in seg, name
        assert "ALLOWED_TRANSITIONS.get(_old, set())" in seg, name
        i_sel = seg.index("SELECT status FROM applications")
        i_upd = seg.index("UPDATE applications")
        assert i_sel < i_upd, f"{name}: Guard NACH dem UPDATE"
        i_notify = seg.index("Ungueltiger Statusuebergang (Whitelist ALLOWED_TRANSITIONS).")
        assert i_sel < i_notify < i_upd, f"{name}: Meldung nicht zwischen Guard und UPDATE"
        # kein History-Eintrag und kein Hook-Task ohne Guard
        assert seg.count("INSERT INTO application_status_history") == 1, name


# ─── N-K2 (01.10.2026): EINE CV-Pool-Quelle ────────────────────────────────

def test_n_k2_konstante_ist_die_pool_quelle():
    assert emp.CAND_CV_STATUS == ("lebenslauf_hochgeladen", "profil_geprueft",
                                  "match_berechnet", "eingeladen")


def test_n_k2_kein_zweiter_hartkodierter_pool():
    """Die 4 Werte stehen nur noch in der Konstanten — nicht als SQL-Literal."""
    flat = " ".join(EMP_SRC.split())  # mehrzeilige Literale zusammenziehen
    assert "'profil_geprueft', 'match_berechnet'" not in flat, (
        "hartkodierte CV-Pool-Liste gefunden (N-K2)")
    # der Passiv-Block bindet die Konstante als SQL-Parameter
    assert "f\"WHERE status IN ({','.join('?' * len(CAND_CV_STATUS))})\"" in EMP_SRC
    assert "list(CAND_CV_STATUS)" in EMP_SRC
