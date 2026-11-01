# infrastructure

> Status: 🟡 Parcial — ambiente local (Docker Compose) disponível; Terraform/Kubernetes ainda planejados

Infraestrutura como código (Terraform), Kubernetes, Docker Compose para ambiente local.

## Ambiente local

[`docker-compose.local.yml`](docker-compose.local.yml) sobe a infra mínima
necessária para `market-data-lake` e `feature-store` (Fase 1, ADR-0003):

```
docker compose -f infrastructure/docker-compose.local.yml up -d
```

| Serviço | Porta | Uso |
|---|---|---|
| PostgreSQL | 5432 | Auditoria de ingestão (`market-data-lake`), ledger e circuit breaker (`risk-engine`) |
| Redis | 6379 | Cache hot-path (`feature-store`) |

Variáveis de configuração estão em [`.env.example`](../.env.example) na raiz.

### Porta já ocupada (ex.: PostgreSQL nativo no Windows)

Se outro Postgres já escuta em 5432 no host, o container sobe sem publicar a
porta e `localhost:5432` cai no Postgres nativo — o sintoma é
`password authentication failed for user "quant"`. Publique o container em
outra porta e aponte os DSNs para ela:

```
$env:QUANT_PG_PORT = "5433"
docker compose -f infrastructure/docker-compose.local.yml up -d
$env:QUANT_TEST_PG_DSN = "postgresql://quant:quant@localhost:5433/quant_platform_test"
```

(`MARKET_DATA_LAKE_PG_DSN`/`RISK_ENGINE_PG_DSN` também, se for rodar os
módulos em dev.) `QUANT_REDIS_PORT` faz o mesmo para o Redis.

### Banco de teste separado

A suíte de testes usa `quant_platform_test` (Postgres) e o db 15 (Redis) —
nunca `quant_platform`/db 0, porque os testes limpam tabelas. Os testes leem
apenas `QUANT_TEST_PG_DSN`/`QUANT_TEST_REDIS_URL` e recusam um banco cujo nome
não termine em `_test`.

O banco de teste é criado por [`postgres/init/`](postgres/init/) só quando o
volume é criado. Se o seu volume já existia antes disso:

```
docker compose -f infrastructure/docker-compose.local.yml exec postgres createdb -U quant quant_platform_test
```

Sem infra de pé, os testes de integração são pulados localmente; com
`QUANT_REQUIRE_INTEGRATION=1` (padrão no CI) eles falham.

ClickHouse e Kafka entram quando `streaming-engine`/produção real exigirem
(ADR-0003) — não fazem parte do ambiente local mínimo.

## Secrets manager (produção — antes de qualquer credencial de corretora)

[ADR-0009](../docs/adr/0009-secrets-management.md) exige AWS Secrets Manager
(ou Vault) para qualquer credencial capaz de executar ordens — nunca `.env`
ou secret nativo do Kubernetes sem criptografia. Isso é provisionado via
Terraform como parte do setup de produção, fora do `docker-compose.local.yml`
(que continua só com Postgres/Redis para dev, sem segredo de execução real).
Rotação automática (rotation Lambda / dynamic secrets) é parte do
provisionamento, não um passo manual posterior.

## Spec

_Terraform/Kubernetes: a ser escrita seguindo Spec-Driven Development, antes
de qualquer código de provisionamento em nuvem._

## Arquitetura interna

Este módulo é infraestrutura declarativa (IaC/Compose), não segue a
layering `domain/application/infrastructure/api` usada nos módulos Python
analíticos.

## ADRs relevantes

- [ADR-0003](../docs/adr/0003-database-strategy.md) — estratégia de banco de dados
- [ADR-0009](../docs/adr/0009-secrets-management.md) — secrets manager para credenciais de corretora
- Ver [docs/adr](../docs/adr/README.md)
