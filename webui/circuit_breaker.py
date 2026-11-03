"""
KM-HR-Agent – Circuit-Breaker (framework-frei, 02.11.2026)
=========================================================
Schutzschalter pro LLM-Modell. Ziel: Ein ausgefallener Anbieter darf den
Runner nicht mit vollen Timeouts blockieren — nach N Fehlern wird das
Modell für `cooldown` Sekunden übersprungen und sofort das nächste Modell
der Kette versucht.

Zustände:
  closed     – alles ok, Aufrufe erlaubt
  open       – Schwelle erreicht; Aufrufe werden sofort abgelehnt
  half_open  – Cooldown abgelaufen; ein Probeanruf ist erlaubt

Rein lokal (Prozess-Speicher). Kein Persistieren nötig: Nach einem
Neustart beginnt der Runner wieder mit `closed` — das ist gewollt, weil
der Cooldown sonst über Deployments hinweg „klebt".
"""
from __future__ import annotations

import time


class CircuitBreaker:
    """Einfacher, testbarer Schalter (Uhr injizierbar für Unit-Tests)."""

    def __init__(self, threshold: int = 2, cooldown: float = 300.0,
                 clock=time.monotonic):
        self.threshold = max(1, int(threshold))
        self.cooldown = max(0.0, float(cooldown))
        self._clock = clock
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if self._clock() - self.opened_at >= self.cooldown:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        """True, wenn ein Aufruf erlaubt ist (closed oder half_open)."""
        return self.state != "open"

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> str:
        """Zählt einen Fehler; öffnet den Schalter bei Erreichen der Schwelle."""
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = self._clock()
        return self.state

    def remaining(self) -> float:
        """Restliche Cooldown-Sekunden (0.0, wenn nicht offen)."""
        if self.opened_at is None:
            return 0.0
        return max(0.0, self.cooldown - (self._clock() - self.opened_at))


def breaker_for(registry: dict, key: str, *, threshold: int = 2,
                cooldown: float = 300.0) -> CircuitBreaker:
    """Lazy-Registry-Helfer (ein Schalter pro Modellname)."""
    br = registry.get(key)
    if br is None:
        br = CircuitBreaker(threshold=threshold, cooldown=cooldown)
        registry[key] = br
    return br
