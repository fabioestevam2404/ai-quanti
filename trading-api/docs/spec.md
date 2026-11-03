# Spec — trading-api (interface de corretora)

**Status:** v1 (port de corretora) implementada; [v2 (REQ-03: orquestração e paper trading em replay)](#v2--req-03-orquestração-de-ordens-e-paper-trading-em-replay) aprovada em 2026-11-03 — pronta para implementação
**Fase:** 4 — Produto
**Depende de:** nenhum módulo interno nesta fatia (o port não chama `risk_engine`/`market_data_lake` ainda)
**ADRs relevantes:** [ADR-0004](../../docs/adr/0004-money-precision-standard.md) (Decimal), [ADR-0006](../../docs/adr/0006-risk-engine-pre-trade-gate.md) (gate), [ADR-0007](../../docs/adr/0007-trading-api-safety-layers.md) (camadas de segurança), [ADR-0008](../../docs/adr/0008-paper-trading-gate.md) (mesmo código em paper e produção)

## Objetivo desta fatia

Definir o **port de execução de ordens** (`BrokerAdapter`) que qualquer
corretora — real ou simulada — implementa, e entregar a primeira
implementação (`SimulatedBrokerAdapter`, paper trading) sem nenhuma
credencial ou chamada de rede. Um adapter de corretora real fica para uma
spec futura, quando uma corretora específica for escolhida — o objetivo
aqui é que essa escolha futura não force redesenho do contrato.

## Escopo desta fatia

- `domain.entities`: modelo de ordem, execução e posição — agnóstico de
  corretora.
- `domain.broker`: `BrokerAdapter` (Protocol) + exceções.
- `infrastructure.brokers.simulated_broker_adapter`: implementação em
  memória, para paper trading (ADR-0008) e para os próprios testes do
  contrato.

## Fora de escopo desta fatia (próximos incrementos)

- Adapter de corretora real (precisa de ADR de qual corretora + ADR-0009
  para credenciais).
- Kill switch, ledger de idempotência persistido, job de reconciliação,
  position limits hard-coded (ADR-0007) — todos consomem este port, mas são
  uma camada acima dele. Ficam para quando `trading-api` tiver uma spec
  completa de orquestração de ordem.
- Chamada ao gate do `risk-engine` antes de `submit_order` (ADR-0006) — de
  novo, é a camada de orquestração acima do port, não o port em si.

## Modelo de domínio

- `Side`: `BUY` | `SELL`.
- `OrderType`: `MARKET` | `LIMIT`.
- `TimeInForce`: `DAY` (única suportada nesta fatia).
- `OrderStatus`: `PENDING`, `ACCEPTED`, `PARTIALLY_FILLED`, `FILLED`,
  `REJECTED`, `CANCELLED`, `UNKNOWN` — `UNKNOWN` existe especificamente
  para quando uma chamada ao broker falha de forma ambígua (timeout): a
  ordem pode ou não ter sido criada do lado de lá. Um adapter real nunca
  infere sucesso ou falha nesse caso — devolve `UNKNOWN` e deixa a
  reconciliação resolver.
- `OrderRequest`: `client_order_id` (obrigatório — chave de idempotência,
  ADR-0007), ticker, side, quantity (`Decimal`), order_type, limit_price
  (`Decimal | None`, obrigatório só para `LIMIT`), time_in_force.
- `Fill`: quantity, price, filled_at (execuções parciais ou totais).
- `OrderState`: client_order_id, broker_order_id (`str | None` — pode não
  existir ainda se `PENDING`/`UNKNOWN`), status, filled_quantity,
  average_fill_price, fills.
- `Position`: ticker, quantity (`Decimal`, sinal indica direção),
  average_price.
- `AccountBalance`: cash, buying_power.

## Contrato do port (`domain.broker.BrokerAdapter`)

```python
class BrokerAdapter(Protocol):
    def submit_order(self, request: OrderRequest) -> OrderState: ...
    def get_order_state(self, client_order_id: str) -> OrderState | None: ...
    def cancel_order(self, client_order_id: str) -> OrderState: ...
    def list_open_orders(self) -> list[OrderState]: ...
    def get_positions(self) -> list[Position]: ...
    def get_account_balance(self) -> AccountBalance: ...
```

Regras do contrato (valem para **qualquer** implementação, simulada ou real):

1. **`submit_order` é idempotente por `client_order_id`.** Reenviar o mesmo
   `client_order_id` nunca cria ordem duplicada — devolve o `OrderState`
   já existente. Isso é a defesa de idempotência no nível do adapter,
   complementar (não substituta) ao ledger que `trading-api` mantém
   (ADR-0007 é defesa em profundidade: duas camadas, não uma).
2. **`cancel_order` de uma ordem já `FILLED`/`CANCELLED` não é erro** —
   devolve o estado atual (idempotente pelo mesmo motivo).
3. **`get_order_state` devolve `None` só se o `client_order_id` nunca foi
   submetido** — se foi submetido mas o resultado é incerto, devolve
   `OrderState` com `status=UNKNOWN`, nunca `None`.
4. **Erros são tipados**, nunca exceção genérica:
   `BrokerConnectionError` (transitório — retry com o mesmo
   `client_order_id` é seguro), `BrokerRejectionError` (definitivo —
   corretora recusou por motivo de negócio, não adianta retry automático),
   `BrokerAuthenticationError` (credencial inválida — crítico, deve
   propagar para acionar alerta, nunca ser engolido).

## SimulatedBrokerAdapter (paper trading, ADR-0008)

- Preenche `MARKET` imediatamente ao preço corrente (via `price_lookup`
  injetado — em uso real seria `market_data_lake.api`, nos testes é
  um dicionário fixo). `LIMIT` preenche só se o preço corrente já
  satisfaz o limite; senão fica `ACCEPTED` (sem motor de matching —
  simplificação conhecida desta fatia).
- Estado (ordens, posições, caixa) **em memória** — não sobrevive a
  restart do processo. Aceitável para esta fatia: paper trading formal
  (com persistência) é parte da camada de orquestração ainda não
  construída, não deste port.
- Nunca retorna `UNKNOWN` (é síncrono e determinístico por natureza) — mas
  implementa o contrato completo, então testar contra ele já valida que a
  interface é utilizável antes de um adapter real existir.

## Critérios de aceite

1. Duas chamadas de `submit_order` com o mesmo `client_order_id` produzem
   o mesmo `OrderState` — nunca duas ordens.
2. `cancel_order` em ordem já preenchida não lança exceção.
3. Todo valor monetário/quantidade no port é `Decimal` — nunca `float`.
4. `SimulatedBrokerAdapter` passa por todos os métodos do `BrokerAdapter`
   sem exigir nenhuma variável de ambiente ou credencial.

## Rastreabilidade

Cada critério de aceite e o teste que o comprova (caminhos relativos a
`trading-api/tests/`). Critério novo entra nesta tabela no mesmo PR;
critério sem teste automatizado precisa de justificativa aqui.

| Critério | Evidência | Tipo |
|---|---|---|
| 1. `submit_order` idempotente por `client_order_id` | `test_simulated_broker_adapter.py::test_submeter_o_mesmo_client_order_id_duas_vezes_nao_duplica` | Unitário |
| 2. Cancelar ordem preenchida não é erro | `test_simulated_broker_adapter.py::test_cancelar_ordem_ja_preenchida_e_idempotente_nao_lanca_erro` | Unitário |
| 3. Valores monetários e quantidades em `Decimal` | `test_entities.py::test_quantity_float_e_rejeitada`; `::test_limit_price_float_e_rejeitado` | Unitário |
| 4. Port completo sem variável de ambiente ou credencial | `test_simulated_broker_adapter.py::test_percorre_todo_o_port_sem_nenhuma_variavel_de_ambiente` | Unitário |

Critério 3 valida a **entrada** do port (`OrderRequest`). As saídas
(`OrderState`, `Fill`, `Position`, `AccountBalance`) são produzidas pelo
adapter a partir de `Decimal`; um adapter real precisará converter a
resposta da corretora para `Decimal` na própria fronteira — requisito da
spec desse adapter.

---

## v2 — REQ-03: orquestração de ordens e paper trading em replay

**Requisito:** REQ-03 da [visão do ciclo 1](../../docs/vision.md) (decisão 3:
replay primeiro, tempo real depois).
**Base:** [ADR-0006](../../docs/adr/0006-risk-engine-pre-trade-gate.md) (gate
síncrono, fail-closed), [ADR-0007](../../docs/adr/0007-trading-api-safety-layers.md)
(quatro camadas), [ADR-0008](../../docs/adr/0008-paper-trading-gate.md) (paper
com o mesmo código de produção), [relatório 0003](../../docs/research/0003-primeiro-backtest-real.md)
(estratégia apta para paper: médias de 10 e 50 dias em PETR4, VALE3, ITUB4).

### Objetivo

Toda ordem passa pelas quatro camadas do ADR-0007 e pelo gate do
`risk-engine` antes de chegar ao adapter de corretora. Em replay, a estratégia
apta roda pregão a pregão sobre o histórico, com o adapter simulado, e o
resultado **reproduz o backtest** do mesmo período — prova de que paper e
backtest executam a mesma estratégia.

### Escopo

**1. Fluxo de uma ordem** (`place_order`), nesta ordem, cada passo podendo
recusar:

| # | Passo | Recusa quando | Motivo registrado |
|---|---|---|---|
| 1 | Idempotência (ADR-0007, camada 2) | `client_order_id` já processado: devolve o resultado guardado, sem reenviar | — |
| 2 | Kill switch (camada 1) | ligado | `kill_switch` |
| 3 | Limites fixos no código (camada 4) | exposição projetada acima do teto por ativo, ou ordens no minuto acima do teto | `hard_limit_exposure`, `hard_limit_rate` |
| 4 | Gate do `risk-engine` (ADR-0006) | `BLOCK` ou falha ao consultar (fail-closed) | motivo do gate |
| 5 | Envio ao `BrokerAdapter` | rejeição da corretora | `broker_rejected` |
| 6 | Fill registrado no `risk-engine` (`record_fill`, P&L realizado em `Decimal`) | — | — |

- **Toda tentativa é persistida**, enviada ou recusada, com o passo e o motivo:
  é a evidência do QA-01 da visão (ordens enviadas = ordens com `ALLOW`).
- **`client_order_id` determinístico** a partir de estratégia, ativo, lado e
  data do sinal (ADR-0007): reprocessar o mesmo pregão nunca duplica ordem.
- **Relógio injetável:** o limite de ordens por minuto e as datas do gate usam
  o relógio da execução — em replay, o tempo simulado do pregão.

**2. Persistência em Postgres** (schema via Alembic, ADR-0012; tabela de
versão própria): tentativas de ordem (`client_order_id` `UNIQUE`), fills e
estado do kill switch (linha única, como o circuit breaker).

**3. Kill switch:** `activate_kill_switch(actor, reason)` e
`reset_kill_switch(actor)`; estado persistido, reset só manual (camada 1).

**4. Reconciliação** (camada 3): compara a posição que o `trading-api`
registrou (fills persistidos) com a reportada pelo adapter. Qualquer
divergência é registrada; acima do limiar (padrão: qualquer diferença de
quantidade) **liga o kill switch** automaticamente. Em replay, roda ao fim de
cada pregão.

**5. Limites fixos no código** (constantes, mudança só por PR):

| Constante | Valor proposto | Motivo |
|---|---|---|
| Exposição máxima por ativo | R$ 60.000 | ~2× a fatia de R$ 33.333 por ativo do capital de R$ 100.000 |
| Ordens por minuto | 30 | Folga larga para 3 ativos com ordens no máximo diárias |

**6. Limites do gate** (`RiskLimits`, configuração da execução): exposição por
ativo R$ 40.000 e perda diária R$ 3.000 (3% do capital).

**7. Estratégia em paper**

- Sinal: `backtesting_engine.api` ganha uma função **aditiva** que devolve o
  sinal de um ativo num pregão a partir das barras até aquele pregão — a mesma
  função do backtest, sem reimplementação.
- Preços ajustados do `market-data-lake` (mesma declaração do item 7).
- Dimensionamento igual ao backtest: cada ativo opera com sua fatia de caixa
  (capital ÷ nº de ativos), maior quantidade inteira que cabe, ordem `MARKET`
  executada na abertura do pregão seguinte ao sinal.

**8. Adapter simulado** (mudanças no `SimulatedBrokerAdapter`):

- `CostModel` opcional (custo e slippage por lado, como no backtest).
- Relógio e preço de execução injetáveis: em replay, o fill acontece na
  abertura do pregão de execução, com horário simulado — replay reproduzível.

**9. Replay** (`run_paper_replay`): percorre os pregões de um período,
gera sinais, envia ordens pelo fluxo completo, reconcilia ao fim de cada
pregão e devolve um relatório: ordens por passo e motivo, patrimônio diário,
métricas (via `risk_engine.api`) e aderência ao backtest do mesmo período.

### Fora de escopo (v2)

- Paper em **tempo real** pelos 20 pregões (passo 4 da ordem de execução;
  exige agendamento diário e o COTAHIST diário): v3.
- Adapter de corretora real e credenciais (ADR-0009); capital real.
- API HTTP (FastAPI) e `trading-dashboard`: o fluxo é exposto em
  `trading_api.api` como funções Python.
- Ordens `LIMIT` na estratégia, venda a descoberto, ordens parciais.

### Contrato de API (`trading_api.api`, adições)

```python
def place_order(intent: OrderIntent, context: ExecutionContext) -> OrderAttempt: ...
def activate_kill_switch(actor: str, reason: str) -> None: ...
def reset_kill_switch(actor: str) -> None: ...
def reconcile(context: ExecutionContext) -> ReconciliationResult: ...
def run_paper_replay(config: ReplayConfig) -> ReplayReport: ...
```

`trading_api` importa apenas `risk_engine.api`, `backtesting_engine.api` e
`market_data_lake.api` (contrato `forbidden` novo no import-linter).

### Critérios de aceite (v2)

5. **Ordem só sai com `ALLOW`:** em qualquer combinação de recusas, o adapter
   só recebe ordens cujo gate respondeu `ALLOW`; contagem de enviadas = `ALLOW`.
6. **Fail-closed:** com o `risk-engine` indisponível, nenhuma ordem chega ao
   adapter e a tentativa fica registrada com o motivo.
7. **Idempotência:** o mesmo `client_order_id` enviado duas vezes (inclusive
   após reiniciar o processo) gera uma única ordem no adapter.
8. **Kill switch:** ligado, recusa toda ordem antes do gate; o estado sobrevive
   a reinício; reset só manual.
9. **Limites fixos:** recusam mesmo com o gate respondendo `ALLOW` (gate
   simulado permissivo).
10. **Reconciliação:** divergência entre posição registrada e posição do
    adapter liga o kill switch e fica registrada.
11. **Fill no ledger:** cada execução chega ao `record_fill` do `risk-engine`
    em `Decimal`, com P&L realizado nas vendas.
12. **Replay reproduz o backtest:** no período out-of-sample do relatório 0003,
    o patrimônio final do replay fica a até 0,5% do backtest, com as mesmas
    operações (datas, lados e quantidades).
13. **Replay reproduzível:** mesma configuração e mesmos dados produzem o
    mesmo relatório.
14. **QA-01 medido:** o relatório do replay informa ordens enviadas, ordens
    com `ALLOW` e recusas por passo — e as duas primeiras são iguais.
15. **Infra real:** testes de integração contra Postgres real (fluxo, kill
    switch, idempotência após reinício).
