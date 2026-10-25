"""Tests für den autonomen Social-Media-Agenten (scripts/social_agent.py).

Kein Netz: alle Adapter-Tests laufen gegen Dry-Run/Fakes; die DB ist eine
temporäre SQLite-Datei. Es werden keine echten Konten oder Tokens benötigt.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOD_PATH = ROOT / "scripts" / "social_agent.py"


def _load():
    spec = importlib.util.spec_from_file_location("social_agent_mod", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod(tmp_path, monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "OUT_ROOT", tmp_path / "social")
    monkeypatch.setattr(m, "LOG_FILE", tmp_path / "social-agent.log")
    monkeypatch.setenv("KMHR_SOCIAL_ENABLED", "1")
    monkeypatch.setenv("KMHR_SOCIAL_AUTO_PUBLISH", "0")
    return m


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "feedback.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY, titel TEXT, standort TEXT, land TEXT,
            stellentyp TEXT, gehaltsrahmen_min INTEGER, gehaltsrahmen_max INTEGER,
            erstellt_am TEXT, status TEXT);
        CREATE TABLE applications (id INTEGER PRIMARY KEY, status TEXT);
        INSERT INTO jobs VALUES
            (1, 'Python Entwickler', 'Berlin', 'DE', 'Vollzeit', 55000, 70000, '2026-10-24', 'aktiv'),
            (2, 'Logistik-Fachkraft', 'Lyon', 'FR', 'Vollzeit', 32000, 38000, '2026-10-20', 'aktiv');
        INSERT INTO applications VALUES
            (1, 'eingeladen'), (2, 'eingeladen'), (3, 'eingestellt'), (4, 'abgelehnt');
        """
    )
    conn.commit()
    conn.close()
    return path


def test_wochenplan_hat_7_eintraege(mod):
    plan = mod.build_weekly_plan(date(2026, 10, 26))
    assert len(plan) == 7
    assert [p["day"] for p in plan] == [
        "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29",
        "2026-10-30", "2026-10-31", "2026-11-01",
    ]
    assert {p["platform"] for p in plan} == {"linkedin", "facebook", "instagram"}
    assert all(p["topic"] in mod.TOPICS for p in plan)


def test_render_post_ist_pii_frei_und_hat_link(mod, db):
    agg = mod.read_aggregates(db)
    entry = {"day": "2026-10-26", "platform": "linkedin",
             "topic": "new_jobs", "language": "de"}
    post = mod.render_post(entry, agg)
    assert "Python Entwickler" in post["text"]
    assert post["link"].startswith("https://")
    assert "@" not in post["text"]
    assert "Kandidat #" not in post["text"]
    assert "KI-unterstützt" in post["text"]
    assert post["post_id"]


def test_stats_post_hat_aggregate_und_keine_personen(mod, db):
    agg = mod.read_aggregates(db)
    entry = {"day": "2026-10-29", "platform": "facebook",
             "topic": "hiring_stats", "language": "de"}
    post = mod.render_post(entry, agg)
    assert "Aktive Stellen: 2" in post["text"]
    assert "Bewerbungen: 4" in post["text"]
    assert "Eingestellt: 1" in post["text"]
    mod.assert_no_pii(post["text"])


def test_dsgvo_guard_blockt_email_und_telefon(mod):
    with pytest.raises(mod.SocialError):
        mod.assert_no_pii("Kontakt: max@example.com")
    with pytest.raises(mod.SocialError):
        mod.assert_no_pii("Ruf an: +49 30 12345678")
    with pytest.raises(mod.SocialError):
        mod.assert_no_pii("Kandidat #42 hat den Job.")


def test_dry_run_schreibt_outbox_ohne_netz(mod, db, monkeypatch):
    def _no_network(*a, **kw):
        raise AssertionError("Dry-Run darf kein HTTP senden")
    monkeypatch.setattr(mod.requests, "post", _no_network)
    result = mod.run_once(date(2026, 10, 26), db, mode="dry_run")
    assert result["status"] == "dry_run"
    out = Path(result["path"])
    assert out.is_file()
    data = mod.json.loads(out.read_text(encoding="utf-8"))
    assert data["result"]["status"] == "dry_run"
    assert data["post"]["platform"] == "linkedin"
    assert (out.parent / "plan.json").is_file()
    assert (out.parent / "linkedin-new_jobs.md").is_file()


def test_zweiter_lauf_ist_idempotent(mod, db):
    first = mod.run_once(date(2026, 10, 26), db, mode="dry_run")
    second = mod.run_once(date(2026, 10, 26), db, mode="dry_run")
    assert first["status"] == "dry_run"
    assert second["status"] == "skipped"


def test_live_ohne_auto_publish_bleibt_dry_run(mod, db, monkeypatch):
    monkeypatch.setenv("KMHR_SOCIAL_AUTO_PUBLISH", "0")
    result = mod.run_once(date(2026, 10, 26), db, mode="live")
    assert result["status"] == "dry_run"
    data = mod.json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert data["result"]["reason"].startswith("approval_required")


def test_live_mit_auto_publish_nutzt_adapter(mod, db, monkeypatch):
    monkeypatch.setenv("KMHR_SOCIAL_AUTO_PUBLISH", "1")
    calls = []

    def fake_publish(self, post):
        calls.append(post)
        return {"status": "published", "platform": "linkedin", "external_id": "urn:li:share:1"}

    monkeypatch.setattr(mod.LinkedInAdapter, "publish", fake_publish)
    result = mod.run_once(date(2026, 10, 26), db, mode="live")
    assert result["status"] == "published"
    assert len(calls) == 1
    data = mod.json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert data["result"]["external_id"] == "urn:li:share:1"


def test_facebook_app_token_wird_abgelehnt(mod, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "123")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "1142211678381849|secret")
    post = {"platform": "facebook", "text": "x", "link": "https://example.org"}
    with pytest.raises(mod.SocialError) as exc:
        mod.FacebookAdapter().publish(post)
    assert "App Access Token" in str(exc.value)


def test_instagram_ohne_bild_ist_konfigurationsfehler(mod, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_USER_ID", "123")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "token")
    monkeypatch.delenv("INSTAGRAM_IMAGE_URL", raising=False)
    post = {"platform": "instagram", "text": "x", "link": "https://example.org",
            "image_url": None}
    with pytest.raises(mod.SocialError):
        mod.InstagramAdapter().publish(post)


def test_missing_tokens_fuehren_zu_failed(tmp_path, db, monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "OUT_ROOT", tmp_path / "social")
    monkeypatch.setattr(m, "LOG_FILE", tmp_path / "social-agent.log")
    monkeypatch.setenv("KMHR_SOCIAL_AUTO_PUBLISH", "1")
    for key in ("LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN"):
        monkeypatch.delenv(key, raising=False)
    result = m.run_once(date(2026, 10, 26), db, mode="live")
    # Fehlende Tokens werden als failed persistiert, nicht als "published" versprochen.
    assert result["status"] == "failed"
    data = m.json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert data["result"]["status"] == "failed"
