from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class FeatureVector:
    ticker: str
    reference_date: date
    features: dict[str, float] = field(default_factory=dict)
