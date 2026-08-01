from __future__ import annotations

from datetime import date
from pathlib import Path

from market_data_lake.domain.entities import Instrument, OHLCVBar
from market_data_lake.infrastructure.persistence.duckdb_bar_repository import (
    DuckDBBarRepository,
)


def _bar(ticker: str, bar_date: date, close: float) -> OHLCVBar:
    return OHLCVBar(
        instrument=Instrument(ticker=ticker),
        bar_date=bar_date,
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=1_000.0,
    )


def test_salva_e_le_barras_do_arquivo_real(duckdb_path: Path) -> None:
    repository = DuckDBBarRepository(db_path=duckdb_path)
    bars = [
        _bar("PETR4", date(2026, 8, 3), 30.0),
        _bar("PETR4", date(2026, 8, 4), 31.5),
    ]

    repository.save_bars(bars)
    result = repository.get_bars("PETR4", date(2026, 8, 1), date(2026, 8, 10))

    assert [bar.close for bar in result] == [30.0, 31.5]
    repository.close()


def test_persiste_entre_conexoes_diferentes(duckdb_path: Path) -> None:
    DuckDBBarRepository(db_path=duckdb_path).save_bars([_bar("VALE3", date(2026, 8, 3), 68.0)])

    reopened = DuckDBBarRepository(db_path=duckdb_path)
    result = reopened.get_bars("VALE3", date(2026, 8, 1), date(2026, 8, 10))

    assert len(result) == 1
    assert result[0].close == 68.0
    reopened.close()


def test_upsert_atualiza_barra_existente(duckdb_path: Path) -> None:
    repository = DuckDBBarRepository(db_path=duckdb_path)
    repository.save_bars([_bar("ITUB4", date(2026, 8, 3), 30.0)])
    repository.save_bars([_bar("ITUB4", date(2026, 8, 3), 31.0)])

    result = repository.get_bars("ITUB4", date(2026, 8, 1), date(2026, 8, 10))

    assert len(result) == 1
    assert result[0].close == 31.0
    repository.close()


def test_filtra_por_ticker_e_periodo(duckdb_path: Path) -> None:
    repository = DuckDBBarRepository(db_path=duckdb_path)
    repository.save_bars(
        [
            _bar("PETR4", date(2026, 8, 3), 30.0),
            _bar("PETR4", date(2026, 9, 3), 35.0),
            _bar("VALE3", date(2026, 8, 3), 68.0),
        ]
    )

    result = repository.get_bars("PETR4", date(2026, 8, 1), date(2026, 8, 31))

    assert len(result) == 1
    assert result[0].instrument.ticker == "PETR4"
    assert result[0].close == 30.0
    repository.close()
