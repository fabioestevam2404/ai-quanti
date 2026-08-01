from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
import redis

DEFAULT_TEST_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_TEST_PG_DSN = "postgresql://quant:quant@localhost:5432/quant_platform"


@pytest.fixture
def market_data_duckdb_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "market_data_lake_test.duckdb"
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(db_path))
    return db_path


@pytest.fixture
def market_data_postgres_dsn(monkeypatch: pytest.MonkeyPatch) -> str:
    """ingest_daily_bars() grava auditoria em Postgres — precisa da infra real de pé."""
    dsn = os.environ.get("MARKET_DATA_LAKE_PG_DSN", DEFAULT_TEST_PG_DSN)
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            pass
    except psycopg.OperationalError:
        pytest.skip(
            "Postgres real indisponível — suba `docker compose -f "
            "infrastructure/docker-compose.local.yml up -d` antes de rodar "
            "os testes de integração (ADR: testes contra infra real, não mocks)."
        )
    monkeypatch.setenv("MARKET_DATA_LAKE_PG_DSN", dsn)
    return dsn


@pytest.fixture
def redis_url() -> str:
    url = os.environ.get("FEATURE_STORE_REDIS_URL", DEFAULT_TEST_REDIS_URL)
    client = redis.Redis.from_url(url)
    try:
        client.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip(
            "Redis real indisponível — suba `docker compose -f "
            "infrastructure/docker-compose.local.yml up -d` antes de rodar "
            "os testes de integração (ADR: testes contra infra real, não mocks)."
        )
    finally:
        client.close()
    return url
