# ADR-0001: Monólito modular vs. Microsserviços

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** Plataforma inteira

## Contexto

A plataforma tem 14 capacidades candidatas a "módulo" (data lake, streaming,
backtesting, risco, ML, RL, RAG, copiloto, API, dashboard, otimizador,
infraestrutura, monitoramento, notebooks). Microsserviços "de verdade" (deploy
independente, banco por serviço, comunicação só por rede) trazem overhead de
operação — service mesh, contratos de API versionados, tracing distribuído —
que não se paga sem uma equipe dedicada a isso e sem carga real de produção.

Por outro lado, um monólito único sem fronteiras internas tende a virar um
emaranhado onde `backtesting-engine` importa direto de `ml-predictions`, que
importa de `trading-api`, e nada pode evoluir isolado.

## Decisão

Adotar um **monólito modular** (também chamado *modular monolith*): um único
processo/deploy por ambiente, mas com **cada módulo como um pacote Python
isolado**, com fronteiras de Clean Architecture (`domain/application/
infrastructure/api`) e **sem imports cruzados de camadas internas** — apenas
via interfaces explícitas expostas por cada módulo (ex: `feature_store.api`).

Os módulos que já têm perfil de serviço de rede desde o início — porque
falam com o mundo externo ou têm ciclo de deploy naturalmente diferente —
rodam como processos separados desde já:
- `trading-api` (precisa de disponibilidade e latência isoladas da análise pesada)
- `streaming-engine` (processo de longa duração, consumo contínuo de Kafka)
- `trading-dashboard` (frontend, obviamente separado)

Todo o resto (`backtesting-engine`, `risk-engine`, `ml-predictions`,
`portfolio-optimizer`, `feature-store`) roda como bibliotecas dentro do
mesmo processo de "worker" analítico, orquestradas via Celery/Airflow,
seguindo o mesmo padrão de isolamento por usuário já validado no Norte
(Celery beat com falhas isoladas por usuário).

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Microsserviços completos (14 serviços) | Deploy e escala independentes | Overhead operacional enorme para um time de 1 pessoa; latência de rede entre módulos que precisam conversar muito (backtest ↔ feature-store) | Custo não se justifica no estágio atual |
| Monólito sem fronteiras internas | Simplicidade máxima no início | Acoplamento implícito, impossível de testar/avaliar módulos isoladamente, péssimo para portfólio técnico | Não demonstra arquitetura, só "funciona" |

## Consequências

- **Positivas:** cada módulo pode ser avaliado, testado e até extraído como
  repositório próprio no futuro sem reescrita, porque a fronteira já existe
  a nível de código.
- **Negativas / trade-offs aceitos:** é preciso disciplina para não furar as
  fronteiras "porque é mais rápido"; CI deve ter uma checagem de dependências
  entre módulos (ex: `import-linter`) para impedir isso automaticamente.
- **Impacto em outros módulos:** define a estrutura de pastas de todos os
  módulos analíticos (ADR-0002 detalha linguagem/stack por módulo).
