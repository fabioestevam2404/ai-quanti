from __future__ import annotations

from datetime import date
from typing import Protocol

from market_data_lake.domain.entities import IngestionRun, OHLCVBar


class PriceRepository(Protocol):
    def save_bars(self, bars: list[OHLCVBar]) -> None: ...

    def get_bars(self, ticker: str, start: date, end: date) -> list[OHLCVBar]: ...


class IngestionLogRepository(Protocol):
    def save_run(self, run: IngestionRun) -> None: ...
