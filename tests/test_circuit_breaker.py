"""Circuit-Breaker (02.11.2026): Zustände, Cooldown, Erfolgs-Reset.

Framework-frei — kein NiceGUI, kein Netzwerk. Die Uhr wird injiziert,
damit der Cooldown deterministisch testbar ist.
"""
from webui.circuit_breaker import CircuitBreaker, breaker_for


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_closed_bis_schwelle_erreicht():
    c = FakeClock()
    br = CircuitBreaker(threshold=2, cooldown=10, clock=c)
    assert br.state == "closed"
    assert br.allow()
    br.record_failure()
    assert br.state == "closed"
    assert br.allow()
    br.record_failure()
    assert br.state == "open"
    assert not br.allow()


def test_half_open_nach_cooldown_und_erneutes_oeffnen():
    c = FakeClock()
    br = CircuitBreaker(threshold=1, cooldown=10, clock=c)
    br.record_failure()
    assert br.state == "open"
    assert not br.allow()
    c.t = 9.9
    assert br.state == "open"
    c.t = 10.0
    assert br.state == "half_open"
    assert br.allow()
    br.record_failure()
    assert br.state == "open"
    assert not br.allow()


def test_erfolg_setzt_zurueck():
    c = FakeClock()
    br = CircuitBreaker(threshold=2, cooldown=10, clock=c)
    br.record_failure()
    br.record_success()
    assert br.failures == 0
    assert br.state == "closed"
    br.record_failure()
    assert br.allow()  # erst der zweite Fehler öffnet


def test_remaining_ist_null_wenn_geschlossen():
    br = CircuitBreaker(threshold=1, cooldown=10, clock=FakeClock())
    assert br.remaining() == 0.0
    br.record_failure()
    assert 0.0 < br.remaining() <= 10.0


def test_registry_liefert_gleichen_schalter():
    reg: dict = {}
    a = breaker_for(reg, "modell-a", threshold=3, cooldown=5)
    b = breaker_for(reg, "modell-a")
    assert a is b
    assert reg["modell-a"] is a
