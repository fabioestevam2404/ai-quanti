# risk-engine

> Status: 📋 Planejado — aguardando spec (SDD) antes da implementação

Papel duplo desde [ADR-0006](../docs/adr/0006-risk-engine-pre-trade-gate.md):

1. **Analítico (batch)** — VaR, Sharpe, Sortino, Calmar, drawdown máximo, exposição por ativo/setor. Para dashboard e avaliação de estratégia.
2. **Gate pré-trade (síncrono)** — chamado por `trading-api` **antes** de qualquer ordem real ser enviada. Bloqueia por limite de exposição por ativo ou por limite de perda diária (circuit breaker). `trading-api` bloqueia por padrão (fail-closed) se este gate não responder.

## Spec

_A ser escrita seguindo Spec-Driven Development, antes de qualquer código._
A spec precisa definir, no mínimo: SLA de resposta do modo gate (ex: p99 < 50ms), formato da decisão `ALLOW`/`BLOCK` + motivo, e como o circuit breaker é resetado (sempre manual, nunca automático).

## Arquitetura interna

Segue Clean Architecture (`domain / application / infrastructure / api`),
consistente com os demais módulos da plataforma.

## ADRs relevantes

- [ADR-0006](../docs/adr/0006-risk-engine-pre-trade-gate.md) — de métricas pós-fato para gate pré-trade
- [ADR-0007](../docs/adr/0007-trading-api-safety-layers.md) — position limits hard-coded como defesa independente deste módulo
- Ver [docs/adr](../docs/adr/README.md)
