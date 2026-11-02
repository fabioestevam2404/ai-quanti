from __future__ import annotations

from dataclasses import dataclass
from datetime import date

BPS = 10_000


@dataclass(frozen=True, slots=True)
class MovingAverageParams:
    """Janelas do cruzamento de médias móveis (spec: `2 <= N < M`)."""

    short_window: int
    long_window: int

    def __post_init__(self) -> None:
        if self.short_window < 2:
            raise ValueError(f"janela curta precisa ser >= 2: {self.short_window}")
        if self.short_window >= self.long_window:
            raise ValueError(
                f"janela curta ({self.short_window}) precisa ser menor que a longa "
                f"({self.long_window})"
            )


@dataclass(frozen=True, slots=True)
class CostModel:
    """Custo de transação e slippage por lado, em pontos-base.

    Zero é aceito aqui de propósito: o checklist (item 3) é quem reprova um
    backtest sem custo, com evidência no relatório — não uma exceção.
    """

    cost_bps: float
    slippage_bps: float

    def __post_init__(self) -> None:
        if self.cost_bps < 0 or self.slippage_bps < 0:
            raise ValueError("cost_bps e slippage_bps não podem ser negativos")

    @property
    def cost_rate(self) -> float:
        return self.cost_bps / BPS

    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / BPS


@dataclass(frozen=True, slots=True)
class Trade:
    """Uma operação comprada. Sem saída = posição ainda aberta no fim do período."""

    ticker: str
    quantity: int
    entry_date: date
    entry_price: float
    entry_cost: float
    exit_date: date | None = None
    exit_price: float | None = None
    exit_cost: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.exit_date is None


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """Patrimônio (caixa + posição a mercado pelo fechamento) ao fim de um pregão."""

    bar_date: date
    equity: float


@dataclass(frozen=True, slots=True)
class TickerSimulation:
    ticker: str
    trades: tuple[Trade, ...]
    equity_curve: tuple[EquityPoint, ...]
    final_cash: float
    final_quantity: int

    @property
    def total_costs(self) -> float:
        return sum(trade.entry_cost + trade.exit_cost for trade in self.trades)
