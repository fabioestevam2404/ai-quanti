from __future__ import annotations

import os

import psycopg

from market_data_lake.domain.entities import IngestionRun

DEFAULT_DSN = "postgresql://quant:quant@localhost:5432/quant_platform"


class PostgresIngestionLogRepository:
    """Auditoria de execuções de ingestão em PostgreSQL (ADR-0003)."""

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("MARKET_DATA_LAKE_PG_DSN", DEFAULT_DSN)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_data_lake_ingestion_runs (
                    id SERIAL PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    source TEXT NOT NULL,
                    period_start DATE NOT NULL,
                    period_end DATE NOT NULL,
                    bars_ingested INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    executed_at TIMESTAMPTZ NOT NULL,
                    error_message TEXT
                )
                """
            )
            conn.commit()

    def save_run(self, run: IngestionRun) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO market_data_lake_ingestion_runs
                    (ticker, source, period_start, period_end, bars_ingested,
                     status, executed_at, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run.ticker,
                    run.source,
                    run.period_start,
                    run.period_end,
                    run.bars_ingested,
                    run.status.value,
                    run.executed_at,
                    run.error_message,
                ),
            )
            conn.commit()
