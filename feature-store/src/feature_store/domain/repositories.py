from __future__ import annotations

from typing import Protocol

from feature_store.domain.entities import FeatureVector


class OnlineFeatureStore(Protocol):
    def save(self, vector: FeatureVector) -> None: ...

    def get(self, ticker: str) -> FeatureVector | None: ...
