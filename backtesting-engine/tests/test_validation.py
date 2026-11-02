from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest
from backtesting_engine.application.validation import (
    neighbor_params,
    plan_periods,
    robustness_passed,
    run_validation,
)
from backtesting_engine.domain.entities import CostModel, MovingAverageParams, ValidationConfig
from synthetic import START, wave_universe

from market_data_lake.domain.entities import OHLCVBar

COSTS = CostModel(cost_bps=5, slippage_bps=5)
CAPITAL = 100_000.0
GRID = (
    MovingAverageParams(3, 8),
    MovingAverageParams(3, 15),
    MovingAverageParams(5, 15),
    MovingAverageParams(5, 25),
)
CONFIG = ValidationConfig(oos_fraction=0.2, walk_forward_folds=3, param_grid=GRID)


def _universe() -> dict[str, list[OHLCVBar]]:
    return wave_universe()


def _scramble_after(bars: list[OHLCVBar], cutoff: date) -> list[OHLCVBar]:
    # Reescreve todos os preços posteriores ao corte (datas mantidas).
    return [
        bar
        if bar.bar_date <= cutoff
        else replace(
            bar,
            open=bar.open * 3.7,
            high=bar.high * 3.7,
            low=bar.low * 0.2,
            close=bar.close * (0.2 if bar.bar_date.day % 2 else 3.7),
        )
        for bar in bars
    ]


def test_planejamento_reserva_o_fim_e_dobras_nao_se_sobrepoem() -> None:
    dates = [START + timedelta(days=i) for i in range(100)]

    in_sample, out_of_sample, folds = plan_periods(dates, CONFIG)

    assert out_of_sample == type(out_of_sample)(dates[80], dates[99])
    assert in_sample.start == dates[0] and in_sample.end == dates[79]
    assert len(folds) == 3
    for train, test in folds:
        assert train.start == dates[0]
        assert train.end < test.start  # teste sempre depois do treino
    for (_, previous_test), (_, next_test) in zip(folds, folds[1:], strict=False):
        assert previous_test.end < next_test.start  # testes sem sobreposição
    assert folds[-1][1].end == in_sample.end


def test_historico_curto_demais_para_as_dobras_e_rejeitado() -> None:
    dates = [START + timedelta(days=i) for i in range(4)]

    with pytest.raises(ValueError, match="dobras"):
        plan_periods(dates, CONFIG)


def test_out_of_sample_nao_influencia_a_selecao() -> None:
    # Critério 5: reescrever o período reservado não muda nenhum parâmetro escolhido.
    universe = _universe()
    original = run_validation(universe, COSTS, CAPITAL, CONFIG)
    cutoff = original.in_sample.end
    altered = run_validation(
        {t: _scramble_after(bars, cutoff) for t, bars in universe.items()}, COSTS, CAPITAL, CONFIG
    )

    assert altered.final_params == original.final_params
    assert [f.chosen_params for f in altered.folds] == [f.chosen_params for f in original.folds]
    assert altered.in_sample_result == original.in_sample_result
    assert altered.out_of_sample_result != original.out_of_sample_result  # o OOS mudou, sim


def test_cada_dobra_escolhe_so_com_o_proprio_treino() -> None:
    # Critério 6. Comparar só o parâmetro escolhido não basta: numa grade
    # pequena o vencedor pode coincidir por acaso. O resultado da seleção
    # precisa ter sido calculado exatamente no período de treino...
    universe = _universe()
    original = run_validation(universe, COSTS, CAPITAL, CONFIG)
    for fold in original.folds:
        assert fold.train_result.period == fold.train
        assert fold.train_result.params == fold.chosen_params

    # ...e não pode mudar quando tudo depois do treino é reescrito.
    first_train_end = original.folds[0].train.end
    altered = run_validation(
        {t: _scramble_after(bars, first_train_end) for t, bars in universe.items()},
        COSTS,
        CAPITAL,
        CONFIG,
    )
    assert altered.folds[0].train_result == original.folds[0].train_result
    assert altered.folds[0].chosen_params == original.folds[0].chosen_params


def test_vizinhos_perturbam_n_e_m_em_10_e_20_por_cento() -> None:
    neighbors = neighbor_params(MovingAverageParams(10, 50), (0.1, 0.2))

    assert len(neighbors) == 24  # 5 x 5 combinações de N e M, menos o próprio
    assert MovingAverageParams(10, 50) not in neighbors
    assert {p.short_window for p in neighbors} == {8, 9, 10, 11, 12}
    assert {p.long_window for p in neighbors} == {40, 45, 50, 55, 60}


def test_vizinhos_invalidos_sao_descartados() -> None:
    # N=2 não pode cair abaixo de 2; M=3 perturbado vira 2, 3 ou 4 (2 e 3 inválidos ou iguais).
    assert neighbor_params(MovingAverageParams(2, 3), (0.1, 0.2)) == (MovingAverageParams(2, 4),)


@pytest.mark.parametrize(
    ("base", "neighbors", "expected"),
    [
        (1.0, [0.6, 0.5], True),
        (1.0, [0.6, 0.49], False),
        (0.0, [0.3], None),
        (-0.2, [-0.1], None),
    ],
)
def test_regra_de_robustez(base: float, neighbors: list[float], expected: bool | None) -> None:
    # Critério 7: aprovado se todos os vizinhos mantêm >= 50% do Sharpe base;
    # com Sharpe base <= 0 a regra não se aplica.
    assert robustness_passed(base, neighbors, min_ratio=0.5) is expected


def test_robustez_do_resultado_segue_a_regra_sobre_os_vizinhos_reportados() -> None:
    result = run_validation(_universe(), COSTS, CAPITAL, CONFIG)
    robustness = result.robustness

    assert robustness.neighbors
    assert robustness.base_sharpe == result.in_sample_result.metrics.sharpe
    assert robustness.passed is robustness_passed(
        robustness.base_sharpe, [sharpe for _, sharpe in robustness.neighbors], 0.5
    )


def test_validacao_e_deterministica() -> None:
    assert run_validation(_universe(), COSTS, CAPITAL, CONFIG) == run_validation(
        _universe(), COSTS, CAPITAL, CONFIG
    )
