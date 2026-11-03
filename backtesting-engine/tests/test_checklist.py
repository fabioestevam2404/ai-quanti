from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from backtesting_engine.application.checklist import build_checklist
from backtesting_engine.application.validation import run_validation
from backtesting_engine.domain.entities import (
    BacktestConfig,
    ChecklistItem,
    ChecklistStatus,
    CostModel,
    MovingAverageParams,
    UniverseDeclaration,
    ValidationConfig,
    ValidationResult,
    is_eligible_for_paper,
    is_eligible_for_real_capital,
)
from synthetic import START, wave_universe

from market_data_lake.api import AdjustmentDeclaration, Pendency, PendencyKind
from market_data_lake.domain.entities import OHLCVBar

V = ChecklistStatus.VERIFICADO
L = ChecklistStatus.LIMITACAO_DECLARADA
N = ChecklistStatus.NAO_VERIFICADO
F = ChecklistStatus.FALHOU

GRID = (MovingAverageParams(3, 8), MovingAverageParams(5, 15))
VALIDATION = ValidationConfig(oos_fraction=0.2, walk_forward_folds=3, param_grid=GRID)
COSTS = CostModel(cost_bps=5, slippage_bps=5)


def _config(
    costs: CostModel = COSTS, point_in_time: bool = False, criterion: str = "líquidas"
) -> BacktestConfig:
    return BacktestConfig(
        universe=UniverseDeclaration(
            tickers=("PETR4", "VALE3"),
            selection_criterion=criterion,
            selected_on=date(2026, 11, 1),
            point_in_time=point_in_time,
        ),
        start=START,
        end=date(2025, 12, 31),
        initial_capital=Decimal("100000"),
        costs=costs,
        validation=VALIDATION,
    )


@pytest.fixture(scope="module")
def universe() -> dict[str, list[OHLCVBar]]:
    return wave_universe()


@pytest.fixture(scope="module")
def validation(universe: dict[str, list[OHLCVBar]]) -> ValidationResult:
    return run_validation(universe, COSTS, 100_000.0, VALIDATION)


def _status(items: tuple[ChecklistItem, ...], number: int) -> ChecklistStatus:
    return next(item.status for item in items if item.number == number)


def _items(statuses: list[ChecklistStatus]) -> tuple[ChecklistItem, ...]:
    return tuple(ChecklistItem(i + 1, f"item {i + 1}", s, "") for i, s in enumerate(statuses))


# --- Critério 8: elegibilidade (ADR-0013), item a item --------------------------


@pytest.mark.parametrize("item", range(1, 8))
@pytest.mark.parametrize("status", [V, L, N, F])
def test_elegibilidade_com_um_item_fora_do_verificado(item: int, status: ChecklistStatus) -> None:
    statuses = [V] * 7
    statuses[item - 1] = status
    items = _items(statuses)

    # Paper: tudo verificado, exceto o item 2, que admite limitação declarada.
    assert is_eligible_for_paper(items) is (status is V or (item == 2 and status is L))
    # Capital real: os 7 verificados, sem exceção.
    assert is_eligible_for_real_capital(items) is (status is V)


@pytest.mark.parametrize("other", range(3, 8))
@pytest.mark.parametrize("status", [L, N, F])
def test_limitacao_no_item_2_nao_compensa_outro_item_ruim(
    other: int, status: ChecklistStatus
) -> None:
    statuses = [V] * 7
    statuses[1] = L
    statuses[other - 1] = status

    assert is_eligible_for_paper(_items(statuses)) is False


def test_checklist_incompleto_nunca_e_elegivel() -> None:
    assert is_eligible_for_paper(_items([V] * 6)) is False
    assert is_eligible_for_real_capital(_items([V] * 6)) is False


# --- Regras de cada item -----------------------------------------------------------


