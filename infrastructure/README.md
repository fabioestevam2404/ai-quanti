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
| PostgreSQL | 5432 | Auditoria de ingestão (`market-data-lake`) |
| Redis | 6379 | Cache hot-path (`feature-store`) |

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
