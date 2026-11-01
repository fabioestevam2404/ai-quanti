from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

# Variável própria dos testes (não RISK_ENGINE_PG_DSN): um `.env` de dev nunca
# redireciona a suíte para o banco de desenvolvimento.
DEFAULT_TEST_PG_DSN = "postgresql://quant:quant@localhost:5432/quant_platform_test"


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


@pytest.fixture
def market_data_duckdb_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "market_data_lake_test.duckdb"
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(db_path))
    return db_path


@pytest.fixture
def postgres_dsn(monkeypatch: pytest.MonkeyPatch) -> str:
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
    monkeypatch.setenv("RISK_ENGINE_PG_DSN", dsn)
    # compute_metrics_for_ticker ingere via market_data_lake, que grava
    # auditoria pelo DSN dele — sem isto, essa escrita cairia no banco de dev.
    monkeypatch.setenv("MARKET_DATA_LAKE_PG_DSN", dsn)
    _reset_risk_tables(dsn)
    return dsn


def _reset_risk_tables(dsn: str) -> None:
    # Garante o schema (idempotente) antes de limpar — primeira execução
    # nesta instância de Postgres ainda não tem as tabelas.
    from risk_engine.infrastructure.persistence.postgres_circuit_breaker import (
        PostgresCircuitBreaker,
    )
    from risk_engine.infrastructure.persistence.postgres_position_ledger import (
        PostgresPositionLedger,
    )

    PostgresPositionLedger(dsn=dsn)
    PostgresCircuitBreaker(dsn=dsn)

    with psycopg.connect(dsn) as conn:
        conn.execute("DELETE FROM risk_positions")
        conn.execute("DELETE FROM risk_daily_pnl")
        conn.execute(
            "UPDATE risk_circuit_breaker_state "
            "SET tripped = FALSE, tripped_date = NULL, tripped_reason = NULL, "
            "reset_at = NULL, reset_by = NULL "
            "WHERE id = 1"
        )
        conn.commit()
