"""Critérios 14 e 15 (v2): ingestão via API com source="cotahist", sem rede.

O cache já contém o ZIP montado a partir da amostra real: o provider não tem
motivo para baixar nada, e a ingestão grava no DuckDB e na auditoria reais.
"""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest

from market_data_lake.api import get_price_series, ingest_daily_bars
from market_data_lake.domain.entities import IngestionStatus

FIXTURES = Path(__file__).parent / "fixtures" / "cotahist"


def test_ingere_do_cotahist_e_le_pela_api(
    duckdb_path: Path, postgres_dsn: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cotahist"
    cache.mkdir()
    with zipfile.ZipFile(cache / "COTAHIST_A2008.ZIP", "w") as archive:
        archive.write(FIXTURES / "COTAHIST_A2008.TXT", "COTAHIST_A2008.TXT")
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MARKET_DATA_LAKE_COTAHIST_DIR", str(cache))

    run = ingest_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30), source="cotahist")

    assert run.status == IngestionStatus.SUCCESS
    assert run.source == "cotahist"
    bars = get_price_series("PETR4", date(2008, 4, 1), date(2008, 4, 30))
    assert [(b.bar_date, b.close) for b in bars] == [
        (date(2008, 4, 25), 84.3),
        (date(2008, 4, 28), 42.59),
    ]
