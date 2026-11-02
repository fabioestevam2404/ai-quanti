"""Critério 12: a fronteira float -> Decimal do relatório (ADR-0004)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from backtesting_engine.domain.money import to_money


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1000.0, "1000.00"),
        (663.4144, "663.41"),
        (0.125, "0.13"),  # meio centavo arredonda para cima (ROUND_HALF_UP)
        # 2.675 em float é 2.67499999...; Decimal(2.675) daria 2.67. A conversão
        # parte da representação curta do float ("2.675"), que é o valor que
        # a simulação quis dizer.
        (2.675, "2.68"),
        (0.1 + 0.2, "0.30"),  # 0.30000000000000004
        (-0.005, "-0.01"),
    ],
)
def test_converte_para_centavos_com_arredondamento_conhecido(value: float, expected: str) -> None:
    result = to_money(value)

    assert isinstance(result, Decimal)
    assert result == Decimal(expected)
    assert result.as_tuple().exponent == -2


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_rejeita_valor_nao_finito(value: float) -> None:
    with pytest.raises(ValueError, match="finito"):
        to_money(value)
