from __future__ import annotations

from datetime import date, timedelta

import pytest
from backtesting_engine.application.signals import moving_average_cross_signals
from backtesting_engine.application.simulate_execution import simulate_execution
from backtesting_engine.domain.entities import CostModel, MovingAverageParams

from market_data_lake.domain.entities import Instrument, OHLCVBar

START = date(2026, 1, 5)


def _bars(opens: list[float], closes: list[float], ticker: str = "PETR4") -> list[OHLCVBar]:
    return [
        OHLCVBar(
            instrument=Instrument(ticker=ticker),
            bar_date=START + timedelta(days=i),
            open=o,
            high=max(o, c),
            low=min(o, c),
            close=c,
            volume=1_000.0,
        )
        for i, (o, c) in enumerate(zip(opens, closes, strict=True))
    ]


# Caso conhecido (critério 1). Conta feita à mão:
# SMA2 > SMA3 a partir de d4 (11.5 > 11) até d6; em d7 cruza para baixo.
# Abertura de d5 (12.5) difere do fechamento de d4 (13) e a de d8 (8.5) do
# fechamento de d7 (9): executar no fechamento do sinal mudaria todos os números.
# Compra na abertura de d5: 12.5 * 1.01 = 12.625; qtd = floor(1000 / (12.625 * 1.005)) = 78;
#   bruto 984.75, taxa 4.92375, caixa 10.32625.
# Venda na abertura de d8: 8.5 * 0.99 = 8.415; bruto 656.37, taxa 3.28185;
#   caixa final 663.4144.
KNOWN_OPENS = [10.0, 10.0, 10.0, 12.0, 12.5, 14.0, 10.0, 8.5]
KNOWN_CLOSES = [10.0, 10.0, 10.0, 13.0, 14.0, 14.0, 9.0, 8.0]
KNOWN_PARAMS = MovingAverageParams(short_window=2, long_window=3)
KNOWN_COSTS = CostModel(cost_bps=50.0, slippage_bps=100.0)


def test_caso_conhecido_reproduz_a_conta_feita_a_mao() -> None:
    bars = _bars(KNOWN_OPENS, KNOWN_CLOSES)
    signals = moving_average_cross_signals("PETR4", bars, KNOWN_PARAMS)

    result = simulate_execution(bars, signals, initial_capital=1000.0, costs=KNOWN_COSTS)

    assert signals == [0, 0, 0, 1, 1, 1, 0, 0]
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.quantity == 78
    assert trade.entry_date == START + timedelta(days=4)
    assert trade.entry_price == pytest.approx(12.625, abs=1e-9)
    assert trade.entry_cost == pytest.approx(4.92375, abs=1e-9)
    assert trade.exit_date == START + timedelta(days=7)
    assert trade.exit_price == pytest.approx(8.415, abs=1e-9)
    assert trade.exit_cost == pytest.approx(3.28185, abs=1e-9)
    expected_equity = [1000.0, 1000.0, 1000.0, 1000.0, 1102.32625, 1102.32625, 712.32625]
    expected_equity.append(663.4144)
    assert [p.equity for p in result.equity_curve] == pytest.approx(expected_equity, abs=1e-9)
    assert result.final_cash == pytest.approx(663.4144, abs=1e-9)
    assert result.final_quantity == 0
    assert result.total_costs == pytest.approx(4.92375 + 3.28185, abs=1e-9)


def test_compra_executa_na_abertura_seguinte_nunca_no_fechamento_do_sinal() -> None:
    # Critério 3: sinal em d4 (fechamento 13) executa na abertura de d5 (12.5), com slippage.
    bars = _bars(KNOWN_OPENS, KNOWN_CLOSES)
    signals = [0, 0, 0, 1, 1, 1, 1, 1]
    assert bars[4].open != bars[3].close  # senão o teste não distingue os dois preços

    result = simulate_execution(bars, signals, initial_capital=1000.0, costs=KNOWN_COSTS)

    assert result.trades[0].entry_date == bars[4].bar_date
    assert result.trades[0].entry_price == pytest.approx(bars[4].open * 1.01, abs=1e-9)


