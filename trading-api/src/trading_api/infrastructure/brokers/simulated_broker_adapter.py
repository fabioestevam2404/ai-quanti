from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from trading_api.domain.broker import BrokerRejectionError
from trading_api.domain.entities import (
    OPEN_STATUSES,
    AccountBalance,
    Fill,
    OrderRequest,
    OrderState,
    OrderStatus,
    OrderType,
    Position,
    Side,
)


class PriceLookup(Protocol):
    """Fonte de preço corrente para simular execução — em uso real seria
    `market_data_lake.api`, em teste um dicionário fixo."""

    def __call__(self, ticker: str) -> Decimal: ...


class SimulatedBrokerAdapter:
    """Paper trading (ADR-0008): mesmo contrato de `BrokerAdapter`, sem rede
    nem credencial. Preenche `MARKET` imediatamente ao preço corrente;
    `LIMIT` só preenche se o preço corrente já satisfaz o limite — sem
    motor de matching (limitação conhecida da v1, ver docs/spec.md).

    Estado (ordens, posições, caixa) fica em memória — não sobrevive a
    restart do processo.
    """

    def __init__(
        self, price_lookup: PriceLookup, initial_cash: Decimal = Decimal("100000")
    ) -> None:
        self._price_lookup = price_lookup
        self._orders: dict[str, OrderState] = {}
        self._positions: dict[str, Position] = {}
        self._cash = initial_cash

    def submit_order(self, request: OrderRequest) -> OrderState:
        existing = self._orders.get(request.client_order_id)
        if existing is not None:
            return existing

        market_price = self._price_lookup(request.ticker)
        should_fill, execution_price = self._resolve_execution(request, market_price)

        if not should_fill:
            state = OrderState(
                client_order_id=request.client_order_id,
                broker_order_id=request.client_order_id,
                status=OrderStatus.ACCEPTED,
                filled_quantity=Decimal("0"),
                average_fill_price=None,
            )
            self._orders[request.client_order_id] = state
            return state

        fill = Fill(quantity=request.quantity, price=execution_price, filled_at=datetime.now(UTC))
        state = OrderState(
            client_order_id=request.client_order_id,
            broker_order_id=request.client_order_id,
            status=OrderStatus.FILLED,
            filled_quantity=request.quantity,
            average_fill_price=execution_price,
            fills=(fill,),
        )
        self._orders[request.client_order_id] = state
        self._apply_fill(request, fill)
        return state

    def get_order_state(self, client_order_id: str) -> OrderState | None:
        return self._orders.get(client_order_id)

    def cancel_order(self, client_order_id: str) -> OrderState:
        state = self._orders.get(client_order_id)
        if state is None:
            raise BrokerRejectionError(f"ordem desconhecida: {client_order_id}")
        if not state.is_open:
            return state

        cancelled = OrderState(
            client_order_id=state.client_order_id,
            broker_order_id=state.broker_order_id,
            status=OrderStatus.CANCELLED,
            filled_quantity=state.filled_quantity,
            average_fill_price=state.average_fill_price,
            fills=state.fills,
        )
        self._orders[client_order_id] = cancelled
        return cancelled

    def list_open_orders(self) -> list[OrderState]:
        return [state for state in self._orders.values() if state.status in OPEN_STATUSES]

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    def get_account_balance(self) -> AccountBalance:
        return AccountBalance(cash=self._cash, buying_power=self._cash)

    @staticmethod
    def _resolve_execution(request: OrderRequest, market_price: Decimal) -> tuple[bool, Decimal]:
        if request.order_type == OrderType.MARKET:
            return True, market_price

        if request.limit_price is None:
            raise ValueError("limit_price ausente em ordem LIMIT — invariante violada")
        limit_satisfied = (
            market_price <= request.limit_price
            if request.side == Side.BUY
            else market_price >= request.limit_price
        )
        return limit_satisfied, request.limit_price

    def _apply_fill(self, request: OrderRequest, fill: Fill) -> None:
        signed_quantity = fill.quantity if request.side == Side.BUY else -fill.quantity
        notional = fill.quantity * fill.price
        self._cash += -notional if request.side == Side.BUY else notional

        existing = self._positions.get(request.ticker)
        new_quantity = (existing.quantity if existing else Decimal("0")) + signed_quantity

        if new_quantity == 0:
            self._positions.pop(request.ticker, None)
            return

        flipped_side = existing is not None and (existing.quantity > 0) != (new_quantity > 0)
        if existing is None or existing.quantity == 0 or flipped_side:
            new_average = fill.price
        else:
            new_average = (
                (existing.quantity * existing.average_price) + (signed_quantity * fill.price)
            ) / new_quantity

        self._positions[request.ticker] = Position(
            ticker=request.ticker, quantity=new_quantity, average_price=new_average
        )
