from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(StrEnum):
    DAY = "day"


class OrderStatus(StrEnum):
    """`UNKNOWN`: resultado ambíguo (ex: timeout na chamada ao broker) — a
    ordem pode ou não ter sido criada do lado da corretora. Nunca inferir
    sucesso ou falha nesse caso; só a reconciliação (ADR-0007) resolve.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


OPEN_STATUSES = frozenset(
    {OrderStatus.PENDING, OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED}
)
TERMINAL_STATUSES = frozenset(
    {OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED}
)


@dataclass(frozen=True, slots=True)
class OrderRequest:
    client_order_id: str
    ticker: str
    side: Side
    quantity: Decimal
    order_type: OrderType
    limit_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.DAY

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("client_order_id é obrigatório — chave de idempotência (ADR-0007)")
        if self.quantity <= 0:
            raise ValueError(f"quantity precisa ser positiva: {self.quantity}")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price é obrigatório para ordens LIMIT")
        if self.order_type == OrderType.MARKET and self.limit_price is not None:
            raise ValueError("limit_price não deve ser informado para ordens MARKET")
        if self.limit_price is not None and self.limit_price <= 0:
            raise ValueError(f"limit_price precisa ser positivo: {self.limit_price}")


@dataclass(frozen=True, slots=True)
class Fill:
    quantity: Decimal
    price: Decimal
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class OrderState:
    client_order_id: str
    broker_order_id: str | None
    status: OrderStatus
    filled_quantity: Decimal
    average_fill_price: Decimal | None
    fills: tuple[Fill, ...] = field(default_factory=tuple)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES


@dataclass(frozen=True, slots=True)
class Position:
    ticker: str
    quantity: Decimal
    average_price: Decimal


@dataclass(frozen=True, slots=True)
class AccountBalance:
    cash: Decimal
    buying_power: Decimal
