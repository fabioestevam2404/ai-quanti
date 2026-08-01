from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from market_data_lake.application.ingest_daily_bars import IngestDailyBarsUseCase
from market_data_lake.domain.entities import IngestionStatus
from market_data_lake.infrastructure.persistence.duckdb_bar_repository import (
    DuckDBBarRepository,
)
from market_data_lake.infrastructure.persistence.postgres_ingestion_log_repository import (
    PostgresIngestionLogRepository,
)
from market_data_lake.infrastructure.providers.mock_provider import MockMarketDataProvider


class _FailingProvider:
    name = "failing"

    def fetch_daily_bars(self, ticker: str, start: date, end: date) -> list:
        raise RuntimeError("provider indisponível")


def test_ingestao_com_sucesso_persiste_barras_e_auditoria(
    duckdb_path: Path, postgres_dsn: str
) -> None:
    price_repository = DuckDBBarRepository(db_path=duckdb_path)
    log_repository = PostgresIngestionLogRepository(dsn=postgres_dsn)
    use_case = IngestDailyBarsUseCase(
        provider=MockMarketDataProvider(),
        price_repository=price_repository,
        ingestion_log_repository=log_repository,
    )

    run = use_case.execute("PETR4", date(2026, 8, 3), date(2026, 8, 7))

    assert run.status == IngestionStatus.SUCCESS
    assert run.bars_ingested > 0
    persisted = price_repository.get_bars("PETR4", date(2026, 8, 3), date(2026, 8, 7))
    assert len(persisted) == run.bars_ingested
    price_repository.close()


def test_ingestao_com_falha_registra_auditoria_e_propaga_erro(
    duckdb_path: Path, postgres_dsn: str
) -> None:
    price_repository = DuckDBBarRepository(db_path=duckdb_path)
    log_repository = PostgresIngestionLogRepository(dsn=postgres_dsn)
    use_case = IngestDailyBarsUseCase(
        provider=_FailingProvider(),
        price_repository=price_repository,
        ingestion_log_repository=log_repository,
    )

    with pytest.raises(RuntimeError, match="provider indisponível"):
        use_case.execute("PETR4", date(2026, 8, 3), date(2026, 8, 7))

    price_repository.close()
