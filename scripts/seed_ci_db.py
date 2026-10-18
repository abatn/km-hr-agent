#!/usr/bin/env python3
"""Erzeugt aus der Live-DB einen ANONYMISIERTEN Seed für die CI.

Zweck: Die Tests brauchen `data/feedback.db` (Struktur + IDs/Status/Fixtures), aber die
echte DB enthält personenbezogene Daten (DSGVO) und ist daher nicht im Repo.
Dieses Skript ersetzt alle personenbezogenen Felder durch synthetische Werte und
behält IDs, Status, Zähler und Datumswerte — die Test-Erwartungen bleiben erfüllt.

Aufruf:
    python3 scripts/seed_ci_db.py [QUELLE] [ZIEL]
    # Default: data/feedback.db  →  tests/fixtures/seed.db
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "feedback.db"
DST = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "tests" / "fixtures" / "seed.db"

# Pseudonyme Muster (kein Personenbezug)
NAMES = ["Kandidat Eins", "Kandidat Zwei", "Kandidat Drei", "Kandidat Vier",
         "Kandidat Fuenf", "Kandidat Sechs", "Kandidat Sieben", "Kandidat Acht"]
FIRMEN = ["Beispielfirma GmbH", "Musterfirma AG", "Testfirma UG", "Demofirma GmbH"]


def _email(i: int) -> str:
    return f"kandidat{i}@example.invalid"


def main() -> int:
    if not SRC.exists():
        sys.exit(f"Quelle fehlt: {SRC}")
    DST.parent.mkdir(parents=True, exist_ok=True)
    if DST.exists():
        DST.unlink()
    src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    dst = sqlite3.connect(str(DST))
    try:
        src.backup(dst)

        # 18.10.2026: password_resets garantiert im Seed anlegen (falls die
        # Quell-DB sie noch nicht hat — die App legt sie beim Start an).
        dst.execute("""CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP
        )""")
        dst.commit()

        def run(sql: str, params: tuple = ()) -> None:
            dst.execute(sql, params)

        # candidates: Name/E-Mail/Telefon/CV-Datei/CV-Text anonymisieren
        for (cid,) in dst.execute("SELECT id FROM candidates").fetchall():
            run("UPDATE candidates SET email=?, name=?, telefon=?, "
                "lebenslauf_datei=?, lebenslauf_text=?, aktuelle_position=? WHERE id=?",
                (_email(cid), f"Kandidat {cid}", f"+49 000 {cid:04d}",
                 f"kandidat-{cid}-cv.pdf", "[anonymisiert]", f"Position {cid}", cid))
        # employers
        for (eid,) in dst.execute("SELECT id FROM employers").fetchall():
            # `firma` bleibt (Test-Fixture erwartet den Namen), Person bleibt anonym.
            run("UPDATE employers SET email=?, kontaktperson=?, kontakt_email=?, "
                "telefon=?, website=?, beschreibung=? WHERE id=?",
                (f"hr{eid}@example.invalid", f"HR {eid}",
                 f"hr{eid}@example.invalid", f"+49 000 1{eid:03d}",
                 "https://example.invalid", "[anonymisiert]", eid))
        # admins
        run("UPDATE admins SET email='admin@example.invalid', name='Admin'")
        # candidate_documents: Pfad behaelt die Kandidaten-ID (Test-Fixture)
        for (did, cid, pfad) in dst.execute(
                "SELECT id, candidate_id, datei_pfad FROM candidate_documents").fetchall():
            endung = "." + pfad.rsplit(".", 1)[-1] if "." in pfad else ".pdf"
            run("UPDATE candidate_documents SET datei_pfad=? WHERE id=?",
                (f"testdaten/kandidat-{cid}-dokument{endung}", did))
        # applications: Freitext
        run("UPDATE applications SET bewerbungstext='[anonymisiert]' "
            "WHERE bewerbungstext IS NOT NULL AND bewerbungstext != ''")
        # notifications
        run("UPDATE notifications SET titel='Benachrichtigung', nachricht='[anonymisiert]'")
        # mentoring
        run("UPDATE mentoring SET mentor_name='Mentor', notizen=NULL")
        # feedback: Namen/Anmerkungen
        run("UPDATE feedback SET kandidat_name='Kandidat', anmerkungen=NULL, "
            "stellenprofil='Stelle' WHERE kandidat_name IS NOT NULL OR anmerkungen IS NOT NULL")
        # jobs: Titel bleibt (Test-Fixture), nur Freitext anonymisieren
        has_kontakt = _has_col(dst, "jobs", "kontakt")
        if has_kontakt:
            run("UPDATE jobs SET beschreibung='[anonymisiert]', kontakt='HR'")
        else:
            run("UPDATE jobs SET beschreibung='[anonymisiert]'")
        dst.commit()

        # Gegenprobe: keine echten E-Mails mehr (außer example.invalid)
        rest = [r[0] for r in dst.execute(
            "SELECT email FROM candidates UNION SELECT email FROM employers "
            "UNION SELECT email FROM admins") if r[0] and "example.invalid" not in r[0]]
        if rest:
            sys.exit(f"Anonymisierung unvollstaendig: {rest[:3]}")
        print(f"Seed geschrieben: {DST} ({DST.stat().st_size} B)")
    finally:
        src.close()
        dst.close()
    return 0


def _has_col(conn, table: str, col: str) -> bool:
    return any(r[1] == col for r in conn.execute(f"PRAGMA table_info({table})"))


if __name__ == "__main__":
    raise SystemExit(main())
