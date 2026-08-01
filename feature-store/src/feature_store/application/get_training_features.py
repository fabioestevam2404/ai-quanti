from __future__ import annotations

from datetime import date

from feature_store.application.compute_features import ComputeFeaturesUseCase
from feature_store.domain.entities import FeatureVector
from market_data_lake.api import get_price_series


class GetTrainingFeaturesUseCase:
    def __init__(self, window: int = 5) -> None:
        self._compute = ComputeFeaturesUseCase(window=window)

    def execute(self, ticker: str, start: date, end: date) -> list[FeatureVector]:
        bars = get_price_series(ticker, start, end)
        return self._compute.execute(ticker, bars)
