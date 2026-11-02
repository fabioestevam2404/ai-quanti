from __future__ import annotations

from datetime import date
from pathlib import Path

from feature_store.api import compute_features_from_bars, get_training_features
from market_data_lake.api import get_price_series, ingest_daily_bars


def test_calculo_sobre_barras_e_identico_ao_de_treino(
    market_data_duckdb_path: Path, market_data_postgres_dsn: str
) -> None:
    # Sem train/serve skew: o backtest (que passa as barras) e o treino (que
    # lê do market-data-lake) recebem exatamente as mesmas features.
    start, end = date(2026, 8, 3), date(2026, 8, 28)
    ingest_daily_bars("PETR4", start, end, source="mock")

    from_bars = compute_features_from_bars("PETR4", get_price_series("PETR4", start, end), 5)
    training = get_training_features("PETR4", start, end, window=5)

    assert from_bars == training
    assert len(from_bars) > 0
