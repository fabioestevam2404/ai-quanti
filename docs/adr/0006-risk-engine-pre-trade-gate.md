# ADR-0006: risk-engine deixa de ser só análise pós-fato e vira gate pré-trade

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** `risk-engine`, `trading-api`

## Contexto

O design original do `risk-engine` (C2/C3) era puramente analítico: calcula
Sharpe, Sortino, Calmar, VaR e drawdown a partir de dados históricos, para
avaliação de estratégia. Isso é suficiente enquanto tudo roda em backtest ou
paper trading — nenhuma métrica calculada *depois* de uma perda evita a
perda.

Com capital real em jogo, isso deixa de ser aceitável: uma estratégia pode
violar limite de exposição ou acumular perda diária excessiva entre o
momento em que o sinal é gerado e o momento em que alguém olha o dashboard.
`risk-engine` precisa participar do caminho síncrono de envio de ordem, não
só do caminho assíncrono de relatório.

## Decisão

`risk-engine` passa a ter **dois modos**, não um:

1. **Modo analítico (mantido)** — cálculo de métricas para
   `trading-dashboard`/`investment-copilot`: Sharpe, Sortino, Calmar, VaR,
   drawdown. Assíncrono, sem impacto em latência de ordem.
2. **Modo gate pré-trade (novo)** — chamado de forma **síncrona** por
   `trading-api` **antes** de qualquer ordem ser roteada para a corretora.
   Verifica, na ordem de execução:
   - **Limite de exposição por ativo** (e por setor, quando aplicável) —
     rejeita ordem que levaria a posição acima do limite configurado.
   - **Limite de perda diária** (circuit breaker) — se o P&L realizado +
     não-realizado do dia ultrapassar o limite, `risk-engine` retorna
     bloqueio para **todas** as novas ordens até reset manual ou próximo
     pregão.
   - Resultado é binário e determinístico: `ALLOW` ou `BLOCK` com motivo —
     nunca "warning silencioso".

`trading-api` **nunca envia ordem para a corretora sem consultar o gate**.
Isso é reforçado também no lado do `trading-api` como última linha de
defesa (ver [ADR-0007](0007-trading-api-safety-layers.md), position limits
hard-coded).

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Manter risk-engine só analítico; checagem de limite embutida direto no `trading-api` | Menos um ponto de falha síncrono | Duplica lógica de risco em dois módulos; risco de regra desalinhada entre análise e execução | Fonte única da verdade para "o que é um limite" importa mais que simplicidade |
| Gate assíncrono (best-effort, checagem depois de enviar) | Não adiciona latência à ordem | Não é gate — é alarme depois do fato, exatamente o problema que motivou esta ADR | Não resolve o problema real |

## Consequências

- **Positivas:** um único módulo é a fonte da verdade sobre limites de
  risco, usado tanto para análise quanto para bloqueio — sem regra
  duplicada e divergente.
- **Negativas / trade-offs aceitos:** `risk-engine` passa a ser uma
  dependência síncrona no caminho crítico de latência de `trading-api` —
  precisa de SLA de resposta definido (ex: p99 < 50ms) e circuit breaker
  próprio: se `risk-engine` não responder, `trading-api` deve **bloquear
  por padrão** (fail-closed), nunca deixar passar por timeout.
- **Impacto em outros módulos:** `trading-api` ganha uma chamada síncrona
  obrigatória no fluxo de ordem (ver ADR-0007); `trading-dashboard` precisa
  expor o estado do circuit breaker (ativo/inativo) de forma visível para o
  Portfolio Manager.
