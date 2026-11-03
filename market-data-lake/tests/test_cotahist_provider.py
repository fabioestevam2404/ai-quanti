"""Critérios 5 e 6 (v2): provider do COTAHIST — filtro, cache e retentativa.

Nenhum teste usa rede (critério 15): o download é substituído por uma função
que copia a amostra versionada para o destino.
"""

from __future__ import annotations

import os
import time
import zipfile
from datetime import date
from pathlib import Path

import pytest

from market_data_lake.infrastructure.providers.cotahist_provider import (
    CotahistDownloadError,
    CotahistProvider,
)

FIXTURES = Path(__file__).parent / "fixtures" / "cotahist"
TODAY = date(2026, 11, 2)


class _FakeDownloader:
    """Cria o ZIP do ano a partir da amostra; pode falhar nas primeiras chamadas."""

    def __init__(self, failures: int = 0, partial_on_failure: bool = True) -> None:
        self.calls: list[str] = []
        self._failures = failures
        self._partial = partial_on_failure

    def __call__(self, url: str, destination: Path) -> None:
        self.calls.append(url)
        if len(self.calls) <= self._failures:
            if self._partial:
                destination.write_bytes(b"PK\x03\x04 metade de um zip")  # download cortado
            raise ConnectionError("conexão encerrada pelo servidor")
        year = url.rsplit("COTAHIST_A", 1)[1][:4]
        sample = FIXTURES / f"COTAHIST_A{year}.TXT"
        with zipfile.ZipFile(destination, "w") as archive:
            if sample.exists():
                archive.write(sample, sample.name)
            else:
                archive.writestr(sample.name, "")  # ano sem amostra: arquivo sem cotações


def _provider(tmp_path: Path, downloader: _FakeDownloader) -> CotahistProvider:
    return CotahistProvider(
        cache_dir=tmp_path, download=downloader, sleep=lambda _: None, today=lambda: TODAY
    )


def test_so_mercado_a_vista_do_ticker_pedido(tmp_path: Path) -> None:
    bars = _provider(tmp_path, _FakeDownloader()).fetch_daily_bars(
        "PETR4", date(2008, 4, 1), date(2008, 4, 30)
    )

    assert [(b.bar_date, b.open, b.close) for b in bars] == [
        (date(2008, 4, 25), 84.0, 84.3),
        (date(2008, 4, 28), 42.58, 42.59),
    ]
    assert all(b.instrument.ticker == "PETR4" for b in bars)  # PETR4F (fracionário) fora


def test_mesmo_codigo_em_outro_mercado_fica_fora(tmp_path: Path) -> None:
    # PETR4F sai pelo código; o filtro de mercado existe para o mesmo código em
    # outro mercado. Variação sintética de uma linha real, com TPMERC 030 (termo).
    sample = (FIXTURES / "COTAHIST_A2008.TXT").read_text(encoding="latin-1").splitlines()
    real = next(line for line in sample if line[12:24].strip() == "PETR4")
    other_market = real[:2] + "20080429" + real[10:24] + "030" + real[27:]
    (tmp_path / "COTAHIST_A2008.ZIP").unlink(missing_ok=True)
    with zipfile.ZipFile(tmp_path / "COTAHIST_A2008.ZIP", "w") as archive:
        archive.writestr("COTAHIST_A2008.TXT", "\r\n".join([*sample, other_market]) + "\r\n")

    bars = _provider(tmp_path, _FakeDownloader()).fetch_daily_bars(
        "PETR4", date(2008, 4, 1), date(2008, 4, 30)
    )

    assert date(2008, 4, 29) not in [b.bar_date for b in bars]
    assert len(bars) == 2


