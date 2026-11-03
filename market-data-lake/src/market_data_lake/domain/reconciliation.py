"""Reconciliação do ajuste contra o preço real (spec v2, seção 5; R2).

Nenhuma fonte de eventos é confiável sozinha: a da B3 omite o desdobramento
de 2005 da PETR4 (investigação 0002). A reconciliação prova o ajuste — cada
evento de capital tem de explicar o salto que causou, e nenhum salto pode
ficar sem evento. Qualquer divergência vira pendência; série com pendência
não é declarada verificada.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from market_data_lake.domain.adjustment import (
    CAPITAL_KINDS,
    AdjustmentResult,
    EventKind,
    EventOrigin,
)
from market_data_lake.domain.entities import OHLCVBar


@dataclass(frozen=True, slots=True)
class Tolerances:
    capital_event: float = 0.10  # razão observada a ±10% do fator esperado
    gap_low: float = 0.75  # abertura / fechamento anterior fora de [0,75; 1,33]
    gap_high: float = 1.33  # sem evento é salto não explicado
    cash_pct_points: float = 0.01  # percentual da B3 x valor / fechamento
    cash_close_rel: float = 0.005  # fechamento da data-com: B3 x COTAHIST


DEFAULT_TOLERANCES = Tolerances()  # valores da spec v2, seção 5


class PendencyKind(StrEnum):
    CAPITAL_MISMATCH = "evento de capital não explica o salto"
    UNEXPLAINED_GAP = "salto sem evento"
    CASH_INCOHERENT = "percentual do provento incoerente com o valor"
    CASH_CLOSE_MISMATCH = "fechamento da data-com diverge do COTAHIST"
    UNSUPPORTED_EVENT = "evento sem fator de ajuste"


@dataclass(frozen=True, slots=True)
class Pendency:
    kind: PendencyKind
    bar_date: date
    detail: str


ADJUSTMENT_METHOD = (
    "ajuste multiplicativo para trás por proventos (desdobramento, grupamento, "
    "bonificação, dividendos, JCP); fatores das rotas de listadas da B3 e da tabela "
    "de correções curada; reconciliação contra o COTAHIST; volume não ajustado"
)


@dataclass(frozen=True, slots=True)
class AdjustmentDeclaration:
    """O que se pode afirmar sobre o ajuste de uma série (spec v2, R4).

    `verified` só com série ajustada e zero pendências: é o que o item 7 do
    checklist do backtesting-engine exige (ADR-0013).
    """

    ticker: str
    start: date
    end: date
    adjusted: bool
    method: str
    reason: str | None = None  # por que não foi ajustada, quando não foi
    sources: tuple[str, ...] = ()
    events_applied: tuple[tuple[str, int], ...] = ()  # (tipo, quantidade)
    derived_factors: int = 0
    tolerances: Tolerances = DEFAULT_TOLERANCES
    pendencies: tuple[Pendency, ...] = ()

    @property
    def verified(self) -> bool:
        return self.adjusted and not self.pendencies


def reconcile(
    raw: Sequence[OHLCVBar],
    result: AdjustmentResult,
    tolerances: Tolerances = DEFAULT_TOLERANCES,
) -> tuple[Pendency, ...]:
    raw_bars = sorted(raw, key=lambda bar: bar.bar_date)
    adjusted = list(result.bars)
    index_by_date = {bar.bar_date: i for i, bar in enumerate(raw_bars)}
    pendencies: list[Pendency] = []

    capital_dates = {r.ex_date for r in result.applied if r.event.kind in CAPITAL_KINDS}
    for ex_date in sorted(capital_dates):
        # Esperado: todos os fatores daquele dia (um provento pode coincidir).
        expected = math.prod(r.price_factor for r in result.applied if r.ex_date == ex_date)
        i = index_by_date[ex_date]
        observed = raw_bars[i].open / raw_bars[i - 1].close
        if abs(observed / expected - 1) > tolerances.capital_event:
            pendencies.append(
                Pendency(
                    PendencyKind.CAPITAL_MISMATCH,
                    ex_date,
                    f"razão observada {observed:.4f}, fator esperado {expected:.4f}",
                )
            )

    for previous, current in zip(adjusted, adjusted[1:], strict=False):
        if current.bar_date in capital_dates:
            continue  # já conferido acima, contra o fator do evento
        ratio = current.open / previous.close
        if not tolerances.gap_low <= ratio <= tolerances.gap_high:
            pendencies.append(
                Pendency(
                    PendencyKind.UNEXPLAINED_GAP,
                    current.bar_date,
                    f"abertura / fechamento anterior = {ratio:.4f} sem evento que explique",
                )
            )

    for resolved in result.applied:
        event = resolved.event
        if event.kind is not EventKind.CASH or event.origin is not EventOrigin.B3:
            continue
        if event.value_per_share is None or not event.reference_close:
            continue
        if not event.factor_derived:
            informed = (1 - resolved.price_factor) * 100
            implied = event.value_per_share / event.reference_close * 100
            if abs(informed - implied) > tolerances.cash_pct_points:
                pendencies.append(
                    Pendency(
                        PendencyKind.CASH_INCOHERENT,
                        resolved.ex_date,
                        f"{event.label}: B3 informa {informed:.6f}%, valor/fechamento dá "
                        f"{implied:.6f}%",
                    )
                )
        data_com = event.last_date_with_right
        if data_com in index_by_date:
            close = raw_bars[index_by_date[data_com]].close
            if abs(close / event.reference_close - 1) > tolerances.cash_close_rel:
                pendencies.append(
                    Pendency(
                        PendencyKind.CASH_CLOSE_MISMATCH,
                        data_com,
                        f"{event.label}: B3 informa fechamento {event.reference_close}, "
                        f"COTAHIST tem {close}",
                    )
                )

    for event in result.unsupported:
        event_date = event.last_date_with_right or event.ex_date or raw_bars[0].bar_date
        pendencies.append(
            Pendency(
                PendencyKind.UNSUPPORTED_EVENT,
                event_date,
                f"{event.label} ({event.origin}) sem fator: requer linha na tabela de correções",
            )
        )

    return tuple(sorted(pendencies, key=lambda p: (p.bar_date, p.kind)))
