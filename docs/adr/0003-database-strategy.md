# ADR-0003: Estratégia de banco de dados por caso de uso

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** `market-data-lake`, `trading-api`, `feature-store`

## Contexto

A plataforma tem três perfis de dados muito diferentes:
1. Dados transacionais/relacionais (usuários, ordens, configuração de
   estratégias, auditoria) — baixo volume, alta integridade.
2. Séries temporais de mercado (OHLCV, tick data, order book) — altíssimo
   volume, escrita em lote/streaming, leitura analítica por range de tempo.
3. Cache de features "hot-path" para inferência em tempo real — baixíssima
   latência, dados voláteis.

Usar um único banco (ex: só Postgres) para os três casos força trade-offs
ruins: Postgres sem extensão de série temporal degrada em consultas
analíticas de milhões de linhas de tick data.

## Decisão

Banco por responsabilidade, não banco único:

| Uso | Tecnologia | Justificativa |
|---|---|---|
| Transacional / metadados / auditoria | **PostgreSQL** | Já validado no Norte; ACID, migrations com Alembic, JSONB quando preciso de flexibilidade |
| Séries temporais de mercado (OHLCV, ticks) | **ClickHouse** (produção) / **DuckDB** (dev local e notebooks) | Compressão colunar e agregação por range de tempo ordens de magnitude mais rápida que Postgres para este padrão de acesso |
| Cache / feature store hot-path / filas leves | **Redis** | Já validado no Norte para cache e confirmação de fluxos; latência sub-milissegundo |
| Barramento de eventos (streaming) | **Kafka** | Padrão de mercado para ingestão contínua de múltiplas fontes com replay |

`kdb+` (citado como padrão de grandes fundos) fica **fora de escopo**
deliberadamente: é uma tecnologia paga e de nicho que não agrega valor de
portfólio proporcional ao custo de aprendizado neste estágio — ClickHouse
cobre o mesmo caso de uso analítico de séries temporais com stack open-source.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Só PostgreSQL + TimescaleDB | Um único banco para operar | Ainda degrada em volumes muito altos de tick data comparado a colunar puro; menos "impressivo" tecnicamente para o portfólio | Rejeitado, mas fica como opção válida se ClickHouse se mostrar operacionalmente pesado demais |
| kdb+ | Padrão da indústria em HFT | Licenciamento caro, curva de aprendizado (linguagem q), sem necessidade real neste estágio | Custo/benefício não compensa |
| InfluxDB | Fácil de operar | Menos flexível para joins analíticos complexos que ClickHouse | ClickHouse tem melhor relação performance/flexibilidade |

## Consequências

- **Positivas:** cada módulo usa a ferramenta certa para seu padrão de
  acesso; história técnica clara para explicar em entrevista/portfólio.
- **Negativas / trade-offs aceitos:** mais uma tecnologia para provisionar e
  documentar (ClickHouse) além do stack já conhecido do Norte.
- **Impacto em outros módulos:** `market-data-lake` e `feature-store`
  dependem diretamente desta decisão; `infrastructure/` precisa provisionar
  os quatro sistemas via Terraform/Docker Compose.
