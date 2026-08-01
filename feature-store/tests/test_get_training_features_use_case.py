from __future__ import annotations

from datetime import date
from pathlib import Path

from feature_store.application.get_training_features import GetTrainingFeaturesUseCase
from market_data_lake.api import ingest_daily_bars


def test_le_precos_reais_do_market_data_lake_e_calcula_features(
    market_data_duckdb_path: Path, market_data_postgres_dsn: str
) -> None:
    ingest_daily_bars("PETR4", date(2026, 8, 3), date(2026, 8, 14), source="mock")
    use_case = GetTrainingFeaturesUseCase(window=5)

    vectors = use_case.execute("PETR4", date(2026, 8, 3), date(2026, 8, 14))

    assert len(vectors) > 0
    assert all(v.ticker == "PETR4" for v in vectors)
    assert all("daily_return" in v.features for v in vectors)


def test_ticker_sem_dados_retorna_lista_vazia(market_data_duckdb_path: Path) -> None:
    use_case = GetTrainingFeaturesUseCase(window=5)

    vectors = use_case.execute("TICKER_SEM_DADOS", date(2026, 8, 3), date(2026, 8, 14))

    assert vectors == []
