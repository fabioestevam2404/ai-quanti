from __future__ import annotations

from datetime import date
from typing import Protocol

from market_data_lake.domain.entities import OHLCVBar


class MarketDataProvider(Protocol):
    """Porta para uma fonte externa de dados de mercado.

    Vive em `domain` (não em `infrastructure`) porque é a interface que
    `application` depende — os adapters concretos (`MockMarketDataProvider`,
    `AlphaVantageProvider`) ficam em `infrastructure` e implementam esta
    porta, seguindo a inversão de dependência da Clean Architecture.
    """

    name: str

    def fetch_daily_bars(self, ticker: str, start: date, end: date) -> list[OHLCVBar]: ...
