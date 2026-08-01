from __future__ import annotations

from datetime import date, timedelta

from feature_store.application.compute_features import ComputeFeaturesUseCase
from feature_store.domain.entities import FeatureVector
from feature_store.domain.repositories import OnlineFeatureStore
from market_data_lake.api import get_price_series

DEFAULT_LOOKBACK_DAYS = 30


class MaterializeOnlineFeaturesUseCase:
    """Recalcula a feature mais recente e grava no cache hot-path (Redis)."""

    def __init__(self, online_store: OnlineFeatureStore, window: int = 5) -> None:
        self._online_store = online_store
        self._compute = ComputeFeaturesUseCase(window=window)

    def execute(self, ticker: str, as_of: date) -> FeatureVector | None:
        start = as_of - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        bars = get_price_series(ticker, start, as_of)
        vectors = self._compute.execute(ticker, bars)
        if not vectors:
            return None

        latest = vectors[-1]
        self._online_store.save(latest)
        return latest
