"""Registrierungs-Haertung: E-Mail-Pruefung (Maßnahme 6) + Honeypot/Timing (5a).

Framework-frei (kein NiceGUI-Import) wie `webui/db.py`; genutzt von
`webui/pages/login.py` und den Tests. Spec:
`knowledge/system/registration-hardening.md`.

Zwei Schichten, beide per Env-Flag abschaltbar (Rollback ohne Migration):

* `KMHR_REGISTRATION_STRICT_EMAIL` (Default 1): strikte E-Mail-Pruefung nur fuer
  die Registrierungsfelder `r_email`/`er_email`. Flag 0 = Altverhalten
  (Ablehnung wird nur geloggt, nie durchgesetzt).
* `KMHR_REGISTRATION_HONEYPOT` (Default 1): unsichtbares Lockfeld +
  Mindest-Fuellzeit. Flag 0 = Altverhalten (keine Pruefung).

Der Login bleibt in jedem Fall tolerant: Seed-/E2E-Konten tragen reservierte
Adressen (`@example.invalid`), die nur bei der Registrierung abgelehnt werden
(`email_field_valid` vs. `registration_email_field_valid`).

Keine neue DB-Tabelle: der Zustand ist der Render-Zeitpunkt der Seite, den der
Aufrufer als `time.monotonic()`-Wert an `registration_blocked` gibt.
"""
from __future__ import annotations

import os

from email_validator import EmailNotValidError, validate_email

# Env-Flags (Muster: `webui/db.py::welcome_mail_enabled`, `webui/billing.py`).
STRICT_EMAIL_FLAG = "KMHR_REGISTRATION_STRICT_EMAIL"
HONEYPOT_FLAG = "KMHR_REGISTRATION_HONEYPOT"

# Grenzen aus RFC 5321/5322 — `email-validator` prueft sie nicht selbst
# (gemessen 12.11.2026: 65 Zeichen im Lokalteil und TLD `c` werden akzeptiert).
EMAIL_MAX_LEN = 254
LOCAL_MAX_LEN = 64
MIN_TLD_LEN = 2

# Mindest-Fuellzeit in Sekunden. Konservativ: E2E wartet ~3,7 s vor dem Absenden,
# Autofill-Nutzer liegen typisch darunter. Nur zusammen mit dem Honeypot-Flag.
MIN_FILL_SECONDS = 3.0

# IANA-Reserve (RFC 2606/6761): `example` ist eine TLD, `example.com/.net/.org`
# sind reservierte Domaenen. `.com` selbst bleibt erlaubt.
RESERVED_TLDS = frozenset({"invalid", "test", "localhost", "local", "example"})
RESERVED_DOMAINS = frozenset({"example.com", "example.net", "example.org"})


def _flag_enabled(name: str) -> bool:
    """Flag mit sicherem Default 1; nur ausdrueckliche Off-Werte schalten ab."""
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no", "off"}


def strict_email_enabled() -> bool:
    return _flag_enabled(STRICT_EMAIL_FLAG)


def honeypot_enabled() -> bool:
    return _flag_enabled(HONEYPOT_FLAG)


def normalize_email(raw: str | None) -> str:
    """Wie die Registrierungs-Handler: Leerraum weg, Kleinschreibung."""
    return (raw or "").strip().lower()


# ─── E-Mail-Pruefung (Maßnahme 6) ──────────────────────────────────────────

