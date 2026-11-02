from __future__ import annotations

from datetime import date
from pathlib import Path

from feature_store.api import get_online_features, materialize_online_features
from market_data_lake.api import ingest_daily_bars


def test_materializa_no_redis_real_e_le_exatamente_o_gravado(
    market_data_duckdb_path: Path, market_data_postgres_dsn: str, redis_url: str
) -> None:
    ingest_daily_bars("PETR4", date(2026, 8, 3), date(2026, 8, 14), source="mock")

    materialized = materialize_online_features("PETR4", as_of=date(2026, 8, 14))

    assert materialized is not None
    assert materialized.reference_date == date(2026, 8, 14)
    assert get_online_features("PETR4") == materialized


def test_materializar_ticker_sem_dados_retorna_none_sem_erro(
    market_data_duckdb_path: Path, redis_url: str
) -> None:
    assert materialize_online_features("TICKER_SEM_DADOS", as_of=date(2026, 8, 14)) is None
    assert get_online_features("TICKER_SEM_DADOS") is None
