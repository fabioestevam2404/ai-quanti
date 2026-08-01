from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from risk_engine.application.compute_metrics_for_ticker import ComputeMetricsForTickerUseCase

from market_data_lake.api import ingest_daily_bars


def test_calcula_metricas_a_partir_do_market_data_lake(
    market_data_duckdb_path: Path, postgres_dsn: str
) -> None:
    ingest_daily_bars("PETR4", date(2026, 8, 3), date(2026, 8, 21), source="mock")
    use_case = ComputeMetricsForTickerUseCase()

    metrics = use_case.execute("PETR4", date(2026, 8, 3), date(2026, 8, 21))

    assert isinstance(metrics.sharpe, float)
    assert metrics.max_drawdown <= 0.0


def test_historico_insuficiente_leva_a_erro_explicito(
    market_data_duckdb_path: Path, postgres_dsn: str
) -> None:
    ingest_daily_bars("PETR4", date(2026, 8, 3), date(2026, 8, 4), source="mock")
    use_case = ComputeMetricsForTickerUseCase()

    with pytest.raises(ValueError, match="histórico insuficiente"):
        use_case.execute("PETR4", date(2026, 8, 3), date(2026, 8, 4))
