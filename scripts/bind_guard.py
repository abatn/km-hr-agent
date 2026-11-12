"""Start-Guard für die Bindungsadresse der WebUI – fail-closed.

Hintergrund (12.11.2026): Die lokale Dev-Instanz lauschte über ein
systemd-Drop-in auf ``0.0.0.0:8080`` und war damit aus dem Internet
erreichbar, obwohl das Live-Admin-Konto noch das alte Seed-Passwort trägt
(siehe ``knowledge/system/configuration-secrets.md`` §(f)). Der Default
``127.0.0.1`` allein reicht nicht: Ein Drop-in oder eine ``.env`` kann ihn
überschreiben.

Regel:
* Loopback (``127.0.0.0/8``, ``::1``, ``localhost``) ist immer erlaubt.
* Jede andere Adresse – auch ``0.0.0.0``/``::`` – bricht den Start ab,
  solange nicht ``KMHR_ALLOW_PUBLIC_BIND=1`` (auch ``true``/``yes``)
  ausdrücklich gesetzt ist. Öffentlicher Zugang gehört hinter den
  Reverse-Proxy (Caddy/Cloudflare) auf Loopback.

Spec: knowledge/system/configuration-secrets.md §(l).
"""
from __future__ import annotations

import ipaddress
import os

ENV_HOST = "KMHR_HOST"
ENV_OPT_IN = "KMHR_ALLOW_PUBLIC_BIND"
DEFAULT_HOST = "127.0.0.1"

_LOOPBACK_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost"}


class BindConfigError(ValueError):
    """Die konfigurierte Bindungsadresse ist ohne Opt-in nicht zulässig."""


def is_loopback_host(host: str) -> bool:
    """True für Loopback-Adressen und ``localhost``-Namen."""
    h = str(host or "").strip().strip("[]").lower().rstrip(".")
    if h in _LOOPBACK_NAMES or h.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def resolve_host(env: dict | None = None) -> str:
    """Gibt die geprüfte Bindungsadresse zurück (Default ``127.0.0.1``).

    Raises:
        BindConfigError: Adresse ist nicht Loopback und
            ``KMHR_ALLOW_PUBLIC_BIND`` ist nicht ausdrücklich gesetzt.
    """
    werte = os.environ if env is None else env
    host = str(werte.get(ENV_HOST, "") or "").strip() or DEFAULT_HOST
    if is_loopback_host(host):
        return host
    opt_in = str(werte.get(ENV_OPT_IN, "") or "").strip().lower() in ("1", "true", "yes")
    if not opt_in:
        raise BindConfigError(
            f"{ENV_HOST}={host!r} bindet nicht auf Loopback. Die WebUI darf nur "
            "über den Reverse-Proxy erreichbar sein; das Live-Admin-Konto trägt "
            "noch das alte Seed-Passwort. Nur für bewusstes LAN/Diagnose: "
            f"{ENV_OPT_IN}=1 setzen. Details: "
            "knowledge/system/configuration-secrets.md §(l)."
        )
    return host
