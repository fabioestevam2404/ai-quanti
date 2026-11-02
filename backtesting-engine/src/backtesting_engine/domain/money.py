from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


def to_money(value: float) -> Decimal:
    """Único ponto de conversão float -> Decimal do módulo (ADR-0004).

    Parte da representação curta do float (`str`), não do valor binário
    exato: `2.675` vira R$ 2,68, como quem lê o número espera, e não
    R$ 2,67 (o float guarda 2.67499999...). Arredonda meio centavo para
    longe do zero.
    """
    if not math.isfinite(value):
        raise ValueError(f"valor monetário precisa ser finito: {value}")
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)
