"""Eventos das rotas públicas (não documentadas) do portal de listadas da B3.

O ajuste lê sempre de um snapshot guardado (spec v2, R1): a resposta bruta,
com a data da coleta. Assim a série ajustada é reproduzível e não depende de
a rota continuar no ar.
"""

from __future__ import annotations

import base64
import json
import os
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from market_data_lake.domain.adjustment import CorporateEvent, EventKind, EventOrigin
from market_data_lake.infrastructure.http import system_trust_session

B3_LISTED_URL = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall"
DEFAULT_SNAPSHOT_DIR = Path("data") / "raw" / "b3_events"
PAGE_SIZE = 120
MIN_SECONDS_BETWEEN_CALLS = 1.0

Snapshot = dict[str, Any]
JsonFetcher = Callable[[str], Any]


def parse_b3_snapshot(snapshot: Snapshot) -> list[CorporateEvent]:
    source = f"b3:{snapshot['company_code']}:{snapshot['collected_on']}"
    events = [
        _capital_event(raw, source) for raw in snapshot["supplement"].get("stockDividends") or []
    ]
    events += [_cash_event(raw, source) for raw in snapshot.get("cash_dividends") or []]
    return events


def _capital_event(raw: dict[str, Any], source: str) -> CorporateEvent:
    label = str(raw["label"]).strip()
    factor = _number(raw.get("factor"))
    # Sentido do `factor` por tipo, confirmado no COTAHIST (investigação 0002):
    # desdobramento/bonificação = % de ações novas; grupamento = multiplicador.
    kind, price_factor = {
        "DESDOBRAMENTO": (EventKind.SPLIT, _from_new_shares_pct(factor)),
        "BONIFICACAO": (EventKind.BONUS, _from_new_shares_pct(factor)),
        "GRUPAMENTO": (EventKind.REVERSE_SPLIT, 1 / factor if factor else None),
    }.get(label, (EventKind.OTHER, None))
    return CorporateEvent(
        kind=kind,
        label=label,
        price_factor=price_factor,
        origin=EventOrigin.B3,
        last_date_with_right=_date(raw["lastDatePrior"]),
        isin=str(raw["isinCode"]).strip(),
        source=source,
    )


def _cash_event(raw: dict[str, Any], source: str) -> CorporateEvent:
    pct = _number(raw.get("corporateActionPrice"))
    # Antes do grupamento de 2000 a B3 cotava por lote de mil: valor e
    # fechamento vêm por lote (quotedPerShares = 1000). O percentual não muda.
    per_lot = _number(raw.get("quotedPerShares")) or 1.0
    value = _per_share(_number(raw.get("valueCash")), per_lot)
    close = _per_share(_number(raw.get("closingPricePriorExDate")), per_lot)
    price_factor, derived = _cash_factor(pct, value, close)
    return CorporateEvent(
        kind=EventKind.CASH,
        label=str(raw["corporateAction"]).strip(),
        price_factor=price_factor,
        origin=EventOrigin.B3,
        last_date_with_right=_date(raw["lastDatePriorEx"]),
        share_class=str(raw["typeStock"]).strip(),
        source=source,
        value_per_share=value,
        reference_close=close,
        factor_derived=derived,
    )


def _cash_factor(
    pct: float | None, value: float | None, close: float | None
) -> tuple[float | None, bool]:
    # corporateActionPrice é o percentual de ajuste da B3, igual a
    # valueCash / fechamento da data-com. Sem ele, a mesma conta, marcada como
    # derivada (a B3 tem RENDIMENTO de valor simbólico sem percentual).
    if pct is not None and 0 < pct < 100:
        return 1 - pct / 100, False
    if value is not None and close is not None and close > 0 and 0 <= value < close:
        return 1 - value / close, True
    return None, False


def _per_share(value: float | None, per_lot: float) -> float | None:
    return value / per_lot if value is not None else None


def _from_new_shares_pct(factor: float | None) -> float | None:
    return 1 / (1 + factor / 100) if factor is not None and factor > 0 else None


def _number(value: Any) -> float | None:
    # A B3 usa vírgula decimal e, às vezes, ponto de milhar: "1.234,56".
    if value is None or str(value).strip() == "":
        return None
    return float(str(value).strip().replace(".", "").replace(",", "."))


def _date(value: Any) -> date:
    return datetime.strptime(str(value).strip(), "%d/%m/%Y").date()


class B3CorporateEventsClient:
    """Coleta a resposta bruta das duas rotas, no máximo uma chamada por segundo."""

    def __init__(
        self,
        fetch_json: JsonFetcher | None = None,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._fetch_json = fetch_json or _fetch_json_with_system_trust
        self._sleep = sleep
        self._today = today

    def collect(self, company_code: str) -> Snapshot:
        supplement = self._call(
            "GetListedSupplementCompany",
            {
                "issuingCompany": company_code,
                "language": "pt-br",
            },
        )
        company = supplement[0] if isinstance(supplement, list) else supplement
        trading_name = str(company["tradingName"]).strip()  # vem com espaços sobrando
        cash: list[Any] = []
        page, pages = 1, 1
        while page <= pages:
            response = self._call(
                "GetListedCashDividends",
                {
                    "language": "pt-br",
                    "pageNumber": page,
                    "pageSize": PAGE_SIZE,
                    "tradingName": trading_name,
                },
            )
            cash += response.get("results") or []
            pages = int(response.get("page", {}).get("totalPages") or 1)
            page += 1
        return {
            "company_code": company_code,
            "trading_name": trading_name,
            "collected_on": self._today().isoformat(),
            "supplement": company,
            "cash_dividends": cash,
        }

    def _call(self, route: str, payload: dict[str, Any]) -> Any:
        self._sleep(MIN_SECONDS_BETWEEN_CALLS)
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        return self._fetch_json(f"{B3_LISTED_URL}/{route}/{encoded}")


def _fetch_json_with_system_trust(url: str) -> Any:
    response = system_trust_session().get(url, timeout=(10, 60))
    response.raise_for_status()
    return response.json()


class SnapshotStore:
    """Um arquivo JSON por coleta: `{dir}/{empresa}/{AAAA-MM-DD}.json`."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = Path(
            directory or os.environ.get("MARKET_DATA_LAKE_B3_EVENTS_DIR") or DEFAULT_SNAPSHOT_DIR
        )

    def save(self, snapshot: Snapshot) -> Path:
        folder = self._directory / snapshot["company_code"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{snapshot['collected_on']}.json"
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_latest(self, company_code: str) -> Snapshot | None:
        folder = self._directory / company_code
        files = sorted(folder.glob("*.json")) if folder.exists() else []
        if not files:
            return None
        loaded: Snapshot = json.loads(files[-1].read_text(encoding="utf-8"))
        return loaded
