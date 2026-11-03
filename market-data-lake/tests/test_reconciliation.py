"""Reconciliação contra o COTAHIST (spec v2, seção 5): critérios 9, 10 e 11."""

from __future__ import annotations

import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from market_data_lake.domain.adjustment import (
    CorporateEvent,
    EventKind,
    EventOrigin,
    adjust_bars,
)
from market_data_lake.domain.entities import Instrument, OHLCVBar
from market_data_lake.domain.reconciliation import PendencyKind, Tolerances, reconcile
from market_data_lake.infrastructure.corporate_events.b3_snapshot import parse_b3_snapshot
from market_data_lake.infrastructure.corporate_events.corrections import load_corrections
from market_data_lake.infrastructure.providers.cotahist_provider import CotahistProvider

ISIN = "BRPETRACNPR6"
D0 = date(2026, 1, 5)
FIXTURES = Path(__file__).parent / "fixtures"


def _bar(day: int, open_: float, close: float) -> OHLCVBar:
    low, high = min(open_, close), max(open_, close)
    return OHLCVBar(
        Instrument("PETR4", isin=ISIN), D0 + timedelta(day), open_, high, low, close, 1.0
    )


def _split(factor: float, data_com_day: int) -> CorporateEvent:
    return CorporateEvent(
        kind=EventKind.SPLIT,
        label="DESDOBRAMENTO",
        price_factor=factor,
        origin=EventOrigin.B3,
        last_date_with_right=D0 + timedelta(data_com_day),
        isin=ISIN,
    )


def _cash(pct: float, value: float, close: float, data_com_day: int) -> CorporateEvent:
    return CorporateEvent(
        kind=EventKind.CASH,
        label="DIVIDENDO",
        price_factor=1 - pct / 100,
        origin=EventOrigin.B3,
        last_date_with_right=D0 + timedelta(data_com_day),
        share_class="PN",
        value_per_share=value,
        reference_close=close,
    )


def _kinds(raw: list[OHLCVBar], events: list[CorporateEvent]) -> list[PendencyKind]:
    return [p.kind for p in reconcile(raw, adjust_bars(raw, events))]


def test_evento_de_capital_que_explica_o_salto_nao_gera_pendencia() -> None:
    raw = [_bar(0, 100, 100), _bar(1, 50.5, 51)]

    assert _kinds(raw, [_split(0.5, 0)]) == []


def test_evento_de_capital_que_nao_bate_com_o_salto_gera_pendencia() -> None:
    # Fator 0,5, mas o preço só caiu 20%: evento errado ou data errada.
    raw = [_bar(0, 100, 100), _bar(1, 80, 80)]

    assert _kinds(raw, [_split(0.5, 0)]) == [PendencyKind.CAPITAL_MISMATCH]


def test_tolerancia_absorve_o_movimento_do_dia() -> None:
    # Caso da cisão da ITUB4: fator 0,8246, razão observada 0,834 (+1,2%).
    raw = [_bar(0, 29.12, 29.67), _bar(1, 24.75, 24.34)]
    spin_off = CorporateEvent(
        kind=EventKind.OTHER,
        label="cisão",
        price_factor=0.8246,
        origin=EventOrigin.CORRECTION,
        ex_date=D0 + timedelta(1),
        ticker="PETR4",
        source="teste",
    )

    assert _kinds(raw, [spin_off]) == []


def test_salto_sem_evento_gera_pendencia() -> None:
    raw = [_bar(0, 100, 100), _bar(1, 100, 100), _bar(2, 25, 25)]

    pendencies = reconcile(raw, adjust_bars(raw, []))

    assert [p.kind for p in pendencies] == [PendencyKind.UNEXPLAINED_GAP]
    assert pendencies[0].bar_date == D0 + timedelta(2)


@pytest.mark.parametrize("ratio", [0.76, 1.32])
def test_movimento_dentro_da_faixa_nao_e_salto(ratio: float) -> None:
    raw = [_bar(0, 100, 100), _bar(1, 100 * ratio, 100 * ratio)]

    assert _kinds(raw, []) == []


