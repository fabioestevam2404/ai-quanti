"""Declaração de ajuste por série (spec v2, seção 6; R4)."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import date
from pathlib import Path

import pytest

from market_data_lake.api import get_adjustment_declaration, ingest_daily_bars
from market_data_lake.application.declare_adjustment import DeclareAdjustmentUseCase
from market_data_lake.domain.reconciliation import PendencyKind
from market_data_lake.infrastructure.corporate_events.b3_snapshot import parse_b3_snapshot
from market_data_lake.infrastructure.persistence.duckdb_bar_repository import DuckDBBarRepository

FIXTURES = Path(__file__).parent / "fixtures"


def _prepare_cotahist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *years: int) -> None:
    cache = tmp_path / "cotahist"
    cache.mkdir()
    for year in years:
        with zipfile.ZipFile(cache / f"COTAHIST_A{year}.ZIP", "w") as archive:
            archive.write(FIXTURES / "cotahist" / f"COTAHIST_A{year}.TXT", f"COTAHIST_A{year}.TXT")
    events = tmp_path / "b3_events"
    for code in ("PETR", "ITUB"):
        (events / code).mkdir(parents=True)
        shutil.copy(FIXTURES / "b3_events" / f"{code}.json", events / code / "2026-11-03.json")
    monkeypatch.setenv("MARKET_DATA_LAKE_COTAHIST_DIR", str(cache))
    monkeypatch.setenv("MARKET_DATA_LAKE_B3_EVENTS_DIR", str(events))


def test_serie_real_com_eventos_e_declarada_verificada(
    duckdb_path: Path, postgres_dsn: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(duckdb_path))
    _prepare_cotahist(tmp_path, monkeypatch, 2008)
    ingest_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30), source="cotahist")

    declaration = get_adjustment_declaration("PETR4", date(2008, 4, 1), date(2008, 4, 30))

    assert declaration.adjusted is True
    assert declaration.verified is True
    assert declaration.pendencies == ()
    assert dict(declaration.events_applied).get("desdobramento") == 1
    assert any(source.startswith("b3:PETR:") for source in declaration.sources)
    assert "COTAHIST" in declaration.method


def test_serie_do_mock_nao_e_declarada_ajustada(
    duckdb_path: Path, postgres_dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fonte sem eventos: o item 7 do backtest precisa continuar não verificado.
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(duckdb_path))
    ingest_daily_bars("PETR4", date(2026, 8, 3), date(2026, 8, 7), source="mock")

    declaration = get_adjustment_declaration("PETR4", date(2026, 8, 3), date(2026, 8, 7))

    assert declaration.adjusted is False
    assert declaration.verified is False
    assert declaration.reason is not None and "ISIN" in declaration.reason


def test_sem_snapshot_a_serie_nao_e_declarada_ajustada(
    duckdb_path: Path, postgres_dsn: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(duckdb_path))
    _prepare_cotahist(tmp_path, monkeypatch, 2008)
    ingest_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30), source="cotahist")
    monkeypatch.setenv("MARKET_DATA_LAKE_B3_EVENTS_DIR", str(tmp_path / "vazio"))

    declaration = get_adjustment_declaration("PETR4", date(2008, 4, 1), date(2008, 4, 30))

    assert declaration.adjusted is False
    assert declaration.reason is not None and "refresh_corporate_events" in declaration.reason


def test_pendencia_impede_a_declaracao_verificada(
    duckdb_path: Path, postgres_dsn: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sem a tabela de correções, o desdobramento de 2005 fica sem explicação.
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(duckdb_path))
    _prepare_cotahist(tmp_path, monkeypatch, 2005)
    ingest_daily_bars("PETR4", date(2005, 8, 1), date(2005, 9, 30), source="cotahist")
    snapshot = json.loads((FIXTURES / "b3_events" / "PETR.json").read_text(encoding="utf-8"))
    use_case = DeclareAdjustmentUseCase(
        price_repository=DuckDBBarRepository(duckdb_path),
        events_loader=lambda ticker: parse_b3_snapshot(snapshot),  # sem correções
    )

    declaration = use_case.execute("PETR4", date(2005, 8, 1), date(2005, 9, 30))

    assert declaration.adjusted is True
    assert declaration.verified is False
    assert [p.kind for p in declaration.pendencies] == [PendencyKind.UNEXPLAINED_GAP]
