from __future__ import annotations

from datetime import date

import pytest

from feature_store.application.compute_features import ComputeFeaturesUseCase
from market_data_lake.domain.entities import Instrument, OHLCVBar


def _bar(bar_date: date, close: float) -> OHLCVBar:
    return OHLCVBar(
        instrument=Instrument(ticker="PETR4"),
        bar_date=bar_date,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1_000.0,
    )


def test_calcula_retorno_diario_e_sma() -> None:
    bars = [
        _bar(date(2026, 8, 3), 10.0),
        _bar(date(2026, 8, 4), 11.0),
        _bar(date(2026, 8, 5), 12.0),
    ]
    use_case = ComputeFeaturesUseCase(window=3)

    vectors = use_case.execute("PETR4", bars)

    assert len(vectors) == 2
    assert vectors[0].reference_date == date(2026, 8, 4)
    assert vectors[0].features["daily_return"] == pytest.approx(0.1)
    assert vectors[0].features["sma_3d"] == pytest.approx((10.0 + 11.0) / 2)


def test_e_deterministico_para_mesma_janela() -> None:
    bars = [_bar(date(2026, 8, day), 10.0 + day) for day in range(3, 10)]
    use_case = ComputeFeaturesUseCase(window=5)

    first = use_case.execute("PETR4", bars)
    second = use_case.execute("PETR4", bars)

    assert first == second


def test_lista_vazia_nao_gera_features() -> None:
    use_case = ComputeFeaturesUseCase(window=5)

    assert use_case.execute("PETR4", []) == []


def test_rejeita_window_menor_que_dois() -> None:
    with pytest.raises(ValueError, match="window precisa ser >= 2"):
        ComputeFeaturesUseCase(window=1)
