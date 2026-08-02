# Spec — trading-api (interface de corretora)

**Status:** Em implementação (parcial — ver escopo)
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
