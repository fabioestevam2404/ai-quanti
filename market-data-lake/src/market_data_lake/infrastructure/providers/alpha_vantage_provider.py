from __future__ import annotations

import os
from datetime import date, datetime

import requests

from market_data_lake.domain.entities import Instrument, OHLCVBar

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"


class AlphaVantageProvider:
    """Provider real via Alpha Vantage. Requer ALPHA_VANTAGE_API_KEY.

    Uso em produção/staging — para dev local sem chave, use
    `MockMarketDataProvider` (source="mock").
    """

    name = "alpha_vantage"

    def __init__(self, api_key: str | None = None, base_url: str = ALPHA_VANTAGE_BASE_URL) -> None:
        self._api_key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "ALPHA_VANTAGE_API_KEY não configurada — use source='mock' para dev local."
            )
        self._base_url = base_url

    def fetch_daily_bars(self, ticker: str, start: date, end: date) -> list[OHLCVBar]:
        response = requests.get(
            self._base_url,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "full",
                "apikey": self._api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        series = payload.get("Time Series (Daily)")
        if series is None:
            raise RuntimeError(f"Resposta inesperada da Alpha Vantage para {ticker}: {payload}")

        instrument = Instrument(ticker=ticker)
        bars: list[OHLCVBar] = []
        for raw_date, values in series.items():
            bar_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            if start <= bar_date <= end:
                bars.append(
                    OHLCVBar(
                        instrument=instrument,
                        bar_date=bar_date,
                        open=float(values["1. open"]),
                        high=float(values["2. high"]),
                        low=float(values["3. low"]),
                        close=float(values["4. close"]),
                        volume=float(values["5. volume"]),
                    )
                )
        return sorted(bars, key=lambda bar: bar.bar_date)
