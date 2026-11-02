"""Séries sintéticas determinísticas compartilhadas pelos testes do módulo."""

from __future__ import annotations

import math
from datetime import date, timedelta

from market_data_lake.domain.entities import Instrument, OHLCVBar

START = date(2025, 1, 1)


def wave_series(ticker: str, phase: float, length: int = 260) -> list[OHLCVBar]:
    # Ondas com tendência leve: gera cruzamentos de média ao longo do período.
    closes = [50 + 10 * math.sin(i / 9 + phase) + 0.03 * i for i in range(length)]
    opens = [closes[0]] + [closes[i - 1] * (1 + 0.002 * math.sin(i)) for i in range(1, length)]
    return [
        OHLCVBar(
            instrument=Instrument(ticker=ticker),
            bar_date=START + timedelta(days=i),
            open=opens[i],
            high=max(opens[i], closes[i]),
            low=min(opens[i], closes[i]),
            close=closes[i],
            volume=1_000.0,
        )
        for i in range(length)
    ]


def wave_universe() -> dict[str, list[OHLCVBar]]:
    return {"PETR4": wave_series("PETR4", 0.0), "VALE3": wave_series("VALE3", 1.3)}
