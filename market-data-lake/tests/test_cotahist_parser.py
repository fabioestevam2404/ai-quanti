"""Critério 5 (v2): leitura do COTAHIST pelo layout oficial da B3.

A amostra em `fixtures/cotahist/` são linhas reais dos arquivos anuais de 2000
e 2008 (cabeçalho, cotações e rodapé), sem alteração.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from market_data_lake.infrastructure.providers.cotahist_parser import parse_cotahist

FIXTURES = Path(__file__).parent / "fixtures" / "cotahist"


def _lines(year: int) -> list[str]:
    return (FIXTURES / f"COTAHIST_A{year}.TXT").read_text(encoding="latin-1").splitlines()


def test_ignora_cabecalho_e_rodape() -> None:
    quotes = list(parse_cotahist(_lines(2008)))

    assert len(quotes) == 3  # 5 linhas: cabeçalho, 3 cotações, rodapé


def test_le_precos_do_desdobramento_de_2008() -> None:
    quotes = {q.trade_date: q for q in parse_cotahist(_lines(2008)) if q.ticker == "PETR4"}

    before, after = quotes[date(2008, 4, 25)], quotes[date(2008, 4, 28)]
    assert (before.open, before.close) == (84.0, 84.3)
    assert (after.open, after.close) == (42.58, 42.59)
    assert before.market_type == "010"
    assert before.isin == "BRPETRACNPR6"
    assert before.low <= before.close <= before.high


def test_fatcot_1000_vira_preco_por_acao() -> None:
    # Em 21/06/2000 a PETR4 era cotada por lote de mil (515,00 por lote);
    # em 23/06, já por ação (51,51). Sem dividir por FATCOT, pareceria -90%.
    quotes = {q.trade_date: q for q in parse_cotahist(_lines(2000))}

    assert quotes[date(2000, 6, 21)].close == pytest.approx(0.515)
    assert quotes[date(2000, 6, 21)].open == pytest.approx(0.512)
    assert quotes[date(2000, 6, 23)].close == pytest.approx(51.51)


def test_mercado_fracionario_tem_codigo_e_mercado_proprios() -> None:
    fractional = [q for q in parse_cotahist(_lines(2008)) if q.ticker == "PETR4F"]

    assert len(fractional) == 1
    assert fractional[0].market_type == "020"


def _with_fields(line: str, market_type: str, quote_factor: int) -> str:
    # Variação sintética de uma linha real: troca TPMERC (25-27) e FATCOT (211-217).
    return line[:24] + market_type + line[27:210] + f"{quote_factor:07d}" + line[217:]


def test_filtro_vem_antes_do_calculo_de_preco() -> None:
    # O COTAHIST real de 2007 tem 4 opções (TPMERC 070) com FATCOT = 0: com o
    # filtro aplicado antes, elas nunca chegam à divisão.
    real = next(line for line in _lines(2008) if line.startswith("01"))
    option_with_zero_factor = _with_fields(real, "070", 0)

    quotes = list(
        parse_cotahist([option_with_zero_factor, real], ticker="PETR4", market_type="010")
    )

    assert len(quotes) == 1


def test_fatcot_zero_na_linha_pedida_e_erro_explicito() -> None:
    real = next(line for line in _lines(2008) if line.startswith("01"))

    with pytest.raises(ValueError, match="FATCOT"):
        list(parse_cotahist([_with_fields(real, "010", 0)], ticker="PETR4", market_type="010"))


def test_linha_com_tamanho_errado_e_rejeitada() -> None:
    with pytest.raises(ValueError, match="245"):
        list(parse_cotahist(["01" + "x" * 100]))
