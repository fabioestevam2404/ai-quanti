from __future__ import annotations

import hashlib
from datetime import date, timedelta

from market_data_lake.domain.entities import Instrument, OHLCVBar


class MockMarketDataProvider:
    """Provider determinístico para dev/testes — não faz chamada de rede.

    Mesmo ticker + mesma data sempre produzem a mesma barra (hash como
    seed), permitindo rodar a plataforma localmente sem chave de API e
    escrever testes sem depender de rede.
    """

    name = "mock"

    def fetch_daily_bars(self, ticker: str, start: date, end: date) -> list[OHLCVBar]:
        if end < start:
            raise ValueError(f"end ({end}) anterior a start ({start})")

        instrument = Instrument(ticker=ticker)
        bars: list[OHLCVBar] = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                bars.append(self._synthetic_bar(instrument, current))
            current += timedelta(days=1)
        return bars

    @staticmethod
    def _synthetic_bar(instrument: Instrument, bar_date: date) -> OHLCVBar:
        digest = hashlib.sha256(f"{instrument.ticker}:{bar_date.isoformat()}".encode()).digest()
        base_price = 10.0 + (digest[0] / 255) * 90.0
        spread = 0.5 + (digest[1] / 255) * 2.0
        close = round(base_price, 2)
        open_ = round(base_price - spread / 2 + (digest[2] / 255) * spread, 2)
        high = round(max(open_, close) + (digest[3] / 255) * spread, 2)
        low = round(min(open_, close) - (digest[4] / 255) * spread, 2)
        volume = float(100_000 + digest[5] * 4_000)

        return OHLCVBar(
            instrument=instrument,
            bar_date=bar_date,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
