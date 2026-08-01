from __future__ import annotations

from risk_engine.domain.repositories import CircuitBreakerRepository


class ResetCircuitBreakerUseCase:
    """Reset é sempre manual e nomeado (`actor`) — nunca automático em código."""

    def __init__(self, circuit_breaker: CircuitBreakerRepository) -> None:
        self._circuit_breaker = circuit_breaker

    def execute(self, actor: str) -> None:
        if not actor:
            raise ValueError("actor é obrigatório para resetar o circuit breaker")
        self._circuit_breaker.reset(actor)
