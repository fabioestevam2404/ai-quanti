"""Leitura dos snapshots reais da B3 e da tabela de correções (spec v2, seções 2 e 3).

Os snapshots em `fixtures/b3_events/` são respostas reais das rotas da B3,
coletadas em 2026-11-03, sem alteração.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from market_data_lake.domain.adjustment import EventKind, EventOrigin
from market_data_lake.infrastructure.corporate_events.b3_snapshot import (
    SnapshotStore,
    parse_b3_snapshot,
)
from market_data_lake.infrastructure.corporate_events.corrections import load_corrections

FIXTURES = Path(__file__).parent / "fixtures" / "b3_events"


def _snapshot(code: str) -> dict:
    return json.loads((FIXTURES / f"{code}.json").read_text(encoding="utf-8"))


def test_desdobramento_e_grupamento_da_petr4_com_o_fator_de_preco_certo() -> None:
    capital = [e for e in parse_b3_snapshot(_snapshot("PETR")) if e.isin == "BRPETRACNPR6"]
    by_date = {e.last_date_with_right: e for e in capital}

    split = by_date[date(2008, 4, 25)]
    assert split.kind is EventKind.SPLIT
    assert split.price_factor == pytest.approx(0.5)  # factor 100% -> 1 / (1 + 1)
    reverse = by_date[date(2000, 6, 21)]
    assert reverse.kind is EventKind.REVERSE_SPLIT
    assert reverse.price_factor == pytest.approx(100.0)  # factor 0,01 -> 1 / 0,01
    assert all(e.origin is EventOrigin.B3 for e in capital)


def test_proventos_em_dinheiro_usam_o_percentual_da_b3() -> None:
    cash = [e for e in parse_b3_snapshot(_snapshot("PETR")) if e.kind is EventKind.CASH]

    assert len(cash) == 343
    assert {e.share_class for e in cash} <= {"ON", "PN"}
    # 1º evento do snapshot: corporateActionPrice 1,366176 (%).
    first = cash[0]
    assert first.price_factor == pytest.approx(1 - 1.366176 / 100)
    assert first.value_per_share == pytest.approx(0.67407131)
    assert first.reference_close == pytest.approx(49.34)


def test_percentual_ausente_e_derivado_pela_formula_da_b3() -> None:
    # Em eventos com corporateActionPrice, ele é valueCash / fechamento da data-com
    # (0,0681 / 103,15 = 0,066020%). Quando falta, o fator sai da mesma conta e o
    # evento é marcado como derivado — ex.: RENDIMENTO de valor simbólico em 2005.
    cash = [e for e in parse_b3_snapshot(_snapshot("PETR")) if e.kind is EventKind.CASH]
    by_date = {e.last_date_with_right: e for e in cash if e.label == "RENDIMENTO"}

    informed = by_date[date(2005, 3, 31)]
    assert informed.price_factor == pytest.approx(1 - 0.066020 / 100)
    assert informed.factor_derived is False
    assert 1 - informed.value_per_share / informed.reference_close == pytest.approx(
        informed.price_factor, abs=1e-6
    )
    derived = by_date[date(2005, 12, 29)]
    assert derived.factor_derived is True
    assert derived.price_factor == pytest.approx(1 - 0.0000000001 / 37.21)


def test_cisao_do_itau_vem_sem_fator_automatico() -> None:
    spin_offs = [
        e for e in parse_b3_snapshot(_snapshot("ITUB")) if e.label.startswith("CIS RED CAP")
    ]

    assert spin_offs
    assert all(e.kind is EventKind.OTHER and e.price_factor is None for e in spin_offs)


def test_tabela_de_correcoes_versionada() -> None:
    corrections = {(e.ticker, e.ex_date): e for e in load_corrections()}

    petr = corrections[("PETR4", date(2005, 9, 1))]
    assert petr.price_factor == pytest.approx(0.25)
    assert petr.kind is EventKind.SPLIT
    itub = corrections[("ITUB4", date(2021, 10, 4))]
    assert itub.price_factor == pytest.approx(0.8246)
    assert all(e.origin is EventOrigin.CORRECTION and e.source for e in corrections.values())


def test_store_guarda_e_le_o_snapshot_mais_recente(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    older = {**_snapshot("VALE"), "collected_on": "2026-10-01"}
    newer = {**_snapshot("VALE"), "collected_on": "2026-11-03"}

    store.save(older)
    store.save(newer)

    assert store.load_latest("VALE")["collected_on"] == "2026-11-03"
    assert store.load_latest("PETR") is None
