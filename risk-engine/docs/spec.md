# Spec — risk-engine

**Status:** Em implementação
**Fase:** 2 — Análise
**Depende de:** `market-data-lake` (via `market_data_lake.api`)
**ADRs relevantes:** [ADR-0001](../../docs/adr/0001-modular-monolith-vs-microservices.md) (fronteiras), [ADR-0004](../../docs/adr/0004-money-precision-standard.md) (Decimal vs. float), [ADR-0006](../../docs/adr/0006-risk-engine-pre-trade-gate.md) (papel duplo)

## Objetivo

Dois modos, com requisitos de precisão numérica diferentes (ADR-0004):

1. **Analítico (batch, `float64`)** — métricas de performance/risco de uma
   estratégia a partir de uma série histórica de preços: Sharpe, Sortino,
   Calmar, VaR histórico, drawdown máximo. Consumo: dashboard, avaliação de
   estratégia, relatório de backtest (ADR-0010).
2. **Gate pré-trade (síncrono, `Decimal`)** — chamado por `trading-api`
   antes de qualquer ordem real. Decide `ALLOW`/`BLOCK` contra dois limites:
   exposição por ativo e perda diária (circuit breaker). Como envolve
   exposição/P&L, usa `Decimal` (ADR-0004 nomeia `risk-engine` explicitamente
   nesse ponto) — nunca `float`.

## Escopo (v1 — ambiente local/dev)

### Modo analítico

- Lê preços via `market_data_lake.api.get_price_series` (não via
  `feature-store`: Sharpe/VaR/drawdown precisam da série de preços sobre
  uma janela arbitrária definida pelo caller, não da janela fixa de
  features de ML do `feature-store` — evita acoplar risco a um design
  pensado para treino de modelo).
- Calcula retornos diários a partir dos preços, depois: Sharpe, Sortino,
  Calmar, VaR histórico (percentil 95%), drawdown máximo. Anualização com
  252 pregões/ano (mesma convenção do `feature-store`).

### Modo gate pré-trade

- **`risk-engine` é dono do próprio ledger de exposição e P&L diário** —
  não confia em número informado pelo caller. `trading-api` (quando
  existir) chama `record_fill` a cada execução real; para v1, sem
  `trading-api`, o ledger é populado diretamente (testes, scripts, ou
  futura integração).
- `evaluate_order` decide, nesta ordem:
  1. Circuit breaker já disparado hoje → `BLOCK`.
  2. Exposição projetada (exposição atual + a ordem proposta) excede
     `max_exposure_per_ticker` → `BLOCK`.
  3. P&L diário já é pior que `-max_daily_loss` → dispara o circuit breaker
     (persistido) e `BLOCK`.
  4. Senão → `ALLOW`.
- **Fail-closed**: qualquer exceção ao consultar o ledger (ex: Postgres
  fora do ar) é tratada como `BLOCK` — nunca deixa passar por omissão.
- Circuit breaker é por dia: dispara para uma data específica; reset manual
  limpa o estado a qualquer momento; em um novo pregão, o estado do dia
  anterior deixa de valer automaticamente (sem precisar de reset).
- Limites (`max_exposure_per_ticker`, `max_daily_loss`) são passados pelo
  caller a cada chamada — não persistidos pelo `risk-engine` nesta versão
  (evita adicionar uma camada de configuração antes de `trading-api`
  existir para consumi-la).

## Fora de escopo (v1)

- SLA de latência formal (p99 < 50ms citado no README) — vira requisito de
  teste de carga quando `trading-api` existir e puder ser medido de ponta a
  ponta.
- Persistência de limites por estratégia/portfólio (fica para quando
  `trading-api`/`portfolio-optimizer` existirem).
- Alertas automáticos (Slack/PagerDuty) no disparo do circuit breaker —
  fica para `monitoring/`.

## Modelo de domínio

- `RiskMetrics`: sharpe, sortino, calmar, var_95, max_drawdown (todos
  `float`).
- `Side`: `BUY` | `SELL`.
- `OrderProposal`: ticker, side, quantity (`Decimal`), estimated_price
  (`Decimal`).
- `RiskLimits`: max_exposure_per_ticker (`Decimal`), max_daily_loss
  (`Decimal`).
- `GateDecision`: allowed (`bool`), reason (`str | None`).

## Contrato de API (`risk_engine.api`)

```python
def compute_metrics_for_ticker(ticker: str, start: date, end: date, risk_free_rate: float = 0.0) -> RiskMetrics: ...
def evaluate_order(ticker: str, side: Side, quantity: Decimal, estimated_price: Decimal, limits: RiskLimits) -> GateDecision: ...
def record_fill(ticker: str, side: Side, quantity: Decimal, price: Decimal, realized_pnl_delta: Decimal) -> None: ...
def reset_circuit_breaker(actor: str) -> None: ...
```

Nenhum outro módulo importa de `risk_engine.domain`/`application`/
`infrastructure` diretamente — só `risk_engine.api` (fronteira validada por
import-linter). `risk_engine` só importa `market_data_lake.api`, nunca suas
camadas internas.

## Critérios de aceite

1. `evaluate_order` é fail-closed: se o ledger (Postgres) estiver
   indisponível, retorna `BLOCK`, nunca `ALLOW` por omissão.
2. Circuit breaker disparado bloqueia **qualquer** ordem (mesmo abaixo do
   limite de exposição) até reset manual ou até a data virar.
3. `record_fill` e `evaluate_order` operam inteiramente em `Decimal` — um
   `float` vazando para dentro do gate é bug, não just estilo.
4. `compute_metrics_for_ticker` é determinístico para o mesmo período —
   mesmo requisito do `feature-store` (sem depender de estado externo além
   dos preços).
5. Testes rodam contra Postgres real via `docker-compose` — nenhum mock de
   banco.

## Rastreabilidade

Cada critério de aceite e o teste que o comprova (caminhos relativos a
`risk-engine/tests/`). Critério novo entra nesta tabela no mesmo PR;
critério sem teste automatizado precisa de justificativa aqui.

| Critério | Evidência | Tipo |
|---|---|---|
| 1. Fail-closed | `test_evaluate_order_use_case.py::test_falha_no_ledger_e_fail_closed_bloqueia` | Unitário (ledger e breaker que falham) |
| 2. Breaker bloqueia qualquer ordem até reset ou virada da data | `test_evaluate_order_use_case.py::test_circuit_breaker_ja_disparado_bloqueia_qualquer_ordem`; `test_postgres_circuit_breaker.py::test_reset_manual_limpa_o_disparo`; `::test_disparo_nao_vale_para_outro_dia` | Integração |
| 3. Gate e ledger só em `Decimal` | `test_decimal_boundary.py` — `float` rejeitado com `TypeError` em `OrderProposal`, `RiskLimits` e `record_fill` (sem alterar o ledger); ledger devolve `Decimal` exato | Unitário + integração |
| 4. Métricas determinísticas | `test_compute_metrics_for_ticker.py::test_mesmo_periodo_produz_as_mesmas_metricas`; `test_compute_metrics.py::test_e_deterministico` | Integração + unitário |
| 5. Postgres real, sem mock de banco | Estrutural: fixture `postgres_dsn` (Postgres real, schema via migrações — ADR-0012). Exceção deliberada: o teste do critério 1 usa dublês que lançam erro, porque simular indisponibilidade é o objetivo | Estrutural |

`float` com `Decimal` em `evaluate_order` gera `TypeError` na construção de
`OrderProposal`, antes do gate: é erro de programação do caller, não decisão
de risco — nunca resulta em `ALLOW`.
