from __future__ import annotations

from decimal import Decimal

import pytest
from trading_api.domain.entities import OrderRequest, OrderType, Side


def test_client_order_id_e_obrigatorio() -> None:
    with pytest.raises(ValueError, match="client_order_id"):
        OrderRequest(
            client_order_id="",
            ticker="PETR4",
            side=Side.BUY,
            quantity=Decimal("10"),
            order_type=OrderType.MARKET,
        )


def test_quantity_precisa_ser_positiva() -> None:
    with pytest.raises(ValueError, match="quantity"):
        OrderRequest(
            client_order_id="abc",
            ticker="PETR4",
            side=Side.BUY,
            quantity=Decimal("0"),
            order_type=OrderType.MARKET,
        )


def test_limit_order_exige_limit_price() -> None:
    with pytest.raises(ValueError, match="limit_price é obrigatório"):
        OrderRequest(
            client_order_id="abc",
            ticker="PETR4",
            side=Side.BUY,
            quantity=Decimal("10"),
            order_type=OrderType.LIMIT,
        )


def test_market_order_rejeita_limit_price() -> None:
    with pytest.raises(ValueError, match="não deve ser informado"):
        OrderRequest(
            client_order_id="abc",
            ticker="PETR4",
            side=Side.BUY,
            quantity=Decimal("10"),
            order_type=OrderType.MARKET,
            limit_price=Decimal("30"),
        )
