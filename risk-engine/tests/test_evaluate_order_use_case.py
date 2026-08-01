from __future__ import annotations

from datetime import date
from decimal import Decimal

from risk_engine.application.evaluate_order import EvaluateOrderUseCase
from risk_engine.domain.entities import OrderProposal, RiskLimits, Side
from risk_engine.domain.repositories import PositionLedgerRepository
from risk_engine.infrastructure.persistence.postgres_circuit_breaker import PostgresCircuitBreaker
from risk_engine.infrastructure.persistence.postgres_position_ledger import (
    PostgresPositionLedger,
)

TODAY = date(2026, 8, 3)


def _limits() -> RiskLimits:
    return RiskLimits(max_exposure_per_ticker=Decimal("10000"), max_daily_loss=Decimal("500"))


class _RaisingLedger:
    def get_exposure(self, ticker: str) -> Decimal:
        raise ConnectionError("postgres indisponível")

    def get_daily_pnl(self, as_of: date) -> Decimal:
        raise ConnectionError("postgres indisponível")

    def apply_fill(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("postgres indisponível")


def test_ordem_dentro_dos_limites_e_permitida(postgres_dsn: str) -> None:
    use_case = EvaluateOrderUseCase(
        ledger=PostgresPositionLedger(dsn=postgres_dsn),
        circuit_breaker=PostgresCircuitBreaker(dsn=postgres_dsn),
    )
    order = OrderProposal(
        ticker="PETR4", side=Side.BUY, quantity=Decimal("100"), estimated_price=Decimal("30")
    )

    decision = use_case.execute(order, _limits(), as_of=TODAY)

    assert decision.allowed is True


def test_ordem_que_estoura_exposicao_e_bloqueada(postgres_dsn: str) -> None:
    use_case = EvaluateOrderUseCase(
        ledger=PostgresPositionLedger(dsn=postgres_dsn),
        circuit_breaker=PostgresCircuitBreaker(dsn=postgres_dsn),
    )
    order = OrderProposal(
        ticker="PETR4", side=Side.BUY, quantity=Decimal("1000"), estimated_price=Decimal("30")
    )

    decision = use_case.execute(order, _limits(), as_of=TODAY)

    assert decision.allowed is False
    assert decision.reason == "exposure_limit"


def test_perda_diaria_acima_do_limite_dispara_circuit_breaker(postgres_dsn: str) -> None:
    ledger = PostgresPositionLedger(dsn=postgres_dsn)
    ledger.apply_fill("PETR4", Side.SELL, Decimal("10"), Decimal("30"), Decimal("-600"), TODAY)
    breaker = PostgresCircuitBreaker(dsn=postgres_dsn)
    use_case = EvaluateOrderUseCase(ledger=ledger, circuit_breaker=breaker)
    order = OrderProposal(
        ticker="VALE3", side=Side.BUY, quantity=Decimal("10"), estimated_price=Decimal("68")
    )

    decision = use_case.execute(order, _limits(), as_of=TODAY)

    assert decision.allowed is False
    assert decision.reason == "daily_loss_limit"
    assert breaker.get_state().is_tripped_on(TODAY) is True


def test_circuit_breaker_ja_disparado_bloqueia_qualquer_ordem(postgres_dsn: str) -> None:
    breaker = PostgresCircuitBreaker(dsn=postgres_dsn)
    breaker.trip(reason="daily_loss_limit", as_of=TODAY)
    ledger = PostgresPositionLedger(dsn=postgres_dsn)
    use_case = EvaluateOrderUseCase(ledger=ledger, circuit_breaker=breaker)
    small_order = OrderProposal(
        ticker="PETR4", side=Side.BUY, quantity=Decimal("1"), estimated_price=Decimal("1")
    )

    decision = use_case.execute(small_order, _limits(), as_of=TODAY)

    assert decision.allowed is False
    assert decision.reason is not None
    assert "circuit_breaker_tripped" in decision.reason


def test_falha_no_ledger_e_fail_closed_bloqueia() -> None:
    ledger: PositionLedgerRepository = _RaisingLedger()
    use_case = EvaluateOrderUseCase(ledger=ledger, circuit_breaker=_RaisingCircuitBreaker())
    order = OrderProposal(
        ticker="PETR4", side=Side.BUY, quantity=Decimal("1"), estimated_price=Decimal("1")
    )

    decision = use_case.execute(order, _limits(), as_of=TODAY)

    assert decision.allowed is False
    assert decision.reason == "provider_unavailable"


class _RaisingCircuitBreaker:
    def get_state(self) -> object:
        raise ConnectionError("postgres indisponível")

    def trip(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("postgres indisponível")

    def reset(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("postgres indisponível")
