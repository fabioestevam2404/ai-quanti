from __future__ import annotations

import math
from dataclasses import replace

from backtesting_engine.domain.entities import CostModel, EquityPoint, TickerSimulation, Trade
from market_data_lake.api import OHLCVBar


def simulate_execution(
    bars: list[OHLCVBar], signals: list[int], initial_capital: float, costs: CostModel
) -> TickerSimulation:
    """Executa sinais de um ativo: decisão em `t`, ordem na abertura de `t+1`.

    Separado da geração de sinal (ADR-0005). O fechamento de `t` nunca
    executa uma decisão tomada em `t` (item 1 do checklist); sinal no último
    pregão não executa e a posição aberta é marcada a mercado.
    """
    if len(bars) != len(signals):
        raise ValueError(f"{len(signals)} sinais para {len(bars)} barras")
    sorted_bars = sorted(bars, key=lambda bar: bar.bar_date)
    ticker = sorted_bars[0].instrument.ticker if sorted_bars else ""

    cash = initial_capital
    quantity = 0
    open_trade: Trade | None = None
    trades: list[Trade] = []
    equity_curve: list[EquityPoint] = []

    for index, bar in enumerate(sorted_bars):
        if index > 0:
            target = signals[index - 1]
            if target == 1 and quantity == 0:
                price = bar.open * (1 + costs.slippage_rate)
                # Maior quantidade inteira que cabe no caixa já com o custo.
                shares = math.floor(cash / (price * (1 + costs.cost_rate)))
                if shares > 0:
                    gross = shares * price
                    fee = gross * costs.cost_rate
                    cash -= gross + fee
                    quantity = shares
                    open_trade = Trade(
                        ticker=ticker,
                        quantity=shares,
                        entry_date=bar.bar_date,
                        entry_price=price,
                        entry_cost=fee,
                    )
            elif target == 0 and quantity > 0 and open_trade is not None:
                price = bar.open * (1 - costs.slippage_rate)
                gross = quantity * price
                fee = gross * costs.cost_rate
                cash += gross - fee
                trades.append(
                    replace(open_trade, exit_date=bar.bar_date, exit_price=price, exit_cost=fee)
                )
                quantity = 0
                open_trade = None

        equity_curve.append(EquityPoint(bar_date=bar.bar_date, equity=cash + quantity * bar.close))

    if open_trade is not None:
        trades.append(open_trade)

    return TickerSimulation(
        ticker=ticker,
        trades=tuple(trades),
        equity_curve=tuple(equity_curve),
        final_cash=cash,
        final_quantity=quantity,
    )
