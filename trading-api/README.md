# trading-api

> Status: 📋 Planejado — aguardando spec (SDD) antes da implementação

API pública/interna: única porta de saída para a corretora/exchange; expõe estratégias, ordens e portfólio.

Com capital real em jogo, quatro camadas de segurança são obrigatórias
desde a primeira versão que toca uma corretora real — não incrementais,
não opcionais ([ADR-0007](../docs/adr/0007-trading-api-safety-layers.md)):

1. **Kill switch manual** — interrompe todo envio de ordem, estado persistido (não em memória).
2. **Idempotência de ordens** — `client_order_id` determinístico; retry nunca duplica ordem.
3. **Reconciliação periódica** — posição interna vs. posição real na corretora; divergência aciona kill switch.
4. **Position limits hard-coded** — última linha de defesa, independente do `risk-engine`.

Toda ordem passa pelo gate síncrono do `risk-engine`
([ADR-0006](../docs/adr/0006-risk-engine-pre-trade-gate.md)) antes de sair.
Credenciais de corretora vêm de um secrets manager, nunca de variável de
ambiente em texto plano ([ADR-0009](../docs/adr/0009-secrets-management.md)).

## Paper trading

Ambiente formal do próprio `trading-api` (mesmo código, adapter de execução
`sandbox` ou `simulado`), não uma fase de calendário — critério explícito
de promoção para capital real em
[ADR-0008](../docs/adr/0008-paper-trading-gate.md).

## Spec

_A ser escrita seguindo Spec-Driven Development, antes de qualquer código._
Nenhuma linha de código que envie ordem real deve existir antes desta spec
cobrir as quatro camadas de segurança acima e o ambiente de paper trading.

## Arquitetura interna

Segue Clean Architecture (`domain / application / infrastructure / api`),
consistente com os demais módulos da plataforma.

## ADRs relevantes

- [ADR-0006](../docs/adr/0006-risk-engine-pre-trade-gate.md) — gate síncrono de risco
- [ADR-0007](../docs/adr/0007-trading-api-safety-layers.md) — camadas de segurança
- [ADR-0008](../docs/adr/0008-paper-trading-gate.md) — paper trading como gate
- [ADR-0009](../docs/adr/0009-secrets-management.md) — gestão de segredos
- Ver [docs/adr](../docs/adr/README.md)
