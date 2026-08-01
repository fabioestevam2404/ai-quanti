from __future__ import annotations

import pytest
from risk_engine.application.compute_metrics import ComputeMetricsUseCase


def test_serie_sem_perdas_tem_drawdown_zero_e_sharpe_positivo() -> None:
    use_case = ComputeMetricsUseCase()

    metrics = use_case.execute([0.01, 0.02, 0.01, 0.015, 0.005])

    assert metrics.max_drawdown == 0.0
    assert metrics.sharpe > 0
    assert metrics.var_95 <= 0  # nenhum retorno negativo na amostra


def test_serie_com_queda_grande_tem_drawdown_negativo() -> None:
    use_case = ComputeMetricsUseCase()

    metrics = use_case.execute([0.05, -0.20, 0.01, 0.01])

    assert metrics.max_drawdown < -0.15


def test_e_deterministico() -> None:
    use_case = ComputeMetricsUseCase()
    returns = [0.01, -0.02, 0.015, -0.005, 0.03, -0.01]

    first = use_case.execute(returns)
    second = use_case.execute(returns)

    assert first == second


def test_exige_pelo_menos_dois_retornos() -> None:
    use_case = ComputeMetricsUseCase()

    with pytest.raises(ValueError, match="pelo menos 2 retornos"):
        use_case.execute([0.01])
