from __future__ import annotations

import statistics

from risk_engine.domain.entities import RiskMetrics

TRADING_DAYS_PER_YEAR = 252


class ComputeMetricsUseCase:
    """Sharpe, Sortino, Calmar, VaR histórico e drawdown máximo.

    Puro e determinístico: só depende da série de retornos diários
    recebida — nenhum estado externo (spec, critério de aceite 4).
    `max_drawdown` é negativo (convenção: perda), `var_95` é positivo
    (magnitude da perda esperada no pior 5% dos dias).
    """

    def execute(self, returns: list[float], risk_free_rate: float = 0.0) -> RiskMetrics:
        if len(returns) < 2:
            raise ValueError("são necessários pelo menos 2 retornos para calcular métricas")

        daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)

        sharpe = (
            (mean_return - daily_rf) / std_return * (TRADING_DAYS_PER_YEAR**0.5)
            if std_return > 0
            else 0.0
        )

        downside_returns = [r for r in returns if r < daily_rf]
        downside_std = statistics.stdev(downside_returns) if len(downside_returns) > 1 else 0.0
        sortino = (
            (mean_return - daily_rf) / downside_std * (TRADING_DAYS_PER_YEAR**0.5)
            if downside_std > 0
            else 0.0
        )

        max_drawdown = self._max_drawdown(returns)
        annualized_return = self._annualized_return(returns)
        calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

        var_95 = self._historical_var(returns, confidence=0.95)

        return RiskMetrics(
            sharpe=sharpe,
            sortino=sortino,
            calmar=calmar,
            var_95=var_95,
            max_drawdown=max_drawdown,
        )

    @staticmethod
    def _annualized_return(returns: list[float]) -> float:
        wealth = 1.0
        for r in returns:
            wealth *= 1.0 + r
        periods_per_year = TRADING_DAYS_PER_YEAR / len(returns)
        return wealth**periods_per_year - 1.0

    @staticmethod
    def _max_drawdown(returns: list[float]) -> float:
        wealth = 1.0
        peak = 1.0
        worst_drawdown = 0.0
        for r in returns:
            wealth *= 1.0 + r
            peak = max(peak, wealth)
            drawdown = (wealth - peak) / peak
            worst_drawdown = min(worst_drawdown, drawdown)
        return worst_drawdown

    @staticmethod
    def _historical_var(returns: list[float], confidence: float) -> float:
        sorted_returns = sorted(returns)
        tail_index = max(0, int((1.0 - confidence) * len(sorted_returns)) - 1)
        return -sorted_returns[tail_index]
