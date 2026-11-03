from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class Instrument:
    ticker: str
    exchange: str = "B3"
    currency: str = "BRL"
    # Liga o ticker à classe de ação dos eventos da B3 (ex.: PETR4 -> BRPETRACNPR6).
    # None quando a fonte não informa (mock, barras anteriores ao REQ-01).
    isin: str | None = None


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    instrument: Instrument
    bar_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError(f"high ({self.high}) < low ({self.low}) em {self.bar_date}")
        if self.volume < 0:
            raise ValueError(f"volume negativo em {self.bar_date}: {self.volume}")


class IngestionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class IngestionRun:
    ticker: str
    source: str
    period_start: date
    period_end: date
    bars_ingested: int
    status: IngestionStatus
    executed_at: datetime
    error_message: str | None = None
