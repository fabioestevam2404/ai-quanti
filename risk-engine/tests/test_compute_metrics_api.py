from __future__ import annotations

import pytest
from risk_engine.api import compute_metrics_from_returns
from risk_engine.application.compute_metrics import ComputeMetricsUseCase


def test_api_expoe_o_mesmo_calculo_do_caso_de_uso() -> None:
    # Usado pelo backtesting-engine: as métricas do backtest e as do modo
    # analítico saem da mesma fórmula, sem reimplementação.
    returns = [0.01, -0.02, 0.015, 0.003, -0.007, 0.02]

    assert compute_metrics_from_returns(returns) == ComputeMetricsUseCase().execute(returns)
    assert compute_metrics_from_returns(returns, risk_free_rate=0.1) == (
        ComputeMetricsUseCase().execute(returns, risk_free_rate=0.1)
    )


def test_menos_de_dois_retornos_e_rejeitado() -> None:
    with pytest.raises(ValueError, match="2 retornos"):
        compute_metrics_from_returns([0.01])
