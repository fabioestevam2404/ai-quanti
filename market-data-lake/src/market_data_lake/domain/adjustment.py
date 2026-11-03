"""Ajuste de preços por proventos (spec v2, seção 4).

Multiplicativo e para trás: cada preço anterior à data ex de um evento é
multiplicado pelo fator de preço do evento. O último preço da série nunca
muda, e eventos posteriores ao fim da série não entram.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from market_data_lake.domain.entities import OHLCVBar


class EventKind(StrEnum):
    SPLIT = "desdobramento"
    BONUS = "bonificação"
    REVERSE_SPLIT = "grupamento"
    CASH = "provento em dinheiro"
    OTHER = "outro"  # cisão, redução de capital...: sem fator automático


class EventOrigin(StrEnum):
    B3 = "b3"
    CORRECTION = "correção"


CAPITAL_KINDS = frozenset(
    {EventKind.SPLIT, EventKind.BONUS, EventKind.REVERSE_SPLIT, EventKind.OTHER}
)
_SHARE_CLASS_BY_SUFFIX = {"3": "ON", "4": "PN", "5": "PNA", "6": "PNB"}


def share_class_of(ticker: str) -> str | None:
    """Classe pela convenção da B3: final 3 = ON, 4 = PN, 5 = PNA, 6 = PNB."""
    return _SHARE_CLASS_BY_SUFFIX.get(ticker[-1:])


@dataclass(frozen=True, slots=True)
class CorporateEvent:
    """Um evento que muda o preço. Identifica o ativo por ISIN (eventos de
    capital da B3), por classe (proventos em dinheiro da B3) ou por ticker
    (tabela de correções)."""

    kind: EventKind
    label: str
    price_factor: float | None  # None = sem fator automático: vira "não suportado"
    origin: EventOrigin
    last_date_with_right: date | None = None  # data-com (B3)
    ex_date: date | None = None  # data ex (tabela de correções)
    isin: str | None = None
    share_class: str | None = None
    ticker: str | None = None
    source: str = ""
    value_per_share: float | None = None  # proventos em dinheiro: para a reconciliação
    reference_close: float | None = None  # fechamento na data-com informado pela B3
    factor_derived: bool = False  # fator calculado por nós, sem o percentual da B3

    def __post_init__(self) -> None:
        if (self.last_date_with_right is None) == (self.ex_date is None):
            raise ValueError("evento precisa de exatamente uma data: data-com ou data ex")
        if self.isin is None and self.share_class is None and self.ticker is None:
            raise ValueError("evento precisa identificar o ativo (ISIN, classe ou ticker)")
        if self.price_factor is not None and self.price_factor <= 0:
            raise ValueError(f"fator de preço precisa ser positivo: {self.price_factor}")

    def applies_to(self, ticker: str, isins: set[str]) -> bool:
        if self.ticker is not None:
            return self.ticker == ticker
        if self.isin is not None:
            return self.isin in isins
        return self.share_class == share_class_of(ticker)


@dataclass(frozen=True, slots=True)
class ResolvedEvent:
    event: CorporateEvent
    ex_date: date  # primeiro pregão da série em que o preço já está ex
    price_factor: float


@dataclass(frozen=True, slots=True)
class AdjustmentResult:
    bars: tuple[OHLCVBar, ...]
    applied: tuple[ResolvedEvent, ...]
    unsupported: tuple[CorporateEvent, ...]


def adjust_bars(bars: Iterable[OHLCVBar], events: Iterable[CorporateEvent]) -> AdjustmentResult:
    ordered = sorted(bars, key=lambda bar: bar.bar_date)
    if not ordered:
        return AdjustmentResult(bars=(), applied=(), unsupported=())
    ticker = ordered[0].instrument.ticker
    isins = {bar.instrument.isin for bar in ordered if bar.instrument.isin}
    dates = [bar.bar_date for bar in ordered]

    # dict.fromkeys: a B3 repete linhas idênticas (ex.: a cisão do Itaú).
    relevant = list(dict.fromkeys(e for e in events if e.applies_to(ticker, isins)))
    located = [(event, _ex_date_in_series(event, dates)) for event in relevant]
    in_series = [(event, ex) for event, ex in located if ex is not None]

    # Correção prevalece sobre o evento da B3 da mesma natureza na mesma data ex.
    corrected = {
        (ex, event.kind in CAPITAL_KINDS)
        for event, ex in in_series
        if event.origin is EventOrigin.CORRECTION
    }
    kept = [
        (event, ex)
        for event, ex in in_series
        if event.origin is EventOrigin.CORRECTION
        or (ex, event.kind in CAPITAL_KINDS) not in corrected
    ]

    applied = tuple(
        ResolvedEvent(event=event, ex_date=ex, price_factor=event.price_factor)
        for event, ex in sorted(kept, key=lambda item: item[1])
        if event.price_factor is not None
    )
    unsupported = tuple(event for event, _ in kept if event.price_factor is None)
    return AdjustmentResult(
        bars=tuple(_apply(ordered, applied)), applied=applied, unsupported=unsupported
    )


def _ex_date_in_series(event: CorporateEvent, dates: list[date]) -> date | None:
    """Primeiro pregão já ex, se houver pregão da série antes dele (senão, sem efeito)."""
    if event.ex_date is not None:
        ex_date = event.ex_date
        candidates = [d for d in dates if d >= ex_date]
    elif event.last_date_with_right is not None:
        data_com = event.last_date_with_right
        candidates = [d for d in dates if d > data_com]
    else:  # impossível pelo __post_init__; explícito para não depender de assert
        raise ValueError("evento sem data")
    if not candidates or candidates[0] == dates[0]:
        return None
    return candidates[0]


def _apply(ordered: list[OHLCVBar], applied: tuple[ResolvedEvent, ...]) -> list[OHLCVBar]:
    # Varre de trás para frente acumulando os fatores dos eventos já passados.
    pending = sorted(applied, key=lambda resolved: resolved.ex_date, reverse=True)
    factor = 1.0
    index = 0
    adjusted: list[OHLCVBar] = []
    for bar in reversed(ordered):
        while index < len(pending) and pending[index].ex_date > bar.bar_date:
            factor *= pending[index].price_factor
            index += 1
        if factor == 1.0:
            adjusted.append(bar)
        else:
            adjusted.append(
                replace(
                    bar,
                    open=bar.open * factor,
                    high=bar.high * factor,
                    low=bar.low * factor,
                    close=bar.close * factor,
                )
            )
    adjusted.reverse()
    return adjusted
