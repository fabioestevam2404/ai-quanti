from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from risk_engine.domain.entities import CircuitBreakerState, Side


class PositionLedgerRepository(Protocol):
    """Fonte da verdade de exposição e P&L diário — risk-engine é dono do dado.

    Não confia em número informado pelo caller (ver spec): quem quiser que
    uma ordem seja avaliada precisa primeiro ter reportado os fills reais
    via `apply_fill`.
    """

    def get_exposure(self, ticker: str) -> Decimal: ...

    def get_daily_pnl(self, as_of: date) -> Decimal: ...

    def apply_fill(
        self,
        ticker: str,
        side: Side,
        quantity: Decimal,
        price: Decimal,
        realized_pnl_delta: Decimal,
        as_of: date,
    ) -> None: ...


class CircuitBreakerRepository(Protocol):
    def get_state(self) -> CircuitBreakerState: ...

    def trip(self, reason: str, as_of: date) -> None: ...

    def reset(self, actor: str) -> None: ...
