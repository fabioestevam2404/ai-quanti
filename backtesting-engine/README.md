# backtesting-engine

> Status: 🟡 v1 local (REQ-02 implementado) — relatório com checklist de 7 itens; o item 7 (preços ajustados) fica "não verificado" até o REQ-01

## Uso

```python
from datetime import date
from decimal import Decimal

from backtesting_engine.api import (
    BacktestConfig, CostModel, UniverseDeclaration, run_backtest,
)

report = run_backtest(BacktestConfig(
    universe=UniverseDeclaration(
        tickers=("PETR4", "VALE3", "ITUB4"),
        selection_criterion="ações líquidas da B3 listadas hoje",
        selected_on=date(2026, 11, 1),
    ),
    start=date(2015, 1, 1),
    end=date(2025, 12, 31),
    initial_capital=Decimal("100000.00"),
    costs=CostModel(cost_bps=5, slippage_bps=5),
))

for item in report.checklist:
    print(item.number, item.status, item.evidence)
print(report.apto_para_paper, report.apto_para_capital_real)
```

Os preços vêm do `market-data-lake`, que precisa ter o período ingerido.

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
