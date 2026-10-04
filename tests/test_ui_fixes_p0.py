"""Unit-Nachweis fuer die UI-Fixes vom 28.09.2026 (P0).

Deckt den gemeinsamen Datenzugriff beider Rollen ab:
get_documents() wird von Kandidaten-Portal (candidate.py) UND
HR-Dokumenten-Tab (employer.py) benutzt — ein Fix, zwei Rollen.

Read-only: nur SELECT gegen die Live-DB.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webui import db  # noqa: E402
from webui.components import STATUS_LABELS, status_label  # noqa: E402
from webui.logic import profile_display_name  # noqa: E402


def test_clean_filename():
    """S3c/R5-2: Dateinamen-Bereinigung — JETZT gegen die echte Funktion
    logic.safe_upload_name (vorher: kopierte Logik, Beweis-Risiko).
    Umlaute werden transliteriert (ä→ae, Design-Entscheidung R5-2),
    nicht mehr still gelöscht."""
    from webui.logic import safe_upload_name
    cases = [
        ("../../x.pdf", "x.pdf"),              # Pfad-Traversal
        ("..\\x.pdf", "x.pdf"),               # Backslash-Traversal
        ("my file (1).txt", "my_file_1_.txt"), # Leerzeichen/Klammern
        ("München.pdf", "Muenchen.pdf"),       # Umlaut → transliteriert
        ("Straße.pdf", "Strasse.pdf"),         # ß → ss
        ("", "unnamed"),                        # leer
        ("%%%$$$%%%", "unnamed"),               # nur Sonderzeichen
        ("bild.png", "bild.png"),               # falsche Endung bleibt
        # sehr langer Name: auf 80 Zeichen gekürzt, Endung bleibt
        ("a" * 100 + ".pdf", "a" * 76 + ".pdf"),
    ]
    for raw, expected in cases:
        result = safe_upload_name(raw)
        assert result == expected, f"{raw!r} -> {result!r} (erwartet {expected!r})"


def test_get_documents_liefert_zeilen():
    """P0-1: Spaltenname dokumententyp, keine stille Fehler-Unterdrueckung."""
    rows = db.get_documents(22)
    assert len(rows) >= 1, "Dokument von Kandidat 22 muss sichtbar sein"
    d_id, d_typ, d_pfad, d_dat = rows[0]
    assert d_typ == "Zeugnis", f"dokumententyp erwartet, war {d_typ!r}"
    assert "kandidat-22" in d_pfad
    assert d_dat is not None


def test_get_documents_leerer_kandidat():
    """P0-1: unbekannte ID liefert leere Liste, kein Fehler."""
    assert db.get_documents(999999) == []


def test_status_labels_klartext():
    """P0-4: DB-Slugs werden als Klartext ausgegeben."""
    assert status_label("lebenslauf_hochgeladen") == "Lebenslauf hochgeladen"
    assert status_label("eingeladen") == "Eingeladen"
    assert status_label("zurückgezogen") == "Zurückgezogen"
    for slug in ("eingegangen", "angesehen", "eingeladen", "eingestellt",
                 "abgelehnt", "zurückgezogen", "registriert",
                 "lebenslauf_hochgeladen", "zugeordnet", "aktiv"):
        assert slug in STATUS_LABELS, f"{slug} fehlt in der Status-Komponente"
        assert "_" not in status_label(slug), f"{slug} wird nicht als Klartext geliefert"


def test_profile_display_name_kein_dateiname():
    """P0-3: Auswahlfelder zeigen Namen, keine .md-Dateinamen."""
    name = profile_display_name("testdaten/profil---**name:**-anna-schuster.md")
    assert ".md" not in name
    assert "**" not in name
    assert "profil-" not in name
    assert name == "Anna Schuster", f"unerwartet: {name!r}"


def test_profile_display_name_fallback():
    """P0-3: ohne **Name:** wird der Dateistamm aufgeraeumt."""
    name = profile_display_name("testdaten/profil-abdelkader-batnini.md")
    assert name == "Abdelkader Batnini", f"unerwartet: {name!r}"