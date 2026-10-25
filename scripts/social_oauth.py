"""OAuth-Bootstrap für den Social-Agenten (LinkedIn + Facebook/Meta).

Die Client-ID/App-ID allein reicht nicht zum Posten:
- LinkedIn: 3-legged OAuth mit Client Secret + Redirect-URI + Nutzerfreigabe.
- Facebook: User-Login, danach Page-Token über /me/accounts; Page-Posting
  braucht die Page-Rolle und die passenden Permissions.

Wichtig: Die Redirect-URI muss in der jeweiligen App **exakt** registriert sein
(Schema, Host, Port und Pfad). Dieses Skript bindet den lokalen Callback-Server
deshalb an genau den Host/Port aus `*_REDIRECT_URI`; es rät keine Ports.

Beispiele:
  python3 scripts/social_oauth.py linkedin --url
  python3 scripts/social_oauth.py linkedin --serve
  python3 scripts/social_oauth.py facebook --serve --page-id 123
  python3 scripts/social_oauth.py linkedin --serve --redirect-uri \
      http://127.0.0.1:8765/oauth/callback

`--serve` öffnet den Browser NICHT automatisch (WSL/Headless: DBus/GCM/WebGL-
Fehler). Die URL wird ausgegeben und kann im normalen Browser geöffnet werden.
"""
from __future__ import annotations

import argparse
import errno
import secrets
import sys
import time
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


def _redirect(env: dict[str, str], key: str, override: str | None = None) -> str:
    uri = (override or env.get(key, "")).strip()
    if not uri:
        raise SystemExit(f"{key} fehlt in .env-social (z. B. http://localhost:8765/oauth/callback)")
    return uri


def redirect_with_port(uri: str, port: int) -> str:
    """Ersetzt nur den Port; Schema/Host/Pfad bleiben unverändert."""
    p = urllib.parse.urlparse(uri)
    host = p.hostname or "127.0.0.1"
    netloc = f"{host}:{port}"
    return urllib.parse.urlunparse(p._replace(netloc=netloc))


def parse_redirect(uri: str) -> tuple[str, int, str]:
    """Liefert (bind_host, port, path) aus der registrierten Redirect-URI."""
    p = urllib.parse.urlparse(uri)
    if p.scheme != "http" or p.hostname not in ("localhost", "127.0.0.1"):
        raise SystemExit(
            f"--serve unterstützt nur http://localhost/127.0.0.1, nicht {uri!r}.\n"
            "Für eine öffentliche HTTPS-Redirect-URI braucht es einen echten "
            "Callback-Endpunkt (Reverse Proxy), keinen lokalen Server.")
    port = p.port or 80
    path = p.path or "/oauth/callback"
    bind_host = "127.0.0.1" if p.hostname == "localhost" else p.hostname
    return bind_host, port, path


def _make_server(uri: str) -> tuple[HTTPServer, str]:
    bind_host, port, path = parse_redirect(uri)

    class _Server(HTTPServer):
        # Erlaubt erneutes Binden nach Ctrl+C/TIME_WAIT auf demselben Port.
        allow_reuse_address = True

    try:
        return _Server((bind_host, port), _Callback), path
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise SystemExit(
                f"Port {port} ist bereits belegt (Errno 98).\n"
                f"Beende den alten OAuth-Prozess:  ss -ltnp | grep :{port}\n"
                "Oder nutze einen anderen Port und registriere die neue URI:\n"
                f"  python3 scripts/social_oauth.py <provider> --serve --port <frei>\n"
                "Die ausgegebene Redirect-URI muss exakt in der App stehen."
            ) from exc
        raise


def linkedin_url(env: dict[str, str], state: str, redirect_uri: str | None = None) -> str:
    _require(env, "LINKEDIN_CLIENT_ID")
    params = {
        "response_type": "code",
        "client_id": env["LINKEDIN_CLIENT_ID"],
        "redirect_uri": _redirect(env, "LINKEDIN_REDIRECT_URI", redirect_uri),
        "scope": env.get("LINKEDIN_SCOPES", "w_member_social"),
        "state": state,
    }
    return "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(params)


def facebook_url(env: dict[str, str], state: str, redirect_uri: str | None = None) -> str:
    _require(env, "FACEBOOK_APP_ID")
    params = {
        "client_id": env["FACEBOOK_APP_ID"],
        "redirect_uri": _redirect(env, "FACEBOOK_REDIRECT_URI", redirect_uri),
        "state": state,
        "scope": env.get("FACEBOOK_SCOPES",
                         "pages_show_list,pages_manage_posts,pages_read_engagement"),
        "response_type": "code",
    }
    return "https://www.facebook.com/v21.0/dialog/oauth?" + urllib.parse.urlencode(params)


