# Relatório 0003: primeiro backtest com dados reais

**Data:** 2026-11-03
**Objetivo:** rodar o fluxo do MVP de ponta a ponta com dados reais — REQ-01
(preços ajustados e reconciliados) alimentando o REQ-02 (backtest com
checklist) — antes de começar o REQ-03 (paper trading).

## Como reproduzir

```powershell
# Caminhos isolados do ambiente de dev (opcional): MARKET_DATA_LAKE_DUCKDB_PATH,
# MARKET_DATA_LAKE_COTAHIST_DIR, MARKET_DATA_LAKE_B3_EVENTS_DIR, MARKET_DATA_LAKE_PG_DSN
uv run python backtesting-engine/scripts/run_mvp_backtest.py --refresh-events
```

| Parâmetro | Valor |
|---|---|
| Universo | PETR4, VALE3, ITUB4 (decisão 2 da visão; universo fixo declarado) |
| Período | 2010-01-04 a 2025-12-30 (3.967 pregões por ativo) |
| Preços | COTAHIST da B3, ajustados por proventos; eventos coletados na B3 em 2026-11-03 |
| Estratégia | Cruzamento de médias móveis; grade padrão da spec (N 5/10/20 × M 50/100/200) |
| Custos | 5 bps de custo + 5 bps de slippage por lado |
| Capital inicial | R$ 100.000,00, dividido igualmente entre os três ativos |
| Validação | Out-of-sample de 20%, walk-forward em 3 dobras, robustez ±10%/±20% |

## Achado: grupamento do Itaú em 2011

A primeira execução terminou com o item 7 `não verificado` por uma pendência:

> ITUB4, 2011-11-01 — evento de capital não explica o salto: razão observada
> 0,9594, fator esperado 99,9633.

A B3 lista um **grupamento 100:1** da ITUB4 com data-com em 31/10/2011, mas o
preço não teve salto (fechamento R$ 32,73 → abertura R$ 31,40). Em 2011 o Itaú
fez **grupamento 100:1 seguido de desdobramento 1:100 simultâneos** (AGE de
25/04/2011), com efeito líquido nulo; a B3 lista só o grupamento
([InfoMoney](https://www.infomoney.com.br/negocios/banco-central-aprova-grupamento-de-acoes-on-e-pn-do-itau-unibanco/);
[InfoMoney](https://www.infomoney.com.br/negocios/para-ajustar-a-base-acionaria-itau-unibanco-propoe-grupamento-e-desdobramento-simultaneo/)).

Sem a reconciliação, todos os preços da ITUB4 antes de novembro de 2011
seriam multiplicados por 100, sem nenhum aviso. Correção: linha nova na
tabela de correções (fator 1,0 na data ex 01/11/2011), com teste de
reconciliação sobre as linhas reais do COTAHIST de 2011.

**Impacto do evento errado no resultado** (mesmos dados, antes e depois):

| Métrica in-sample | Com o grupamento da B3 | Com a correção |
|---|---|---|
| Sharpe | 0,33 | 0,49 |
| Drawdown máximo | −60,5% | −32,8% |
| Parâmetro da 1ª dobra | N=5, M=50 | N=20, M=50 |
| Patrimônio final | R$ 185.148,70 | R$ 270.841,15 |

Um único evento errado mudou o drawdown pela metade e a seleção de parâmetro
— e o relatório ainda teria seis itens verificados.

## Resultado (com a correção)

| Período | Sharpe | Sortino | Calmar | Drawdown máx. | VaR 95% |
|---|---|---|---|---|---|
| In-sample (2010-01 a 2022-10) | 0,49 | 0,58 | 0,25 | −32,8% | 1,98% |
| Out-of-sample (2022-10 a 2025-12) | 0,44 | 0,57 | 0,21 | −22,8% | 1,32% |

- Parâmetros finais: N=10, M=50. Walk-forward: Sharpe nos testes −0,21,
  1,10 e 1,03.
- 129 operações fechadas no in-sample; taxa de acerto 43,4%; profit factor 1,79;
  custos de R$ 5.661,39.

| Item do checklist | Estado |
|---|---|
| 1. Sem look-ahead | verificado (15 cortes) |
| 2. Sem viés de sobrevivência | limitação declarada |
| 3. Custos e slippage | verificado |
| 4. Walk-forward | verificado |
| 5. Out-of-sample | verificado (794 pregões) |
| 6. Robustez de parâmetro | verificado (24 vizinhos) |
| 7. Preços ajustados | verificado (407 eventos, zero pendências) |

**Apto para paper: sim. Apto para capital real: não** (item 2 com limitação
declarada; e o ADR-0008 ainda exige o período em paper).

## Como ler este resultado

- **Prova o processo, não a estratégia.** O universo foi escolhido entre ações
  que existem hoje (item 2): o resultado pode estar inflado por viés de
  sobrevivência. Isso é o que o ADR-0013 permite levar a paper, e não a capital.
- Sharpe fora da amostra (0,44) próximo do in-sample (0,49) e robustez aprovada
  sugerem que o parâmetro não está sobreajustado à grade; a 1ª dobra negativa
  (−0,21) lembra que o desempenho varia muito entre períodos.
- Sem comparação com comprar e manter (buy and hold) nem com o CDI: fora do
  escopo da spec, e necessária antes de qualquer conclusão sobre a estratégia.

## Tempo de execução

| Etapa | Tempo |
|---|---|
| Ingestão por ativo (16 arquivos anuais; parte baixada na hora) | 69–93 s |
| Coleta dos eventos (3 empresas) | segundos |
| Backtest (grade de 9, 3 dobras, 24 vizinhos) | 154 s na 1ª execução; 99 s na 2ª |

Aceitável para o ciclo: não há motivo medido para vetorizar agora (ADR-0005).

## Próximos passos

1. REQ-03: orquestração de paper trading no `trading-api`, em replay, com esta
   estratégia (N=10, M=50) e este universo.
2. Should do ciclo: comparação com comprar e manter e com o CDI no relatório.
