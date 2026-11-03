# market-data-lake

> Status: 🟡 v2 local (REQ-01 implementado) — séries oficiais da B3 (COTAHIST), ajuste por proventos, reconciliação contra o COTAHIST e declaração de ajuste por série

Ingestão, versionamento e armazenamento histórico de dados de mercado (preços, volume, order book). Fonte de verdade batch da plataforma.

## Rodando localmente

```
docker compose -f ../infrastructure/docker-compose.local.yml up -d
uv run --all-packages pytest

# Schema do banco de dev (auditoria de ingestão) — ADR-0012
uv run --all-packages alembic upgrade head
```

```python
from datetime import date
from market_data_lake.api import (
    get_adjustment_declaration, get_price_series, ingest_daily_bars, refresh_corporate_events,
)

ingest_daily_bars("PETR4", date(2026, 8, 1), date(2026, 8, 14), source="mock")  # sem default de propósito
get_price_series("PETR4", date(2026, 8, 1), date(2026, 8, 14))

# Séries oficiais da B3: baixa um arquivo anual por ano pedido (cache em
# MARKET_DATA_LAKE_COTAHIST_DIR). Barras guardadas brutas.
ingest_daily_bars("PETR4", date(2015, 1, 1), date(2025, 12, 31), source="cotahist")

# Eventos da B3 (rede): guarda um snapshot em MARKET_DATA_LAKE_B3_EVENTS_DIR.
refresh_corporate_events("PETR4")

# Série ajustada por proventos: snapshot mais recente + tabela de correções
# (reference/corporate_events_corrections.csv). Sem snapshot, LookupError.
get_price_series("PETR4", date(2015, 1, 1), date(2025, 12, 31), adjusted=True)

# O que se pode afirmar sobre o ajuste: reconciliação contra o COTAHIST.
declaration = get_adjustment_declaration("PETR4", date(2015, 1, 1), date(2025, 12, 31))
declaration.verified      # True só com série ajustada e zero pendências
declaration.pendencies    # saltos sem evento, eventos que não explicam o salto...
```

O `backtesting-engine` lê a declaração de cada ativo: usa a série ajustada
quando ela existe e só marca o item 7 do checklist como verificado quando
todas as séries estão verificadas.

A tabela de correções guarda eventos que faltam ou estão errados nas rotas da
B3, sempre com a fonte — hoje, o desdobramento de 2005 da PETR4 e a cisão de
2021 da ITUB4 (investigação 0002).

O download usa os certificados do sistema operacional (`truststore`): funciona
em rede com inspeção TLS sem desligar a verificação.

## Spec

[docs/spec.md](docs/spec.md) — escopo, modelo de domínio, contrato de API e critérios de aceite.

## Arquitetura interna

Segue Clean Architecture (`domain / application / infrastructure / api`),
consistente com os demais módulos da plataforma.

## ADRs relevantes

- [ADR-0003](../docs/adr/0003-database-strategy.md) — DuckDB (dev) / Postgres
- Ver [docs/adr](../docs/adr/README.md)
