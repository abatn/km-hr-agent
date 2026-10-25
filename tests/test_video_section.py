"""Selbstpräsentation-Datei: Video-Abschnitt (A4 30.09.2026; md-Disziplin 21.10.2026).

A4 (30.09.2026): candidate.py::start_prescreen schrieb die Tagesdatei komplett neu
(ohne "## Video-Vorstellung"), _persist_video_link (Sprachtest-Tab) schrieb den
Abschnitt in dieselbe Datei.

md-Disziplin (21.10.2026, Spec knowledge/system/md-schreib-konvention.md):
  R-S2 kein Carry-over über Tagesgrenzen (der 24-Tage-Altlink war im Portal sichtbar),
  R-S3 Zieldatei = heutiges Datum (nie „neueste existierende"),
  R-S5 kein Abschneiden (nur der per Anker adressierte Abschnitt wird ersetzt).

Getestet werden die reinen Modulfunktionen mit tmp_path — keine UI, keine DB,
kein Zugriff auf ergebnisse/.
"""
from datetime import datetime
from pathlib import Path

from webui.pages import candidate as cand



def tmp_path_of():
    """Eigenes Temp-Verzeichnis (ohne pytest-fixture — die Tests sind rein dateibasiert)."""
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="kmhr-hrsicht-"))
    return d


URL = "https://vdo.ninja/?push=vorstellung1abcd1234"
CID = 1


def _prescreen_md(datum="30.09.2026"):
    return (
        f"# Selbstpräsentation: Kandidat #{CID}\n\n**Datum:** {datum}\n\n"
        "## Ihr Meeting-Raum\n\n- **Link:** [x](https://vdo.ninja/?push=selfpresentationzzzz1111)\n\n"
        "## Ihre Leitfragen\n\n1. **[Motivation]** Warum?\n\n*Erstellt am 30.09.2026 vom KM-HR-Agenten.*\n"
    )


def test_video_dann_prescreen_gleicher_tag_link_bleibt(tmp_path):
    """A4: Link und Leitfragen desselben Tages bleiben beim Pre-Screen erhalten."""
    cand.persist_video_link(tmp_path, CID, URL, now=datetime(2026, 9, 30, 10, 0))
    assert cand.load_video_link(tmp_path, CID, now=datetime(2026, 9, 30, 12, 0)) == URL

    fn = "self-presentation-kandidat-1-2026-09-30.md"
    geschrieben = cand.write_prescreen_md(tmp_path, CID, fn, _prescreen_md())

    text = (tmp_path / fn).read_text(encoding="utf-8")
    assert text == geschrieben
    assert cand.VIDEO_HEADING in text and URL in text
    assert "## Ihre Leitfragen" in text          # neuer Pre-Screen-Inhalt ist da
    assert "Noch kein Raum generiert" not in text  # alter Platzhalter-Kopf ersetzt
    assert cand.load_video_link(tmp_path, CID, now=datetime(2026, 9, 30, 12, 0)) == URL


def test_kein_carry_over_ueber_tagesgrenzen(tmp_path):
    """md-Disziplin: der **Schreiber** übernimmt keinen Abschnitt aus einer Vortagesdatei."""
    cand.persist_video_link(tmp_path, CID, URL, now=datetime(2026, 9, 29, 10, 0))
    assert (tmp_path / "self-presentation-kandidat-1-2026-09-29.md").exists()

    cand.write_prescreen_md(tmp_path, CID, "self-presentation-kandidat-1-2026-09-30.md", _prescreen_md())

    heute = (tmp_path / "self-presentation-kandidat-1-2026-09-30.md").read_text(encoding="utf-8")
    assert URL not in heute, "Carry-over über Tagesgrenzen (Spec R-S2)"
    assert cand.extract_video_section(heute) == ""


def test_leser_sieht_link_aus_vortagesdatei(tmp_path):
    """21.10.2026: Der Kandidat soll seinen Link auch dann sehen, wenn er gestern
    erzeugt wurde — nur der SCHREIBER ist an das heutige Datum gebunden (R-S3)."""
    cand.persist_video_link(tmp_path, CID, URL, now=datetime(2026, 9, 29, 10, 0))
    assert cand.load_video_link(tmp_path, CID, now=datetime(2026, 9, 30, 12, 0)) == URL
    # Heutige Datei gewinnt, wenn vorhanden.
    neu = "https://vdo.ninja/?push=vorstellung1heute0000"
    cand.persist_video_link(tmp_path, CID, neu, now=datetime(2026, 9, 30, 13, 0))
    assert cand.load_video_link(tmp_path, CID, now=datetime(2026, 9, 30, 14, 0)) == neu


def test_ohne_video_bleibt_prescreen_unveraendert(tmp_path):
    fn = "self-presentation-kandidat-1-2026-09-30.md"
    md = _prescreen_md()
    assert cand.write_prescreen_md(tmp_path, CID, fn, md) == md
    assert cand.VIDEO_HEADING not in (tmp_path / fn).read_text(encoding="utf-8")
    assert cand.load_video_link(tmp_path, CID, now=datetime(2026, 9, 30, 12, 0)) is None


def test_mehrfaches_prescreen_dupliziert_abschnitt_nicht(tmp_path):
    cand.persist_video_link(tmp_path, CID, URL, now=datetime(2026, 9, 30, 10, 0))
    fn = "self-presentation-kandidat-1-2026-09-30.md"
    for _ in range(3):
        cand.write_prescreen_md(tmp_path, CID, fn, _prescreen_md())
    text = (tmp_path / fn).read_text(encoding="utf-8")
    assert text.count(cand.VIDEO_HEADING) == 1
    assert text.count(f"[{URL}]({URL})") == 1  # ein Markdown-Link (URL steht darin 2x)


