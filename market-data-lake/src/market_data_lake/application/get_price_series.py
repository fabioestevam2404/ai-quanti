from __future__ import annotations

from datetime import date

from market_data_lake.domain.entities import OHLCVBar
from market_data_lake.domain.repositories import PriceRepository


class GetPriceSeriesUseCase:
    def __init__(self, price_repository: PriceRepository) -> None:
        self._price_repository = price_repository

    def execute(self, ticker: str, start: date, end: date) -> list[OHLCVBar]:
        return self._price_repository.get_bars(ticker, start, end)
