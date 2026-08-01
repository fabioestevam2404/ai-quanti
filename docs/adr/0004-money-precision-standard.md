# ADR-0004: Padrão de precisão numérica (Decimal vs. float)

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** Plataforma inteira

## Contexto

No Norte, "Money as Decimal, nunca float" já é princípio estabelecido para
evitar erro de arredondamento em valores monetários. Aqui o risco é maior:
erro de ponto flutuante em cálculo de P&L acumulado, VaR ou peso de carteira
pode silenciosamente invalidar um backtest inteiro — e ninguém percebe até
comparar com um resultado esperado.

Ao mesmo tempo, bibliotecas de ML e cálculo numérico (NumPy, pandas,
scikit-learn, PyTorch) trabalham nativamente em `float64` — não é viável
nem desejável forçar `Decimal` dentro de um modelo de ML ou de uma matriz de
covariância.

## Decisão

Fronteira explícita de precisão, não regra única:

- **Camada de domínio financeiro** (`trading-api`, `risk-engine` nos pontos
  de P&L/exposição, `portfolio-optimizer` na alocação final em BRL/USD) usa
  **`Decimal`** — mesmo padrão do Norte.
- **Camada analítica/numérica** (`backtesting-engine` internamente,
  `ml-predictions`, `reinforcement-learning`, cálculo de indicadores e
  features) usa **`float64`** livremente — é o padrão do ecossistema
  científico e o erro de arredondamento em ponto flutuante é irrelevante
  frente à incerteza estatística do próprio modelo.
- **Toda conversão `float → Decimal` acontece em um único ponto de fronteira
  por módulo** (ex: ao persistir um resultado de backtest como registro
  auditável), nunca espalhada pelo código. Esse ponto é testado
  explicitamente com casos de arredondamento conhecidos.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| `Decimal` em tudo, inclusive modelos de ML | Consistência total | Inviável na prática — NumPy/PyTorch não operam em Decimal; performance inaceitável | Tecnicamente inviável |
| `float` em tudo, inclusive P&L e ordens | Simplicidade, performance | Risco real de erro de centavos acumulado em contas reais | Inaceitável para qualquer coisa que toque dinheiro real |

## Consequências

- **Positivas:** cada camada usa a representação certa para seu propósito;
  o risco fica confinado a um ponto de conversão testável.
- **Negativas / trade-offs aceitos:** exige disciplina de code review para
  garantir que ninguém "vaze" float para dentro da camada financeira.
- **Impacto em outros módulos:** `risk-engine` e `portfolio-optimizer` são
  os que mais cruzam essa fronteira (calculam em float, mas expõem resultado
  final em Decimal) — merecem teste de unidade dedicado à conversão.
