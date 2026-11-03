from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # o domínio só referencia o tipo da API pública
    from market_data_lake.api import AdjustmentDeclaration

BPS = 10_000
CHECKLIST_SIZE = 7


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


def default_param_grid() -> tuple[MovingAverageParams, ...]:
    """Grade padrão da spec: N em 5/10/20, M em 50/100/200."""
    return tuple(
        MovingAverageParams(short_window=n, long_window=m)
        for n in (5, 10, 20)
        for m in (50, 100, 200)
    )


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    oos_fraction: float = 0.2
    walk_forward_folds: int = 3
    robustness_perturbations: tuple[float, ...] = (0.1, 0.2)
    robustness_min_ratio: float = 0.5
    param_grid: tuple[MovingAverageParams, ...] = ()

    def __post_init__(self) -> None:
        if not 0 < self.oos_fraction < 1:
            raise ValueError(f"oos_fraction precisa estar entre 0 e 1: {self.oos_fraction}")
        if self.walk_forward_folds < 1:
            raise ValueError("walk_forward_folds precisa ser >= 1")
        if not 0 < self.robustness_min_ratio <= 1:
            raise ValueError("robustness_min_ratio precisa estar em (0, 1]")
        if not self.param_grid:
            # dataclass frozen: o padrão mutável entra via object.__setattr__.
            object.__setattr__(self, "param_grid", default_param_grid())


@dataclass(frozen=True, slots=True)
class Period:
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """Métricas calculadas pelo risk-engine sobre os retornos da carteira."""

    sharpe: float
    sortino: float
    calmar: float
    var_95: float
    max_drawdown: float


@dataclass(frozen=True, slots=True)
class PeriodResult:
    period: Period
    params: MovingAverageParams
    metrics: PerformanceMetrics
    simulations: tuple[TickerSimulation, ...]
    portfolio_equity: tuple[EquityPoint, ...]


@dataclass(frozen=True, slots=True)
class FoldResult:
    train: Period
    test: Period
    chosen_params: MovingAverageParams
    train_result: PeriodResult  # resultado que levou à escolha: prova que só o treino foi usado
    test_result: PeriodResult | None  # None = dados insuficientes no teste


@dataclass(frozen=True, slots=True)
class RobustnessResult:
    base_sharpe: float
    neighbors: tuple[tuple[MovingAverageParams, float], ...]
    min_ratio: float
    passed: bool | None  # None = regra não se aplica (Sharpe base <= 0)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    in_sample: Period
    out_of_sample: Period
    folds: tuple[FoldResult, ...]
    final_params: MovingAverageParams
    in_sample_result: PeriodResult
    out_of_sample_result: PeriodResult | None  # None = dados insuficientes
    robustness: RobustnessResult


class ChecklistStatus(StrEnum):
    """Estados de um item do checklist (ADR-0010, alterado pelo ADR-0013)."""

    VERIFICADO = "verificado"
    LIMITACAO_DECLARADA = "limitação declarada"  # só o item 2 (universo)
    NAO_VERIFICADO = "não verificado"
    FALHOU = "falhou"


@dataclass(frozen=True, slots=True)
class ChecklistItem:
    number: int
    name: str
    status: ChecklistStatus
    evidence: str


UNIVERSE_ITEM = 2


def is_eligible_for_paper(items: Iterable[ChecklistItem]) -> bool:
    """Todos os 7 itens verificados; o item 2 admite limitação declarada (ADR-0013)."""
    items = tuple(items)
    return len(items) == CHECKLIST_SIZE and all(
        item.status is ChecklistStatus.VERIFICADO
        or (item.number == UNIVERSE_ITEM and item.status is ChecklistStatus.LIMITACAO_DECLARADA)
        for item in items
    )


def is_eligible_for_real_capital(items: Iterable[ChecklistItem]) -> bool:
    """Todos os 7 itens verificados. Necessário, não suficiente: o ADR-0008
    ainda exige o período em paper trading."""
    items = tuple(items)
    return len(items) == CHECKLIST_SIZE and all(
        item.status is ChecklistStatus.VERIFICADO for item in items
    )


@dataclass(frozen=True, slots=True)
class UniverseDeclaration:
    """Universo escolhido antes do backtest (item 2 do checklist).

    `point_in_time=False` significa universo fixo, escolhido entre ativos
    existentes na data `selected_on`: o relatório declara a limitação.
    """

    tickers: tuple[str, ...]
    selection_criterion: str
    selected_on: date
    point_in_time: bool = False

    def __post_init__(self) -> None:
        if not self.tickers:
            raise ValueError("universo precisa de ao menos um ticker")
        if len(set(self.tickers)) != len(self.tickers):
            raise ValueError(f"tickers repetidos no universo: {self.tickers}")


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    universe: UniverseDeclaration
    start: date
    end: date
    initial_capital: Decimal
    costs: CostModel
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    def __post_init__(self) -> None:
        # Entrada monetária da API: Decimal, como nas demais fronteiras (ADR-0004).
        if not isinstance(self.initial_capital, Decimal):
            received = type(self.initial_capital).__name__
            raise TypeError(f"initial_capital precisa ser Decimal, recebido {received}")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital precisa ser positivo")
        if self.start >= self.end:
            raise ValueError(f"start ({self.start}) precisa ser anterior a end ({self.end})")


@dataclass(frozen=True, slots=True)
class MonetarySummary:
    final_equity: Decimal
    total_costs: Decimal


@dataclass(frozen=True, slots=True)
class TradeStats:
    closed_trades: int
    win_rate: float | None  # None = nenhuma operação fechada
    profit_factor: float | None  # None = sem operação perdedora (divisão por zero)


@dataclass(frozen=True, slots=True)
class BacktestReport:
    config: BacktestConfig
    validation: ValidationResult
    checklist: tuple[ChecklistItem, ...]
    in_sample_money: MonetarySummary
    out_of_sample_money: MonetarySummary | None
    in_sample_trades: TradeStats
    # Uma por ativo, do market-data-lake: de onde vieram os preços e se foram
    # ajustados e reconciliados (base do item 7). Só tipo; sem import em runtime.
    price_declarations: tuple[AdjustmentDeclaration, ...] = ()

    @property
    def apto_para_paper(self) -> bool:
        return is_eligible_for_paper(self.checklist)

    @property
    def apto_para_capital_real(self) -> bool:
        return is_eligible_for_real_capital(self.checklist)