def test_resposta_de_sucesso_que_nao_e_zip_nao_entra_no_cache(tmp_path: Path) -> None:
    # Servidor responde sem erro, mas com outra coisa (ex.: página HTML de erro).
    calls: list[str] = []

    def html_instead_of_zip(url: str, destination: Path) -> None:
        calls.append(url)
        destination.write_text("<html>serviço indisponível</html>", encoding="utf-8")

    provider = CotahistProvider(
        cache_dir=tmp_path, download=html_instead_of_zip, sleep=lambda _: None, today=lambda: TODAY
    )

    with pytest.raises(CotahistDownloadError, match="ZIP"):
        provider.fetch_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30))

    assert len(calls) == 3
    assert list(tmp_path.iterdir()) == []


def test_filtra_pelo_periodo_pedido(tmp_path: Path) -> None:
    bars = _provider(tmp_path, _FakeDownloader()).fetch_daily_bars(
        "PETR4", date(2008, 4, 28), date(2008, 4, 28)
    )

    assert [b.bar_date for b in bars] == [date(2008, 4, 28)]


def test_periodo_de_varios_anos_le_um_arquivo_por_ano(tmp_path: Path) -> None:
    downloader = _FakeDownloader()

    bars = _provider(tmp_path, downloader).fetch_daily_bars(
        "PETR4", date(2000, 6, 1), date(2008, 4, 30)
    )

    assert [b.bar_date.year for b in bars] == [2000, 2000, 2005, 2005, 2008, 2008]
    assert len(downloader.calls) == 9  # um arquivo por ano, de 2000 a 2008


def test_ano_ja_baixado_nao_e_baixado_de_novo(tmp_path: Path) -> None:
    downloader = _FakeDownloader()
    provider = _provider(tmp_path, downloader)

    provider.fetch_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30))
    provider.fetch_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30))
    _provider(tmp_path, downloader).fetch_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30))

    assert len(downloader.calls) == 1


def test_falha_no_meio_do_download_nao_deixa_arquivo_parcial(tmp_path: Path) -> None:
    downloader = _FakeDownloader(failures=2)

    bars = _provider(tmp_path, downloader).fetch_daily_bars(
        "PETR4", date(2008, 4, 1), date(2008, 4, 30)
    )

    assert len(downloader.calls) == 3
    assert len(bars) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["COTAHIST_A2008.ZIP"]
    assert zipfile.is_zipfile(tmp_path / "COTAHIST_A2008.ZIP")


def test_todas_as_tentativas_falham_e_erro_cita_a_url(tmp_path: Path) -> None:
    downloader = _FakeDownloader(failures=99)

    with pytest.raises(CotahistDownloadError, match="COTAHIST_A2008.ZIP"):
        _provider(tmp_path, downloader).fetch_daily_bars(
            "PETR4", date(2008, 4, 1), date(2008, 4, 30)
        )

    assert len(downloader.calls) == 3
    assert list(tmp_path.iterdir()) == []  # nada parcial fica no cache


def test_cache_corrompido_e_baixado_de_novo(tmp_path: Path) -> None:
    (tmp_path / "COTAHIST_A2008.ZIP").write_bytes(b"isto nao e um zip")
    downloader = _FakeDownloader()

    bars = _provider(tmp_path, downloader).fetch_daily_bars(
        "PETR4", date(2008, 4, 1), date(2008, 4, 30)
    )

    assert len(downloader.calls) == 1
    assert len(bars) == 2


def test_ano_corrente_vale_so_por_um_dia(tmp_path: Path) -> None:
    # O arquivo do ano em curso cresce a cada pregão: o de ontem está desatualizado.
    downloader = _FakeDownloader()
    provider = CotahistProvider(
        cache_dir=tmp_path,
        download=downloader,
        sleep=lambda _: None,
        today=lambda: date(2008, 12, 31),
    )
    provider.fetch_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30))
    cached = tmp_path / "COTAHIST_A2008.ZIP"
    two_days_ago = time.time() - 2 * 86_400
    os.utime(cached, (two_days_ago, two_days_ago))

    provider.fetch_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30))

    assert len(downloader.calls) == 2
