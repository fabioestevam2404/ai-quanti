from __future__ import annotations

from datetime import date, timedelta

import pytest
from backtesting_engine.application.signals import moving_average_cross_signals
from backtesting_engine.domain.entities import CostModel, MovingAverageParams

from market_data_lake.domain.entities import Instrument, OHLCVBar


def _bars(closes: list[float]) -> list[OHLCVBar]:
    return [
        OHLCVBar(
            instrument=Instrument(ticker="PETR4"),
            bar_date=date(2026, 1, 5) + timedelta(days=i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1_000.0,
        )
        for i, c in enumerate(closes)
    ]


def test_aquecimento_ignora_sma_de_janela_parcial() -> None:
    # Critério 4: em d3 a SMA4 do feature-store usa só 3 fechamentos (janela
    # parcial) e já fica abaixo da SMA2 — mesmo assim, nenhum sinal antes de 4 barras.
    params = MovingAverageParams(short_window=2, long_window=4)

    signals = moving_average_cross_signals("PETR4", _bars([10.0, 20.0, 30.0, 40.0]), params)

    assert signals == [0, 0, 0, 1]


def test_media_curta_abaixo_da_longa_fica_fora() -> None:
    params = MovingAverageParams(short_window=2, long_window=3)

    signals = moving_average_cross_signals("PETR4", _bars([30.0, 20.0, 10.0, 5.0]), params)

    assert signals == [0, 0, 0, 0]


def test_um_sinal_por_barra() -> None:
    bars = _bars([float(10 + i) for i in range(12)])

    signals = moving_average_cross_signals("PETR4", bars, MovingAverageParams(3, 5))

    assert len(signals) == len(bars)


@pytest.mark.parametrize(("short", "long"), [(1, 3), (3, 3), (5, 3)])
def test_parametros_invalidos_sao_rejeitados(short: int, long: int) -> None:
    with pytest.raises(ValueError, match="janela"):
        MovingAverageParams(short_window=short, long_window=long)


def test_custos_negativos_sao_rejeitados() -> None:
    with pytest.raises(ValueError, match="bps"):
        CostModel(cost_bps=-1, slippage_bps=5)
