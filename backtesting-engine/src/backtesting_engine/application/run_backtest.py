from __future__ import annotations

from collections.abc import Callable
from datetime import date

from backtesting_engine.application.checklist import build_checklist
from backtesting_engine.application.validation import run_validation
from backtesting_engine.domain.entities import (
    BacktestConfig,
    BacktestReport,
    MonetarySummary,
    PeriodResult,
    TradeStats,
)
from backtesting_engine.domain.money import to_money
from market_data_lake.api import (
    AdjustmentDeclaration,
    OHLCVBar,
    get_adjustment_declaration,
    get_price_series,
)

PriceLoader = Callable[..., list[OHLCVBar]]  # (ticker, start, end, adjusted=...)
DeclarationLoader = Callable[[str, date, date], AdjustmentDeclaration]


class RunBacktestUseCase:
    """Carrega preços, valida a estratégia e monta o relatório com checklist.

    Cada série é lida ajustada quando o market-data-lake a declara ajustada;
    senão, bruta — e o item 7 do checklist registra o motivo.
    """

    def __init__(
        self,
        price_loader: PriceLoader = get_price_series,
        declaration_loader: DeclarationLoader = get_adjustment_declaration,
    ) -> None:
        self._load_prices = price_loader
        self._declare = declaration_loader

    def execute(self, config: BacktestConfig) -> BacktestReport:
        declarations = {
            ticker: self._declare(ticker, config.start, config.end)
            for ticker in config.universe.tickers
        }
        bars_by_ticker = {
            ticker: self._load_prices(
                ticker, config.start, config.end, adjusted=declarations[ticker].adjusted
            )
            for ticker in config.universe.tickers
        }
        missing = [ticker for ticker, bars in bars_by_ticker.items() if not bars]
        if missing:
            raise ValueError(
                f"sem dados entre {config.start} e {config.end} para: {', '.join(missing)}"
            )

        # Entrada Decimal -> float para a simulação (camada analítica, ADR-0004).
        validation = run_validation(
            bars_by_ticker, config.costs, float(config.initial_capital), config.validation
        )
        oos = validation.out_of_sample_result
        return BacktestReport(
            config=config,
            validation=validation,
            checklist=build_checklist(config, bars_by_ticker, validation, declarations),
            in_sample_money=_money(validation.in_sample_result),
            out_of_sample_money=_money(oos) if oos is not None else None,
            in_sample_trades=_trade_stats(validation.in_sample_result),
            price_declarations=tuple(declarations[t] for t in config.universe.tickers),
        )


def _money(result: PeriodResult) -> MonetarySummary:
    return MonetarySummary(
        final_equity=to_money(result.portfolio_equity[-1].equity),
        total_costs=to_money(sum(sim.total_costs for sim in result.simulations)),
    )


def _trade_stats(result: PeriodResult) -> TradeStats:
    profits = [
        trade.quantity * trade.exit_price
        - trade.exit_cost
        - (trade.quantity * trade.entry_price + trade.entry_cost)
        for sim in result.simulations
        for trade in sim.trades
        if trade.exit_price is not None
    ]
    if not profits:
        return TradeStats(closed_trades=0, win_rate=None, profit_factor=None)
    gains = sum(p for p in profits if p > 0)
    losses = -sum(p for p in profits if p < 0)
    return TradeStats(
        closed_trades=len(profits),
        win_rate=sum(1 for p in profits if p > 0) / len(profits),
        profit_factor=gains / losses if losses > 0 else None,
    )
