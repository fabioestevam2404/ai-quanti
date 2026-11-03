from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import duckdb

from market_data_lake.domain.entities import Instrument, OHLCVBar

DEFAULT_DB_PATH = Path("data") / "market_data_lake.duckdb"


class DuckDBBarRepository:
    """Persistência de barras OHLCV em DuckDB (ADR-0003: DuckDB para dev local)."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        resolved = db_path or os.environ.get("MARKET_DATA_LAKE_DUCKDB_PATH") or DEFAULT_DB_PATH
        self._db_path = Path(resolved)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self._db_path))
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ohlcv_bars (
                ticker VARCHAR NOT NULL,
                exchange VARCHAR NOT NULL,
                currency VARCHAR NOT NULL,
                bar_date DATE NOT NULL,
                open DOUBLE NOT NULL,
                high DOUBLE NOT NULL,
                low DOUBLE NOT NULL,
                close DOUBLE NOT NULL,
                volume DOUBLE NOT NULL,
                PRIMARY KEY (ticker, bar_date)
            )
            """
        )
        # Coluna do REQ-01 (spec v2). DuckDB fica fora do Alembic (ADR-0012):
        # ALTER idempotente para bancos criados antes dela.
        self._connection.execute("ALTER TABLE ohlcv_bars ADD COLUMN IF NOT EXISTS isin VARCHAR")

    def save_bars(self, bars: list[OHLCVBar]) -> None:
        if not bars:
            return
        rows = [
            (
                bar.instrument.ticker,
                bar.instrument.exchange,
                bar.instrument.currency,
                bar.bar_date,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                bar.instrument.isin,
            )
            for bar in bars
        ]
        self._connection.executemany(
            """
            INSERT INTO ohlcv_bars
                (ticker, exchange, currency, bar_date, open, high, low, close, volume, isin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (ticker, bar_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                isin = excluded.isin
            """,
            rows,
        )

    def get_bars(self, ticker: str, start: date, end: date) -> list[OHLCVBar]:
        result = self._connection.execute(
            """
            SELECT ticker, exchange, currency, bar_date, open, high, low, close, volume, isin
            FROM ohlcv_bars
            WHERE ticker = ? AND bar_date BETWEEN ? AND ?
            ORDER BY bar_date
            """,
            [ticker, start, end],
        ).fetchall()

        return [
            OHLCVBar(
                instrument=Instrument(ticker=row[0], exchange=row[1], currency=row[2], isin=row[9]),
                bar_date=row[3],
                open=row[4],
                high=row[5],
                low=row[6],
                close=row[7],
                volume=row[8],
            )
            for row in result
        ]

    def close(self) -> None:
        self._connection.close()