def test_video_nach_prescreen_persistieren_ersetzt_link_und_keeps_rest(tmp_path):
    """Spec R-S5: nur der Video-Abschnitt wird ersetzt — der Rest bleibt."""
    fn = "self-presentation-kandidat-1-2026-09-30.md"
    cand.write_prescreen_md(tmp_path, CID, fn, _prescreen_md())
    cand.persist_video_link(tmp_path, CID, URL, now=datetime(2026, 9, 30, 10, 0))
    neu = "https://vdo.ninja/?push=vorstellung1neu00000"
    cand.persist_video_link(tmp_path, CID, neu, now=datetime(2026, 9, 30, 11, 0))
    text = (tmp_path / fn).read_text(encoding="utf-8")
    assert neu in text and URL not in text
    assert "## Ihre Leitfragen" in text and text.count(cand.VIDEO_HEADING) == 1


def test_persist_video_link_schreibt_heutige_datei(tmp_path):
    """Spec R-S3: Ziel ist die Datei des heutigen Tages, nicht die neueste existierende."""
    alt = tmp_path / "self-presentation-kandidat-1-2026-09-19.md"
    alt.write_text("# alt\n\n## Video-Vorstellung\n\n- **Link:** [alt](https://vdo.ninja/?push=alt1234)\n",
                   encoding="utf-8")
    ziel = cand.persist_video_link(tmp_path, CID, URL, now=datetime(2026, 9, 30, 10, 0))
    assert ziel.name == "self-presentation-kandidat-1-2026-09-30.md"
    assert URL in ziel.read_text(encoding="utf-8")
    # Die ältere Datei bleibt unverändert (kein Schreiben in ein Altartefakt).
    assert "alt1234" in alt.read_text(encoding="utf-8")


def test_replace_video_section_anker_ohne_abschneiden():
    text = ("# Kopf\n\n## Video-Vorstellung\n\n- **Link:** [alt](u)\n\n"
            "## Ihre Leitfragen\n\n1. Frage\n")
    neu = cand.replace_video_section(text, cand.video_section_md("neu"))
    assert "neu" in neu and "[alt](u)" not in neu
    assert "## Ihre Leitfragen" in neu and "1. Frage" in neu
    ohne = cand.replace_video_section(text, "")
    assert cand.VIDEO_HEADING not in ohne
    assert "## Ihre Leitfragen" in ohne


def test_andere_kandidaten_werden_nicht_vermischt(tmp_path):
    cand.persist_video_link(tmp_path, 2, "https://vdo.ninja/?push=fremd1234",
                            now=datetime(2026, 9, 30, 10, 0))
    assert cand.load_video_link(tmp_path, CID, now=datetime(2026, 9, 30, 12, 0)) is None
    cand.write_prescreen_md(tmp_path, CID, "self-presentation-kandidat-1-2026-09-30.md", _prescreen_md())
    assert "fremd" not in (tmp_path / "self-presentation-kandidat-1-2026-09-30.md").read_text(encoding="utf-8")


def test_extract_video_section_endet_vor_naechster_ueberschrift():
    text = "# K\n\n## Video-Vorstellung\n\n- **Link:** [u](https://vdo.ninja/?push=a)\n\n## Anderes\n\nx\n"
    ab = cand.extract_video_section(text)
    assert ab.startswith("## Video-Vorstellung") and "Anderes" not in ab
    assert cand.extract_video_section("nichts") == ""
    assert cand.extract_video_section(None) == ""


# ── V-19 (21.10.2026): HR-Sicht — je Kandidat nur der NEUSTE Stand mit
# Video-Abschnitt; veraltete `?director=`-Links sind kein nutzbarer Link.
def _datei_mit_video(pfad, url):
    pfad.write_text(
        "# Selbstpräsentation\n\n## Video-Vorstellung\n\n"
        f"- **Link:** [{url}]({url})\n",
        encoding="utf-8")


def test_hr_sicht_zeigt_nur_den_neuesten_stand_mit_video():
    from webui import components
    tmp = tmp_path_of()
    _datei_mit_video(tmp / "self-presentation-kandidat-1-2026-09-17.md",
                      "https://vdo.ninja/?push=alt12345678")
    _datei_mit_video(tmp / "self-presentation-kandidat-1-2026-10-04.md",
                      "https://vdo.ninja/?push=neu12345678")
    res = components.selbstpraesentation_je_kandidat(tmp)
    assert 1 in res, res
    eintrag = res[1]
    assert eintrag["pfad"].name == "self-presentation-kandidat-1-2026-10-04.md"
    assert "neu12345678" in eintrag["video_url"]
    assert eintrag["aeltere"] == 1


def test_hr_sicht_ignoriert_veralteten_director_link():
    from webui import components
    tmp = tmp_path_of()
    _datei_mit_video(tmp / "self-presentation-kandidat-2-2026-09-17.md",
                      "https://vdo.ninja/?director=altverzeichnis")
    res = components.selbstpraesentation_je_kandidat(tmp)
    assert 2 in res, res
    assert res[2]["video_url"] is None, res[2]
    assert res[2]["aeltere"] == 0


def test_hr_sicht_zeigt_dokument_auch_ohne_video_link():
    from webui import components
    tmp = tmp_path_of()
    (tmp / "self-presentation-kandidat-3-2026-09-17.md").write_text(
        "# Selbstpräsentation\n\n## Ihr Meeting-Raum\n\n- **Link:** [x](https://vdo.ninja/?push=abc12345)\n",
        encoding="utf-8")
    res = components.selbstpraesentation_je_kandidat(tmp)
    assert 3 in res, res
    assert res[3]["video_url"] is None
    assert res[3]["pfad"].name == "self-presentation-kandidat-3-2026-09-17.md"
