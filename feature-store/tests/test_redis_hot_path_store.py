from __future__ import annotations

from datetime import date

from feature_store.domain.entities import FeatureVector
from feature_store.infrastructure.redis_hot_path_store import RedisHotPathStore


def test_salva_e_le_do_redis_real(redis_url: str) -> None:
    store = RedisHotPathStore(redis_url=redis_url)
    vector = FeatureVector(
        ticker="PETR4",
        reference_date=date(2026, 8, 3),
        features={"daily_return": 0.01, "sma_5d": 30.5},
    )

    store.save(vector)
    result = store.get("PETR4")

    assert result == vector


def test_ticker_sem_dado_retorna_none(redis_url: str) -> None:
    store = RedisHotPathStore(redis_url=redis_url)

    assert store.get("TICKER_INEXISTENTE_XYZ") is None
