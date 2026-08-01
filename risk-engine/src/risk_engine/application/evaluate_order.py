from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from risk_engine.domain.entities import GateDecision, OrderProposal, RiskLimits
from risk_engine.domain.repositories import CircuitBreakerRepository, PositionLedgerRepository

logger = logging.getLogger(__name__)


class EvaluateOrderUseCase:
    """Gate síncrono pré-trade (ADR-0006) — fail-closed por construção.

    Qualquer exceção ao consultar o ledger ou o circuit breaker vira
    `BLOCK`, nunca `ALLOW` por omissão (spec, critério de aceite 1).
    """

    def __init__(
        self,
        ledger: PositionLedgerRepository,
        circuit_breaker: CircuitBreakerRepository,
    ) -> None:
        self._ledger = ledger
        self._circuit_breaker = circuit_breaker

    def execute(
        self, order: OrderProposal, limits: RiskLimits, as_of: date | None = None
    ) -> GateDecision:
        today = as_of or datetime.now(UTC).date()

        try:
            return self._evaluate(order, limits, today)
        except Exception:
            logger.exception("risk-engine gate falhou — bloqueando por fail-closed")
            return GateDecision(allowed=False, reason="provider_unavailable")

    def _evaluate(self, order: OrderProposal, limits: RiskLimits, today: date) -> GateDecision:
        state = self._circuit_breaker.get_state()
        if state.is_tripped_on(today):
            return GateDecision(
                allowed=False, reason=f"circuit_breaker_tripped: {state.tripped_reason}"
            )

        current_exposure = self._ledger.get_exposure(order.ticker)
        projected_exposure = current_exposure + order.signed_notional
        if abs(projected_exposure) > limits.max_exposure_per_ticker:
            return GateDecision(allowed=False, reason="exposure_limit")

        daily_pnl = self._ledger.get_daily_pnl(today)
        if daily_pnl <= -limits.max_daily_loss:
            self._circuit_breaker.trip(reason="daily_loss_limit", as_of=today)
            return GateDecision(allowed=False, reason="daily_loss_limit")

        return GateDecision(allowed=True)
