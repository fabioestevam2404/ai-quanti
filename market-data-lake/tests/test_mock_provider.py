from __future__ import annotations

from datetime import date

import pytest

from market_data_lake.infrastructure.providers.mock_provider import MockMarketDataProvider


def test_gera_apenas_dias_uteis() -> None:
    provider = MockMarketDataProvider()

    # 2026-08-01 é sábado, 2026-08-03 é segunda
    bars = provider.fetch_daily_bars("PETR4", date(2026, 8, 1), date(2026, 8, 3))

    assert [bar.bar_date for bar in bars] == [date(2026, 8, 3)]


def test_e_deterministico() -> None:
    provider = MockMarketDataProvider()

    first = provider.fetch_daily_bars("VALE3", date(2026, 8, 3), date(2026, 8, 7))
    second = provider.fetch_daily_bars("VALE3", date(2026, 8, 3), date(2026, 8, 7))

    assert first == second


def test_high_sempre_maior_ou_igual_a_low() -> None:
    provider = MockMarketDataProvider()

    bars = provider.fetch_daily_bars("ITUB4", date(2026, 8, 3), date(2026, 8, 14))

    assert all(bar.high >= bar.low for bar in bars)


def test_rejeita_periodo_invertido() -> None:
    provider = MockMarketDataProvider()

    with pytest.raises(ValueError, match="anterior a start"):
        provider.fetch_daily_bars("PETR4", date(2026, 8, 10), date(2026, 8, 1))