def test_provento_com_percentual_incoerente_com_o_valor_gera_pendencia() -> None:
    # Valor 0,50 sobre 50,00 = 1%; a B3 informa 2%.
    raw = [_bar(0, 50, 50), _bar(1, 49.5, 49.5)]

    assert _kinds(raw, [_cash(2.0, 0.50, 50.0, 0)]) == [PendencyKind.CASH_INCOHERENT]


def test_provento_coerente_nao_gera_pendencia() -> None:
    raw = [_bar(0, 50, 50), _bar(1, 49.5, 49.5)]

    assert _kinds(raw, [_cash(1.0, 0.50, 50.0, 0)]) == []


def test_fechamento_da_data_com_diferente_do_cotahist_gera_pendencia() -> None:
    # A B3 diz que o fechamento da data-com foi 55,00; o COTAHIST diz 50,00.
    raw = [_bar(0, 50, 50), _bar(1, 49.5, 49.5)]

    assert _kinds(raw, [_cash(1.0, 0.55, 55.0, 0)]) == [PendencyKind.CASH_CLOSE_MISMATCH]


def test_evento_sem_fator_gera_pendencia() -> None:
    raw = [_bar(0, 100, 100), _bar(1, 99, 99)]
    without_factor = CorporateEvent(
        kind=EventKind.OTHER,
        label="CIS RED CAP",
        price_factor=None,
        origin=EventOrigin.B3,
        last_date_with_right=D0,
        isin=ISIN,
    )

    assert _kinds(raw, [without_factor]) == [PendencyKind.UNSUPPORTED_EVENT]


def test_tolerancias_sao_as_da_spec() -> None:
    tolerances = Tolerances()

    assert (tolerances.capital_event, tolerances.gap_low, tolerances.gap_high) == (0.10, 0.75, 1.33)
    assert (tolerances.cash_pct_points, tolerances.cash_close_rel) == (0.01, 0.005)


# --- Dados reais ------------------------------------------------------------------


def _download(url: str, destination: Path) -> None:
    year = url.rsplit("COTAHIST_A", 1)[1][:4]
    sample = FIXTURES / "cotahist" / f"COTAHIST_A{year}.TXT"
    with zipfile.ZipFile(destination, "w") as archive:
        archive.writestr(
            sample.name, sample.read_text(encoding="latin-1") if sample.exists() else ""
        )


def _real(ticker: str, code: str, start: date, end: date, tmp_path: Path, corrections: bool):
    raw = CotahistProvider(
        cache_dir=tmp_path, download=_download, sleep=lambda _: None
    ).fetch_daily_bars(ticker, start, end)
    snapshot = json.loads((FIXTURES / "b3_events" / f"{code}.json").read_text(encoding="utf-8"))
    events = parse_b3_snapshot(snapshot) + (load_corrections() if corrections else [])
    return reconcile(raw, adjust_bars(raw, events))


def test_sem_a_correcao_de_2005_a_reconciliacao_acusa_o_salto(tmp_path: Path) -> None:
    # Critério 9, segunda metade.
    without = _real("PETR4", "PETR", date(2005, 8, 1), date(2005, 9, 30), tmp_path, False)
    with_fix = _real("PETR4", "PETR", date(2005, 8, 1), date(2005, 9, 30), tmp_path, True)

    assert [(p.kind, p.bar_date) for p in without] == [
        (PendencyKind.UNEXPLAINED_GAP, date(2005, 9, 1))
    ]
    assert with_fix == ()


def test_cisao_sem_correcao_vira_pendencia_e_com_correcao_nao(tmp_path: Path) -> None:
    # Critério 10.
    without = _real("ITUB4", "ITUB", date(2021, 9, 1), date(2021, 10, 31), tmp_path, False)
    with_fix = _real("ITUB4", "ITUB", date(2021, 9, 1), date(2021, 10, 31), tmp_path, True)

    assert PendencyKind.UNSUPPORTED_EVENT in [p.kind for p in without]
    assert with_fix == ()
