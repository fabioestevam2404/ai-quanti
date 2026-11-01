# market-data-lake

> Status: 🟡 Em implementação (v1 local/dev) — OHLCV diário, provider mock + Alpha Vantage

Ingestão, versionamento e armazenamento histórico de dados de mercado (preços, volume, order book). Fonte de verdade batch da plataforma.

## Rodando localmente

```
docker compose -f ../infrastructure/docker-compose.local.yml up -d
uv run --all-packages pytest
```

```python
from datetime import date
from market_data_lake.api import ingest_daily_bars, get_price_series

ingest_daily_bars("PETR4", date(2026, 8, 1), date(2026, 8, 14), source="mock")  # sem default de propósito
get_price_series("PETR4", date(2026, 8, 1), date(2026, 8, 14))
```

## Spec

[docs/spec.md](docs/spec.md) — escopo, modelo de domínio, contrato de API e critérios de aceite.

## Arquitetura interna

Segue Clean Architecture (`domain / application / infrastructure / api`),
consistente com os demais módulos da plataforma.

## ADRs relevantes

- [ADR-0003](../docs/adr/0003-database-strategy.md) — DuckDB (dev) / Postgres
- Ver [docs/adr](../docs/adr/README.md)
