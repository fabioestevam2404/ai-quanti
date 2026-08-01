# backtesting-engine

> Status: 📋 Planejado — aguardando spec (SDD) antes da implementação

Motor próprio de simulação histórica de estratégias, com custos de transação, slippage e walk-forward validation (ver ADR-0005).

Desde [ADR-0010](../docs/adr/0010-backtesting-validation-checklist.md), o
relatório de backtest tem um **contrato de saída obrigatório**, não só
métricas de performance: sem look-ahead bias, sem viés de sobrevivência,
custos habilitados, walk-forward executado, teste out-of-sample e robustez
a perturbação de parâmetro. Nenhuma estratégia avança para paper trading
([ADR-0008](../docs/adr/0008-paper-trading-gate.md)) sem esses seis campos
preenchidos — "não verificado" bloqueia a promoção tanto quanto "falhou".

## Spec

_A ser escrita seguindo Spec-Driven Development, antes de qualquer código._
A spec precisa modelar o checklist de validação do ADR-0010 como parte do
contrato de `backtesting-engine.api`, não como relatório à parte.

## Arquitetura interna

Segue Clean Architecture (`domain / application / infrastructure / api`),
consistente com os demais módulos da plataforma.

## ADRs relevantes

- [ADR-0005](../docs/adr/0005-custom-backtesting-engine.md) — motor próprio, custos e walk-forward
- [ADR-0010](../docs/adr/0010-backtesting-validation-checklist.md) — checklist de validação obrigatório
- Ver [docs/adr](../docs/adr/README.md)
