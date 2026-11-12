"""Basis-URL für Links in Mails – eine Quelle, fail-closed.

Hintergrund (12.11.2026): Ein Passwort-Reset wurde mit
``http://127.0.0.1:8080/login?reset=…`` verschickt, weil eine Dev-Instanz
``KMHR_PUBLIC_BASE_URL`` auf Loopback stehen hatte und der Runner den Wert
ungeprüft übernahm. Der Link ist für Empfänger unbrauchbar – und ein
Loopback-/HTTP-Link in einer echten Mail ist ein Konfigurationsfehler.

Regel:
* ``KMHR_PUBLIC_BASE_URL`` ist **Pflicht**. Fehlt sie, wird kein Link erzeugt.
* Im Betrieb (``KMHR_DEV`` nicht gesetzt) muss die URL ``https`` sein und
  darf nicht auf localhost/private/link-local Adressen zeigen.
* Nur mit ``KMHR_DEV=1`` sind ``http`` und lokale Hosts erlaubt (lokale
  Entwicklung). Ein öffentlicher Host bleibt auch dort ``https``-pflichtig.

Spec: knowledge/system/configuration-secrets.md §(g)/(h),
knowledge/system/agent-automation.md (Mail-Links).
"""
from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlsplit

ENV_NAME = "KMHR_PUBLIC_BASE_URL"

_LOCAL_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost"}


class MailLinkConfigError(ValueError):
    """Die konfigurierte Basis-URL ist für Mail-Links nicht zulässig."""


def dev_mode(env: dict | None = None) -> bool:
    """True, wenn ``KMHR_DEV`` explizit auf 1/true/yes steht."""
    werte = os.environ if env is None else env
    return str(werte.get("KMHR_DEV", "")).strip().lower() in ("1", "true", "yes")


def _is_local_host(host: str) -> bool:
    """Loopback, private, link-local oder anderweitig nicht-öffentliche Adresse."""
    host = host.strip().strip("[]").lower().rstrip(".")
    if host in _LOCAL_NAMES or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    # is_global ist nur für öffentlich routbare Adressen True; deckt Loopback,
    # private, link-local, reservierte, unspezifizierte und CGNAT-Bereiche ab.
    return not ip.is_global


def public_base_url(env: dict | None = None) -> str:
    """Gibt die geprüfte Basis-URL ohne abschließenden ``/`` zurück.

    Raises:
        MailLinkConfigError: Variable fehlt, ist keine gültige http(s)-URL
            oder im Betrieb nicht öffentlich/https.
    """
    werte = os.environ if env is None else env
    raw = str(werte.get(ENV_NAME, "") or "").strip()
    if not raw:
        raise MailLinkConfigError(
            f"{ENV_NAME} fehlt. Ohne öffentliche Basis-URL werden keine "
            "Mail-Links erzeugt (fail-closed). Betrieb: "
            "https://jobs.hanibal-ai.com"
        )
    base = raw.rstrip("/")
    teile = urlsplit(base)
    if teile.scheme not in ("http", "https") or not teile.hostname:
        raise MailLinkConfigError(
            f"{ENV_NAME}={raw!r} ist keine gültige http(s)-URL."
        )
    if teile.username or teile.password:
        raise MailLinkConfigError(
            f"{ENV_NAME} darf keine Zugangsdaten enthalten."
        )
    if teile.query or teile.fragment:
        raise MailLinkConfigError(
            f"{ENV_NAME}={raw!r} darf keine Query/Fragment enthalten."
        )
    lokal = _is_local_host(teile.hostname)
    if not dev_mode(werte):
        if lokal:
            raise MailLinkConfigError(
                f"{ENV_NAME}={raw!r} zeigt auf localhost/privates Netz. Im "
                "Betrieb muss die öffentliche URL stehen, sonst sind die "
                "Links für Empfänger unbrauchbar. Lokale Entwicklung: "
                "KMHR_DEV=1 setzen."
            )
        if teile.scheme != "https":
            raise MailLinkConfigError(
                f"{ENV_NAME}={raw!r} muss im Betrieb https sein."
            )
    elif not lokal and teile.scheme != "https":
        raise MailLinkConfigError(
            f"{ENV_NAME}={raw!r} muss auch im Dev-Modus für öffentliche "
            "Hosts https sein."
        )
    return base
