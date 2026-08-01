from __future__ import annotations

import json
import os
from datetime import date

import redis

from feature_store.domain.entities import FeatureVector

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
KEY_PREFIX = "feature_store:online:"


class RedisHotPathStore:
    """Cache de features hot-path em Redis (ADR-0003)."""

    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url or os.environ.get("FEATURE_STORE_REDIS_URL", DEFAULT_REDIS_URL)
        self._client = redis.Redis.from_url(url, decode_responses=True)

    def save(self, vector: FeatureVector) -> None:
        payload = {
            "ticker": vector.ticker,
            "reference_date": vector.reference_date.isoformat(),
            "features": vector.features,
        }
        self._client.set(f"{KEY_PREFIX}{vector.ticker}", json.dumps(payload))

    def get(self, ticker: str) -> FeatureVector | None:
        raw = self._client.get(f"{KEY_PREFIX}{ticker}")
        if raw is None:
            return None
        payload = json.loads(raw)
        return FeatureVector(
            ticker=payload["ticker"],
            reference_date=date.fromisoformat(payload["reference_date"]),
            features=payload["features"],
        )
