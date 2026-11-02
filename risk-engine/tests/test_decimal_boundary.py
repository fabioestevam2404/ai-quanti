"""Critério de aceite 3: o gate e o ledger operam só em `Decimal` (ADR-0004).

Um `float` vazando para exposição/P&L é bug: a conta perde precisão e o
valor impreciso fica persistido no ledger, que é a fonte de verdade do gate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from risk_engine.application.record_fill import RecordFillUseCase
from risk_engine.domain.entities import OrderProposal, RiskLimits, Side
from risk_engine.infrastructure.persistence.postgres_position_ledger import (
    PostgresPositionLedger,
)

TODAY = date(2026, 8, 3)


@pytest.mark.parametrize("field", ["quantity", "estimated_price"])
def test_order_proposal_rejeita_float(field: str) -> None:
    values: dict[str, object] = {"quantity": Decimal("10"), "estimated_price": Decimal("30")}
    values[field] = 10.0

    with pytest.raises(TypeError, match=field):
        OrderProposal(ticker="PETR4", side=Side.BUY, **values)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["max_exposure_per_ticker", "max_daily_loss"])
def test_risk_limits_rejeita_float(field: str) -> None:
    values: dict[str, object] = {
        "max_exposure_per_ticker": Decimal("10000"),
        "max_daily_loss": Decimal("500"),
    }
    values[field] = 500.0

    with pytest.raises(TypeError, match=field):
        RiskLimits(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["quantity", "price", "realized_pnl_delta"])
def test_record_fill_rejeita_float_e_nao_altera_o_ledger(postgres_dsn: str, field: str) -> None:
    ledger = PostgresPositionLedger(dsn=postgres_dsn)
    values: dict[str, object] = {
        "quantity": Decimal("10"),
        "price": Decimal("30.10"),
        "realized_pnl_delta": Decimal("-5.25"),
    }
    values[field] = 0.1

    with pytest.raises(TypeError, match=field):
        RecordFillUseCase(ledger=ledger).execute(
            "PETR4",
            Side.BUY,
            as_of=TODAY,
            **values,  # type: ignore[arg-type]
        )

    assert ledger.get_exposure("PETR4") == Decimal("0")
    assert ledger.get_daily_pnl(TODAY) == Decimal("0")


def test_ledger_devolve_decimal_exato(postgres_dsn: str) -> None:
    ledger = PostgresPositionLedger(dsn=postgres_dsn)

    RecordFillUseCase(ledger=ledger).execute(
        "PETR4", Side.BUY, Decimal("3"), Decimal("0.1"), Decimal("-0.3"), TODAY
    )

    exposure = ledger.get_exposure("PETR4")
    daily_pnl = ledger.get_daily_pnl(TODAY)
    assert isinstance(exposure, Decimal)
    assert isinstance(daily_pnl, Decimal)
    # 3 x 0.1 em float daria 0.30000000000000004.
    assert exposure == Decimal("0.3")
    assert daily_pnl == Decimal("-0.3")
