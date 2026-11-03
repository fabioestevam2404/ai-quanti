"""Critérios 7 a 10 e 12 (spec v2): ajuste com dados reais.

Preços: linhas reais do COTAHIST (fixtures/cotahist). Eventos: snapshots reais
da B3 (fixtures/b3_events) e a tabela de correções versionada. Nenhum teste
usa rede.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import date
from pathlib import Path

import pytest

from market_data_lake.api import get_price_series, ingest_daily_bars
from market_data_lake.domain.adjustment import CorporateEvent, EventOrigin, adjust_bars
from market_data_lake.domain.entities import OHLCVBar
from market_data_lake.infrastructure.corporate_events.b3_snapshot import parse_b3_snapshot
from market_data_lake.infrastructure.corporate_events.corrections import load_corrections
from market_data_lake.infrastructure.providers.cotahist_provider import CotahistProvider

FIXTURES = Path(__file__).parent / "fixtures"
NO_JUMP = (0.9, 1.1)  # razão abertura(ex) / fechamento(com) depois do ajuste


def _download_from_fixtures(url: str, destination: Path) -> None:
    year = url.rsplit("COTAHIST_A", 1)[1][:4]
    sample = FIXTURES / "cotahist" / f"COTAHIST_A{year}.TXT"
    with zipfile.ZipFile(destination, "w") as archive:
        if sample.exists():
            archive.write(sample, sample.name)
        else:
            archive.writestr(sample.name, "")


def _raw(ticker: str, start: date, end: date, tmp_path: Path) -> list[OHLCVBar]:
    provider = CotahistProvider(
        cache_dir=tmp_path, download=_download_from_fixtures, sleep=lambda _: None
    )
    return provider.fetch_daily_bars(ticker, start, end)


def _events(code: str, with_corrections: bool = True) -> list[CorporateEvent]:
    snapshot = json.loads((FIXTURES / "b3_events" / f"{code}.json").read_text(encoding="utf-8"))
    return parse_b3_snapshot(snapshot) + (load_corrections() if with_corrections else [])


def _gap(bars: list[OHLCVBar] | tuple[OHLCVBar, ...], before: date, after: date) -> float:
    by_date = {b.bar_date: b for b in bars}
    return by_date[after].open / by_date[before].close


def test_desdobramento_de_2008_e_grupamento_de_2000_sem_salto(tmp_path: Path) -> None:
    # Critério 8: o sentido do fator, confirmado na investigação 0002.
    raw = _raw("PETR4", date(2000, 6, 1), date(2008, 4, 30), tmp_path)
    assert _gap(raw, date(2008, 4, 25), date(2008, 4, 28)) == pytest.approx(0.505, abs=0.01)

    adjusted = adjust_bars(raw, _events("PETR")).bars

    assert NO_JUMP[0] < _gap(adjusted, date(2008, 4, 25), date(2008, 4, 28)) < NO_JUMP[1]
    assert NO_JUMP[0] < _gap(adjusted, date(2000, 6, 21), date(2000, 6, 23)) < NO_JUMP[1]


def test_desdobramento_de_2005_so_existe_na_tabela_de_correcoes(tmp_path: Path) -> None:
    # Critério 9: sem a correção, a queda de 75% continua na série.
    raw = _raw("PETR4", date(2005, 8, 1), date(2005, 9, 30), tmp_path)

    without = adjust_bars(raw, _events("PETR", with_corrections=False)).bars
    with_fix = adjust_bars(raw, _events("PETR")).bars

    assert _gap(without, date(2005, 8, 31), date(2005, 9, 1)) == pytest.approx(0.25, abs=0.01)
    assert NO_JUMP[0] < _gap(with_fix, date(2005, 8, 31), date(2005, 9, 1)) < NO_JUMP[1]


def test_cisao_da_itub4_ajustada_pela_correcao(tmp_path: Path) -> None:
    # Critério 10: fator 0,8246; razão observada 0,834 vira ~1,01 depois do ajuste.
    raw = _raw("ITUB4", date(2021, 9, 1), date(2021, 10, 31), tmp_path)

    without = adjust_bars(raw, _events("ITUB", with_corrections=False))
    with_fix = adjust_bars(raw, _events("ITUB"))

    assert any(e.label.startswith("CIS RED CAP") for e in without.unsupported)
    assert with_fix.unsupported == ()
    assert any(r.event.origin is EventOrigin.CORRECTION for r in with_fix.applied)
    ratio = _gap(with_fix.bars, date(2021, 10, 1), date(2021, 10, 4))
    assert ratio == pytest.approx(24.75 / (29.67 * 0.8246), rel=0.01)


def test_ultimo_preco_igual_ao_bruto(tmp_path: Path) -> None:
    # Critério 12.
    raw = _raw("PETR4", date(2000, 6, 1), date(2008, 4, 30), tmp_path)

    adjusted = adjust_bars(raw, _events("PETR")).bars

    assert adjusted[-1] == raw[-1]


def test_api_ajusta_a_partir_do_snapshot_sem_rede(
    duckdb_path: Path, postgres_dsn: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Critério 7: com o snapshot guardado, a série ajustada sai igual, sem rede.
    cotahist = tmp_path / "cotahist"
    cotahist.mkdir()
    _download_from_fixtures("COTAHIST_A2008.ZIP", cotahist / "COTAHIST_A2008.ZIP")
    events_dir = tmp_path / "b3_events" / "PETR"
    events_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / "b3_events" / "PETR.json", events_dir / "2026-11-03.json")
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MARKET_DATA_LAKE_COTAHIST_DIR", str(cotahist))
    monkeypatch.setenv("MARKET_DATA_LAKE_B3_EVENTS_DIR", str(tmp_path / "b3_events"))
    ingest_daily_bars("PETR4", date(2008, 4, 1), date(2008, 4, 30), source="cotahist")

    raw = get_price_series("PETR4", date(2008, 4, 1), date(2008, 4, 30))
    first = get_price_series("PETR4", date(2008, 4, 1), date(2008, 4, 30), adjusted=True)
    second = get_price_series("PETR4", date(2008, 4, 1), date(2008, 4, 30), adjusted=True)

    assert first == second
    assert raw[0].close == 84.3  # padrão continua bruto (critério 14)
    assert first[0].close == pytest.approx(84.3 * 0.5, rel=0.02)
    assert first[0].instrument.isin == "BRPETRACNPR6"


def test_api_sem_snapshot_e_erro_explicito(
    duckdb_path: Path, postgres_dsn: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MARKET_DATA_LAKE_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MARKET_DATA_LAKE_B3_EVENTS_DIR", str(tmp_path / "vazio"))
    ingest_daily_bars("PETR4", date(2026, 8, 3), date(2026, 8, 7), source="mock")

    with pytest.raises(LookupError, match="refresh_corporate_events"):
        get_price_series("PETR4", date(2026, 8, 3), date(2026, 8, 7), adjusted=True)
