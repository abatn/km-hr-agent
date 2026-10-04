"""Regression 01.10.2026: `.bak`-Retention darf frische Backups NICHT löschen,
wenn der Originalname ein kompaktes Datum trägt.

Bug: `re.search(r"(20\\d{6})", name)` nahm den ersten Treffer — bei
`m16-timing-20260929.md.bak-20261001-1955` also `20260929` statt `20261001`
→ frisches Backup wurde als Verstoß gelöscht (Beleg:
`/tmp/opencode/bakcheck/deleted_2_20261001-2002.tar.gz`).
Fix: `_bak_timestamp()` liest nur den Teil direkt nach `bak`.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webui import logic  # noqa: E402


def _tag(delta: int = 0) -> str:
    return (datetime.now() + timedelta(days=delta)).strftime("%Y%m%d")


def test_bak_timestamp_nimmt_datum_nach_bak():
    # Bug-Fall: Originalname trägt kompaktes Datum, Backup-Stempel = heute
    assert logic._bak_timestamp(f"m16-timing-20260929.md.bak-{_tag()}-1955") == _tag()
    assert logic._bak_timestamp(f"employer.py.bak-{_tag()}-1752") == _tag()
    assert logic._bak_timestamp("foo.bak") is None
    assert logic._bak_timestamp("foo.bak-2026-10-01") is None


def test_scan_behaelt_frisches_backup_trotz_datum_im_originalnamen(tmp_path, monkeypatch):
    monkeypatch.setattr(logic, "BASE_DIR", tmp_path)
    frisch = tmp_path / f"m16-timing-20260929.md.bak-{_tag()}-1955"
    frisch.write_text("x", encoding="utf-8")
    assert logic.bak_retention_scan() == []


def test_scan_flaggt_altes_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(logic, "BASE_DIR", tmp_path)
    alt = tmp_path / f"x.md.bak-{_tag(-5)}-1000"
    alt.write_text("x", encoding="utf-8")
    assert str(alt.relative_to(tmp_path)) in logic.bak_retention_scan()


def test_scan_flaggt_backup_ohne_datum(tmp_path, monkeypatch):
    monkeypatch.setattr(logic, "BASE_DIR", tmp_path)
    (tmp_path / "x.py.bak").write_text("x", encoding="utf-8")
    assert "x.py.bak" in logic.bak_retention_scan()


def test_scan_ignoriert_venv(tmp_path, monkeypatch):
    monkeypatch.setattr(logic, "BASE_DIR", tmp_path)
    d = tmp_path / ".venv" / "x.py.bak"
    d.parent.mkdir()
    d.write_text("x", encoding="utf-8")
    assert logic.bak_retention_scan() == []
