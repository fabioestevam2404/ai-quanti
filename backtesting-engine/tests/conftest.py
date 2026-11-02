from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg.conninfo import conninfo_to_dict

# Variável própria dos testes (não MARKET_DATA_LAKE_PG_DSN): um `.env` de dev
# nunca redireciona a suíte para o banco de desenvolvimento.
DEFAULT_TEST_PG_DSN = "postgresql://quant:quant@localhost:5432/quant_platform_test"
MARKET_DATA_LAKE_DIR = Path(__file__).resolve().parents[2] / "market-data-lake"

_migrated: set[str] = set()


def _integration_unavailable(reason: str) -> None:
    # No CI (QUANT_REQUIRE_INTEGRATION=1), infra ausente é falha, não skip —
    # senão os critérios de aceite "contra infra real" passam sem rodar.
    if os.environ.get("QUANT_REQUIRE_INTEGRATION") == "1":
        pytest.fail(reason)
    pytest.skip(reason)


def _require_test_database(dsn: str) -> None:
    # Os testes limpam tabelas — recusar qualquer banco que não seja de teste.
    dbname = conninfo_to_dict(dsn).get("dbname") or ""
    if not str(dbname).endswith("_test"):
        pytest.fail(f"QUANT_TEST_PG_DSN aponta para '{dbname}'; use um banco *_test.")


def _apply_market_data_lake_migrations(dsn: str) -> None:
    # A ingestão grava auditoria no schema do market-data-lake (ADR-0012).
    if dsn in _migrated:
        return
    config = Config(str(MARKET_DATA_LAKE_DIR / "alembic.ini"))
    config.attributes["dsn"] = dsn
    command.upgrade(config, "head")
    _migrated.add(dsn)


@pytest.fixture
def market_data_duckdb_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "market_data_lake_test.duckdb"
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(db_path))
    return db_path


@pytest.fixture
def market_data_postgres_dsn(monkeypatch: pytest.MonkeyPatch) -> str:
    dsn = os.environ.get("QUANT_TEST_PG_DSN", DEFAULT_TEST_PG_DSN)
    _require_test_database(dsn)
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            pass
    except psycopg.OperationalError:
        _integration_unavailable(
            "Postgres de teste indisponível — suba `docker compose -f "
            "infrastructure/docker-compose.local.yml up -d` antes de rodar "
            "os testes de integração (ADR: testes contra infra real, não mocks)."
        )
    _apply_market_data_lake_migrations(dsn)
    monkeypatch.setenv("MARKET_DATA_LAKE_PG_DSN", dsn)
    return dsn
