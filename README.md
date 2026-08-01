# Quant AI Platform

Plataforma modular de **Quantitative Trading** que integra Engenharia de Dados,
Machine Learning, IA Generativa e Engenharia de Software para pesquisa,
backtesting, gestão de risco e execução de estratégias quantitativas.

> Status geral: 🟡 **Fase 1-2** (market-data-lake, feature-store e risk-engine em implementação local/dev)

## Visão

Em vez de 14 projetos isolados, esta plataforma trata cada capacidade como um
**módulo com fronteira clara**, comunicando-se por contratos explícitos
(APIs internas / eventos), permitindo que cada peça evolua — e seja avaliada
tecnicamente — de forma independente, mas dentro de uma arquitetura coerente.

## Estrutura do repositório

```
quant-ai-platform/
│
├── docs/                    # C4, ADRs, decisões e documentação técnica
│   ├── architecture/c4/     # Diagramas de Contexto e Container (C4 Model)
│   └── adr/                 # Architecture Decision Records
│
├── market-data-lake/        # Ingestão e armazenamento de dados de mercado
├── streaming-engine/        # Pipeline de dados em tempo real (Kafka/streams)
├── feature-store/           # Engenharia de atributos para ML
├── backtesting-engine/      # Motor de simulação histórica de estratégias
├── portfolio-optimizer/     # Otimização de carteira (Markowitz, Black-Litterman etc.)
├── risk-engine/             # Métricas de risco (VaR, Sharpe, drawdown...)
├── ml-predictions/          # Modelos preditivos (XGBoost, LSTM, Transformers)
├── reinforcement-learning/  # Agentes de RL para execução/alocação
├── financial-rag/           # RAG sobre relatórios, filings e notícias financeiras
├── investment-copilot/      # Copiloto conversacional (LLM) para análise de investimentos
├── trading-api/             # API pública/interna de execução e consulta
├── trading-dashboard/       # Frontend (Next.js) de visualização e operação
├── infrastructure/          # Terraform, Kubernetes, IaC
├── monitoring/              # Observabilidade (métricas, logs, tracing, alertas)
└── notebooks/               # Pesquisa exploratória e prova de conceito
```

## Princípios de engenharia

Os mesmos princípios aplicados no desenvolvimento do Norte guiam esta plataforma:

- **Spec-Driven Development (SDD)** — cada módulo nasce de uma spec antes do código.
- **Clean Architecture** — domain / application / infrastructure / api em cada módulo.
- **ADRs obrigatórios** para toda decisão estrutural relevante.
- **Decimal, nunca float**, para qualquer cálculo financeiro (P&L, risco, alocação).
- **Testes contra infraestrutura real** (Postgres, ClickHouse, Redis) — não mocks.
- **Conventional Commits** e CI/CD (lint, type-check, security scan) desde o commit zero.
- **Observabilidade desde o dia 1** — sem "vamos adicionar logging depois".
- **Nenhuma ordem real sem gate de risco síncrono e paper trading aprovado**
  — `risk-engine` bloqueia antes de enviar, não só mede depois (ADR-0006);
  toda estratégia passa por paper trading com critério explícito de
  promoção antes de capital real (ADR-0008).
- **Credencial de execução nunca em texto plano** — secrets manager,
  rotação obrigatória, redação em qualquer log (ADR-0009).

## Roadmap por fases

| Fase | Módulos | Objetivo |
|---|---|---|
| 0 — Fundação | `docs/` (C4 + ADRs), CI/CD esqueleto | Definir arquitetura antes de codar |
| 1 — Dados | `market-data-lake`, `feature-store` | Base de dados confiável e versionada |
| 2 — Análise | `backtesting-engine`, `risk-engine` | Validar estratégias matematicamente (backtesting-engine com checklist de validação, ADR-0010; risk-engine com modo analítico + gate pré-trade, ADR-0006) |
| 3 — Inteligência | `ml-predictions`, `financial-rag`, `investment-copilot` | Camada de IA/ML |
| 4 — Produto | `trading-api`, `trading-dashboard`, `portfolio-optimizer` | Superfície de uso — `trading-api` só toca capital real após paper trading aprovado (ADR-0008), com kill switch, idempotência e reconciliação (ADR-0007) |
| 5 — Operação | `infrastructure`, `monitoring`, `reinforcement-learning` | Produção e experimentação avançada |

## Documentação

- [Diagrama de Contexto (C4)](docs/architecture/c4/c1-context.md)
- [Diagrama de Container (C4)](docs/architecture/c4/c2-container.md)
- [ADRs](docs/adr/README.md)
