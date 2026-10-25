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


def test_linkedin_default_scopes_enthalten_openid_profile():
    m = _load()
    env = {"LINKEDIN_CLIENT_ID": "client-123",
           "LINKEDIN_REDIRECT_URI": "https://jobs.hanibal-ai.com/oauth/callback"}
    url = m.linkedin_url(env, "state")
    assert "scope=openid+profile+w_member_social" in url


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


def test_redirect_port_override_behaelt_host_und_pfad():
    m = _load()
    assert m.redirect_with_port(
        "http://localhost:8765/oauth/callback", 8790
    ) == "http://localhost:8790/oauth/callback"


def test_parse_redirect_lokal_und_https_proxy():
    m = _load()
    assert m.parse_redirect("http://localhost:8765/oauth/callback") == (
        "127.0.0.1", 8765, "/oauth/callback", False)
    assert m.parse_redirect("https://jobs.hanibal-ai.com/oauth/callback", 8765) == (
        "127.0.0.1", 8765, "/oauth/callback", True)
    with pytest.raises(SystemExit):
        m.parse_redirect("ftp://example.org/oauth/callback")


def test_belegter_port_liefert_klartext():
    import socket
    m = _load()
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        with pytest.raises(SystemExit) as exc:
            m._make_server(f"http://127.0.0.1:{port}/oauth/callback")
        assert "bereits belegt" in str(exc.value)
    finally:
        sock.close()


def test_url_override_wird_verwendet():
    m = _load()
    env = {"LINKEDIN_CLIENT_ID": "client-123"}
    url = m.linkedin_url(env, "state", "http://127.0.0.1:8790/oauth/callback")
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8790%2Foauth%2Fcallback" in url


def test_facebook_fields_instagram_ist_opt_in():
    m = _load()
    assert m.facebook_fields({}) == "id,name,access_token"
    assert m.facebook_fields({"FACEBOOK_FETCH_INSTAGRAM": "1"}) == (
        "id,name,access_token,instagram_business_account")
