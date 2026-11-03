"""Audit-Secret fail-closed (02.11.2026).

Ohne `KMHR_AUDIT_SECRET` darf es KEINE Signatur und KEINEN unsignierten
Eintrag geben. Die Tabellen-Anlage bleibt erlaubt (sie signiert nicht).
"""
import pytest

from webui import db


def test_ohne_secret_keine_signatur(monkeypatch):
    monkeypatch.delenv("KMHR_AUDIT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="KMHR_AUDIT_SECRET"):
        db._audit_secret()


def test_mit_secret_liefert_bytes(monkeypatch):
    monkeypatch.setenv("KMHR_AUDIT_SECRET", "test-secret")
    assert db._audit_secret() == b"test-secret"


def test_append_audit_ohne_secret_verweigert(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "audit.db")
    monkeypatch.delenv("KMHR_AUDIT_SECRET", raising=False)
    db.init_audit_log_table()
    conn = db.get_conn()
    try:
        with pytest.raises(RuntimeError, match="KMHR_AUDIT_SECRET"):
            db.append_audit(conn, actor_role="employer", action="status_change",
                            application_id=1, prev_status="angesehen",
                            new_status="eingeladen")
        assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0
    finally:
        conn.close()


def test_tabellenanlage_ohne_secret_erlaubt(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "audit.db")
    monkeypatch.delenv("KMHR_AUDIT_SECRET", raising=False)
    db.init_audit_log_table()  # signiert nicht -> kein Secret nötig
    conn = db.get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        assert count == 0
    finally:
        conn.close()