def test_venda_executa_na_abertura_seguinte_com_slippage_contra() -> None:
    bars = _bars(KNOWN_OPENS, KNOWN_CLOSES)
    signals = [0, 0, 0, 1, 1, 1, 0, 0]
    assert bars[7].open != bars[6].close

    result = simulate_execution(bars, signals, initial_capital=1000.0, costs=KNOWN_COSTS)

    assert result.trades[0].exit_date == bars[7].bar_date
    assert result.trades[0].exit_price == pytest.approx(bars[7].open * 0.99, abs=1e-9)


def test_sinal_no_ultimo_dia_nao_executa_e_posicao_aberta_e_marcada_a_mercado() -> None:
    bars = _bars(KNOWN_OPENS, KNOWN_CLOSES)
    signals = [0, 0, 0, 1, 1, 1, 1, 0]  # saída sinalizada só no último dia

    result = simulate_execution(bars, signals, initial_capital=1000.0, costs=KNOWN_COSTS)

    assert len(result.trades) == 1
    assert result.trades[0].is_open
    assert result.final_quantity == 78
    assert result.equity_curve[-1].equity == pytest.approx(10.32625 + 78 * 8.0, abs=1e-9)


def test_quantidade_e_inteira_e_caixa_nunca_fica_negativo() -> None:
    bars = _bars([10.0, 10.0, 33.0, 33.0], [10.0, 10.0, 33.0, 33.0])

    result = simulate_execution(
        bars, [0, 1, 1, 1], initial_capital=100.0, costs=CostModel(cost_bps=5, slippage_bps=5)
    )

    # 100 / (33 * 1.0005 * 1.0005) = 3.02 -> 3 ações; sobra fica em caixa.
    assert result.trades[0].quantity == 3
    assert result.final_cash >= 0


def test_sem_capital_para_uma_acao_nao_opera() -> None:
    bars = _bars([10.0, 500.0, 500.0], [10.0, 500.0, 500.0])

    result = simulate_execution(
        bars, [1, 1, 1], initial_capital=100.0, costs=CostModel(cost_bps=5, slippage_bps=5)
    )

    assert result.trades == ()
    assert result.equity_curve[-1].equity == pytest.approx(100.0)


def test_sinais_e_barras_com_tamanhos_diferentes_sao_rejeitados() -> None:
    with pytest.raises(ValueError, match="sinais"):
        simulate_execution(
            _bars([10.0, 10.0], [10.0, 10.0]),
            [0],
            initial_capital=100.0,
            costs=KNOWN_COSTS,
        )


def test_dados_posteriores_a_t_nao_alteram_sinais_nem_patrimonio_ate_t() -> None:
    # Critério 2 (sem look-ahead): reescrever o futuro não muda o passado.
    closes = [10.0 + (i % 7) * 1.5 - (i % 4) for i in range(30)]
    opens = [c - 0.5 for c in closes]
    params = MovingAverageParams(short_window=3, long_window=5)
    costs = CostModel(cost_bps=5, slippage_bps=5)
    cut = 15
    altered_closes = closes[: cut + 1] + [c * 3 for c in closes[cut + 1 :]]
    altered_opens = opens[: cut + 1] + [o * 3 for o in opens[cut + 1 :]]

    original_bars = _bars(opens, closes)
    altered_bars = _bars(altered_opens, altered_closes)
    original_signals = moving_average_cross_signals("PETR4", original_bars, params)
    altered_signals = moving_average_cross_signals("PETR4", altered_bars, params)
    original = simulate_execution(original_bars, original_signals, 1000.0, costs)
    altered = simulate_execution(altered_bars, altered_signals, 1000.0, costs)

    assert original_signals[: cut + 1] == altered_signals[: cut + 1]
    assert original.equity_curve[: cut + 1] == altered.equity_curve[: cut + 1]
