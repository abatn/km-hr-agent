"""Schlüssel für die Kontakt-Sperre: Firma + Stellenanzeige."""
from __future__ import annotations

import hashlib
import re
import unicodedata


def _ascii(text: str) -> str:
    """Wandelt Text in reines ASCII um (Umlaute werden transliteriert)."""
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")


def _slug(text: str) -> str:
    """Macht aus freiem Text einen kleingeschriebenen Bindestrich-Slug."""
    return re.sub(r"[^a-z0-9]+", "-", _ascii(text).lower()).strip("-")


RECHTSFORM = re.compile(
    r"\s+(gmbh\s*&\s*co\.?\s*kg|gmbh|ag|se|kg|ohg|e\.?\s?v\.?|sarl|sas|sa|ug|mbh)\.?$",
    re.I,
)


def firma_key(name: str) -> str:
    """Normiert einen Firmennamen: Rechtsform am Ende weg, dann Slug.

    Beispiele: "Permacon GmbH" -> "permacon",
    "AWO Regionalverband Mitte-West Thüringen e.V." ->
    "awo-regionalverband-mitte-west-thuringen".
    """
    text = re.sub(r"\s+", " ", (name or "").strip())
    # Rechtsform kann mehrfach am Ende stehen ("Foo GmbH AG").
    while True:
        neu = RECHTSFORM.sub("", text).strip()
        if neu == text:  # Schutz gegen Endlosschleife
            text = neu
            break
        text = neu
    return _slug(text)


def titel_norm(titel: str) -> str:
    """Normiert einen Stellentitel (nur die ersten 80 Zeichen zählen)."""
    return _slug((titel or "")[:80])


def anzeige_keys(url: str, firma: str, titel: str) -> list[str]:
    """Liefert die Sperr-Schlüssel einer Anzeige: ID zuerst, dann Titel-Hash.

    Enthält die URL eine Anzeigen-ID (Bundesagentur, EURES, ...), kommt
    ``id:<ID>`` zuerst. Der Hash aus Firma und Titel ist immer dabei.
    """
    keys: list[str] = []
    m = re.search(r"(?:jobdetail|jv-details|jobAdvertisements)/([^/?#\s\)]+)", url or "")
    if m:
        keys.append(f"id:{m.group(1)}")
    basis = f"{firma_key(firma)}|{titel_norm(titel)}"
    keys.append(f"hash:{hashlib.sha1(basis.encode('utf-8')).hexdigest()[:16]}")
    return keys


def ist_gesperrt(keys: list[str], sperre: set[str] | list[str]) -> bool:
    """True, wenn mindestens ein Schlüssel in der Sperre steht."""
    return any(k in sperre for k in keys)
