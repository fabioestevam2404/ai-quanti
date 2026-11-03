"""Backtest do MVP do ciclo 1 com dados reais da B3 (docs/vision.md).

Ingere o período pelo COTAHIST, coleta os eventos da B3 (opcional), roda o
backtest com a configuração padrão da spec e imprime o relatório. Os caminhos
vêm das variáveis do market-data-lake (MARKET_DATA_LAKE_DUCKDB_PATH,
MARKET_DATA_LAKE_COTAHIST_DIR, MARKET_DATA_LAKE_B3_EVENTS_DIR,
MARKET_DATA_LAKE_PG_DSN).

    uv run python backtesting-engine/scripts/run_mvp_backtest.py --refresh-events
"""

from __future__ import annotations

import argparse
import time
from datetime import date
from decimal import Decimal

from backtesting_engine.api import (
    BacktestConfig,
    BacktestReport,
    CostModel,
    UniverseDeclaration,
    run_backtest,
)
from backtesting_engine.domain.entities import PerformanceMetrics

from market_data_lake.api import ingest_daily_bars, refresh_corporate_events

UNIVERSE = ("PETR4", "VALE3", "ITUB4")  # decisão 2 da visão


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=date.fromisoformat, default=date(2010, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--refresh-events", action="store_true", help="coleta eventos na B3 (rede)")
    parser.add_argument("--skip-ingest", action="store_true", help="usa o que já está no DuckDB")
    args = parser.parse_args()

    if not args.skip_ingest:
        for ticker in UNIVERSE:
            started = time.perf_counter()
            run = ingest_daily_bars(ticker, args.start, args.end, source="cotahist")
            elapsed = time.perf_counter() - started
            print(f"ingestão {ticker}: {run.bars_ingested} pregões ({elapsed:.0f} s)")
    if args.refresh_events:
        for ticker in UNIVERSE:
            print(f"eventos {ticker}: coletados em {refresh_corporate_events(ticker)}")

    config = BacktestConfig(
        universe=UniverseDeclaration(
            tickers=UNIVERSE,
            selection_criterion="ações líquidas da B3 escolhidas na visão do ciclo 1",
            selected_on=date(2026, 11, 1),
        ),
        start=args.start,
        end=args.end,
        initial_capital=Decimal("100000.00"),
        costs=CostModel(cost_bps=5, slippage_bps=5),
    )
    started = time.perf_counter()
    report = run_backtest(config)
    print(f"\nbacktest: {time.perf_counter() - started:.0f} s")
    print_report(report)


def print_report(report: BacktestReport) -> None:
    validation = report.validation
    print(f"parâmetros finais: {validation.final_params}")
    print(
        f"in-sample {validation.in_sample.start} a {validation.in_sample.end}: "
        f"{_metrics(validation.in_sample_result.metrics)}"
    )
    oos = validation.out_of_sample_result
    print(
        f"out-of-sample {validation.out_of_sample.start} a {validation.out_of_sample.end}: "
        f"{_metrics(oos.metrics) if oos else 'sem dados'}"
    )
    for i, fold in enumerate(validation.folds, start=1):
        test = fold.test_result
        print(
            f"  dobra {i}: treino até {fold.train.end}, escolhido {fold.chosen_params}, "
            f"Sharpe no teste {test.metrics.sharpe:.2f}"
            if test
            else f"  dobra {i}: sem teste"
        )
    robustness = validation.robustness
    print(
        f"robustez: base {robustness.base_sharpe:.2f}, {len(robustness.neighbors)} vizinhos, "
        f"aprovada={robustness.passed}"
    )
    print(
        f"patrimônio final in-sample: R$ {report.in_sample_money.final_equity}; "
        f"custos R$ {report.in_sample_money.total_costs}"
    )
    if report.out_of_sample_money:
        print(f"patrimônio final out-of-sample: R$ {report.out_of_sample_money.final_equity}")
    trades = report.in_sample_trades
    print(
        f"operações fechadas (in-sample): {trades.closed_trades}; taxa de acerto "
        f"{trades.win_rate}; profit factor {trades.profit_factor}"
    )
    print("\nchecklist:")
    for item in report.checklist:
        print(f"  {item.number}. {item.name}: {item.status.value}\n     {item.evidence}")
    print(
        f"\napto para paper: {report.apto_para_paper}; "
        f"apto para capital real: {report.apto_para_capital_real}"
    )


def _metrics(m: PerformanceMetrics) -> str:
    return (
        f"Sharpe {m.sharpe:.2f}, Sortino {m.sortino:.2f}, Calmar {m.calmar:.2f}, "
        f"drawdown {m.max_drawdown:.1%}, VaR95 {m.var_95:.2%}"
    )


if __name__ == "__main__":
    main()
