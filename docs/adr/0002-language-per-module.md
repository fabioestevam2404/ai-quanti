# ADR-0002: Linguagem por módulo

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** Plataforma inteira

## Contexto

Quant trading "de livro" frequentemente cita C++/Rust para partes de baixa
latência (HFT, market making). Mas esta plataforma, no estágio atual, não
tem como objetivo HFT — o objetivo é demonstrar domínio de arquitetura,
dados e ML aplicados a mercado financeiro. Introduzir uma segunda linguagem
prematuramente multiplica a superfície de manutenção sem benefício real de
performance neste estágio.

## Decisão

- **Python é a linguagem padrão de toda a plataforma**, incluindo
  `backtesting-engine`, `risk-engine`, `ml-predictions`, `feature-store`,
  `market-data-lake`, `streaming-engine`, `trading-api` (FastAPI) e
  `investment-copilot`.
- **Rust/C++ ficam reservados para uma extensão futura e isolada**, apenas
  se um profiling real apontar um gargalo específico (ex: núcleo de
  simulação do `backtesting-engine` rodando milhões de barras) — nunca por
  antecipação. Se isso acontecer, vira um novo ADR com o profiling anexado.
- **`trading-dashboard` usa Next.js/TypeScript** (consistente com o
  frontend do Norte).

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| C++ no `backtesting-engine` desde o início | Performance máxima | Complexidade de build, debugging e testes muito maior; ninguém validou que é o gargalo real | Otimização prematura |
| Julia para o núcleo numérico | Boa performance com sintaxe alto nível | Ecossistema menor, mais um runtime para operar/documentar | Não compensa frente ao ganho de simplicidade do Python |

## Consequências

- **Positivas:** um único ecossistema de tooling (ruff, mypy, bandit,
  pytest, pip-audit) para toda a plataforma — mesmo pipeline de CI do Norte,
  reaproveitável quase sem alteração.
- **Negativas / trade-offs aceitos:** performance bruta de simulação será
  menor que uma engine em C++; mitigado com vetorização (NumPy/Pandas) e,
  se necessário, `numba`/`polars` antes de considerar outra linguagem.
- **Impacto em outros módulos:** define o stack de CI/CD (ADR futuro) e a
  base de bibliotecas Python padrão da plataforma.
