# risk-engine

> Status: 🟡 Em implementação (v1 local/dev) — modo analítico + gate pré-trade

Papel duplo desde [ADR-0006](../docs/adr/0006-risk-engine-pre-trade-gate.md):

1. **Analítico (batch, `float64`)** — VaR histórico, Sharpe, Sortino, Calmar, drawdown máximo, a partir do histórico de preços do `market-data-lake`.
2. **Gate pré-trade (síncrono, `Decimal`)** — decide `ALLOW`/`BLOCK` contra limite de exposição por ativo e perda diária (circuit breaker). Fail-closed: qualquer falha ao consultar o ledger vira `BLOCK`, nunca `ALLOW` por omissão.

## Rodando localmente

Depende do `market-data-lake`; o uv workspace da raiz instala os dois no
mesmo ambiente ([ADR-0011](../docs/adr/0011-uv-workspace-lockfile.md)).

```
docker compose -f ../infrastructure/docker-compose.local.yml up -d
uv run --all-packages pytest
```

```python
from datetime import date
from decimal import Decimal
from risk_engine.api import compute_metrics_for_ticker, evaluate_order, record_fill, reset_circuit_breaker
from risk_engine.domain.entities import RiskLimits, Side

compute_metrics_for_ticker("PETR4", date(2026, 8, 1), date(2026, 8, 21))

limits = RiskLimits(max_exposure_per_ticker=Decimal("10000"), max_daily_loss=Decimal("500"))
decision = evaluate_order("PETR4", Side.BUY, Decimal("100"), Decimal("30.00"), limits)
# decision.allowed, decision.reason

record_fill("PETR4", Side.BUY, Decimal("100"), Decimal("30.00"), Decimal("0"), date.today())
reset_circuit_breaker(actor="quant@example.com")
```

## Spec

[docs/spec.md](docs/spec.md) — escopo, modelo de domínio, contrato de API e critérios de aceite.
SLA de latência do modo gate (ex: p99 < 50ms) fica para quando `trading-api` existir e puder medir de ponta a ponta — fora de escopo desta versão.

## Arquitetura interna

Segue Clean Architecture (`domain / application / infrastructure / api`),
consistente com os demais módulos da plataforma. Só importa
`market_data_lake.api` (nunca suas camadas internas) — fronteira validada
por import-linter.

## ADRs relevantes

- [ADR-0004](../docs/adr/0004-money-precision-standard.md) — Decimal no modo gate, float no modo analítico
- [ADR-0006](../docs/adr/0006-risk-engine-pre-trade-gate.md) — de métricas pós-fato para gate pré-trade
- [ADR-0007](../docs/adr/0007-trading-api-safety-layers.md) — position limits hard-coded como defesa independente deste módulo
- Ver [docs/adr](../docs/adr/README.md)
