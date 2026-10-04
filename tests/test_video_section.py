"""A4 (30.09.2026): Pre-Screen-Datei darf den Video-Abschnitt nicht löschen.

Befund: candidate.py::start_prescreen schrieb die Tagesdatei komplett neu (ohne
"## Video-Vorstellung"), _persist_video_link (Sprachtest-Tab) schrieb den Abschnitt in dieselbe
Datei. Getestet werden die reinen Modulfunktionen mit tmp_path — keine UI, keine DB,
kein Zugriff auf ergebnisse/.
"""
from datetime import datetime

from webui.pages import candidate as cand

URL = "https://vdo.ninja/?director=vorstellung-1-abcd1234"
CID = 1


def _prescreen_md(datum="30.09.2026"):
    return (
        f"# Selbstpräsentation: Kandidat #{CID}\n\n**Datum:** {datum}\n\n"
        "## Ihr Meeting-Raum\n\n- **Link:** [x](https://vdo.ninja/?director=self-presentation-zzzz1111)\n\n"
        "## Ihre Leitfragen\n\n1. **[Motivation]** Warum?\n\n*Erstellt am 30.09.2026 vom KM-HR-Agenten.*\n"
    )


def test_video_dann_prescreen_gleicher_tag_link_bleibt(tmp_path):
    cand.persist_video_link(tmp_path, CID, URL, now=datetime(2026, 9, 30, 10, 0))
    assert cand.load_video_link(tmp_path, CID) == URL

    fn = "self-presentation-kandidat-1-2026-09-30.md"
    geschrieben = cand.write_prescreen_md(tmp_path, CID, fn, _prescreen_md())

    text = (tmp_path / fn).read_text(encoding="utf-8")
    assert text == geschrieben
    assert cand.VIDEO_HEADING in text and URL in text
    assert "## Ihre Leitfragen" in text          # neuer Pre-Screen-Inhalt ist da
    assert "Noch kein Raum generiert" not in text  # alter Platzhalter-Kopf ersetzt
    assert cand.load_video_link(tmp_path, CID) == URL


def test_video_alter_tag_wird_in_neue_tagesdatei_uebernommen(tmp_path):
    # Video liegt in Datei von gestern; heute erzeugt Pre-Screen eine NEUE Datei.
    cand.persist_video_link(tmp_path, CID, URL, now=datetime(2026, 9, 29, 10, 0))
    assert (tmp_path / "self-presentation-kandidat-1-2026-09-29.md").exists()

    cand.write_prescreen_md(tmp_path, CID, "self-presentation-kandidat-1-2026-09-30.md", _prescreen_md())

    heute = (tmp_path / "self-presentation-kandidat-1-2026-09-30.md").read_text(encoding="utf-8")
    assert URL in heute
    # neueste Datei enthält den Link → Lookup findet ihn auch dann, wenn nur nach "neueste" gesucht würde
    assert cand.extract_video_section(heute) != ""
    assert cand.load_video_link(tmp_path, CID) == URL


def test_ohne_video_bleibt_prescreen_unveraendert(tmp_path):
    fn = "self-presentation-kandidat-1-2026-09-30.md"
    md = _prescreen_md()
    assert cand.write_prescreen_md(tmp_path, CID, fn, md) == md
    assert cand.VIDEO_HEADING not in (tmp_path / fn).read_text(encoding="utf-8")
    assert cand.load_video_link(tmp_path, CID) is None


def test_mehrfaches_prescreen_dupliziert_abschnitt_nicht(tmp_path):
    cand.persist_video_link(tmp_path, CID, URL, now=datetime(2026, 9, 30, 10, 0))
    fn = "self-presentation-kandidat-1-2026-09-30.md"
    for _ in range(3):
        cand.write_prescreen_md(tmp_path, CID, fn, _prescreen_md())
    text = (tmp_path / fn).read_text(encoding="utf-8")
    assert text.count(cand.VIDEO_HEADING) == 1
    assert text.count(f"[{URL}]({URL})") == 1  # ein Markdown-Link (URL steht darin 2x)


def test_video_nach_prescreen_persistieren_ersetzt_link(tmp_path):
    fn = "self-presentation-kandidat-1-2026-09-30.md"
    cand.write_prescreen_md(tmp_path, CID, fn, _prescreen_md())
    cand.persist_video_link(tmp_path, CID, URL)
    neu = "https://vdo.ninja/?director=vorstellung-1-neu00000"
    cand.persist_video_link(tmp_path, CID, neu)
    text = (tmp_path / fn).read_text(encoding="utf-8")
    assert neu in text and URL not in text
    assert "## Ihre Leitfragen" in text and text.count(cand.VIDEO_HEADING) == 1


def test_andere_kandidaten_werden_nicht_vermischt(tmp_path):
    cand.persist_video_link(tmp_path, 2, "https://vdo.ninja/?director=fremd", now=datetime(2026, 9, 30))
    assert cand.load_video_link(tmp_path, CID) is None
    cand.write_prescreen_md(tmp_path, CID, "self-presentation-kandidat-1-2026-09-30.md", _prescreen_md())
    assert "fremd" not in (tmp_path / "self-presentation-kandidat-1-2026-09-30.md").read_text(encoding="utf-8")


def test_extract_video_section_endet_vor_naechster_ueberschrift():
    text = "# K\n\n## Video-Vorstellung\n\n- **Link:** [u](https://vdo.ninja/?director=a)\n\n## Anderes\n\nx\n"
    ab = cand.extract_video_section(text)
    assert ab.startswith("## Video-Vorstellung") and "Anderes" not in ab
    assert cand.extract_video_section("nichts") == ""
    assert cand.extract_video_section(None) == ""
