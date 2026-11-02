from __future__ import annotations

import math
from datetime import date

from backtesting_engine.application.evaluate_period import evaluate_period
from backtesting_engine.domain.entities import (
    CostModel,
    FoldResult,
    MovingAverageParams,
    Period,
    PeriodResult,
    RobustnessResult,
    ValidationConfig,
    ValidationResult,
)
from market_data_lake.api import OHLCVBar


def plan_periods(
    dates: list[date], config: ValidationConfig
) -> tuple[Period, Period, list[tuple[Period, Period]]]:
    """Reserva o out-of-sample no fim; divide o resto em `k + 1` blocos contíguos.

    Dobra `i` treina nos blocos `0..i-1` (janela crescente) e testa no bloco
    `i`: testes em sequência, sem sobreposição, sempre depois do treino.
    """
    ordered = sorted(set(dates))
    oos_size = max(1, math.ceil(len(ordered) * config.oos_fraction))
    in_sample_dates = ordered[: len(ordered) - oos_size]
    oos_dates = ordered[len(ordered) - oos_size :]

    blocks = config.walk_forward_folds + 1
    if len(in_sample_dates) < blocks:
        raise ValueError(
            f"histórico insuficiente para {config.walk_forward_folds} dobras: "
            f"{len(in_sample_dates)} pregões fora do out-of-sample"
        )
    size, remainder = divmod(len(in_sample_dates), blocks)
    chunks: list[list[date]] = []
    position = 0
    for index in range(blocks):
        length = size + (1 if index < remainder else 0)
        chunks.append(in_sample_dates[position : position + length])
        position += length

    folds = [
        (
            Period(in_sample_dates[0], chunks[index - 1][-1]),
            Period(chunks[index][0], chunks[index][-1]),
        )
        for index in range(1, blocks)
    ]
    return (
        Period(in_sample_dates[0], in_sample_dates[-1]),
        Period(oos_dates[0], oos_dates[-1]),
        folds,
    )


def select_params(
    bars_by_ticker: dict[str, list[OHLCVBar]],
    grid: tuple[MovingAverageParams, ...],
    costs: CostModel,
    initial_capital: float,
    period: Period,
) -> PeriodResult:
    """Maior Sharpe no período; empate fica com o primeiro da grade (determinístico)."""
    best: PeriodResult | None = None
    for params in grid:
        try:
            result = evaluate_period(bars_by_ticker, params, costs, initial_capital, period)
        except ValueError:
            continue  # dados insuficientes para este parâmetro no período
        if best is None or result.metrics.sharpe > best.metrics.sharpe:
            best = result
    if best is None:
        raise ValueError(f"nenhum parâmetro da grade pôde ser avaliado em {period}")
    return best


def neighbor_params(
    base: MovingAverageParams, perturbations: tuple[float, ...]
) -> tuple[MovingAverageParams, ...]:
    """Combinações de N e M perturbados em ±p, arredondados; inválidos descartados."""
    factors = [1.0] + [1 + sign * p for p in perturbations for sign in (-1, 1)]
    neighbors: list[MovingAverageParams] = []
    for short_factor in factors:
        for long_factor in factors:
            short = math.floor(base.short_window * short_factor + 0.5)
            long = math.floor(base.long_window * long_factor + 0.5)
            if short < 2 or short >= long:
                continue
            candidate = MovingAverageParams(short_window=short, long_window=long)
            if candidate != base and candidate not in neighbors:
                neighbors.append(candidate)
    return tuple(neighbors)


def robustness_passed(
    base_sharpe: float, neighbor_sharpes: list[float], min_ratio: float
) -> bool | None:
    """Todos os vizinhos mantêm `min_ratio` do Sharpe base (ADR-0010, item 6).

    Com Sharpe base <= 0 não há desempenho a preservar e a proporção perde o
    sentido: devolve None, e o checklist registra o item como não verificado.
    """
    if base_sharpe <= 0 or not neighbor_sharpes:
        return None
    return all(sharpe >= min_ratio * base_sharpe for sharpe in neighbor_sharpes)


def run_validation(
    bars_by_ticker: dict[str, list[OHLCVBar]],
    costs: CostModel,
    initial_capital: float,
    config: ValidationConfig,
) -> ValidationResult:
    dates = [bar.bar_date for bars in bars_by_ticker.values() for bar in bars]
    in_sample, out_of_sample, fold_periods = plan_periods(dates, config)

    folds: list[FoldResult] = []
    for train, test in fold_periods:
        chosen = select_params(bars_by_ticker, config.param_grid, costs, initial_capital, train)
        folds.append(
            FoldResult(
                train=train,
                test=test,
                chosen_params=chosen.params,
                train_result=chosen,
                test_result=_try_evaluate(
                    bars_by_ticker, chosen.params, costs, initial_capital, test
                ),
            )
        )

    final = select_params(bars_by_ticker, config.param_grid, costs, initial_capital, in_sample)

    neighbor_results: list[tuple[MovingAverageParams, float]] = []
    for params in neighbor_params(final.params, config.robustness_perturbations):
        result = _try_evaluate(bars_by_ticker, params, costs, initial_capital, in_sample)
        if result is not None:
            neighbor_results.append((params, result.metrics.sharpe))

    return ValidationResult(
        in_sample=in_sample,
        out_of_sample=out_of_sample,
        folds=tuple(folds),
        final_params=final.params,
        in_sample_result=final,
        out_of_sample_result=_try_evaluate(
            bars_by_ticker, final.params, costs, initial_capital, out_of_sample
        ),
        robustness=RobustnessResult(
            base_sharpe=final.metrics.sharpe,
            neighbors=tuple(neighbor_results),
            min_ratio=config.robustness_min_ratio,
            passed=robustness_passed(
                final.metrics.sharpe,
                [sharpe for _, sharpe in neighbor_results],
                config.robustness_min_ratio,
            ),
        ),
    )


def _try_evaluate(
    bars_by_ticker: dict[str, list[OHLCVBar]],
    params: MovingAverageParams,
    costs: CostModel,
    initial_capital: float,
    period: Period,
) -> PeriodResult | None:
    try:
        return evaluate_period(bars_by_ticker, params, costs, initial_capital, period)
    except ValueError:
        return None
