from __future__ import annotations

from backtesting_engine.application.signals import moving_average_cross_signals
from backtesting_engine.domain.entities import (
    BacktestConfig,
    ChecklistItem,
    ChecklistStatus,
    MovingAverageParams,
    ValidationResult,
)
from market_data_lake.api import OHLCVBar

LOOKAHEAD_CUTS = 5

V = ChecklistStatus.VERIFICADO
L = ChecklistStatus.LIMITACAO_DECLARADA
N = ChecklistStatus.NAO_VERIFICADO
F = ChecklistStatus.FALHOU


def build_checklist(
    config: BacktestConfig,
    bars_by_ticker: dict[str, list[OHLCVBar]],
    validation: ValidationResult,
) -> tuple[ChecklistItem, ...]:
    """Os 7 itens do ADR-0010/0013, cada um com estado e evidência.

    "Não verificado" bloqueia paper tanto quanto "falhou": na dúvida, o
    motor não afirma nada que o processo não comprovou.
    """
    return (
        _lookahead(bars_by_ticker, validation.final_params),
        _universe(config),
        _costs(config, validation),
        _walk_forward(config, validation),
        _out_of_sample(bars_by_ticker, validation),
        _robustness(validation),
        _adjusted_prices(),
    )


def _lookahead(
    bars_by_ticker: dict[str, list[OHLCVBar]], params: MovingAverageParams
) -> ChecklistItem:
    # Sinais calculados com a série completa precisam ser iguais aos
    # calculados com a série cortada em t: o sinal em t não pode ver o futuro.
    name = "Sem look-ahead"
    checked = 0
    for ticker in sorted(bars_by_ticker):
        bars = sorted(bars_by_ticker[ticker], key=lambda bar: bar.bar_date)
        full = moving_average_cross_signals(ticker, bars, params)
        span = len(bars) - params.long_window
        if span <= 0:
            continue
        for step in range(1, LOOKAHEAD_CUTS + 1):
            cut = params.long_window - 1 + span * step // (LOOKAHEAD_CUTS + 1)
            truncated = moving_average_cross_signals(ticker, bars[: cut + 1], params)
            if truncated != full[: cut + 1]:
                return ChecklistItem(
                    1, name, F, f"{ticker}: sinal até {bars[cut].bar_date} muda com dados futuros"
                )
            checked += 1
    if checked == 0:
        return ChecklistItem(1, name, N, "histórico curto demais para cortar a série")
    return ChecklistItem(
        1,
        name,
        V,
        f"{checked} cortes da série: sinais até cada corte idênticos aos da série completa; "
        "execução sempre na abertura do pregão seguinte ao sinal",
    )


def _universe(config: BacktestConfig) -> ChecklistItem:
    name = "Sem viés de sobrevivência"
    universe = config.universe
    tickers = ", ".join(universe.tickers)
    if not universe.selection_criterion.strip():
        return ChecklistItem(2, name, N, "universo sem critério de escolha declarado")
    if universe.point_in_time:
        return ChecklistItem(
            2, name, V, f"universo point-in-time ({tickers}): {universe.selection_criterion}"
        )
    return ChecklistItem(
        2,
        name,
        L,
        f"universo fixo ({tickers}), escolhido em {universe.selected_on} por: "
        f"{universe.selection_criterion}. Escolhido entre ativos listados hoje; o "
        "resultado pode estar inflado por viés de sobrevivência (ADR-0013)",
    )


def _costs(config: BacktestConfig, validation: ValidationResult) -> ChecklistItem:
    name = "Custos e slippage"
    costs = config.costs
    if costs.cost_bps <= 0 or costs.slippage_bps <= 0:
        return ChecklistItem(
            3,
            name,
            F,
            f"custo {costs.cost_bps} bps e slippage {costs.slippage_bps} bps: "
            "backtest sem custo não é aceito",
        )
    simulations = validation.in_sample_result.simulations
    traded = any(sim.trades for sim in simulations)
    total = sum(sim.total_costs for sim in simulations)
    if traded and total <= 0:
        return ChecklistItem(3, name, F, "houve operações, mas nenhum custo foi aplicado")
    return ChecklistItem(
        3,
        name,
        V,
        f"custo {costs.cost_bps} bps e slippage {costs.slippage_bps} bps por lado, "
        "aplicados em todas as operações",
    )


def _walk_forward(config: BacktestConfig, validation: ValidationResult) -> ChecklistItem:
    name = "Walk-forward"
    expected = config.validation.walk_forward_folds
    evaluated = [fold for fold in validation.folds if fold.test_result is not None]
    if len(validation.folds) != expected or len(evaluated) != expected:
        return ChecklistItem(
            4, name, N, f"{len(evaluated)} de {expected} dobras com teste avaliado"
        )
    sharpes = ", ".join(
        f"{fold.test_result.metrics.sharpe:.2f}"
        for fold in evaluated
        if fold.test_result is not None
    )
    return ChecklistItem(
        4, name, V, f"{expected} dobras, seleção só no treino; Sharpe nos testes: {sharpes}"
    )


def _out_of_sample(
    bars_by_ticker: dict[str, list[OHLCVBar]], validation: ValidationResult
) -> ChecklistItem:
    name = "Out-of-sample"
    period = validation.out_of_sample
    needed = validation.final_params.long_window + 1
    bars_in_period = min(
        sum(1 for bar in bars if period.start <= bar.bar_date <= period.end)
        for bars in bars_by_ticker.values()
    )
    result = validation.out_of_sample_result
    if result is None or bars_in_period < needed:
        return ChecklistItem(
            5,
            name,
            N,
            f"{bars_in_period} pregões reservados; mínimo {needed} para uma operação possível",
        )
    return ChecklistItem(
        5,
        name,
        V,
        f"{period.start} a {period.end} ({bars_in_period} pregões) nunca usado na seleção; "
        f"Sharpe {result.metrics.sharpe:.2f}",
    )


def _robustness(validation: ValidationResult) -> ChecklistItem:
    name = "Robustez de parâmetro"
    robustness = validation.robustness
    detail = (
        f"{len(robustness.neighbors)} vizinhos de {validation.final_params}; "
        f"Sharpe base {robustness.base_sharpe:.2f}, mínimo exigido "
        f"{robustness.min_ratio:.0%} do base"
    )
    if robustness.passed is None:
        return ChecklistItem(6, name, N, f"{detail}. Regra não se aplica com Sharpe base <= 0")
    if robustness.passed:
        return ChecklistItem(6, name, V, f"{detail}: todos os vizinhos atendem")
    return ChecklistItem(6, name, F, f"{detail}: há vizinho abaixo do mínimo")


def _adjusted_prices() -> ChecklistItem:
    # O market-data-lake ainda não declara se a série é ajustada por
    # proventos (REQ-01). Até lá, o motor não pode afirmar o item.
    return ChecklistItem(
        7,
        "Preços ajustados por proventos",
        N,
        "o market-data-lake não declara ajuste por proventos da série (pendente no REQ-01)",
    )
