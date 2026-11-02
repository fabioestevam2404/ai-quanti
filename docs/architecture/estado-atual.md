# Arquitetura — estado atual e MVP do ciclo 1

Os diagramas [C4](README.md) descrevem a arquitetura-alvo completa. Este
documento mostra o que existe no código hoje e o que o MVP do ciclo 1
([vision.md](../vision.md)) acrescenta. A visão geral dos módulos está no
[README](../../README.md#arquitetura).

## Camadas dentro de cada módulo

Cada módulo segue Clean Architecture. A regra é verificada pelo
`import-linter` no CI ([`.importlinter`](../../.importlinter)): uma camada só
importa as camadas abaixo dela.

```mermaid
flowchart TB
    other["Outro módulo<br/>ex.: risk-engine"]

    subgraph mod["Módulo, ex.: market-data-lake"]
        api["api<br/>fachada pública: monta os casos de uso"]
        infra["infrastructure<br/>DuckDB, Postgres, Redis, providers"]
        app["application<br/>casos de uso"]
        domain["domain<br/>entidades, regras, ports (Protocol)"]
    end

    other -->|"só pode importar"| api
    other -.->|"proibido (contrato forbidden)"| infra
    api --> infra
    api --> app
    infra --> app
    infra --> domain
    app --> domain

    classDef boundary fill:#d3f9d8,stroke:#2b8a3e,color:#1b4332
    classDef inner fill:#f1f3f5,stroke:#495057,color:#212529
    class api boundary
    class infra,app,domain inner
    linkStyle 1 stroke:#c92a2a,color:#c92a2a
```

| Contrato do import-linter | Regra |
|---|---|
| `*-layers` (um por módulo) | `api` → `infrastructure` → `application` → `domain`; nunca no sentido inverso |
| `feature-store-so-usa-market-data-lake-api` | `feature_store` importa só `market_data_lake.api` |
| `risk-engine-so-usa-market-data-lake-api` | `risk_engine` importa só `market_data_lake.api` |
| `trading-api-layers` | `infrastructure` → `domain`; `application`/`api` entram com a orquestração (REQ-03) |

O schema de cada banco pertence ao módulo que o usa, com migrações e tabela
de versão próprias ([ADR-0012](../adr/0012-schema-migrations-alembic.md)).

## Fluxo de uma ordem em paper trading (MVP, REQ-03)

O gate de risco e o adapter simulado já existem; a orquestração no
`trading-api` é o que o REQ-03 constrói.

```mermaid
sequenceDiagram
    autonumber
    participant S as Estratégia
    participant T as trading-api<br/>(orquestração, REQ-03)
    participant R as risk_engine.api
    participant P as PostgreSQL
    participant B as SimulatedBrokerAdapter

    S->>T: sinal (ticker, lado, quantidade em Decimal)
    T->>T: client_order_id já processado? (idempotência, ADR-0007)
    T->>R: evaluate_order(...)
    R->>P: circuit breaker, exposição, P&L do dia
    alt falha ao consultar (fail-closed, ADR-0006)
        R-->>T: BLOCK: provider_unavailable
        T-->>S: ordem não enviada
    else limite excedido ou breaker disparado
        R-->>T: BLOCK com motivo
        T-->>S: ordem não enviada
    else dentro dos limites
        R-->>T: ALLOW
        T->>B: submit_order(OrderRequest)
        B-->>T: OrderState (FILLED ou ACCEPTED)
        T->>R: record_fill(...) se houve execução
        R->>P: atualiza exposição e P&L
        T-->>S: estado da ordem
    end
```

Já implementado e testado: `evaluate_order`, `record_fill`, circuit breaker,
`BrokerAdapter` e `SimulatedBrokerAdapter`. Planejado no REQ-03: a
orquestração (passos 1–2 e as chamadas entre `trading-api` e `risk-engine`),
o ledger de idempotência persistido, o kill switch e a reconciliação
(ADR-0007).

## Como uma mudança chega ao `main`

```mermaid
flowchart LR
    branch["Branch curta"] --> pr["Pull request"]
    pr --> quality
    pr --> boundaries

    subgraph quality["Job quality"]
        direction TB
        q1["uv sync --locked"] --> q2["ruff check + format"]
        q2 --> q3["mypy"] --> q4["bandit + pip-audit"]
        q4 --> q5["migrações: upgrade, downgrade, upgrade"]
        q5 --> q6["pytest contra Postgres e Redis reais"]
    end

    subgraph boundaries["Job import-boundaries"]
        b1["lint-imports"]
    end

    quality --> gate{"Ruleset do main:<br/>2 checks verdes"}
    boundaries --> gate
    gate -->|merge| main["main"]
```

Push direto e force push no `main` são bloqueados pelo ruleset; o merge
exige os dois jobs verdes e não exige aprovação de outra pessoa (fluxo solo).

## Diferenças em relação aos diagramas C4

| Item | C4 (alvo) | Hoje |
|---|---|---|
| `market-data-lake` | Python + Airflow, ClickHouse/DuckDB | Python, DuckDB local; orquestração e ClickHouse ficam para produção (ADR-0003) |
| `trading-api` | FastAPI, PostgreSQL, Secrets Manager | Biblioteca Python (port + adapter simulado); sem HTTP nem credenciais neste ciclo |
| Kafka, Vector DB, Secrets Manager | Presentes | Ausentes: módulos que os usam são Won't no ciclo 1 |
