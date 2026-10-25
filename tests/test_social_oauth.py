"""Tests für den OAuth-Bootstrap (scripts/social_oauth.py) — ohne Netz."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOD_PATH = ROOT / "scripts" / "social_oauth.py"


def _load():
    spec = importlib.util.spec_from_file_location("social_oauth_mod", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_linkedin_url_enthält_client_id_redirect_scope():
    m = _load()
    env = {"LINKEDIN_CLIENT_ID": "client-123",
           "LINKEDIN_REDIRECT_URI": "http://localhost:8765/oauth/callback",
           "LINKEDIN_SCOPES": "w_member_social"}
    url = m.linkedin_url(env, "state-abc")
    assert url.startswith("https://www.linkedin.com/oauth/v2/authorization?")
    assert "client_id=client-123" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Foauth%2Fcallback" in url
    assert "scope=w_member_social" in url
    assert "state=state-abc" in url


def test_facebook_url_enthält_app_id_und_scopes():
    m = _load()
    env = {"FACEBOOK_APP_ID": "1142211678381849",
           "FACEBOOK_REDIRECT_URI": "http://localhost:8765/oauth/callback",
           "FACEBOOK_SCOPES": "pages_manage_posts,pages_read_engagement"}
    url = m.facebook_url(env, "state-xyz")
    assert url.startswith("https://www.facebook.com/v21.0/dialog/oauth?")
    assert "client_id=1142211678381849" in url
    assert "scope=pages_manage_posts%2Cpages_read_engagement" in url
    assert "state=state-xyz" in url


def test_update_env_ersetzt_und_haengt_an(tmp_path):
    m = _load()
    p = tmp_path / ".env-social"
    p.write_text("# Kommentar\nFOO=alt\nBAR=bleibt\n", encoding="utf-8")
    m.update_env(p, {"FOO": "neu", "TOKEN": "secret"})
    text = p.read_text(encoding="utf-8")
    assert "FOO=neu" in text
    assert "BAR=bleibt" in text
    assert "TOKEN=secret" in text
    assert "# Kommentar" in text
    assert (p.stat().st_mode & 0o777) == 0o600


def test_fehlende_konfiguration_ist_klartext():
    m = _load()
    with pytest.raises(SystemExit) as exc:
        m.linkedin_url({}, "state")
    assert "LINKEDIN_CLIENT_ID" in str(exc.value)


def test_exchange_ohne_secret_wird_abgelehnt():
    m = _load()
    with pytest.raises(SystemExit) as exc:
        m.linkedin_exchange({"LINKEDIN_CLIENT_ID": "x",
                             "LINKEDIN_REDIRECT_URI": "http://localhost/cb"}, "code")
    assert "LINKEDIN_CLIENT_SECRET" in str(exc.value)
