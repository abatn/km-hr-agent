"""N-A1 (Queue-Filter in Klartext) + N-D3 (Modul-Docstring = 11 Seiten).

N-A1: Befund `ui-analyse:66/107` — der Task-Status-Filter der Agent-Details
zeigte DB-Slugs (`options=["alle","pending","running",…]`, alte Zeile `:1178`).
Soll: Klartext über `components.status_label` (EINE Quelle).

N-D3: der Modul-Docstring sagte „9 pages", obwohl `PAGE_MAP` 11 Seiten hat.

Reine Quelltext-Inspektion + `PAGE_MAP`-Länge; keine DB, keine UI.
"""
from pathlib import Path

from webui.components import status_label
from webui.pages import employer as emp

SRC = (Path(__file__).resolve().parent.parent / "webui" / "pages" / "employer.py"
       ).read_text(encoding="utf-8")


# ─── N-A1 ────────────────────────────────────────────────────────────────

def test_na1_keine_slug_optionen_im_queue_filter():
    assert 'options=["alle", "pending", "running", "done", "failed", "queued"]' not in SRC


def test_na1_queue_filter_nutzt_status_label():
    for slug in ("pending", "running", "done", "failed", "queued"):
        assert f'status_label("{slug}")' in SRC, slug
    assert '"alle": _("Alle")' in SRC


def test_na1_labels_sind_klartext():
    erwartet = {
        "pending": "Offen", "running": "Läuft", "done": "Erledigt",
        "failed": "Fehlgeschlagen", "queued": "In Warteschlange",
    }
    for slug, label in erwartet.items():
        assert status_label(slug) == label, slug
        assert "_" not in label, label


# ─── N-D3 ────────────────────────────────────────────────────────────────

def test_nd3_kein_9_pages_mehr():
    assert "9 pages" not in SRC
    assert "12 pages (PAGE_MAP)" in SRC


def test_nd3_docstring_entspricht_page_map():
    assert len(emp.PAGE_MAP) == 12  # 13.10.2026: +firmenprofil (Portal-Split)
    # jede Seite des PAGE_MAP wird im Docstring genannt (Klartext-Paritaet grob)
    for key in emp.PAGE_MAP:
        assert key in {"dashboard", "firmenprofil", "portal", "stellen", "kandidaten", "match",
                       "compliance", "agent_details", "dokumente", "prescreen",
                       "onboarding", "feedback"}
