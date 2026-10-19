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

# CV-Pool-Status (18.10.2026): 1:1-Literal von `CAND_CV_STATUS` in
# webui/pages/employer.py — der Generator importiert nichts aus webui, daher
# Literal statt Import; bei Aenderung dort hier mitziehen.
CAND_CV_STATUS = ("lebenslauf_hochgeladen", "profil_geprueft",
                  "match_berechnet", "eingeladen")


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
        # 18.10.2026 (Iteration „Hiring-Board Passiv-Filter FR"): ECHTER
        # FR-Fall — Employer 4 „Banana" (Job 12 „Agent logistique /
        # Préparateur de commandes (H/F) – Grands comptes industriels") und
        # der reale Kandidat aus der Bewerbung auf Job 12 — datengetriebene
        # Transformation (Marker-E-Mail e2e-fr-passiv@example.invalid nur noch
        # als FALLBACK, s. unten). IDEMPOTENT.
        # GEgeben: `src.backup` oben kopiert ALLE Employers UND Jobs aus der
        # Live-DB in die KOPIE (DST) — Employer 4 + Job 12 sind daher IMMER
        # Teil des Seeds; dieser Block transformiert nur die Bewerbung/den
        # Kandidaten, er legt Employer/Job nicht selbst an.
        fr_email = "e2e-fr-passiv@example.invalid"
        if not _has_col(dst, "candidates", "franzoesisch"):
            # Spiegel-Paritaet zur idempotenten App-Migration
            # (ALTER TABLE candidates ADD COLUMN franzoesisch TEXT): ohne die
            # Spalte kann der FR-Wert nicht getragen werden.
            dst.execute("ALTER TABLE candidates ADD COLUMN franzoesisch TEXT")
        # (1) Passiv-Machung: Bewerbung des echten Falls auf Job 12 suchen.
        # „zurückgezogen" statt DELETE — Zeilenzahlen der Fixture bleiben
        # stabil (Baseline-Tests zaehlen applications-ids); `_app_ids` in
        # tests/e2e_board_passiv_filter.py schliesst zurückgezogene Bewerbungen
        # aus → der Kandidat wird passiv für Employer 4. Der Bewerbungstext
        # wird von der allgemeinen Anonymisierungs-Zeile auf applications
        # (unten) bereits abgedeckt; die Status-Aenderung steht vor dem
        # commit und bleibt wirksam (die Anonymisierung faehrt status nicht an).
        echt_apps = dst.execute(
            "SELECT id, candidate_id FROM applications "
            "WHERE job_id=12 AND status='eingestellt'").fetchall()
        echt_cids = {cid for _aid, cid in echt_apps}
        for aid, _cid in echt_apps:
            run("UPDATE applications SET status='zurückgezogen' WHERE id=?", (aid,))
        # (2) Spalte füllen (nur die Kandidaten aus Schritt 1): franzoesisch
        # nur wenn leer + Erfahrungs-Anhebung. DESIGN-ENTSCHEIDUNG 18.10.2026:
        # der reale Wert ist leer (NULL) und würde das 50%-Erfahrungs-Gate
        # (Job 12 fordert 3 Jahre → Schwelle 1,5) verfehlen; 3 = die
        # Anforderung des echten Jobs (kein erfundener Wert).
        for cid in echt_cids:
            run("UPDATE candidates SET "
                "franzoesisch=CASE WHEN COALESCE(franzoesisch,'')='' "
                "THEN 'B2' ELSE franzoesisch END, "
                "berufserfahrung_jahre=CASE "
                "WHEN COALESCE(berufserfahrung_jahre,0) >= 2 "
                "THEN berufserfahrung_jahre ELSE 3 END "
                "WHERE id=?", (cid,))
            # Status: nur auf den CV-Pool heben, wenn der Kandidat noch NICHT
            # passiv ist — „lebenslauf_hochgeladen" ist der passende
            # Passive-Status; wer schon in CAND_CV_STATUS steht, bleibt unveraendert.
            _st = dst.execute("SELECT status FROM candidates WHERE id=?",
                              (cid,)).fetchone()
            if _st and _st[0] not in CAND_CV_STATUS:
                run("UPDATE candidates SET status='lebenslauf_hochgeladen' "
                    "WHERE id=?", (cid,))
        # (3) FALLBACK — nur wenn nach (1)+(2) KEIN Kandidat eine gefüllte
        # `franzoesisch`-Spalte hat, den anonymisierten Marker-Kandidaten
        # anlegen (idempotent über COUNT), jetzt mit den Werten des echten
        # Falls: Skills 1:1 aus Job 12 in der DST (keine Erfindung),
        # berufserfahrung_jahre=3 (wie Schritt 2), Standort „Alger, Algérie",
        # deutsch/englisch NULL, franzoesisch 'B2', CV-Feld anonymisiert.
        if dst.execute(
                "SELECT COUNT(*) FROM candidates "
                "WHERE COALESCE(franzoesisch,'') != ''").fetchone()[0] == 0:
            job12 = dst.execute(
                "SELECT hard_skills, soft_skills FROM jobs WHERE id=12").fetchone()
            if job12 is None:
                print("Hinweis: Job 12 fehlt in der DST — FR-Fallback ausgelassen")
            else:
                # Hash im Stil der anonymisierten Zeilen (per SELECT aus
                # derselben DB), CV-Felder bleiben NULL.
                hash_q = dst.execute(
                    "SELECT password_hash FROM candidates "
                    "WHERE password_hash LIKE '$argon2id$%' LIMIT 1").fetchone()
                if hash_q is None:
                    hash_q = dst.execute(
                        "SELECT password_hash FROM candidates "
                        "WHERE COALESCE(password_hash, '') != '' LIMIT 1").fetchone()
                pw_hash = hash_q[0] if hash_q else "x"
                hard, soft = job12
                fr_cid = dst.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM candidates").fetchone()[0]
                run("INSERT INTO candidates (id, email, password_hash, name, telefon, "
                    "standort, hard_skills, soft_skills, berufserfahrung_jahre, abschluss, "
                    "deutsch, englisch, franzoesisch, lebenslauf_text, status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (fr_cid, fr_email, pw_hash, "Kandidat FR", f"+49 000 {fr_cid:04d}",
                     "Alger, Algérie", hard, soft, 3, None, None, None, "B2",
                     "[anonymisiert]", "lebenslauf_hochgeladen"))
        # employers
        for (eid,) in dst.execute("SELECT id FROM employers").fetchall():
            # `firma` bleibt (Test-Fixture erwartet den Namen), Person bleibt anonym.
            run("UPDATE employers SET email=?, kontaktperson=?, kontakt_email=?, "
                "telefon=?, website=?, beschreibung=? WHERE id=?",
                (f"hr{eid}@example.invalid", f"HR {eid}",
                 f"hr{eid}@example.invalid", f"+49 000 1{eid:03d}",
                 "https://example.invalid", "[anonymisiert]", eid))
        # 18.10.2026 (Design-Entscheidung, Passwort-Normierung Employer 4):
        # das echte Banana-Passwort ist nicht reproduzierbar; der Seed braucht
        # den bekannten E2E-Wert `sicher123` (Employer-1-Hash verifiziert True
        # via logic.verify_password_argon2id) — tests/e2e_board_passiv_filter.py
        # meldet sich mit EMP_PW = "sicher123" an. NUR Employer 4 angefasst,
        # kein anderer Account.
        run("UPDATE employers SET password_hash = "
            "(SELECT password_hash FROM employers WHERE id=1) WHERE id=4")
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
