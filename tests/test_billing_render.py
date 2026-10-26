"""Render-Smoke-Tests für die Gebühren-UI in allen drei Profilen.

Sichert die Verdrahtung ab (Import, Flag-Gate, Beschriftung), nicht die
Berechnung — die deckt `tests/test_billing.py` ab.
"""
from __future__ import annotations


async def test_kandidat_rendert_mit_flag(user, monkeypatch):
    monkeypatch.setenv("KMHR_BILLING_ENABLED", "1")
    await user.open("/billing-candidate")
    await user.should_see("Gebühren & Rechnungen")
    await user.should_see("Beratung / CV-Check buchen (99 €)")
    await user.should_see("Zahlung per Banküberweisung")


async def test_arbeitgeber_rendert_mit_flag(user, monkeypatch):
    monkeypatch.setenv("KMHR_BILLING_ENABLED", "1")
    await user.open("/billing-employer")
    await user.should_see("Gebühren & Rechnungen")
    await user.should_see("Zahlung per Banküberweisung")


async def test_admin_rendert_mit_flag(user, monkeypatch):
    monkeypatch.setenv("KMHR_BILLING_ENABLED", "1")
    await user.open("/billing-admin")
    await user.should_see("Abrechnung")
    await user.should_see("Visumgebühr erfassen (nach Visum-Genehmigung)")
    await user.should_see("Zahlungseingang bestätigen / stornieren")


async def test_ohne_flag_rendert_nichts(user, monkeypatch):
    """Default aus: keine Rechnungs-Sektion, nur der Admin-Hinweis."""
    monkeypatch.delenv("KMHR_BILLING_ENABLED", raising=False)
    await user.open("/billing-candidate")
    await user.should_not_see("Gebühren & Rechnungen")
