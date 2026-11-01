# trading-api

> Status: 🟡 Em implementação (parcial) — port `BrokerAdapter` + `SimulatedBrokerAdapter` (paper trading)

API pública/interna: única porta de saída para a corretora/exchange; expõe estratégias, ordens e portfólio.

Com capital real em jogo, quatro camadas de segurança são obrigatórias
desde a primeira versão que toca uma corretora real — não incrementais,
não opcionais ([ADR-0007](../docs/adr/0007-trading-api-safety-layers.md)):

1. **Kill switch manual** — interrompe todo envio de ordem, estado persistido (não em memória).
2. **Idempotência de ordens** — `client_order_id` determinístico; retry nunca duplica ordem.
3. **Reconciliação periódica** — posição interna vs. posição real na corretora; divergência aciona kill switch.
4. **Position limits hard-coded** — última linha de defesa, independente do `risk-engine`.

Toda ordem passa pelo gate síncrono do `risk-engine`
([ADR-0006](../docs/adr/0006-risk-engine-pre-trade-gate.md)) antes de sair.
Credenciais de corretora vêm de um secrets manager, nunca de variável de
ambiente em texto plano ([ADR-0009](../docs/adr/0009-secrets-management.md)).

**As quatro camadas acima ainda não estão implementadas.** O que existe
hoje é só a base que elas vão consumir: o port `BrokerAdapter` (contrato
agnóstico de corretora) e `SimulatedBrokerAdapter` (paper trading, sem
credencial). Kill switch, ledger de idempotência, reconciliação e position
limits são o próximo incremento — ver
[docs/spec.md](docs/spec.md#fora-de-escopo-desta-fatia-próximos-incrementos).

## Rodando localmente

Sem dependências externas nesta fatia — não precisa de Docker Compose.

```
uv run --all-packages pytest
```

```python
from decimal import Decimal
from trading_api.domain.entities import OrderRequest, OrderType, Side
from trading_api.infrastructure.brokers.simulated_broker_adapter import SimulatedBrokerAdapter

adapter = SimulatedBrokerAdapter(price_lookup=lambda ticker: Decimal("30.00"))
state = adapter.submit_order(
    OrderRequest(
        client_order_id="order-1",
        ticker="PETR4",
        side=Side.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.MARKET,
    )
)
# state.status == OrderStatus.FILLED
```

## Paper trading

Ambiente formal do próprio `trading-api` (mesmo código, adapter de execução
`sandbox` ou `simulado`), não uma fase de calendário — critério explícito
de promoção para capital real em
[ADR-0008](../docs/adr/0008-paper-trading-gate.md).
`SimulatedBrokerAdapter` é o adapter `simulado` — falta ainda persistência
entre execuções (hoje é em memória) para paper trading valer como ambiente
formal de verdade.

## Spec

[docs/spec.md](docs/spec.md) — cobre só o port de corretora nesta fatia.
Nenhuma linha de código que envie ordem real deve existir antes de uma
spec futura cobrir as quatro camadas de segurança e um adapter real.

## Arquitetura interna

Segue Clean Architecture (`domain / infrastructure` nesta fatia —
`application`/`api` entram com a camada de orquestração), consistente com
os demais módulos da plataforma.

## ADRs relevantes

- [ADR-0004](../docs/adr/0004-money-precision-standard.md) — Decimal em todo o port
- [ADR-0006](../docs/adr/0006-risk-engine-pre-trade-gate.md) — gate síncrono de risco
- [ADR-0007](../docs/adr/0007-trading-api-safety-layers.md) — camadas de segurança
- [ADR-0008](../docs/adr/0008-paper-trading-gate.md) — paper trading como gate
- [ADR-0009](../docs/adr/0009-secrets-management.md) — gestão de segredos
- Ver [docs/adr](../docs/adr/README.md)
