"""API pública do market-data-lake — único ponto de acesso para outros módulos.

`feature-store`, `backtesting-engine` e `risk-engine` devem importar apenas
daqui, nunca de `market_data_lake.domain`/`application`/`infrastructure`
(fronteira validada por import-linter, ver docs/spec.md e ADR-0001).
"""

from __future__ import annotations

from datetime import date

from market_data_lake.application.declare_adjustment import DeclareAdjustmentUseCase
from market_data_lake.application.get_price_series import GetPriceSeriesUseCase
from market_data_lake.application.ingest_daily_bars import IngestDailyBarsUseCase
from market_data_lake.domain.adjustment import CorporateEvent
from market_data_lake.domain.entities import IngestionRun, OHLCVBar
from market_data_lake.domain.providers import MarketDataProvider
from market_data_lake.domain.reconciliation import AdjustmentDeclaration

# Reexportados para outros módulos (ex.: item 7 do backtesting-engine), que só
# podem importar desta API (ADR-0001).
from market_data_lake.domain.reconciliation import Pendency as Pendency
from market_data_lake.domain.reconciliation import PendencyKind as PendencyKind
from market_data_lake.domain.reconciliation import Tolerances as Tolerances
from market_data_lake.infrastructure.corporate_events.b3_snapshot import (
    B3CorporateEventsClient,
    SnapshotStore,
    parse_b3_snapshot,
)
from market_data_lake.infrastructure.corporate_events.corrections import load_corrections
from market_data_lake.infrastructure.persistence.duckdb_bar_repository import (
    DuckDBBarRepository,
)
from market_data_lake.infrastructure.persistence.postgres_ingestion_log_repository import (
    PostgresIngestionLogRepository,
)
from market_data_lake.infrastructure.providers.cotahist_provider import CotahistProvider
from market_data_lake.infrastructure.providers.mock_provider import MockMarketDataProvider

_PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "mock": MockMarketDataProvider,
    # Séries oficiais da B3, preços brutos (spec v2). A Alpha Vantage saiu: no
    # plano gratuito só entrega ~100 barras sem ajuste (investigação 0001).
    "cotahist": CotahistProvider,
}


def _build_provider(source: str) -> MarketDataProvider:
    provider_cls = _PROVIDERS.get(source)
    if provider_cls is None:
        raise ValueError(f"Fonte desconhecida: {source!r}. Opções: {list(_PROVIDERS)}")
    return provider_cls()


def ingest_daily_bars(ticker: str, start: date, end: date, source: str) -> IngestionRun:
    """Ingere barras diárias OHLCV e registra auditoria da execução.

    `source` é obrigatório e sem default deliberadamente: um job agendado
    sem esse parâmetro explícito não deve conseguir ingerir dados
    sintéticos (`mock`) silenciosamente em vez de dados reais.
    """
    use_case = IngestDailyBarsUseCase(
        provider=_build_provider(source),
        price_repository=DuckDBBarRepository(),
        ingestion_log_repository=PostgresIngestionLogRepository(),
    )
    return use_case.execute(ticker, start, end)


def get_price_series(ticker: str, start: date, end: date, adjusted: bool = False) -> list[OHLCVBar]:
    """Lê a série histórica de preços já ingerida.

    `adjusted=True` ajusta por proventos a partir do último snapshot de
    eventos da B3 e da tabela de correções (spec v2). O padrão continua
    bruto, para não mudar o comportamento de quem já usa a função.
    """
    use_case = GetPriceSeriesUseCase(
        price_repository=DuckDBBarRepository(), events_loader=_load_events
    )
    return use_case.execute(ticker, start, end, adjusted=adjusted)


def get_adjustment_declaration(ticker: str, start: date, end: date) -> AdjustmentDeclaration:
    """Declara se a série do período está ajustada e reconciliada (spec v2, R4).

    `verified` só com zero pendências na reconciliação contra o COTAHIST. Série
    sem eventos (mock) ou sem snapshot é declarada não ajustada, com o motivo.
    """
    use_case = DeclareAdjustmentUseCase(
        price_repository=DuckDBBarRepository(), events_loader=_load_events
    )
    return use_case.execute(ticker, start, end)


def refresh_corporate_events(ticker: str) -> date:
    """Coleta os eventos da empresa nas rotas da B3 e guarda um snapshot novo.

    Devolve a data da coleta. Faz chamadas de rede; o ajuste em si só lê
    snapshots já guardados.
    """
    store = SnapshotStore()
    snapshot = B3CorporateEventsClient().collect(_company_code(ticker))
    store.save(snapshot)
    return date.fromisoformat(snapshot["collected_on"])


def _company_code(ticker: str) -> str:
    return ticker[:4]  # convenção da B3: PETR4 -> PETR


def _load_events(ticker: str) -> list[CorporateEvent]:
    snapshot = SnapshotStore().load_latest(_company_code(ticker))
    if snapshot is None:
        raise LookupError(
            f"sem snapshot de eventos da B3 para {ticker}: "
            f"rode refresh_corporate_events({ticker!r}) antes de pedir série ajustada"
        )
    return parse_b3_snapshot(snapshot) + load_corrections()
