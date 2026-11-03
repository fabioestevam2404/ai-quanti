from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

QUOTE_RECORD = "01"  # 00 = cabeçalho, 99 = rodapé
LINE_LENGTH = 245


@dataclass(frozen=True, slots=True)
class CotahistQuote:
    """Um registro `01` do COTAHIST, já em preço por ação (ver `FATCOT`)."""

    trade_date: date
    ticker: str
    market_type: str  # TPMERC: 010 = à vista, 020 = fracionário, ...
    isin: str
    open: float
    high: float
    low: float
    close: float
    volume: float  # QUATOT: quantidade de títulos negociados


def parse_cotahist(
    lines: Iterable[str], ticker: str | None = None, market_type: str | None = None
) -> Iterator[CotahistQuote]:
    """Lê registros de cotação pelo layout oficial da B3 (posições fixas).

    Preços vêm com duas casas implícitas e, quando `FATCOT` = 1000, por lote
    de mil ações: dividir por `FATCOT` evita saltos falsos (a PETR4 passou de
    lote para unidade no grupamento de 2000 — investigação 0002).

    `ticker` e `market_type` filtram **antes** de converter preços: o arquivo
    anual tem centenas de milhares de linhas, e algumas de outros mercados
    vêm com `FATCOT` = 0 (opções, no COTAHIST de 2007).
    """
    for raw in lines:
        line = raw.rstrip("\r\n")
        if line[:2] != QUOTE_RECORD:
            continue
        if len(line) != LINE_LENGTH:
            raise ValueError(f"registro 01 com {len(line)} caracteres; o layout tem {LINE_LENGTH}")
        code = line[12:24].strip()
        market = line[24:27]
        if (ticker is not None and code != ticker) or (
            market_type is not None and market != market_type
        ):
            continue
        quote_factor = int(line[210:217])  # FATCOT
        if quote_factor <= 0:
            raise ValueError(f"FATCOT inválido ({quote_factor}) para {code} em {line[2:10]}")
        yield CotahistQuote(
            trade_date=datetime.strptime(line[2:10], "%Y%m%d").date(),
            ticker=code,
            market_type=market,
            isin=line[230:242],
            open=_price(line[56:69], quote_factor),
            high=_price(line[69:82], quote_factor),
            low=_price(line[82:95], quote_factor),
            close=_price(line[108:121], quote_factor),
            volume=float(int(line[152:170])),
        )


def _price(field: str, quote_factor: int) -> float:
    # Decimal na conta evita ruído de ponto flutuante (8430/100 = 84.3, exato).
    return float(Decimal(int(field)) / 100 / quote_factor)
