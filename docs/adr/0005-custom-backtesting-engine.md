# ADR-0005: Motor de backtesting próprio vs. Backtrader/Zipline

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** `backtesting-engine`

## Contexto

Backtrader e Zipline são as opções mais citadas para backtesting em Python.
Na prática: Zipline está sem manutenção ativa há anos e sua API assume um
formato de dados (Quandl/bundles) que não se integra bem com o
`market-data-lake` desta plataforma. Backtrader é mais flexível, mas ainda
assim é uma dependência de terceiro cuja engine interna é uma caixa-preta —
o que é ruim tanto para debugar resultados quanto para portfólio técnico
(usar uma lib pronta demonstra menos do que construir o motor).

## Decisão

Construir um **motor de backtesting próprio**, vetorizado com pandas/NumPy,
com os seguintes componentes explícitos desde o início (spec antes de código,
conforme SDD):
- Simulador de execução com **custos de transação e slippage configuráveis**
  (backtest sem custo de transação é o erro mais comum e mais enganoso da área).
- Separação clara entre **geração de sinal** (estratégia) e **simulação de
  carteira** (execução), para permitir testar a mesma estratégia com
  diferentes regras de position sizing sem reescrever nada.
- Suporte a **walk-forward validation** desde o design inicial, não como
  adição posterior — é o que diferencia um backtest ingênuo (overfit ao
  histórico) de um processo validado de forma mais robusta.
- Output padronizado alimentando diretamente o `risk-engine` (Sharpe,
  Sortino, Calmar, drawdown, win rate, profit factor).

Bibliotecas como `backtrader` podem ser usadas em `notebooks/` para
prototipagem rápida e comparação de resultados, mas **não como dependência
de produção** do `backtesting-engine`.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Zipline | Usado historicamente por instituições | Sem manutenção ativa, integração de dados rígida | Risco de dependência morta |
| Backtrader | Mais flexível, comunidade ativa | Engine interna pouco transparente; dificulta customizar custo de transação/slippage de forma granular | Motor próprio demonstra mais domínio técnico e dá controle total |
| vectorbt | Muito rápido (vetorizado) | Modelo de programação menos intuitivo para lógica de estratégia complexa; menos didático para expor arquitetura em portfólio | Prioriza-se clareza arquitetural sobre performance bruta neste estágio |

## Consequências

- **Positivas:** controle total sobre a modelagem de custos, slippage e
  walk-forward; é a peça que mais demonstra rigor quantitativo no portfólio;
  reutilizável por `ml-predictions` e `reinforcement-learning` como ambiente
  de avaliação.
- **Negativas / trade-offs aceitos:** mais tempo de desenvolvimento do que
  usar uma lib pronta; precisa de testes extensivos com casos conhecidos
  (ex: reproduzir manualmente o resultado de uma estratégia simples de média
  móvel) para validar que a engine está correta antes de confiar nela.
- **Impacto em outros módulos:** `risk-engine`, `ml-predictions` e
  `reinforcement-learning` consomem a saída padronizada deste motor —
  formato de output vira contrato estável entre módulos.
