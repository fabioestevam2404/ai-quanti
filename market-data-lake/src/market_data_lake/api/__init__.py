"""API pública do market-data-lake — único ponto de acesso para outros módulos.

`feature-store`, `backtesting-engine` e `risk-engine` devem importar apenas
daqui, nunca de `market_data_lake.domain`/`application`/`infrastructure`
(fronteira validada por import-linter, ver docs/spec.md e ADR-0001).
"""

from __future__ import annotations

from datetime import date

from market_data_lake.application.get_price_series import GetPriceSeriesUseCase
from market_data_lake.application.ingest_daily_bars import IngestDailyBarsUseCase
from market_data_lake.domain.entities import IngestionRun, OHLCVBar
from market_data_lake.domain.providers import MarketDataProvider
from market_data_lake.infrastructure.persistence.duckdb_bar_repository import (
    DuckDBBarRepository,
)
from market_data_lake.infrastructure.persistence.postgres_ingestion_log_repository import (
    PostgresIngestionLogRepository,
)
from market_data_lake.infrastructure.providers.alpha_vantage_provider import (
    AlphaVantageProvider,
)
from market_data_lake.infrastructure.providers.cotahist_provider import CotahistProvider
from market_data_lake.infrastructure.providers.mock_provider import MockMarketDataProvider

_PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "mock": MockMarketDataProvider,
    "alpha_vantage": AlphaVantageProvider,
    "cotahist": CotahistProvider,  # séries oficiais da B3, preços brutos (spec v2)
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


def get_price_series(ticker: str, start: date, end: date) -> list[OHLCVBar]:
    """Lê a série histórica de preços já ingerida."""
    use_case = GetPriceSeriesUseCase(price_repository=DuckDBBarRepository())
    return use_case.execute(ticker, start, end)
