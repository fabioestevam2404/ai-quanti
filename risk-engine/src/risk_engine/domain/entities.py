from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class RiskMetrics:
    sharpe: float
    sortino: float
    calmar: float
    var_95: float
    max_drawdown: float


@dataclass(frozen=True, slots=True)
class OrderProposal:
    ticker: str
    side: Side
    quantity: Decimal
    estimated_price: Decimal

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"quantity precisa ser positiva: {self.quantity}")
        if self.estimated_price <= 0:
            raise ValueError(f"estimated_price precisa ser positivo: {self.estimated_price}")

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.estimated_price

    @property
    def signed_notional(self) -> Decimal:
        return self.notional if self.side == Side.BUY else -self.notional


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_exposure_per_ticker: Decimal
    max_daily_loss: Decimal

    def __post_init__(self) -> None:
        if self.max_exposure_per_ticker <= 0:
            raise ValueError("max_exposure_per_ticker precisa ser positivo")
        if self.max_daily_loss <= 0:
            raise ValueError("max_daily_loss precisa ser positivo")


@dataclass(frozen=True, slots=True)
class GateDecision:
    allowed: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.allowed and not self.reason:
            raise ValueError("decisão de bloqueio precisa de motivo (reason)")


@dataclass(frozen=True, slots=True)
class CircuitBreakerState:
    tripped: bool
    tripped_date: date | None = None
    tripped_reason: str | None = None

    def is_tripped_on(self, as_of: date) -> bool:
        return self.tripped and self.tripped_date == as_of
