"""Tabela de correções curada (spec v2, R3): eventos ausentes ou errados na B3.

Versionada no repositório, uma linha por evento, sempre com a fonte. A linha
prevalece sobre o evento da B3 da mesma natureza na mesma data ex.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from market_data_lake.domain.adjustment import CorporateEvent, EventKind, EventOrigin

# market-data-lake/reference/ — fora de src/, como as migrações (ADR-0012).
DEFAULT_PATH = (
    Path(__file__).resolve().parents[4] / "reference" / "corporate_events_corrections.csv"
)

_KINDS = {
    "desdobramento": EventKind.SPLIT,
    "bonificação": EventKind.BONUS,
    "grupamento": EventKind.REVERSE_SPLIT,
    "cisão": EventKind.OTHER,
    "provento": EventKind.CASH,
}


def load_corrections(path: Path = DEFAULT_PATH) -> list[CorporateEvent]:
    with path.open(encoding="utf-8", newline="") as file:
        return [_to_event(row, line) for line, row in enumerate(csv.DictReader(file), start=2)]


def _to_event(row: dict[str, str], line: int) -> CorporateEvent:
    kind = _KINDS.get(row["tipo"].strip())
    if kind is None:
        raise ValueError(f"linha {line}: tipo desconhecido {row['tipo']!r}")
    if not row["fonte"].strip():
        raise ValueError(f"linha {line}: correção sem fonte")
    return CorporateEvent(
        kind=kind,
        label=row["tipo"].strip(),
        price_factor=float(row["price_factor"]),
        origin=EventOrigin.CORRECTION,
        ex_date=date.fromisoformat(row["ex_date"].strip()),
        ticker=row["ticker"].strip(),
        source=row["fonte"].strip(),
    )
