# ADR-0010: Checklist de validação (overfitting/look-ahead bias) como contrato do backtesting-engine

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** `backtesting-engine`
**Estende:** [ADR-0005](0005-custom-backtesting-engine.md)

## Contexto

ADR-0005 já definiu custos de transação, slippage e walk-forward validation
como parte do design do motor. O que faltava formalizar: **nada sai do
`backtesting-engine` rumo a paper trading sem passar por um checklist de
validação explícito.** Estratégia com resultado bonito em backtest e furada
por look-ahead bias (usar informação que não existiria no momento da
decisão) ou viés de sobrevivência (universo de teste só com ativos que
"sobreviveram" até hoje) é, de longe, a causa mais comum de perda real de
dinheiro em quant — mais comum que erro de execução ou bug de infra. Até
aqui isso era "boa prática" implícita; precisa virar gate obrigatório,
verificável, não deixado à disciplina de quem escreveu a estratégia.

## Decisão

Nenhuma estratégia avança de `backtesting-engine` para paper trading
(ADR-0008) sem que o relatório de backtest declare, explicitamente,
resposta a cada item abaixo — "não verificado" bloqueia a promoção tanto
quanto "falhou":

1. **Sem look-ahead bias**: a simulação usa, em cada barra `t`, apenas
   dados disponíveis até `t` (preço de fechamento de `t` não pode informar
   decisão tomada *em* `t`; indicadores derivados de dados revisados
   posteriormente — ex: PIB, resultado trimestral — usam a data de
   *publicação*, não a data de referência do dado).
2. **Sem viés de sobrevivência**: o universo de ativos testado inclui
   ativos que saíram do índice/faliram/foram deslistados no período —
   testar só com o que "sobreviveu" até hoje infla artificialmente o
   resultado.
3. **Custos de transação e slippage habilitados** (já exigido por
   ADR-0005) — resultado sem custo não é aceito como validação, mesmo como
   primeira aproximação.
4. **Walk-forward validation executada** (já exigido por ADR-0005) — não
   apenas backtest de janela única sobre todo o histórico.
5. **Teste out-of-sample**: parte do histórico é reservada e nunca usada
   para calibrar parâmetro nenhum da estratégia — só para validação final.
6. **Robustez a perturbação de parâmetro**: variar os parâmetros da
   estratégia em ±10–20% não deve destruir a performance — se destruir, é
   sinal de overfitting aos parâmetros exatos do backtest original.

O relatório de backtest (`backtesting-engine.api`) expõe esses seis campos
como parte do contrato de saída — não como texto livre em um relatório à
parte. `trading-api`/processo de promoção (ADR-0008) recusa uma estratégia
cujo relatório não tenha os seis itens preenchidos.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Checklist como documentação/boa prática (não no contrato de código) | Mais rápido de implementar | Depende de disciplina — exatamente o modo de falha que motivou esta ADR | Não resolve o problema real |
| Validação automática 100% (sem revisão humana) | Remove atrito | Alguns itens (ex: "esse indicador usa data de publicação correta?") exigem julgamento de domínio, não só código | Nem todo item é mecanicamente verificável hoje — aceitar isso é mais honesto que fingir automação completa |
| Aplicar o checklist só em estratégias "grandes" (capital alto) | Menos atrito para experimentos pequenos | Perda por overfitting não escala com o tamanho inicial da posição — estratégia pequena e furada ainda é dinheiro real perdido | Gate se aplica a qualquer estratégia que for para paper trading, sem exceção por tamanho |

## Consequências

- **Positivas:** overfitting e look-ahead bias — a causa mais comum de
  perda real citada na literatura de quant — passam a ter um ponto de
  verificação obrigatório e auditável antes de qualquer capital (mesmo
  simulado em paper) ser comprometido.
- **Negativas / trade-offs aceitos:** desacelera a promoção de estratégias
  novas — aceito deliberadamente, é o objetivo desta ADR.
- **Impacto em outros módulos:** `backtesting-engine.api` precisa expor
  esses seis campos como parte do contrato estável já previsto no C3
  ("Recomendações de arquitetura"); [ADR-0008](0008-paper-trading-gate.md)
  passa a exigir esse relatório como pré-condição de entrada em paper, não
  só de saída para capital real.
