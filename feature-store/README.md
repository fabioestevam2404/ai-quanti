# feature-store

> Status: 🟡 Em implementação (v1 local/dev) — retorno diário, SMA e volatilidade sobre janela N

Engenharia de atributos versionada, ponto único de leitura de features para treino (ML/RL) e simulação (backtesting).

## Rodando localmente

Depende do `market-data-lake` já instalado no mesmo ambiente (ver README dele).

```
docker compose -f ../infrastructure/docker-compose.local.yml up -d
pip install -e ../market-data-lake
pip install -e ".[dev]"
pytest
```

```python
from datetime import date
from feature_store.api import get_training_features, materialize_online_features, get_online_features

get_training_features("PETR4", date(2026, 8, 1), date(2026, 8, 14))
materialize_online_features("PETR4", date(2026, 8, 14))
get_online_features("PETR4")
```

## Spec

[docs/spec.md](docs/spec.md) — escopo, modelo de domínio, contrato de API e critérios de aceite.

## Arquitetura interna

Segue Clean Architecture (`domain / application / infrastructure / api`),
consistente com os demais módulos da plataforma.

## ADRs relevantes

- [ADR-0003](../docs/adr/0003-database-strategy.md) — Redis hot-path
- Ver [docs/adr](../docs/adr/README.md)
