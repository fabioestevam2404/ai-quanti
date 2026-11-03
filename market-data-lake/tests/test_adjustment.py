"""Regras do ajuste por proventos (spec v2, seção 4), em séries sintéticas."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from market_data_lake.domain.adjustment import (
    CorporateEvent,
    EventKind,
    EventOrigin,
    adjust_bars,
    share_class_of,
)
from market_data_lake.domain.entities import Instrument, OHLCVBar

ISIN = "BRPETRACNPR6"
D0 = date(2026, 1, 5)


def _bars(closes: list[float], ticker: str = "PETR4", isin: str | None = ISIN) -> list[OHLCVBar]:
    return [
        OHLCVBar(
            instrument=Instrument(ticker=ticker, isin=isin),
            bar_date=D0 + timedelta(days=i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=100.0,
        )
        for i, c in enumerate(closes)
    ]


def _capital(kind: EventKind, factor: float | None, data_com: date) -> CorporateEvent:
    return CorporateEvent(
        kind=kind,
        label=kind.value,
        price_factor=factor,
        last_date_with_right=data_com,
        isin=ISIN,
        origin=EventOrigin.B3,
    )


def _cash(price_factor: float, data_com: date, share_class: str = "PN") -> CorporateEvent:
    return CorporateEvent(
        kind=EventKind.CASH,
        label="DIVIDENDO",
        price_factor=price_factor,
        last_date_with_right=data_com,
        share_class=share_class,
        origin=EventOrigin.B3,
    )


def test_desdobramento_divide_os_precos_anteriores() -> None:
    # 1:2 com data-com no 2º pregão: os dois primeiros preços caem pela metade.
    result = adjust_bars(
        _bars([100.0, 100.0, 50.0, 51.0]), [_capital(EventKind.SPLIT, 0.5, D0 + timedelta(1))]
    )

    assert [b.close for b in result.bars] == [50.0, 50.0, 50.0, 51.0]
    assert [r.ex_date for r in result.applied] == [D0 + timedelta(2)]


def test_grupamento_multiplica_os_precos_anteriores() -> None:
    # 100:1 com data-com no 2º pregão (último ainda a 0,5).
    result = adjust_bars(
        _bars([0.5, 0.5, 50.0]), [_capital(EventKind.REVERSE_SPLIT, 100.0, D0 + timedelta(1))]
    )

    assert [b.close for b in result.bars] == pytest.approx([50.0, 50.0, 50.0])


def test_provento_em_dinheiro_aplica_o_fator_da_b3() -> None:
    # corporateActionPrice 2% -> fator 0.98 antes da data ex.
    result = adjust_bars(_bars([50.0, 50.0, 49.0]), [_cash(0.98, D0 + timedelta(1))])

    assert [b.close for b in result.bars] == pytest.approx([49.0, 49.0, 49.0])


def test_fatores_se_acumulam_para_tras() -> None:
    events = [_capital(EventKind.SPLIT, 0.5, D0), _cash(0.9, D0 + timedelta(1))]

    result = adjust_bars(_bars([100.0, 50.0, 45.0]), events)

    assert [b.close for b in result.bars] == pytest.approx([45.0, 45.0, 45.0])


def test_ultimo_preco_da_serie_nunca_muda() -> None:
    # Critério 12: evento depois do fim da série não entra; o último preço é o bruto.
    raw = _bars([10.0, 11.0, 12.0])
    events = [_cash(0.5, D0 + timedelta(5)), _capital(EventKind.SPLIT, 0.5, D0)]

    result = adjust_bars(raw, events)

    assert result.bars[-1] == raw[-1]
    assert len(result.applied) == 1


def test_evento_antes_do_inicio_da_serie_nao_tem_efeito() -> None:
    result = adjust_bars(_bars([10.0, 10.0]), [_capital(EventKind.SPLIT, 0.5, D0 - timedelta(3))])

    assert [b.close for b in result.bars] == [10.0, 10.0]
    assert result.applied == ()


def test_ohlc_ajustados_e_volume_nao() -> None:
    raw = [
        OHLCVBar(Instrument("PETR4", isin=ISIN), D0, 99.0, 102.0, 98.0, 100.0, 1_000.0),
        OHLCVBar(
            Instrument("PETR4", isin=ISIN), D0 + timedelta(1), 50.0, 51.0, 49.0, 50.0, 2_000.0
        ),
    ]

    bar = adjust_bars(raw, [_capital(EventKind.SPLIT, 0.5, D0)]).bars[0]

    assert (bar.open, bar.high, bar.low, bar.close) == (49.5, 51.0, 49.0, 50.0)
    assert bar.volume == 1_000.0


def test_correcao_prevalece_sobre_evento_de_capital_da_b3_na_mesma_data_ex() -> None:
    # A B3 lista a cisão sem fator; a correção traz o fator na data ex (pregão seguinte).
    b3_spin_off = _capital(EventKind.OTHER, None, D0)
    correction = CorporateEvent(
        kind=EventKind.OTHER,
        label="cisão",
        price_factor=0.8,
        ex_date=D0 + timedelta(1),
        ticker="PETR4",
        origin=EventOrigin.CORRECTION,
    )

    result = adjust_bars(_bars([100.0, 80.0]), [b3_spin_off, correction])

    assert [b.close for b in result.bars] == pytest.approx([80.0, 80.0])
    assert result.unsupported == ()
    assert [r.event.origin for r in result.applied] == [EventOrigin.CORRECTION]


def test_evento_sem_fator_e_sem_correcao_fica_como_nao_suportado() -> None:
    spin_off = _capital(EventKind.OTHER, None, D0)

    result = adjust_bars(_bars([100.0, 80.0]), [spin_off])

    assert [b.close for b in result.bars] == [100.0, 80.0]
    assert result.unsupported == (spin_off,)


def test_linhas_identicas_da_b3_contam_uma_vez_e_distintas_somam() -> None:
    # A B3 repete linhas (a cisão do Itaú aparece duas vezes); dois JCP distintos
    # na mesma data-com são dois eventos.
    same = _cash(0.99, D0)
    other = CorporateEvent(
        kind=EventKind.CASH,
        label="JRS CAP PROPRIO",
        price_factor=0.98,
        last_date_with_right=D0,
        share_class="PN",
        origin=EventOrigin.B3,
    )

    result = adjust_bars(_bars([100.0, 97.0]), [same, same, other])

    assert result.bars[0].close == pytest.approx(100.0 * 0.99 * 0.98)
    assert len(result.applied) == 2


def test_so_eventos_do_ativo_entram() -> None:
    on_dividend = _cash(0.5, D0, share_class="ON")
    other_isin = CorporateEvent(
        kind=EventKind.SPLIT,
        label="DESDOBRAMENTO",
        price_factor=0.5,
        last_date_with_right=D0,
        isin="BRPETRACNOR9",
        origin=EventOrigin.B3,
    )

    result = adjust_bars(_bars([10.0, 10.0]), [on_dividend, other_isin])

    assert [b.close for b in result.bars] == [10.0, 10.0]


@pytest.mark.parametrize(
    ("ticker", "expected"), [("PETR4", "PN"), ("VALE3", "ON"), ("BBDC4", "PN")]
)
def test_classe_da_acao_pelo_final_do_ticker(ticker: str, expected: str) -> None:
    assert share_class_of(ticker) == expected


def test_evento_precisa_de_uma_unica_data() -> None:
    with pytest.raises(ValueError, match="data"):
        CorporateEvent(
            kind=EventKind.SPLIT,
            label="x",
            price_factor=0.5,
            last_date_with_right=D0,
            ex_date=D0,
            isin=ISIN,
            origin=EventOrigin.B3,
        )
