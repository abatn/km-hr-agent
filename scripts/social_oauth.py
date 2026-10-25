"""OAuth-Bootstrap für den Social-Agenten (LinkedIn + Facebook/Meta).

Die Client-ID/App-ID allein reicht nicht zum Posten:
- LinkedIn: 3-legged OAuth mit Client Secret + Redirect-URI + Nutzerfreigabe.
- Facebook: User-Login, danach Page-Token über /me/accounts; Page-Posting
  braucht die Page-Rolle und die passenden Permissions.

Dieses Skript erzeugt Auth-URLs, tauscht den Code gegen Tokens und schreibt
die Tokens **nur** in `.env-social` (chmod 600, gitignored). Tokens werden nie
auf stdout ausgegeben.

Beispiele:
  python3 scripts/social_oauth.py linkedin --url
  python3 scripts/social_oauth.py linkedin --serve
  python3 scripts/social_oauth.py facebook --url
  python3 scripts/social_oauth.py facebook --serve
"""
from __future__ import annotations

import argparse
import secrets
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env-social"


def load_env(path: Path = ENV_FILE) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def update_env(path: Path, updates: dict[str, str]) -> None:
    """Ersetzt Keys in .env-social und behält Kommentare/Reihenfolge."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    path.chmod(0o600)


def _require(env: dict[str, str], *keys: str) -> None:
    missing = [k for k in keys if not env.get(k)]
    if missing:
        raise SystemExit(
            "Fehlende Konfiguration in .env-social: " + ", ".join(missing)
            + "\nBitte ergänzen (Client Secret/Redirect-URI) und erneut starten.")


def linkedin_url(env: dict[str, str], state: str) -> str:
    _require(env, "LINKEDIN_CLIENT_ID", "LINKEDIN_REDIRECT_URI")
    params = {
        "response_type": "code",
        "client_id": env["LINKEDIN_CLIENT_ID"],
        "redirect_uri": env["LINKEDIN_REDIRECT_URI"],
        "scope": env.get("LINKEDIN_SCOPES", "w_member_social"),
        "state": state,
    }
    return "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(params)


def facebook_url(env: dict[str, str], state: str) -> str:
    _require(env, "FACEBOOK_APP_ID", "FACEBOOK_REDIRECT_URI")
    params = {
        "client_id": env["FACEBOOK_APP_ID"],
        "redirect_uri": env["FACEBOOK_REDIRECT_URI"],
        "state": state,
        "scope": env.get("FACEBOOK_SCOPES",
                         "pages_show_list,pages_manage_posts,pages_read_engagement"),
        "response_type": "code",
    }
    return "https://www.facebook.com/v21.0/dialog/oauth?" + urllib.parse.urlencode(params)


def linkedin_exchange(env: dict[str, str], code: str) -> dict[str, str]:
    _require(env, "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "LINKEDIN_REDIRECT_URI")
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={"grant_type": "authorization_code", "code": code,
              "redirect_uri": env["LINKEDIN_REDIRECT_URI"],
              "client_id": env["LINKEDIN_CLIENT_ID"],
              "client_secret": env["LINKEDIN_CLIENT_SECRET"]},
        timeout=30)
    if not resp.ok:
        raise SystemExit(f"LinkedIn-Token-Tausch fehlgeschlagen: HTTP {resp.status_code}")
    token = resp.json().get("access_token", "")
    if not token:
        raise SystemExit("LinkedIn lieferte keinen access_token")
    user = requests.get("https://api.linkedin.com/v2/userinfo",
                        headers={"Authorization": f"Bearer {token}"}, timeout=30)
    author = ""
    if user.ok:
        sub = user.json().get("sub", "")
        if sub:
            author = f"urn:li:person:{sub}"
    updates = {"LINKEDIN_ACCESS_TOKEN": token}
    if author:
        updates["LINKEDIN_AUTHOR_URN"] = author
    update_env(ENV_FILE, updates)
    return {"provider": "linkedin", "token": "gespeichert", "author": author or "nicht ermittelt"}


def facebook_exchange(env: dict[str, str], code: str, page_id: str = "") -> dict[str, str]:
    _require(env, "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "FACEBOOK_REDIRECT_URI")
    resp = requests.get(
        "https://graph.facebook.com/v21.0/oauth/access_token",
        params={"client_id": env["FACEBOOK_APP_ID"],
                "client_secret": env["FACEBOOK_APP_SECRET"],
                "redirect_uri": env["FACEBOOK_REDIRECT_URI"],
                "code": code}, timeout=30)
    if not resp.ok:
        raise SystemExit(f"Facebook-Token-Tausch fehlgeschlagen: HTTP {resp.status_code}")
    user_token = resp.json().get("access_token", "")
    if not user_token:
        raise SystemExit("Facebook lieferte keinen user access_token")
    pages = requests.get(
        "https://graph.facebook.com/v21.0/me/accounts",
        params={"access_token": user_token,
                "fields": "id,name,access_token,instagram_business_account"}, timeout=30)
    if not pages.ok:
        raise SystemExit(f"Facebook /me/accounts fehlgeschlagen: HTTP {pages.status_code}")
    data = pages.json().get("data", [])
    if not data:
        raise SystemExit("Keine Facebook-Page für diesen User sichtbar (App-Rolle/Page-Rolle prüfen)")
    page = next((p for p in data if p.get("id") == page_id), data[0]) if page_id else data[0]
    updates = {
        "FACEBOOK_PAGE_ID": page["id"],
        "FACEBOOK_PAGE_ACCESS_TOKEN": page["access_token"],
    }
    ig = page.get("instagram_business_account") or {}
    if ig.get("id"):
        updates["INSTAGRAM_USER_ID"] = ig["id"]
        updates["INSTAGRAM_ACCESS_TOKEN"] = page["access_token"]
    update_env(ENV_FILE, updates)
    return {"provider": "facebook", "token": "gespeichert",
            "page_id": page["id"], "page_name": page.get("name", ""),
            "pages_visible": len(data),
            "instagram_user_id": ig.get("id", "")}


class _Callback(BaseHTTPRequestHandler):
    code = ""
    state = ""
    expected_state = ""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        if parsed.path != "/oauth/callback":
            self.send_response(404)
            self.end_headers()
            return
        if q.get("state", [""])[0] != self.expected_state:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"State mismatch")
            return
        self.__class__.code = q.get("code", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h2>OAuth-Code empfangen.</h2><p>Du kannst das Fenster schließen.</p>"
                         .encode("utf-8"))

    def log_message(self, *args: Any) -> None:
        return


def serve(provider: str, env: dict[str, str], port: int, page_id: str) -> int:
    state = secrets.token_urlsafe(24)
    url = linkedin_url(env, state) if provider == "linkedin" else facebook_url(env, state)
    _Callback.expected_state = state
    server = HTTPServer(("127.0.0.1", port), _Callback)
    print(f"Auth-URL ({provider}):\n{url}\n")
    print(f"Warte auf Callback auf http://127.0.0.1:{port}/oauth/callback ...")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    server.handle_request()  # ein Request = Callback
    server.server_close()
    if not _Callback.code:
        print("Kein Code empfangen.")
        return 2
    result = (linkedin_exchange(env, _Callback.code) if provider == "linkedin"
              else facebook_exchange(env, _Callback.code, page_id))
    print(result)
    print(f"Tokens in {ENV_FILE} gespeichert (chmod 600).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OAuth-Bootstrap für LinkedIn/Facebook")
    ap.add_argument("provider", choices=("linkedin", "facebook"))
    ap.add_argument("--url", action="store_true", help="nur Auth-URL ausgeben")
    ap.add_argument("--serve", action="store_true", help="lokalen Callback-Server starten")
    ap.add_argument("--exchange", metavar="CODE", help="Authorization-Code einlösen")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--page-id", default="", help="Facebook-Page-ID (sonst erste sichtbare)")
    args = ap.parse_args(argv)
    env = load_env()
    state = secrets.token_urlsafe(24)
    if args.url:
        print(linkedin_url(env, state) if args.provider == "linkedin"
              else facebook_url(env, state))
        return 0
    if args.exchange:
        result = (linkedin_exchange(env, args.exchange) if args.provider == "linkedin"
                  else facebook_exchange(env, args.exchange, args.page_id))
        print(result)
        return 0
    if args.serve:
        return serve(args.provider, env, args.port, args.page_id)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
