from __future__ import annotations

from datetime import date
from decimal import Decimal

from risk_engine.domain.entities import Side
from risk_engine.infrastructure.persistence.postgres_position_ledger import (
    PostgresPositionLedger,
)


def test_ticker_sem_fill_tem_exposicao_zero(postgres_dsn: str) -> None:
    ledger = PostgresPositionLedger(dsn=postgres_dsn)

    assert ledger.get_exposure("PETR4") == Decimal("0")


def test_compra_aumenta_exposicao_e_venda_reduz(postgres_dsn: str) -> None:
    ledger = PostgresPositionLedger(dsn=postgres_dsn)
    today = date(2026, 8, 3)

    ledger.apply_fill("PETR4", Side.BUY, Decimal("100"), Decimal("30.00"), Decimal("0"), today)
    assert ledger.get_exposure("PETR4") == Decimal("3000.00")

    ledger.apply_fill("PETR4", Side.SELL, Decimal("40"), Decimal("31.00"), Decimal("40.00"), today)
    assert ledger.get_exposure("PETR4") == Decimal("3000.00") - Decimal("1240.00")


def test_pnl_diario_acumula_por_data(postgres_dsn: str) -> None:
    ledger = PostgresPositionLedger(dsn=postgres_dsn)
    day1, day2 = date(2026, 8, 3), date(2026, 8, 4)

    ledger.apply_fill("PETR4", Side.SELL, Decimal("10"), Decimal("30"), Decimal("-50.00"), day1)
    ledger.apply_fill("PETR4", Side.SELL, Decimal("10"), Decimal("30"), Decimal("-20.00"), day1)
    ledger.apply_fill("VALE3", Side.SELL, Decimal("5"), Decimal("68"), Decimal("100.00"), day2)

    assert ledger.get_daily_pnl(day1) == Decimal("-70.00")
    assert ledger.get_daily_pnl(day2) == Decimal("100.00")
