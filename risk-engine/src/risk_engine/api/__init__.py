"""API pública do risk-engine — único ponto de acesso para outros módulos.

`trading-api`/`trading-dashboard`/`backtesting-engine` devem importar
apenas daqui, nunca de `risk_engine.domain`/`application`/`infrastructure`
(fronteira validada por import-linter, ver docs/spec.md e ADR-0001).

Modo analítico (`compute_metrics_for_ticker`) e modo gate pré-trade
(`evaluate_order`/`record_fill`/`reset_circuit_breaker`) têm papel duplo
desde ADR-0006 — o segundo é síncrono, fail-closed, e usa `Decimal`
(ADR-0004), nunca `float`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from risk_engine.application.compute_metrics import ComputeMetricsUseCase
from risk_engine.application.compute_metrics_for_ticker import ComputeMetricsForTickerUseCase
from risk_engine.application.evaluate_order import EvaluateOrderUseCase
from risk_engine.application.record_fill import RecordFillUseCase
from risk_engine.application.reset_circuit_breaker import ResetCircuitBreakerUseCase
from risk_engine.domain.entities import GateDecision, OrderProposal, RiskLimits, RiskMetrics, Side
from risk_engine.infrastructure.persistence.postgres_circuit_breaker import PostgresCircuitBreaker
from risk_engine.infrastructure.persistence.postgres_position_ledger import (
    PostgresPositionLedger,
)


def compute_metrics_for_ticker(
    ticker: str, start: date, end: date, risk_free_rate: float = 0.0
) -> RiskMetrics:
    """Sharpe/Sortino/Calmar/VaR/drawdown — modo analítico, `float64`."""
    use_case = ComputeMetricsForTickerUseCase()
    return use_case.execute(ticker, start, end, risk_free_rate=risk_free_rate)


def compute_metrics_from_returns(returns: list[float], risk_free_rate: float = 0.0) -> RiskMetrics:
    """Mesmas métricas do modo analítico, a partir de retornos diários já em mãos.

    Usado pelo `backtesting-engine` sobre a curva de patrimônio simulada:
    uma única definição de Sharpe/Sortino/Calmar/VaR/drawdown na plataforma.
    """
    return ComputeMetricsUseCase().execute(returns, risk_free_rate=risk_free_rate)


def evaluate_order(
    ticker: str,
    side: Side,
    quantity: Decimal,
    estimated_price: Decimal,
    limits: RiskLimits,
    as_of: date | None = None,
) -> GateDecision:
    """Gate síncrono pré-trade — fail-closed. Nunca chame sem consultar antes de enviar ordem."""
    order = OrderProposal(
        ticker=ticker, side=side, quantity=quantity, estimated_price=estimated_price
    )
    use_case = EvaluateOrderUseCase(
        ledger=PostgresPositionLedger(),
        circuit_breaker=PostgresCircuitBreaker(),
    )
    return use_case.execute(order, limits, as_of=as_of)


def record_fill(
    ticker: str,
    side: Side,
    quantity: Decimal,
    price: Decimal,
    realized_pnl_delta: Decimal,
    as_of: date,
) -> None:
    """Registra um fill real — única forma de mudar exposição/P&L do ledger."""
    use_case = RecordFillUseCase(ledger=PostgresPositionLedger())
    use_case.execute(ticker, side, quantity, price, realized_pnl_delta, as_of)


def reset_circuit_breaker(actor: str) -> None:
    """Reset manual e nomeado — nunca automático."""
    use_case = ResetCircuitBreakerUseCase(circuit_breaker=PostgresCircuitBreaker())
    use_case.execute(actor)
