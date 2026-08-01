from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

DEFAULT_TEST_PG_DSN = "postgresql://quant:quant@localhost:5432/quant_platform"


@pytest.fixture
def duckdb_path(tmp_path: Path) -> Path:
    return tmp_path / "market_data_lake_test.duckdb"


@pytest.fixture
def postgres_dsn() -> str:
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
    return dsn
