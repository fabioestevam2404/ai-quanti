from __future__ import annotations

import statistics

from feature_store.domain.entities import FeatureVector
from market_data_lake.api import OHLCVBar

TRADING_DAYS_PER_YEAR = 252


class ComputeFeaturesUseCase:
    """Calcula features determinísticas a partir de uma série OHLCV.

    Determinístico por construção: o valor de uma feature em uma data
    depende só da janela de barras até aquela data, nunca de estado
    externo — pré-requisito para eliminar train/serve skew (ver spec).
    """

    def __init__(self, window: int = 5) -> None:
        if window < 2:
            raise ValueError("window precisa ser >= 2 para calcular retornos/volatilidade")
        self._window = window

    def execute(self, ticker: str, bars: list[OHLCVBar]) -> list[FeatureVector]:
        sorted_bars = sorted(bars, key=lambda bar: bar.bar_date)
        vectors: list[FeatureVector] = []

        for index in range(1, len(sorted_bars)):
            window_start = max(0, index - self._window + 1)
            window_bars = sorted_bars[window_start : index + 1]
            closes = [bar.close for bar in window_bars]
            returns = [
                (closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))
            ]
            if not returns:
                continue

            sma = sum(closes) / len(closes)
            volatility = (
                statistics.stdev(returns) * (TRADING_DAYS_PER_YEAR**0.5)
                if len(returns) > 1
                else 0.0
            )

            vectors.append(
                FeatureVector(
                    ticker=ticker,
                    reference_date=sorted_bars[index].bar_date,
                    features={
                        "daily_return": returns[-1],
                        f"sma_{self._window}d": sma,
                        f"volatility_{self._window}d": volatility,
                    },
                )
            )

        return vectors
