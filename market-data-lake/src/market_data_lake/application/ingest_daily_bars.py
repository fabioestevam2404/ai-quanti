from __future__ import annotations

from datetime import UTC, date, datetime

from market_data_lake.domain.entities import IngestionRun, IngestionStatus
from market_data_lake.domain.providers import MarketDataProvider
from market_data_lake.domain.repositories import IngestionLogRepository, PriceRepository


class IngestDailyBarsUseCase:
    def __init__(
        self,
        provider: MarketDataProvider,
        price_repository: PriceRepository,
        ingestion_log_repository: IngestionLogRepository,
    ) -> None:
        self._provider = provider
        self._price_repository = price_repository
        self._ingestion_log_repository = ingestion_log_repository

    def execute(self, ticker: str, start: date, end: date) -> IngestionRun:
        executed_at = datetime.now(UTC)
        try:
            bars = self._provider.fetch_daily_bars(ticker, start, end)
            self._price_repository.save_bars(bars)
        except Exception as exc:
            failed_run = IngestionRun(
                ticker=ticker,
                source=self._provider.name,
                period_start=start,
                period_end=end,
                bars_ingested=0,
                status=IngestionStatus.FAILED,
                executed_at=executed_at,
                error_message=str(exc),
            )
            self._ingestion_log_repository.save_run(failed_run)
            raise

        run = IngestionRun(
            ticker=ticker,
            source=self._provider.name,
            period_start=start,
            period_end=end,
            bars_ingested=len(bars),
            status=IngestionStatus.SUCCESS,
            executed_at=executed_at,
        )
        self._ingestion_log_repository.save_run(run)
        return run
