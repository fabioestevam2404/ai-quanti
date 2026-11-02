"""API pública do feature-store — único ponto de leitura de features.

`backtesting-engine`, `ml-predictions` e `reinforcement-learning` devem
importar apenas daqui, nunca de `feature_store.domain`/`application`/
`infrastructure` (fronteira validada por import-linter, ver docs/spec.md e
ADR-0001). Isso é o que evita train/serve skew (C2: racional das fronteiras).
"""

from __future__ import annotations

from datetime import date

from feature_store.application.compute_features import ComputeFeaturesUseCase
from feature_store.application.get_training_features import GetTrainingFeaturesUseCase
from feature_store.application.materialize_online_features import (
    MaterializeOnlineFeaturesUseCase,
)
from feature_store.domain.entities import FeatureVector
from feature_store.infrastructure.redis_hot_path_store import RedisHotPathStore
from market_data_lake.api import OHLCVBar

DEFAULT_WINDOW = 5


def get_training_features(
    ticker: str, start: date, end: date, window: int = DEFAULT_WINDOW
) -> list[FeatureVector]:
    """Features para treino/backtesting — recalcula a partir do histórico completo."""
    use_case = GetTrainingFeaturesUseCase(window=window)
    return use_case.execute(ticker, start, end)


def compute_features_from_bars(
    ticker: str, bars: list[OHLCVBar], window: int = DEFAULT_WINDOW
) -> list[FeatureVector]:
    """Mesmo cálculo de `get_training_features`, a partir de barras já em mãos.

    Usado pelo `backtesting-engine`: backtest e treino compartilham a mesma
    definição de feature, sem reimplementar o cálculo (train/serve skew).
    """
    return ComputeFeaturesUseCase(window=window).execute(ticker, bars)


def materialize_online_features(
    ticker: str, as_of: date, window: int = DEFAULT_WINDOW
) -> FeatureVector | None:
    """Recalcula a feature mais recente e grava no cache hot-path (Redis)."""
    use_case = MaterializeOnlineFeaturesUseCase(online_store=RedisHotPathStore(), window=window)
    return use_case.execute(ticker, as_of)


def get_online_features(ticker: str) -> FeatureVector | None:
    """Lê a feature mais recente já materializada no cache hot-path."""
    return RedisHotPathStore().get(ticker)
