from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import psycopg

from risk_engine.domain.entities import Side

DEFAULT_DSN = "postgresql://quant:quant@localhost:5432/quant_platform"


class PostgresPositionLedger:
    """Ledger de exposição e P&L diário — fonte da verdade do risk-engine (ADR-0006).

    Nunca confia em número informado pelo caller de `evaluate_order`; só
    muda via `apply_fill`. O schema vem das migrações em
    `risk-engine/migrations` (ADR-0012); o repositório não cria tabelas.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("RISK_ENGINE_PG_DSN", DEFAULT_DSN)

    def get_exposure(self, ticker: str) -> Decimal:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT exposure FROM risk_positions WHERE ticker = %s", (ticker,)
            ).fetchone()
            return row[0] if row else Decimal("0")

    def get_daily_pnl(self, as_of: date) -> Decimal:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT realized_pnl FROM risk_daily_pnl WHERE pnl_date = %s", (as_of,)
            ).fetchone()
            return row[0] if row else Decimal("0")

    def apply_fill(
        self,
        ticker: str,
        side: Side,
        quantity: Decimal,
        price: Decimal,
        realized_pnl_delta: Decimal,
        as_of: date,
    ) -> None:
        signed_notional = quantity * price if side == Side.BUY else -(quantity * price)
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO risk_positions (ticker, exposure)
                VALUES (%s, %s)
                ON CONFLICT (ticker) DO UPDATE SET exposure = risk_positions.exposure + %s
                """,
                (ticker, signed_notional, signed_notional),
            )
            conn.execute(
                """
                INSERT INTO risk_daily_pnl (pnl_date, realized_pnl)
                VALUES (%s, %s)
                ON CONFLICT (pnl_date) DO UPDATE SET
                    realized_pnl = risk_daily_pnl.realized_pnl + %s
                """,
                (as_of, realized_pnl_delta, realized_pnl_delta),
            )
            conn.commit()
