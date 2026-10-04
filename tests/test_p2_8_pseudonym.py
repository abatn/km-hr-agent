"""P2-8 (01.10.2026): Klarname erst ab Status `eingeladen`.

Entscheidung (Nutzer, 01.10.2026, `ergebnisse/entscheidungen.md`): **Code
anonymisieren**, Umfang **nur Stellenangebote**. Quelle der Regel:
`knowledge/portal/employer-portal-fields.md:110` + `knowledge/lifecycle/
application-status.md:80` („echten Namen erst nach `eingeladen`").

Der frühere P1-Klartext-Fix (28.09.2026, M-06) zeigte den Klarnamen schon ab
`eingegangen`. `anzeige_name()` setzt das auf das Spec-Verhalten zurück, ohne den
Klartext-Kern zu verlieren (nie rohes `#id`, sondern „Kandidat #N").
"""
from pathlib import Path

from webui.pages import employer as emp

_ROOT = Path(__file__).resolve().parents[1]
SRC_EMP = (_ROOT / "webui" / "pages" / "employer.py").read_text(encoding="utf-8")


def test_pseudonym_vor_einladung():
    for status in ("eingegangen", "angesehen", "abgelehnt", "zurückgezogen", ""):
        assert emp.anzeige_name("Anna Schuster", 2, status) == "Kandidat #2", status


def test_klarname_ab_eingeladen():
    for status in ("eingeladen", "eingestellt"):
        assert emp.anzeige_name("Anna Schuster", 2, status) == "Anna Schuster", status


def test_leerer_name_faellt_auf_pseudonym_zurueck():
    # kein Name in der DB (COALESCE(c.name,'')) → keine leere Anzeige
    assert emp.anzeige_name("", 2, "eingeladen") == "Kandidat #2"
    assert emp.anzeige_name(None, 2, "eingestellt") == "Kandidat #2"


# ─── Quelltext-Regeln (Stellenangebote-Seite) ─────────────────────────────

def test_stellenangebote_nutzt_helper_und_kein_rohes_pseudonym():
    # alle ehemaligen `k_name or f"Kandidat #…"`-Stellen laufen jetzt über anzeige_name
    assert "k_name or f" not in SRC_EMP
    assert SRC_EMP.count("anzeige_name(k_name, k_id, a_status)") == 3
    assert "def anzeige_name(name, k_id, status)" in SRC_EMP


def test_freigabe_whitelist_ist_dieselbe_wie_dokumente():
    assert emp.DOC_RELEASE_STATUS == ("eingeladen", "eingestellt")
