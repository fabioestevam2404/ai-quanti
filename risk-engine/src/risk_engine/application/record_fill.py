from __future__ import annotations

from datetime import date
from decimal import Decimal

from risk_engine.domain.entities import Side
from risk_engine.domain.repositories import PositionLedgerRepository


class RecordFillUseCase:
    """Registra um fill real no ledger — a única forma de mudar exposição/P&L.

    `evaluate_order` nunca aceita número informado pelo caller: quem
    executou a ordem (eventualmente `trading-api`) precisa reportar aqui.
    """

    def __init__(self, ledger: PositionLedgerRepository) -> None:
        self._ledger = ledger

    def execute(
        self,
        ticker: str,
        side: Side,
        quantity: Decimal,
        price: Decimal,
        realized_pnl_delta: Decimal,
        as_of: date,
    ) -> None:
        self._ledger.apply_fill(ticker, side, quantity, price, realized_pnl_delta, as_of)
