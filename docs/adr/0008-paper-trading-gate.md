# ADR-0008: Paper trading como gate formal e obrigatório antes de capital real

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** `trading-api`

## Contexto

No roadmap original (README raiz), paper trading aparecia implícito dentro
da Fase 4 — uma etapa que "faria sentido" fazer antes de operar com
dinheiro real, mas sem status formal nem critério de saída. Com capital
real envolvido, "rodar em paper por um tempo e depois trocar a chave" não é
um processo — é uma promessa vaga que qualquer prazo apertado vai atropelar.
Paper trading precisa ser um **ambiente**, não uma fase de calendário, com
critério de promoção explícito e verificável por código, não por confiança.

## Decisão

Paper trading é um **ambiente formal do `trading-api`**, não um script à
parte:
- **Mesmo código de produção** — a única diferença é o adapter de execução:
  `sandbox` (corretora oferece ambiente de teste) quando disponível, ou
  `simulado` (ordens não saem, mas todo o resto do fluxo — kill switch,
  idempotência, reconciliação contra um book de posições simulado,
  risk-engine gate — roda de verdade).
- **Toda estratégia nova, ou qualquer mudança relevante em estratégia já
  aprovada** (troca de parâmetro de risco, novo universo de ativos), volta
  para paper antes de tocar capital real — não existe "atualização direto
  em produção".

### Critério de promoção para capital real (por estratégia)

Uma estratégia só é liberada para capital real quando **todos** os
critérios abaixo são atendidos simultaneamente:

| Critério | Limiar mínimo |
|---|---|
| Tempo corrido em paper | ≥ 20 pregões consecutivos, sem gap de execução não planejado |
| Volume de operações | ≥ 30 ordens executadas (ou o suficiente para cobrir pelo menos 2 ciclos completos do horizonte da estratégia, o que for maior) |
| Aderência ao backtest | Sharpe realizado em paper ≥ 70% do Sharpe do backtest para o mesmo período; drawdown realizado não excede o drawdown do backtest em mais de 30% relativo |
| Incidentes de reconciliação (ADR-0007) | Zero divergências não explicadas entre posição simulada e esperada |
| Kill switch / circuit breaker (ADR-0006/0007) | Testado manualmente ao menos uma vez em paper, com comportamento validado |

A promoção é um ato explícito (registro de decisão, não deploy automático)
— feito por quem tem autoridade de Portfolio Manager, com os números acima
anexados.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Paper trading como "fase" de calendário (ex: "2 semanas em paper") | Simples de comunicar | Sem critério de qualidade — passa o tempo mesmo se a estratégia performar mal | Tempo sozinho não prova nada sobre a estratégia |
| Promoção automática quando métricas batem o limiar | Remove atrito humano | Remove também o único checkpoint de julgamento humano antes de dinheiro real | Decisão de risco financeiro não deve ser 100% automática nesta fase |
| Código de paper trading separado do de produção | Isolamento total | Diverge do que realmente vai rodar com capital real — testa o código errado | Anula o propósito de paper trading (validar o sistema real) |

## Consequências

- **Positivas:** existe um critério auditável e replicável para "podemos
  arriscar dinheiro real nesta estratégia" — não depende de opinião no
  calendário.
- **Negativas / trade-offs aceitos:** estratégias com horizonte muito longo
  (ex: rebalanceamento mensal) podem levar meses para acumular volume de
  operações suficiente — aceito, porque é exatamente o tempo necessário
  para validar essas estratégias de verdade.
- **Impacto em outros módulos:** `backtesting-engine` precisa produzir os
  números de referência (Sharpe, drawdown) no mesmo formato usado para
  comparação em paper (ver [ADR-0010](0010-backtesting-validation-checklist.md));
  `trading-dashboard` precisa expor o progresso de cada estratégia contra
  esses critérios.
