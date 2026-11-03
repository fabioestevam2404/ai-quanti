from __future__ import annotations

from collections.abc import Callable
from datetime import date

from market_data_lake.domain.adjustment import CorporateEvent, adjust_bars
from market_data_lake.domain.entities import OHLCVBar
from market_data_lake.domain.repositories import PriceRepository

EventsLoader = Callable[[str], list[CorporateEvent]]


class GetPriceSeriesUseCase:
    def __init__(
        self, price_repository: PriceRepository, events_loader: EventsLoader | None = None
    ) -> None:
        self._price_repository = price_repository
        self._load_events = events_loader

    def execute(
        self, ticker: str, start: date, end: date, adjusted: bool = False
    ) -> list[OHLCVBar]:
        bars = self._price_repository.get_bars(ticker, start, end)
        if not adjusted:
            return bars
        if self._load_events is None:
            raise ValueError("série ajustada pedida sem fonte de eventos configurada")
        # Ajuste na leitura, sobre as barras brutas: um evento novo nunca deixa
        # uma série ajustada desatualizada (spec v2, seção 1).
        return list(adjust_bars(bars, self._load_events(ticker)).bars)
