"""Audit-Hashkette (02.11.2026): Append-only + Tamper-Erkennung.

Nutzt eine temporäre DB (tmp_path), NICHT den Test-Spiegel — die
conftest-Umleitung greift nur bei Pfaden auf `data/feedback.db`.
"""
from webui import db


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "audit.db")
    monkeypatch.setenv("KMHR_AUDIT_SECRET", "test-secret")
    db.init_audit_log_table()
    return db.get_conn()


def test_kette_gueltig(tmp_path, monkeypatch):
    conn = _setup(tmp_path, monkeypatch)
    try:
        h1 = db.append_audit(
            conn, actor_role="employer", actor_id="hr@example.com",
            action="status_change", application_id=1, candidate_id=2,
            job_id=3, prev_status="angesehen", new_status="eingeladen",
            payload={"trigger": "hr_klick_portal"})
        h2 = db.append_audit(
            conn, actor_role="employer", actor_id="hr@example.com",
            action="status_change", application_id=1, candidate_id=2,
            job_id=3, prev_status="eingeladen", new_status="eingestellt")
        conn.commit()
        assert h1 and h2 and h1 != h2
        res = db.verify_audit_chain(conn)
        assert res == {"ok": True, "broken_id": None, "count": 2}
    finally:
        conn.close()


def test_manipulation_wird_erkannt(tmp_path, monkeypatch):
    conn = _setup(tmp_path, monkeypatch)
    try:
        db.append_audit(conn, actor_role="employer", action="status_change",
                        application_id=1, prev_status="angesehen",
                        new_status="eingeladen")
        db.append_audit(conn, actor_role="employer", action="status_change",
                        application_id=1, prev_status="eingeladen",
                        new_status="eingestellt")
        conn.commit()
        assert db.verify_audit_chain(conn)["ok"] is True
        conn.execute("UPDATE audit_log SET new_status='abgelehnt' WHERE id=1")
        conn.commit()
        res = db.verify_audit_chain(conn)
        assert res["ok"] is False
        assert res["broken_id"] == 1
    finally:
        conn.close()


def test_falsches_secret_bricht_signatur(tmp_path, monkeypatch):
    conn = _setup(tmp_path, monkeypatch)
    try:
        db.append_audit(conn, actor_role="admin", action="status_change",
                        application_id=9, prev_status=None,
                        new_status="eingeladen")
        conn.commit()
        assert db.verify_audit_chain(conn)["ok"] is True
    finally:
        conn.close()
    monkeypatch.setenv("KMHR_AUDIT_SECRET", "anderes-secret")
    conn2 = db.get_conn()
    try:
        res = db.verify_audit_chain(conn2)
    finally:
        conn2.close()
    assert res["ok"] is False


def test_leere_kette_ist_gueltig(tmp_path, monkeypatch):
    conn = _setup(tmp_path, monkeypatch)
    try:
        assert db.verify_audit_chain(conn) == {
            "ok": True, "broken_id": None, "count": 0}
    finally:
        conn.close()
