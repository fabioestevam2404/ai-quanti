from __future__ import annotations

from collections import Counter
from datetime import date

from market_data_lake.application.get_price_series import EventsLoader
from market_data_lake.domain.adjustment import adjust_bars
from market_data_lake.domain.reconciliation import (
    ADJUSTMENT_METHOD,
    DEFAULT_TOLERANCES,
    AdjustmentDeclaration,
    Tolerances,
    reconcile,
)
from market_data_lake.domain.repositories import PriceRepository


class DeclareAdjustmentUseCase:
    """Ajusta, reconcilia e declara o resultado de uma série (spec v2, seção 6)."""

    def __init__(
        self,
        price_repository: PriceRepository,
        events_loader: EventsLoader,
        tolerances: Tolerances = DEFAULT_TOLERANCES,
    ) -> None:
        self._price_repository = price_repository
        self._load_events = events_loader
        self._tolerances = tolerances

    def execute(self, ticker: str, start: date, end: date) -> AdjustmentDeclaration:
        def not_adjusted(reason: str) -> AdjustmentDeclaration:
            return AdjustmentDeclaration(
                ticker, start, end, adjusted=False, method=ADJUSTMENT_METHOD, reason=reason
            )

        raw = self._price_repository.get_bars(ticker, start, end)
        if not raw:
            return not_adjusted(f"sem barras de {ticker} entre {start} e {end}")
        if any(bar.instrument.isin is None for bar in raw):
            # Sem ISIN não há como casar eventos de capital: fonte sem eventos (mock).
            return not_adjusted("série sem ISIN: a fonte não traz eventos (ex.: mock)")
        try:
            events = self._load_events(ticker)
        except LookupError as exc:
            return not_adjusted(str(exc))

        result = adjust_bars(raw, events)
        considered = [r.event for r in result.applied] + list(result.unsupported)
        return AdjustmentDeclaration(
            ticker=ticker,
            start=start,
            end=end,
            adjusted=True,
            method=ADJUSTMENT_METHOD,
            sources=tuple(sorted({event.source for event in considered if event.source})),
            events_applied=tuple(
                sorted(Counter(r.event.kind.value for r in result.applied).items())
            ),
            derived_factors=sum(1 for r in result.applied if r.event.factor_derived),
            tolerances=self._tolerances,
            pendencies=reconcile(raw, result, self._tolerances),
        )