def test_sete_itens_em_ordem(
    universe: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> None:
    items = build_checklist(_config(), universe, validation)

    assert [item.number for item in items] == [1, 2, 3, 4, 5, 6, 7]
    assert all(item.evidence for item in items)


def test_item_1_verificado_pelo_teste_de_truncamento(
    universe: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> None:
    assert _status(build_checklist(_config(), universe, validation), 1) is V


def test_item_1_reprova_sinal_que_espia_o_futuro(
    universe: dict[str, list[OHLCVBar]],
    validation: ValidationResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Sem este teste, uma checagem que sempre aprova passaria despercebida.
    def leaky_signals(ticker: str, bars: list[OHLCVBar], params: MovingAverageParams) -> list[int]:
        ordered = sorted(bars, key=lambda bar: bar.bar_date)
        # Sinal em t olha o fechamento de t+1: exatamente o look-ahead proibido.
        return [
            1 if i + 1 < len(ordered) and ordered[i + 1].close > bar.close else 0
            for i, bar in enumerate(ordered)
        ]

    monkeypatch.setattr(
        "backtesting_engine.application.checklist.moving_average_cross_signals", leaky_signals
    )

    item = build_checklist(_config(), universe, validation)[0]
    assert item.status is F
    assert "dados futuros" in item.evidence


@pytest.mark.parametrize(
    ("point_in_time", "criterion", "expected"),
    [(True, "carteira do índice na data", V), (False, "líquidas", L), (False, "  ", N)],
)
def test_item_2_universo(
    universe: dict[str, list[OHLCVBar]],
    validation: ValidationResult,
    point_in_time: bool,
    criterion: str,
    expected: ChecklistStatus,
) -> None:
    config = _config(point_in_time=point_in_time, criterion=criterion)

    assert _status(build_checklist(config, universe, validation), 2) is expected


@pytest.mark.parametrize(
    ("costs", "expected"),
    [
        (CostModel(cost_bps=5, slippage_bps=5), V),
        (CostModel(cost_bps=0, slippage_bps=5), F),
        (CostModel(cost_bps=5, slippage_bps=0), F),
    ],
)
def test_item_3_custo_zero_reprova(
    universe: dict[str, list[OHLCVBar]],
    validation: ValidationResult,
    costs: CostModel,
    expected: ChecklistStatus,
) -> None:
    # Critério 10.
    assert _status(build_checklist(_config(costs=costs), universe, validation), 3) is expected


def test_item_4_dobra_sem_teste_fica_nao_verificado(
    universe: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> None:
    assert _status(build_checklist(_config(), universe, validation), 4) is V
    broken = replace(validation, folds=(replace(validation.folds[0], test_result=None),))

    assert _status(build_checklist(_config(), universe, broken), 4) is N


def test_item_5_sem_out_of_sample_fica_nao_verificado(
    universe: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> None:
    assert _status(build_checklist(_config(), universe, validation), 5) is V
    broken = replace(validation, out_of_sample_result=None)

    assert _status(build_checklist(_config(), universe, broken), 5) is N


@pytest.mark.parametrize(("passed", "expected"), [(True, V), (False, F), (None, N)])
def test_item_6_segue_a_regra_de_robustez(
    universe: dict[str, list[OHLCVBar]],
    validation: ValidationResult,
    passed: bool | None,
    expected: ChecklistStatus,
) -> None:
    with_rule = replace(validation, robustness=replace(validation.robustness, passed=passed))

    assert _status(build_checklist(_config(), universe, with_rule), 6) is expected


def _declaration(ticker: str, **changes: object) -> AdjustmentDeclaration:
    base = AdjustmentDeclaration(
        ticker=ticker,
        start=START,
        end=date(2025, 12, 31),
        adjusted=True,
        method="ajuste para trás; reconciliação contra o COTAHIST",
        sources=("b3:PETR:2026-11-03",),
        events_applied=(("desdobramento", 1), ("provento em dinheiro", 12)),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_item_7_sem_declaracao_fica_nao_verificado(
    universe: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> None:
    # Critério 9: sem declaração do market-data-lake, o motor não afirma o ajuste.
    items = build_checklist(_config(point_in_time=True), universe, validation)

    assert _status(items, 7) is N
    assert is_eligible_for_paper(items) is False


def test_item_7_verificado_com_todas_as_series_ajustadas_e_sem_pendencias(
    universe: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> None:
    # Critério 13 (spec v2 do market-data-lake).
    declarations = {t: _declaration(t) for t in universe}

    item = build_checklist(_config(), universe, validation, declarations)[6]

    assert item.status is V
    assert "PETR4" in item.evidence and "VALE3" in item.evidence


def test_item_7_uma_pendencia_em_qualquer_ativo_mantem_nao_verificado(
    universe: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> None:
    pendency = Pendency(PendencyKind.UNEXPLAINED_GAP, date(2025, 3, 3), "razão 0,2500 sem evento")
    declarations = {
        "PETR4": _declaration("PETR4"),
        "VALE3": _declaration("VALE3", pendencies=(pendency,)),
    }

    item = build_checklist(_config(), universe, validation, declarations)[6]

    assert item.status is N
    assert "VALE3" in item.evidence and "salto sem evento" in item.evidence


def test_item_7_serie_nao_ajustada_mostra_o_motivo(
    universe: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> None:
    declarations = {
        "PETR4": _declaration("PETR4"),
        "VALE3": _declaration("VALE3", adjusted=False, reason="série sem ISIN (mock)"),
    }

    item = build_checklist(_config(), universe, validation, declarations)[6]

    assert item.status is N
    assert "série sem ISIN (mock)" in item.evidence


def test_item_7_ativo_sem_declaracao_fica_nao_verificado(
    universe: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> None:
    item = build_checklist(_config(), universe, validation, {"PETR4": _declaration("PETR4")})[6]

    assert item.status is N
    assert "VALE3" in item.evidence
