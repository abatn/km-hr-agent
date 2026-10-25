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


def parse_redirect(uri: str, listen_port: int = 8765) -> tuple[str, int, str, bool]:
    """Liefert (bind_host, bind_port, path, proxy_mode).

    - http://localhost|127.0.0.1:  lokaler Server direkt auf Host/Port.
    - https://...:                 Caddy/Reverse-Proxy terminiert TLS und
                                   leitet den Pfad an 127.0.0.1:<listen_port>.
      Das ist der produktive Weg; LinkedIn verlangt HTTPS.
    """
    p = urllib.parse.urlparse(uri)
    path = p.path or "/oauth/callback"
    if p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1"):
        port = p.port or 80
        bind_host = "127.0.0.1" if p.hostname == "localhost" else p.hostname
        return bind_host, port, path, False
    if p.scheme == "https" and p.hostname:
        return "127.0.0.1", listen_port, path, True
    raise SystemExit(
        f"Ungültige Redirect-URI: {uri!r}\n"
        "Erlaubt: https://<öffentlicher-host>/oauth/callback (Produktion) "
        "oder http://localhost:<port>/oauth/callback (nur lokale Tests).")


def _make_server(uri: str, listen_port: int = 8765) -> tuple[HTTPServer, str, bool]:
    bind_host, port, path, proxy_mode = parse_redirect(uri, listen_port)

    class _Server(HTTPServer):
        # Erlaubt erneutes Binden nach Ctrl+C/TIME_WAIT auf demselben Port.
        allow_reuse_address = True

    try:
        return _Server((bind_host, port), _Callback), path, proxy_mode
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
        "scope": env.get("LINKEDIN_SCOPES", "openid profile w_member_social"),
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
    author = env.get("LINKEDIN_AUTHOR_URN", "").strip()
    if not author:
        headers = {"Authorization": f"Bearer {token}"}
        # userinfo braucht openid/profile; /v2/me braucht r_liteprofile.
        for url, field in (("https://api.linkedin.com/v2/userinfo", "sub"),
                           ("https://api.linkedin.com/v2/me", "id")):
            user = requests.get(url, headers=headers, timeout=30)
            if not user.ok:
                continue
            value = user.json().get(field, "")
            if value:
                author = f"urn:li:person:{value}"
                break
    updates = {"LINKEDIN_ACCESS_TOKEN": token}
    if author:
        updates["LINKEDIN_AUTHOR_URN"] = author
    update_env(ENV_FILE, updates)
    warning = ""
    if not author:
        warning = ("LINKEDIN_AUTHOR_URN fehlt: Scopes 'openid profile' "
                   "(Sign In with LinkedIn using OpenID Connect) hinzufügen "
                   "und neu autorisieren.")
    return {"provider": "linkedin", "token": "gespeichert",
            "author": author or "FEHLT", "warning": warning}


def facebook_fields(env: dict[str, str]) -> str:
    """Page-Felder; Instagram nur bei explizit aktivierter Permission."""
    fields = "id,name,access_token"
    if env.get("FACEBOOK_FETCH_INSTAGRAM", "0").strip().lower() in ("1", "true", "yes"):
        fields += ",instagram_business_account"
    return fields


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
        params={"access_token": user_token, "fields": facebook_fields(env)}, timeout=30)
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
          timeout: float = 300.0, open_browser: bool = False,
          listen_port: int = 8765) -> int:
    key = "LINKEDIN_REDIRECT_URI" if provider == "linkedin" else "FACEBOOK_REDIRECT_URI"
    uri = _redirect(env, key, redirect_override)
    if port_override and urllib.parse.urlparse(uri).scheme == "https":
        raise SystemExit(
            "Bei einer HTTPS-Redirect-URI keinen --port verwenden.\n"
            "Der öffentliche Port ist 443; der lokale Helper lauscht auf "
            f"--listen-port (Default {listen_port}).")
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
    server, _path, proxy_mode = _make_server(uri, listen_port)
    url = (linkedin_url(env, state, uri) if provider == "linkedin"
           else facebook_url(env, state, uri))
    print(f"Redirect-URI (muss exakt in der App registriert sein):\n  {uri}\n")
    if proxy_mode:
        print(f"Öffentlicher HTTPS-Callback; lokaler Helper lauscht auf "
              f"127.0.0.1:{listen_port}. Caddy/Proxy muss "
              f"{_Callback.expected_path} dorthin leiten.\n")
    else:
        print(f"Lokaler Callback-Server: {uri}\n")
    print(f"Auth-URL ({provider}):\n{url}\n")
    print(f"Warte auf Callback (Timeout {int(timeout)} s) ...")
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
        print("Timeout: kein Callback empfangen. Bei HTTPS: Caddy-Route und "
              "Firewall prüfen; bei HTTP: Browser auf demselben Rechner?")
        return 2
    result = (linkedin_exchange(env, _Callback.code, uri) if provider == "linkedin"
              else facebook_exchange(env, _Callback.code, page_id, uri))
    print(result)
    if result.get("warning"):
        print("WARNUNG:", result["warning"])
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
                    help="nur lokale HTTP-URI: Port überschreiben (neu registrieren)")
    ap.add_argument("--listen-port", type=int, default=8765,
                    help="lokaler Helper-Port bei HTTPS-Redirect (Default 8765)")
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
        base = _redirect(env, key, redirect)
        if urllib.parse.urlparse(base).scheme == "https":
            raise SystemExit("--port ist nur für lokale HTTP-URIs. "
                             "Bei HTTPS den Helper-Port mit --listen-port setzen.")
        redirect = redirect_with_port(base, args.port)

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
                     args.timeout, args.open_browser, args.listen_port)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
