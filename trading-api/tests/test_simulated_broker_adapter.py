from __future__ import annotations

from decimal import Decimal

import pytest
from trading_api.domain.broker import BrokerRejectionError
from trading_api.domain.entities import OrderRequest, OrderStatus, OrderType, Side
from trading_api.infrastructure.brokers.simulated_broker_adapter import SimulatedBrokerAdapter

PRICES = {"PETR4": Decimal("30.00"), "VALE3": Decimal("68.00")}


def _adapter() -> SimulatedBrokerAdapter:
    return SimulatedBrokerAdapter(price_lookup=lambda ticker: PRICES[ticker])


def test_market_order_preenche_imediatamente_ao_preco_corrente() -> None:
    adapter = _adapter()
    request = OrderRequest(
        client_order_id="order-1",
        ticker="PETR4",
        side=Side.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.MARKET,
    )

    state = adapter.submit_order(request)

    assert state.status == OrderStatus.FILLED
    assert state.filled_quantity == Decimal("100")
    assert state.average_fill_price == Decimal("30.00")


def test_submeter_o_mesmo_client_order_id_duas_vezes_nao_duplica() -> None:
    adapter = _adapter()
    request = OrderRequest(
        client_order_id="order-1",
        ticker="PETR4",
        side=Side.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.MARKET,
    )

    first = adapter.submit_order(request)
    second = adapter.submit_order(request)

    assert first == second
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0].quantity == Decimal("100")


def test_limit_nao_satisfeito_fica_accepted_e_nao_move_posicao() -> None:
    adapter = _adapter()
    request = OrderRequest(
        client_order_id="order-1",
        ticker="PETR4",
        side=Side.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.LIMIT,
        limit_price=Decimal("25.00"),  # abaixo do preço corrente (30.00) — compra não fecha
    )

    state = adapter.submit_order(request)

    assert state.status == OrderStatus.ACCEPTED
    assert state.filled_quantity == Decimal("0")
    assert adapter.get_positions() == []
    assert state in adapter.list_open_orders()


def test_limit_satisfeito_preenche_ao_preco_limite() -> None:
    adapter = _adapter()
    request = OrderRequest(
        client_order_id="order-1",
        ticker="PETR4",
        side=Side.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.LIMIT,
        limit_price=Decimal("35.00"),  # acima do preço corrente — compra fecha
    )

    state = adapter.submit_order(request)

    assert state.status == OrderStatus.FILLED
    assert state.average_fill_price == Decimal("35.00")


def test_compra_seguida_de_venda_zera_posicao_e_atualiza_caixa() -> None:
    adapter = _adapter()
    buy = OrderRequest(
        client_order_id="buy-1",
        ticker="PETR4",
        side=Side.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.MARKET,
    )
    sell = OrderRequest(
        client_order_id="sell-1",
        ticker="PETR4",
        side=Side.SELL,
        quantity=Decimal("100"),
        order_type=OrderType.MARKET,
    )
    initial_cash = adapter.get_account_balance().cash

    adapter.submit_order(buy)
    adapter.submit_order(sell)

    assert adapter.get_positions() == []
    assert adapter.get_account_balance().cash == initial_cash


def test_cancelar_ordem_aberta_transiciona_para_cancelled() -> None:
    adapter = _adapter()
    request = OrderRequest(
        client_order_id="order-1",
        ticker="PETR4",
        side=Side.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.LIMIT,
        limit_price=Decimal("25.00"),
    )
    adapter.submit_order(request)

    cancelled = adapter.cancel_order("order-1")

    assert cancelled.status == OrderStatus.CANCELLED
    assert adapter.list_open_orders() == []


def test_cancelar_ordem_ja_preenchida_e_idempotente_nao_lanca_erro() -> None:
    adapter = _adapter()
    request = OrderRequest(
        client_order_id="order-1",
        ticker="PETR4",
        side=Side.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.MARKET,
    )
    filled = adapter.submit_order(request)

    result = adapter.cancel_order("order-1")

    assert result.status == OrderStatus.FILLED
    assert result == filled


def test_cancelar_ordem_desconhecida_lanca_erro_tipado() -> None:
    adapter = _adapter()

    with pytest.raises(BrokerRejectionError):
        adapter.cancel_order("nunca-existiu")


def test_get_order_state_de_id_nunca_submetido_e_none() -> None:
    adapter = _adapter()

    assert adapter.get_order_state("nunca-existiu") is None
