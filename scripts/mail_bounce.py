"""IMAP-DSN-Poller für Zustellfehler (Bounce), 30.10.2026.

Spec: knowledge/system/agent-automation.md §3.2. Standardmäßig aus
(KMHR_BOUNCE_POLL_ENABLED=0). Der Poller liest nur (BODY.PEEK, readonly),
wertet Delivery-Status-Berichte mit Action=failed und Status 5.x.x aus und
schreibt je Konto und DSN genau eine agent_tasks-Zeile
(task_type 'mail_bounce', Status done). Adressen werden weder geloggt noch
in die Ablage geschrieben; die Rückgabe enthält nur Zähler.
"""
from __future__ import annotations

import hashlib
import imaplib
import os
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser

SEARCH_DAYS = 14
MAX_MESSAGES_PER_RUN = 200


def _dsn_blocks(part) -> list[dict]:
    """Feldblöcke eines message/delivery-status-Teils (kleingeschriebene Keys)."""
    payload = part.get_payload()
    if isinstance(payload, list):
        return [{k.lower(): str(v) for k, v in sub.items()} for sub in payload]
    blocks: list[dict] = []
    cur: dict = {}
    for line in str(payload).splitlines():
        if not line.strip():
            if cur:
                blocks.append(cur)
                cur = {}
            continue
        if line[0] in " \t" or ":" not in line:
            continue
        k, v = line.split(":", 1)
        cur[k.strip().lower()] = v.strip()
    if cur:
        blocks.append(cur)
    return blocks


def parse_dsn(raw: bytes) -> list[dict]:
    """Harte Zustellfehler (Action failed, Status 5.x.x) aus einer DSN-Nachricht.

    Rückgabe: Liste von {"address", "status", "message_id"}. Keine DSN -> [].
    Weiche Fehler (4.x.x, delayed) werden ignoriert: der MTA versucht erneut.
    """
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    if msg.get_content_type() != "multipart/report":
        return []
    if (msg.get_param("report-type") or "").lower() != "delivery-status":
        return []
    message_id = str(msg.get("Message-ID") or "").strip()
    treffer: list[dict] = []
    for part in msg.iter_parts():
        if part.get_content_type() != "message/delivery-status":
            continue
        for block in _dsn_blocks(part):
            if "final-recipient" not in block:
                continue
            adresse = block["final-recipient"].split(";", 1)[-1].strip()
            action = block.get("action", "").strip().lower()
            status = block.get("status", "").strip()
            if action == "failed" and status.startswith("5.") and "@" in adresse:
                treffer.append({"address": adresse, "status": status,
                                "message_id": message_id})
    return treffer


def dsn_key(message_id: str, role: str, subject_id: int, index: int) -> str:
    """Idempotenz-Schlüssel je DSN, Empfänger-Position und Konto (ohne Adresse)."""
    basis = f"{message_id}|{role}|{subject_id}|{index}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def poll_bounces(*, env=None, now=None, imap_factory=None) -> dict:
    """Ein Poll-Lauf. Standardmäßig No-op (KMHR_BOUNCE_POLL_ENABLED != 1)."""
    env = os.environ if env is None else env
    if env.get("KMHR_BOUNCE_POLL_ENABLED", "0") != "1":
        return {"status": "disabled"}
    host = env.get("KMHR_IMAP_HOST", "").strip()
    user = env.get("KMHR_IMAP_USER", "").strip()
    password = env.get("KMHR_IMAP_PASSWORD", "")
    if not (host and user and password):
        return {"status": "nicht_konfiguriert"}
    port = int(env.get("KMHR_IMAP_PORT", "993") or 993)
    mailbox = env.get("KMHR_IMAP_MAILBOX", "INBOX") or "INBOX"
    now = now or datetime.now(timezone.utc)
    factory = imap_factory or imaplib.IMAP4_SSL

    from webui import db as _db

    zaehler = {"gesehen": 0, "erfasst": 0, "duplikat": 0, "unbekannt": 0}
    mailbox_conn = factory(host, port)
    try:
        mailbox_conn.login(user, password)
        mailbox_conn.select(mailbox, readonly=True)
        since = (now - timedelta(days=SEARCH_DAYS)).strftime("%d-%b-%Y")
        typ, data = mailbox_conn.search(None, "SINCE", since)
        if typ != "OK" or not data or not data[0]:
            return {"status": "ok", **zaehler}
        for num in data[0].split()[-MAX_MESSAGES_PER_RUN:]:
            typ, parts = mailbox_conn.fetch(num, "(BODY.PEEK[])")
            if typ != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            raw = parts[0][1]
            zaehler["gesehen"] += 1
            for index, treffer in enumerate(parse_dsn(raw)):
                konto = _db.find_account_for_mail(treffer["address"])
                if konto is None:
                    zaehler["unbekannt"] += 1
                    continue
                role, subject_id = konto
                mid = treffer["message_id"] or hashlib.sha256(raw).hexdigest()
                key = dsn_key(mid, role, subject_id, index)
                if _db.record_mail_bounce(role, subject_id, key, treffer["status"]):
                    zaehler["erfasst"] += 1
                else:
                    zaehler["duplikat"] += 1
    finally:
        try:
            mailbox_conn.logout()
        except Exception:
            pass
    return {"status": "ok", **zaehler}
