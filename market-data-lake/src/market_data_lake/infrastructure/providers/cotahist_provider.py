from __future__ import annotations

import io
import os
import time
import zipfile
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

from market_data_lake.domain.entities import Instrument, OHLCVBar
from market_data_lake.infrastructure.http import system_trust_session
from market_data_lake.infrastructure.providers.cotahist_parser import (
    CotahistQuote,
    parse_cotahist,
)

COTAHIST_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
DEFAULT_CACHE_DIR = Path("data") / "raw" / "cotahist"
SPOT_MARKET = "010"
CURRENT_YEAR_MAX_AGE_SECONDS = 86_400

Downloader = Callable[[str, Path], None]


class CotahistDownloadError(RuntimeError):
    """Download do arquivo anual falhou em todas as tentativas."""


def download_with_system_trust(url: str, destination: Path) -> None:
    with system_trust_session().get(url, stream=True, timeout=(10, 300)) as response:
        response.raise_for_status()
        with destination.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1 << 20):
                file.write(chunk)


class CotahistProvider:
    """Séries históricas oficiais da B3 (decisão 4 da visão, spec v2).

    Um arquivo anual por ano pedido, guardado em cache. Ano passado não muda
    e é baixado uma vez; o arquivo do ano em curso cresce a cada pregão e
    vale por um dia. Preços **brutos**: o ajuste por proventos é outra etapa.
    """

    name = "cotahist"

    def __init__(
        self,
        cache_dir: Path | None = None,
        download: Downloader = download_with_system_trust,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
        max_attempts: int = 3,
    ) -> None:
        self._cache_dir = Path(
            cache_dir or os.environ.get("MARKET_DATA_LAKE_COTAHIST_DIR") or DEFAULT_CACHE_DIR
        )
        self._download = download
        self._sleep = sleep
        self._today = today
        self._max_attempts = max_attempts

    def fetch_daily_bars(self, ticker: str, start: date, end: date) -> list[OHLCVBar]:
        if end < start:
            raise ValueError(f"end ({end}) anterior a start ({start})")
        bars: list[OHLCVBar] = []
        for year in range(start.year, end.year + 1):
            # O fracionário tem código próprio (PETR4F) e TPMERC 020: o filtro
            # por código exato e mercado à vista exclui os dois.
            for quote in _read_quotes(self._archive_for(year), ticker):
                if start <= quote.trade_date <= end:
                    bars.append(_to_bar(quote))
        return sorted(bars, key=lambda bar: bar.bar_date)

    def _archive_for(self, year: int) -> Path:
        archive = self._cache_dir / f"COTAHIST_A{year}.ZIP"
        if not self._is_fresh(archive, year):
            self._download_year(year, archive)
        return archive

    def _is_fresh(self, archive: Path, year: int) -> bool:
        if not archive.exists() or not zipfile.is_zipfile(archive):
            return False
        if year < self._today().year:
            return True
        return time.time() - archive.stat().st_mtime <= CURRENT_YEAR_MAX_AGE_SECONDS

    def _download_year(self, year: int, archive: Path) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        url = COTAHIST_URL.format(year=year)
        partial = archive.with_name(archive.name + ".part")
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                self._download(url, partial)
                if not zipfile.is_zipfile(partial):
                    raise ValueError("conteúdo baixado não é um ZIP válido")
                partial.replace(archive)  # só um arquivo completo entra no cache
                return
            except Exception as exc:  # rede, HTTP, ZIP truncado: todos tentam de novo
                last_error = exc
                partial.unlink(missing_ok=True)
                if attempt < self._max_attempts:
                    self._sleep(2 ** (attempt - 1))
        raise CotahistDownloadError(
            f"falha ao baixar {url} após {self._max_attempts} tentativas: {last_error}"
        ) from last_error


def _read_quotes(archive: Path, ticker: str) -> Iterator[CotahistQuote]:
    with zipfile.ZipFile(archive) as zipped:
        members = [name for name in zipped.namelist() if name.upper().endswith(".TXT")]
        if not members:
            raise ValueError(f"{archive.name} não contém o arquivo TXT do COTAHIST")
        with zipped.open(members[0]) as raw:
            yield from parse_cotahist(
                io.TextIOWrapper(raw, encoding="latin-1"), ticker=ticker, market_type=SPOT_MARKET
            )


def _to_bar(quote: CotahistQuote) -> OHLCVBar:
    return OHLCVBar(
        # ISIN por barra: liga o ticker à classe de ação dos eventos da B3.
        instrument=Instrument(ticker=quote.ticker, isin=quote.isin),
        bar_date=quote.trade_date,
        open=quote.open,
        high=quote.high,
        low=quote.low,
        close=quote.close,
        volume=quote.volume,
    )
