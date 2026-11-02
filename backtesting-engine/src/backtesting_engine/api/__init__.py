"""API pública do backtesting-engine — único ponto de acesso para outros módulos.

O relatório não diz que a estratégia é boa: diz se ela pode ir a paper
trading (`apto_para_paper`) ou a capital real (`apto_para_capital_real`),
pelo checklist dos ADRs 0010 e 0013. Ver docs/spec.md.
"""

from __future__ import annotations

from backtesting_engine.application.run_backtest import RunBacktestUseCase
from backtesting_engine.domain.entities import (
    BacktestConfig,
    BacktestReport,
    ChecklistItem,
    ChecklistStatus,
    CostModel,
    MovingAverageParams,
    UniverseDeclaration,
    ValidationConfig,
)

__all__ = [
    "BacktestConfig",
    "BacktestReport",
    "ChecklistItem",
    "ChecklistStatus",
    "CostModel",
    "MovingAverageParams",
    "UniverseDeclaration",
    "ValidationConfig",
    "run_backtest",
]


def run_backtest(config: BacktestConfig) -> BacktestReport:
    """Executa o backtest com preços do market-data-lake e devolve o relatório."""
    return RunBacktestUseCase().execute(config)
