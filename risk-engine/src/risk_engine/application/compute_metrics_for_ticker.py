from __future__ import annotations

from datetime import date

from market_data_lake.api import get_price_series
from risk_engine.application.compute_metrics import ComputeMetricsUseCase
from risk_engine.domain.entities import RiskMetrics


class ComputeMetricsForTickerUseCase:
    def __init__(self) -> None:
        self._compute = ComputeMetricsUseCase()

    def execute(
        self, ticker: str, start: date, end: date, risk_free_rate: float = 0.0
    ) -> RiskMetrics:
        bars = sorted(get_price_series(ticker, start, end), key=lambda bar: bar.bar_date)
        if len(bars) < 3:
            raise ValueError(
                f"histórico insuficiente para {ticker} entre {start} e {end} "
                f"({len(bars)} barras) — mínimo de 3 barras (2 retornos)"
            )

        returns = [
            (bars[i].close - bars[i - 1].close) / bars[i - 1].close for i in range(1, len(bars))
        ]
        return self._compute.execute(returns, risk_free_rate=risk_free_rate)