def check_registration_email(raw: str | None) -> tuple[bool, str]:
    """Strikte Pruefung fuer Registrierungen. Rueckgabe: (ok, Grund-Code).

    Grund-Codes (stabil, ohne Adresse — DSGVO: keine PII ins Log):
    `ok`, `format`, `total_len`, `local_len`, `tld`, `reserved_tld`,
    `reserved_domain`.

    `check_deliverability=False`: keine DNS-/MX-Abfrage im Registrierungspfad
    (kein Resolver-Leak, keine Latenz).
    """
    email = normalize_email(raw)
    if not email:
        return False, "format"
    if len(email) > EMAIL_MAX_LEN:
        return False, "total_len"
    local, _, domain = email.rpartition("@")
    if not local or not domain:
        return False, "format"
    if len(local) > LOCAL_MAX_LEN:
        return False, "local_len"
    try:
        info = validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        # `email-validator` weist Reserve-TLDs (`.invalid`, `.test`, `.localhost`)
        # selbst ab, nennt aber nur "reserved name". Fuer einen stabilen Grund
        # unterscheiden wir hier nach: nur mit Punkt ist es eine TLD-Regel,
        # `anna@localhost` oder eine IP bleibt ein Formatfehler.
        tld_raw = domain.strip().rstrip(".").lower().rsplit(".", 1)[-1]
        if "." in domain and tld_raw in RESERVED_TLDS:
            return False, "reserved_tld"
        return False, "format"
    domain_norm = (info.domain or "").strip().lower().rstrip(".")
    labels = domain_norm.split(".")
    if len(labels) < 2:
        return False, "format"
    tld = labels[-1]
    if tld in RESERVED_TLDS:
        return False, "reserved_tld"
    if len(tld) < MIN_TLD_LEN:
        return False, "tld"
    if domain_norm in RESERVED_DOMAINS:
        return False, "reserved_domain"
    return True, "ok"


def registration_email_blocked(raw: str | None) -> bool:
    """Serverseitige Entscheidung: True = Registrierung ablehnen.

    Bei `KMHR_REGISTRATION_STRICT_EMAIL=0` wird nur geloggt (Altverhalten);
    die Client-Validierung `registration_email_field_valid` ist dann ebenfalls
    tolerant.
    """
    ok, grund = check_registration_email(raw)
    if ok:
        return False
    if strict_email_enabled():
        return True
    print(f"[registration_guard] E-Mail abgelehnt (Flag aus, log-only): grund={grund}")
    return False


def email_field_valid(value: str | None) -> bool:
    """Tolerante Client-Validierung der drei Login-Felder (Altverhalten).

    Bewusst unveraendert: `"@" in v and "." in v`. Seed-/E2E-Konten
    (`@example.invalid`) muessen sich weiter einloggen koennen.
    """
    v = value or ""
    return "@" in v and "." in v


def registration_email_field_valid(value: str | None) -> bool:
    """Client-Validierung der Registrierungsfelder (`r_email`, `er_email`).

    Leeres Feld gilt hier als gueltig — die Pflichtfeld-Meldung kommt aus dem
    Handler. Bei Flag 0 exakt das Altverhalten.
    """
    v = (value or "").strip()
    if not v:
        return True
    if not strict_email_enabled():
        return email_field_valid(v)
    ok, _ = check_registration_email(v)
    return ok


# ─── Honeypot + Mindest-Fuellzeit (Maßnahme 5a) ────────────────────────────

def honeypot_triggered(value: str | None) -> bool:
    """True, wenn das unsichtbare Lockfeld gefuellt wurde."""
    return bool((value or "").strip())


def too_fast(elapsed_seconds: float, min_seconds: float | None = None) -> bool:
    """True, wenn das Formular schneller als `MIN_FILL_SECONDS` abgeschickt wurde."""
    grenze = MIN_FILL_SECONDS if min_seconds is None else min_seconds
    return elapsed_seconds < grenze


def registration_blocked(honeypot_value: str | None, elapsed_seconds: float) -> bool:
    """Eine Entscheidung fuer beide Schichten; Flag 0 = keine Pruefung.

    Loggt nur den Grund, nie die Eingabe.
    """
    if not honeypot_enabled():
        return False
    if honeypot_triggered(honeypot_value):
        print("[registration_guard] Registrierung blockiert: Honeypot gefuellt")
        return True
    if too_fast(elapsed_seconds):
        print(f"[registration_guard] Registrierung blockiert: zu schnell ({elapsed_seconds:.2f}s)")
        return True
    return False
