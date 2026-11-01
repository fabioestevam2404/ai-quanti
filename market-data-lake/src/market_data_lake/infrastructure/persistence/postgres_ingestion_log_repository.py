from __future__ import annotations

import os

import psycopg

from market_data_lake.domain.entities import IngestionRun

DEFAULT_DSN = "postgresql://quant:quant@localhost:5432/quant_platform"


class PostgresIngestionLogRepository:
    """Auditoria de execuções de ingestão em PostgreSQL (ADR-0003).

    O schema vem das migrações em `market-data-lake/migrations` (ADR-0012);
    o repositório não cria tabelas.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("MARKET_DATA_LAKE_PG_DSN", DEFAULT_DSN)

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
