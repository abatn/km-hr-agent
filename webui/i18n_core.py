"""Framework-freie i18n-Kernschicht (gettext) fuer KM-HR-Agent.

Spec: knowledge/system/i18n.md + knowledge/system/i18n-runner-chain.md §7.1
(Variante B, P1 07.10.2026).

WARUM GETRENNT: `webui/i18n.py` haengt an NiceGUI (`app.storage.user` =
Session-Sprache). Der Agent-Runner laeuft in einem eigenen Prozess **ohne**
NiceGUI-Session und darf deshalb nur diese Kernschicht importieren. Diese
Datei importiert **kein** nicegui — nur gettext + stdlib.

Eine Katalogquelle: `webui/locales` (LOCALES_DIR).
"""
from __future__ import annotations

import functools
import gettext
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
SUPPORTED = ("de", "en", "fr", "ar")
DEFAULT = "de"


@functools.lru_cache(maxsize=None)
def _translation(lang: str) -> gettext.GNUTranslations:
    """gettext-Katalog je Sprache (einmalig geladen, fallback=True)."""
    return gettext.translation("messages", str(LOCALES_DIR),
                               languages=[lang], fallback=True)


@functools.lru_cache(maxsize=None)
def _translate(msgid: str, lang: str) -> str:
    """Reine gettext-Uebersetzung je (msgid, lang) — gecached.

    `de` = Identitaet (Original). Unbekannter msgid -> Original (gettext-
    Fallback). Das Formatieren (`**fmt`) liegt BEWUSST ausserhalb des Caches,
    weil die Formatwerte nicht in den Cache-Schluessel gehoeren.
    """
    if lang == DEFAULT:
        return msgid
    try:
        hit = _translation(lang).gettext(msgid)
    except Exception:
        return msgid
    return hit or msgid


def tr(msgid: str, lang: str, **fmt) -> str:
    """Uebersetzt `msgid` nach `lang` (Fallback: Original; `de` = Identitaet).

    `lang` nicht in SUPPORTED -> DEFAULT. `**fmt` wird via `.format(**fmt)`
    eingesetzt (Konvention: keine f-Strings in msgids, Ruff INT001).
    """
    if lang not in SUPPORTED:
        lang = DEFAULT
    result = _translate(msgid, lang)
    if fmt:
        result = result.format(**fmt)
    return result
