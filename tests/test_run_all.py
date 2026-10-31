"""Ein-Befehl-Lauf: alle Adapter, keine automatischen Mails, Cron-Artefakte."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "run_all.sh"


def test_run_all_existiert_und_ist_ausfuehrbar():
    assert RUN.exists()
    assert RUN.stat().st_mode & 0o111


def test_run_all_ruft_alle_adapter_und_die_lattice():
    s = RUN.read_text(encoding="utf-8")
    for teil in ("jobs_api.py", "jobs_ch.py", "jobs_eures.py", "jobs_lhr.py",
                 "jobs_jdp.py", "jobs_recipients.py", "jobs_induce.py"):
        assert teil in s, teil
    assert "induce" in s and "transfer" in s and "forms" in s


def test_run_all_versendet_keine_mails():
    s = RUN.read_text(encoding="utf-8")
    for zeile in s.splitlines():
        if zeile.strip().startswith(("run ", "run_tolerant ")):
            assert "jobs_mail.py" not in zeile
            assert "--send" not in zeile


def test_cron_und_unit_existieren():
    assert (ROOT / "deploy" / "systemd" / "kmhr-jobs.timer").exists()
    assert (ROOT / "deploy" / "systemd" / "kmhr-jobs.service").exists()
    assert (ROOT / "deploy" / "cron" / "kmhr-jobs.cron").exists()
    assert (ROOT / "deploy" / "logrotate" / "kmhr-jobs").exists()


def test_timer_laeuft_um_sechs_uhr():
    s = (ROOT / "deploy" / "systemd" / "kmhr-jobs.timer").read_text(encoding="utf-8")
    assert "OnCalendar=*-*-* 06:00:00" in s
    assert "Persistent=true" in s


def test_ruhezeit_ist_im_versand_verdrahtet():
    s = (ROOT / "scripts" / "jobs_mail.py").read_text(encoding="utf-8")
    assert "stunde < 8 or stunde >= 20" in s
