from __future__ import annotations

from datetime import date

from backtesting_engine.domain.entities import MovingAverageParams
from feature_store.api import compute_features_from_bars
from market_data_lake.api import OHLCVBar


def moving_average_cross_signals(
    ticker: str, bars: list[OHLCVBar], params: MovingAverageParams
) -> list[int]:
    """Um sinal por barra: 1 (comprado) se SMA curta > SMA longa, senão 0.

    O sinal em `t` só usa fechamentos até `t`. As médias vêm do feature-store
    (mesmo cálculo do treino). Ele calcula a SMA com janela parcial no início
    da série; por isso nenhum sinal é emitido antes de `long_window` barras
    (aquecimento, spec critério 4).
    """
    sorted_bars = sorted(bars, key=lambda bar: bar.bar_date)
    short = _sma_by_date(ticker, sorted_bars, params.short_window)
    long = _sma_by_date(ticker, sorted_bars, params.long_window)

    signals: list[int] = []
    for index, bar in enumerate(sorted_bars):
        warmed_up = index + 1 >= params.long_window
        short_sma = short.get(bar.bar_date)
        long_sma = long.get(bar.bar_date)
        if warmed_up and short_sma is not None and long_sma is not None:
            signals.append(1 if short_sma > long_sma else 0)
        else:
            signals.append(0)
    return signals


def _sma_by_date(ticker: str, bars: list[OHLCVBar], window: int) -> dict[date, float]:
    key = f"sma_{window}d"
    return {
        vector.reference_date: vector.features[key]
        for vector in compute_features_from_bars(ticker, bars, window=window)
    }