def linkedin_exchange(env: dict[str, str], code: str,
                      redirect_uri: str | None = None) -> dict[str, str]:
    _require(env, "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET")
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={"grant_type": "authorization_code", "code": code,
              "redirect_uri": _redirect(env, "LINKEDIN_REDIRECT_URI", redirect_uri),
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
    return {"provider": "linkedin", "token": "gespeichert",
            "author": author or "nicht ermittelt"}


def facebook_exchange(env: dict[str, str], code: str, page_id: str = "",
                      redirect_uri: str | None = None) -> dict[str, str]:
    _require(env, "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET")
    resp = requests.get(
        "https://graph.facebook.com/v21.0/oauth/access_token",
        params={"client_id": env["FACEBOOK_APP_ID"],
                "client_secret": env["FACEBOOK_APP_SECRET"],
                "redirect_uri": _redirect(env, "FACEBOOK_REDIRECT_URI", redirect_uri),
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
        raise SystemExit("Keine Facebook-Page sichtbar (App-Rolle/Page-Rolle prüfen)")
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
            "pages_visible": len(data), "instagram_user_id": ig.get("id", "")}


class _Callback(BaseHTTPRequestHandler):
    code = ""
    error = ""
    error_description = ""
    expected_state = ""
    expected_path = "/oauth/callback"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        if parsed.path != self.expected_path:
            self.send_response(404)
            self.end_headers()
            return
        if q.get("error", [""])[0]:
            self.__class__.error = q["error"][0]
            self.__class__.error_description = q.get("error_description", [""])[0]
            self._html(400, "<h2>OAuth-Fehler</h2><p>Details stehen im Terminal.</p>")
            return
        if q.get("state", [""])[0] != self.expected_state:
            self._html(400, "<h2>State mismatch</h2>")
            return
        code = q.get("code", [""])[0]
        if not code:
            self._html(400, "<h2>Kein Code im Callback.</h2>")
            return
        self.__class__.code = code
        self._html(200, "<h2>OAuth-Code empfangen.</h2><p>Fenster kann geschlossen werden.</p>")

    def _html(self, status: int, body: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args: Any) -> None:
        return


def serve(provider: str, env: dict[str, str], page_id: str = "",
          redirect_override: str | None = None, port_override: int | None = None,
          timeout: float = 300.0, open_browser: bool = False) -> int:
    key = "LINKEDIN_REDIRECT_URI" if provider == "linkedin" else "FACEBOOK_REDIRECT_URI"
    uri = _redirect(env, key, redirect_override)
    if port_override:
        uri = redirect_with_port(uri, port_override)
        print(f"Hinweis: Port überschrieben. Diese URI muss registriert sein:\n  {uri}")
    if provider == "linkedin":
        _require(env, "LINKEDIN_CLIENT_SECRET")
    else:
        _require(env, "FACEBOOK_APP_SECRET")

    state = secrets.token_urlsafe(24)
    _Callback.code = ""
    _Callback.error = ""
    _Callback.error_description = ""
    _Callback.expected_state = state
    _Callback.expected_path = urllib.parse.urlparse(uri).path or "/oauth/callback"
    server, _path = _make_server(uri)
    url = (linkedin_url(env, state, uri) if provider == "linkedin"
           else facebook_url(env, state, uri))
    print(f"Redirect-URI (muss exakt in der App registriert sein):\n  {uri}\n")
    print(f"Auth-URL ({provider}):\n{url}\n")
    print(f"Warte auf Callback auf {uri} (Timeout {int(timeout)} s) ...")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline and not _Callback.code and not _Callback.error:
            server.timeout = max(1.0, min(5.0, deadline - time.monotonic()))
            server.handle_request()
    except KeyboardInterrupt:
        print("\nAbgebrochen (Ctrl+C). Port wird freigegeben.")
        return 130
    finally:
        server.server_close()

    if _Callback.error:
        print(f"OAuth-Fehler: {_Callback.error} — {_Callback.error_description}")
        return 1
    if not _Callback.code:
        print("Timeout: kein Callback empfangen. Läuft der Browser auf demselben Rechner?")
        return 2
    result = (linkedin_exchange(env, _Callback.code, uri) if provider == "linkedin"
              else facebook_exchange(env, _Callback.code, page_id, uri))
    print(result)
    print(f"Tokens in {ENV_FILE} gespeichert (chmod 600).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OAuth-Bootstrap für LinkedIn/Facebook")
    ap.add_argument("provider", choices=("linkedin", "facebook"))
    ap.add_argument("--url", action="store_true", help="nur Auth-URL ausgeben")
    ap.add_argument("--serve", action="store_true", help="lokalen Callback-Server starten")
    ap.add_argument("--exchange", metavar="CODE", help="Authorization-Code einlösen")
    ap.add_argument("--redirect-uri", default=None,
                    help="überschreibt *_REDIRECT_URI für diesen Lauf")
    ap.add_argument("--port", type=int, default=None,
                    help="Port überschreiben (neue URI muss registriert sein)")
    ap.add_argument("--timeout", type=float, default=300.0,
                    help="Sekunden bis der Callback-Server aufgibt (Default 300)")
    ap.add_argument("--open-browser", action="store_true",
                    help="Browser automatisch öffnen (auf WSL/Headless oft defekt)")
    ap.add_argument("--page-id", default="", help="Facebook-Page-ID (sonst erste sichtbare)")
    args = ap.parse_args(argv)
    env = load_env()
    state = secrets.token_urlsafe(24)
    redirect = args.redirect_uri
    if args.port:
        key = "LINKEDIN_REDIRECT_URI" if args.provider == "linkedin" else "FACEBOOK_REDIRECT_URI"
        redirect = redirect_with_port(_redirect(env, key, redirect), args.port)

    if args.url:
        print(linkedin_url(env, state, redirect) if args.provider == "linkedin"
              else facebook_url(env, state, redirect))
        return 0
    if args.exchange:
        result = (linkedin_exchange(env, args.exchange, redirect)
                  if args.provider == "linkedin"
                  else facebook_exchange(env, args.exchange, args.page_id, redirect))
        print(result)
        return 0
    if args.serve:
        return serve(args.provider, env, args.page_id, redirect, args.port,
                     args.timeout, args.open_browser)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
