# backtesting-engine

> Status: 🟡 Em implementação (REQ-02) — fatias 1 e 2: sinais, execução e validação (out-of-sample, walk-forward, robustez); checklist e relatório na fatia 3

Motor próprio de simulação histórica de estratégias, com custos de transação, slippage e walk-forward validation (ver ADR-0005).

Desde [ADR-0010](../docs/adr/0010-backtesting-validation-checklist.md), o
relatório de backtest tem um **contrato de saída obrigatório**, não só
métricas de performance: sem look-ahead bias, sem viés de sobrevivência,
custos habilitados, walk-forward executado, teste out-of-sample e robustez
a perturbação de parâmetro. Nenhuma estratégia avança para paper trading
([ADR-0008](../docs/adr/0008-paper-trading-gate.md)) sem esses seis campos
preenchidos — "não verificado" bloqueia a promoção tanto quanto "falhou".

## Spec

[docs/spec.md](docs/spec.md): cruzamento de médias móveis com execução na
abertura seguinte, custos e slippage, walk-forward, out-of-sample, robustez
de parâmetro e o checklist de 7 itens (ADR-0010 e
[ADR-0013](../docs/adr/0013-universo-declarado-no-checklist.md)) como parte
do contrato de `backtesting_engine.api`.

## Arquitetura interna

Segue Clean Architecture (`domain / application / infrastructure / api`),
consistente com os demais módulos da plataforma.

## ADRs relevantes

- [ADR-0005](../docs/adr/0005-custom-backtesting-engine.md) — motor próprio, custos e walk-forward
- [ADR-0010](../docs/adr/0010-backtesting-validation-checklist.md) — checklist de validação obrigatório
- Ver [docs/adr](../docs/adr/README.md)
