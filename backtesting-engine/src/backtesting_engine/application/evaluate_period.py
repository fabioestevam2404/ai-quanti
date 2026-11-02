from __future__ import annotations

from risk_engine.api import compute_metrics_from_returns

from backtesting_engine.application.signals import moving_average_cross_signals
from backtesting_engine.application.simulate_execution import simulate_execution
from backtesting_engine.domain.entities import (
    CostModel,
    EquityPoint,
    MovingAverageParams,
    PerformanceMetrics,
    Period,
    PeriodResult,
    TickerSimulation,
)
from market_data_lake.api import OHLCVBar


def evaluate_period(
    bars_by_ticker: dict[str, list[OHLCVBar]],
    params: MovingAverageParams,
    costs: CostModel,
    initial_capital: float,
    period: Period,
) -> PeriodResult:
    """Simula a carteira num período: capital igual por ativo, sem rebalanceamento.

    Os sinais usam o histórico até `period.end` — inclusive antes de
    `period.start`, para o aquecimento das médias —, nunca depois. Cada
    período começa sem posição: o primeiro pregão não executa sinal anterior.
    Levanta `ValueError` se não houver dados para calcular métricas.
    """
    if not bars_by_ticker:
        raise ValueError("universo vazio")
    share = initial_capital / len(bars_by_ticker)
    simulations: list[TickerSimulation] = []
    for ticker in sorted(bars_by_ticker):
        history = sorted(
            (bar for bar in bars_by_ticker[ticker] if bar.bar_date <= period.end),
            key=lambda bar: bar.bar_date,
        )
        signals = moving_average_cross_signals(ticker, history, params)
        in_period = [
            (bar, signal)
            for bar, signal in zip(history, signals, strict=True)
            if bar.bar_date >= period.start
        ]
        if not in_period:
            raise ValueError(f"{ticker} sem barras entre {period.start} e {period.end}")
        simulations.append(
            simulate_execution(
                [bar for bar, _ in in_period], [signal for _, signal in in_period], share, costs
            )
        )

    equity = _portfolio_equity(simulations, share)
    # Pares consecutivos da mesma série: a segunda é uma a menos, por definição.
    returns = [
        current.equity / previous.equity - 1
        for previous, current in zip(equity, equity[1:], strict=False)
    ]
    risk = compute_metrics_from_returns(returns)
    return PeriodResult(
        period=period,
        params=params,
        metrics=PerformanceMetrics(
            sharpe=risk.sharpe,
            sortino=risk.sortino,
            calmar=risk.calmar,
            var_95=risk.var_95,
            max_drawdown=risk.max_drawdown,
        ),
        simulations=tuple(simulations),
        portfolio_equity=tuple(equity),
    )


def _portfolio_equity(simulations: list[TickerSimulation], share: float) -> list[EquityPoint]:
    # Soma as curvas por data. Ativo sem pregão numa data mantém o último
    # patrimônio conhecido (ou a fatia inicial, antes do primeiro pregão).
    by_ticker = [{p.bar_date: p.equity for p in sim.equity_curve} for sim in simulations]
    all_dates = sorted({d for curve in by_ticker for d in curve})
    last = [share] * len(by_ticker)
    portfolio: list[EquityPoint] = []
    for day in all_dates:
        for index, curve in enumerate(by_ticker):
            if day in curve:
                last[index] = curve[day]
        portfolio.append(EquityPoint(bar_date=day, equity=sum(last)))
    return portfolio
