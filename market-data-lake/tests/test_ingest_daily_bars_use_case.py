from __future__ import annotations

from datetime import date
from pathlib import Path

import psycopg
import pytest

from market_data_lake.api import get_price_series, ingest_daily_bars
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


def _count_audit_rows(dsn: str, ticker: str, status: IngestionStatus) -> int:
    # Lê direto da tabela de auditoria: o critério 3 é sobre o registro em
    # Postgres, não sobre o objeto devolvido pelo use case.
    with psycopg.connect(dsn) as conn:
        row = conn.execute(
            "SELECT count(*) FROM market_data_lake_ingestion_runs "
            "WHERE ticker = %s AND status = %s",
            (ticker, status.value),
        ).fetchone()
    assert row is not None
    return int(row[0])


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
    audit_before = _count_audit_rows(postgres_dsn, "PETR4", IngestionStatus.SUCCESS)

    run = use_case.execute("PETR4", date(2026, 8, 3), date(2026, 8, 7))

    assert run.status == IngestionStatus.SUCCESS
    assert run.bars_ingested > 0
    persisted = price_repository.get_bars("PETR4", date(2026, 8, 3), date(2026, 8, 7))
    assert len(persisted) == run.bars_ingested
    assert _count_audit_rows(postgres_dsn, "PETR4", IngestionStatus.SUCCESS) == audit_before + 1
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
    audit_before = _count_audit_rows(postgres_dsn, "PETR4", IngestionStatus.FAILED)

    with pytest.raises(RuntimeError, match="provider indisponível"):
        use_case.execute("PETR4", date(2026, 8, 3), date(2026, 8, 7))

    assert _count_audit_rows(postgres_dsn, "PETR4", IngestionStatus.FAILED) == audit_before + 1
    price_repository.close()


def test_api_ingere_com_mock_sem_chave_de_api(
    duckdb_path: Path, postgres_dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Critério 1: dev sem chave de API nem rede. DuckDB e Postgres apontam para
    # o ambiente de teste (fixtures), não para dev.
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(duckdb_path))

    run = ingest_daily_bars("PETR4", date(2026, 8, 3), date(2026, 8, 7), source="mock")

    assert run.status == IngestionStatus.SUCCESS
    assert len(get_price_series("PETR4", date(2026, 8, 3), date(2026, 8, 7))) == run.bars_ingested
