from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from backtesting_engine.api import run_backtest
from backtesting_engine.application.run_backtest import RunBacktestUseCase
from backtesting_engine.domain.entities import (
    BacktestConfig,
    BacktestReport,
    ChecklistStatus,
    CostModel,
    MovingAverageParams,
    UniverseDeclaration,
    ValidationConfig,
)
from synthetic import START, wave_universe

from market_data_lake.api import ingest_daily_bars
from market_data_lake.domain.entities import OHLCVBar

GRID = (MovingAverageParams(3, 8), MovingAverageParams(5, 15))
VALIDATION = ValidationConfig(oos_fraction=0.2, walk_forward_folds=3, param_grid=GRID)


def _config(
    tickers: tuple[str, ...] = ("PETR4", "VALE3"), end: date = date(2025, 9, 17)
) -> BacktestConfig:
    return BacktestConfig(
        universe=UniverseDeclaration(
            tickers=tickers,
            selection_criterion="ações líquidas da B3 listadas hoje",
            selected_on=date(2026, 11, 1),
        ),
        start=START,
        end=end,
        initial_capital=Decimal("100000.00"),
        costs=CostModel(cost_bps=5, slippage_bps=5),
        validation=VALIDATION,
    )


def _synthetic_loader(ticker: str, start: date, end: date) -> list[OHLCVBar]:
    return [bar for bar in wave_universe()[ticker] if start <= bar.bar_date <= end]


def _run() -> BacktestReport:
    return RunBacktestUseCase(price_loader=_synthetic_loader).execute(_config())


def test_relatorio_tem_checklist_completo_e_elegibilidade() -> None:
    report = _run()

    assert [item.number for item in report.checklist] == [1, 2, 3, 4, 5, 6, 7]
    assert report.checklist[1].status is ChecklistStatus.LIMITACAO_DECLARADA
    # Item 7 não verificado (fonte sem ajuste declarado) bloqueia paper e capital real.
    assert report.apto_para_paper is False
    assert report.apto_para_capital_real is False


def test_valores_monetarios_do_relatorio_sao_decimal_em_centavos() -> None:
    # Critério 12.
    report = _run()

    for money in (report.in_sample_money, report.out_of_sample_money):
        assert money is not None
        assert isinstance(money.final_equity, Decimal)
        assert isinstance(money.total_costs, Decimal)
        assert money.final_equity.as_tuple().exponent == -2
    expected = report.validation.in_sample_result.portfolio_equity[-1].equity
    assert report.in_sample_money.final_equity == Decimal(str(expected)).quantize(Decimal("0.01"))


def test_estatisticas_de_operacao_sao_coerentes() -> None:
    stats = _run().in_sample_trades

    assert stats.closed_trades > 0
    assert stats.win_rate is not None and 0 <= stats.win_rate <= 1


def test_relatorio_e_deterministico() -> None:
    # Critério 11.
    assert _run() == _run()


def test_ativo_sem_dados_no_periodo_e_erro_explicito() -> None:
    use_case = RunBacktestUseCase(price_loader=lambda ticker, start, end: [])

    with pytest.raises(ValueError, match="sem dados"):
        use_case.execute(_config())


def test_capital_inicial_precisa_ser_decimal() -> None:
    with pytest.raises(TypeError, match="initial_capital"):
        BacktestConfig(
            universe=UniverseDeclaration(("PETR4",), "x", date(2026, 11, 1)),
            start=START,
            end=date(2025, 9, 17),
            initial_capital=100_000.0,  # type: ignore[arg-type]
            costs=CostModel(cost_bps=5, slippage_bps=5),
        )


def test_ponta_a_ponta_pelas_apis_contra_infra_real(
    market_data_duckdb_path: Path, market_data_postgres_dsn: str
) -> None:
    # Critério 14: dados ingeridos via market_data_lake.api (DuckDB real, auditoria
    # em Postgres real) e lidos de volta pelo run_backtest. O provider mock gera
    # ruído: o teste verifica o relatório, não a qualidade da estratégia.
    tickers = ("PETR4", "VALE3", "ITUB4")
    for ticker in tickers:
        ingest_daily_bars(ticker, date(2025, 1, 1), date(2025, 12, 31), source="mock")

    report = run_backtest(_config(tickers=tickers, end=date(2025, 12, 31)))

    assert len(report.validation.in_sample_result.simulations) == 3
    assert len(report.checklist) == 7
    assert report.apto_para_paper is False  # item 7: fonte sem ajuste declarado
    assert report == run_backtest(_config(tickers=tickers, end=date(2025, 12, 31)))
