# Spec — backtesting-engine

**Status:** Aprovada em 2026-11-02 — pronta para implementação
**Fase:** 2 — Análise
**Requisito:** REQ-02 ([visão do ciclo 1](../../docs/vision.md))
**Depende de:** `feature_store.api` (médias móveis), `market_data_lake.api` (preço de execução), `risk_engine.api` (métricas)
**ADRs relevantes:** [ADR-0001](../../docs/adr/0001-modular-monolith-vs-microservices.md) (fronteiras), [ADR-0004](../../docs/adr/0004-money-precision-standard.md) (float interno, Decimal na fronteira), [ADR-0005](../../docs/adr/0005-custom-backtesting-engine.md) (motor próprio), [ADR-0010](../../docs/adr/0010-backtesting-validation-checklist.md) e [ADR-0013](../../docs/adr/0013-universo-declarado-no-checklist.md) (checklist de validação)

## Objetivo

Simular a estratégia de referência do ciclo 1 sobre um universo declarado e
produzir um **relatório cujo contrato inclui o checklist de validação** dos
ADRs 0010 e 0013. O relatório diz se a estratégia pode ir a paper trading;
ele não diz que a estratégia é boa.

## Escopo (v1 — ciclo 1)

### Estratégia de referência: cruzamento de médias móveis

- Parâmetros: janela curta `N` e janela longa `M`, com `2 ≤ N < M`.
- **Sinal em `t`:** `1` (comprado) se `SMA_N(t) > SMA_M(t)`, senão `0` (fora).
  Usa apenas fechamentos até `t`, lidos de `feature_store.api`.
- **Long-only:** sem venda a descoberto.
- **Aquecimento:** nenhum sinal antes de `M` barras disponíveis. O
  `feature-store` calcula a SMA com janela parcial no início da série; o
  backtest descarta esses valores em vez de operar com eles.

### Simulação de execução (separada do sinal, ADR-0005)

- Mudança de sinal em `t` executa na **abertura de `t+1`**
  (`market_data_lake.api`). O fechamento de `t` nunca executa uma decisão
  tomada em `t` (item 1 do checklist).
- **Slippage:** compra a `abertura × (1 + slippage)`, venda a
  `abertura × (1 − slippage)`.
- **Custo de transação:** proporcional ao valor negociado, em cada lado.
- **Quantidade:** número inteiro de ações (mercado fracionário), o maior que
  cabe no caixa após custo e slippage. Sobra fica em caixa, sem remuneração.
- **Alocação:** capital inicial dividido igualmente entre os ativos do
  universo; cada ativo é simulado de forma independente com sua fatia. A
  curva da carteira é a soma das curvas dos ativos. Sem rebalanceamento.
- **Fim do período:** posição aberta é marcada a mercado pelo último
  fechamento (sem venda forçada).
- Cálculo interno em `float64` (ADR-0004).

### Validação (contrato do relatório)

| Etapa | Regra |
|---|---|
| Out-of-sample | Os últimos `oos_fraction` do período (padrão 20%) ficam reservados. Nunca entram em seleção de parâmetro; são avaliados uma única vez, com os parâmetros finais |
| Walk-forward | O período restante é dividido em `k` dobras (padrão 3), com janela de treino crescente e teste logo após. Em cada dobra, `(N, M)` é escolhido na grade de parâmetros maximizando o Sharpe **só no treino** e avaliado no teste |
| Parâmetro final | Escolhido na grade com todo o período fora do out-of-sample |
| Robustez | `N` e `M` perturbados em ±10% e ±20% (arredondados, mantendo `N < M`). Aprovado se **todos** os vizinhos tiverem Sharpe ≥ `robustness_min_ratio` (padrão 0,5) × Sharpe do parâmetro final, no mesmo período |

Regras fixadas na implementação (fatia 2):

- **Cada período avaliado começa sem posição.** As médias usam o histórico
  anterior ao período (aquecimento), nunca dados posteriores ao seu fim.
- **Empate na seleção** fica com o primeiro parâmetro da grade
  (determinismo, critério 11).
- **Robustez com Sharpe base ≤ 0:** a proporção não se aplica; o resultado é
  "não aplicável" e o item 6 do checklist fica `não verificado`.
- Cada dobra guarda o resultado de treino que levou à escolha, para provar
  que só o treino foi usado.

As médias móveis vêm de `feature_store.api.compute_features_from_bars`
(mudança **aditiva** feita na fatia 1): o mesmo cálculo de
`get_training_features`, recebendo as barras em mãos. Assim o backtest usa a
definição de feature do treino sem reimplementá-la, e pode ser testado com
séries sintéticas.

Métricas de risco (Sharpe, Sortino, Calmar, VaR 95%, drawdown máximo) vêm do
`risk-engine`. Esta spec inclui uma mudança **aditiva** na `risk_engine.api`:
`compute_metrics_from_returns(returns, risk_free_rate=0.0) -> RiskMetrics`,
que expõe o caso de uso já existente. Métricas de operação (número de
operações, taxa de acerto, profit factor, custos totais) são calculadas aqui.

### Checklist de validação

Cada item tem um estado: `verificado`, `limitação declarada` (só o item 2,
ADR-0013), `não verificado` ou `falhou`, mais um texto de evidência.

| # | Item | Como o motor determina o estado |
|---|---|---|
| 1 | Sem look-ahead | `verificado` se o teste de truncamento passar: os sinais até `t` calculados com a série completa são iguais aos calculados com a série cortada em `t`, para cortes em pontos espaçados do período |
| 2 | Sem viés de sobrevivência | `verificado` se o universo for declarado point-in-time; `limitação declarada` se for universo fixo declarado (lista, critério de escolha e data da escolha); `não verificado` se não houver declaração |
| 3 | Custos e slippage | `verificado` se ambos forem > 0 e os custos totais forem > 0 quando houve operação; `falhou` se algum for zero |
| 4 | Walk-forward | `verificado` se as `k` dobras rodarem com dados suficientes; `não verificado` caso contrário |
| 5 | Out-of-sample | `verificado` se o período reservado tiver barras suficientes para ao menos uma operação possível (≥ `M` + 1 barras); `não verificado` caso contrário |
| 6 | Robustez de parâmetro | `verificado` ou `falhou` pela regra da tabela anterior |
| 7 | Preços ajustados | `verificado` só se o `market-data-lake` declarar a série como ajustada, com método. **Até o REQ-01, é sempre `não verificado`** — e o relatório fica inelegível para paper, como deve ser |

**Elegibilidade (ADR-0013):**
- `apto_para_paper`: todos os itens `verificado`, exceto o item 2, que pode
  ser `limitação declarada`.
- `apto_para_capital_real`: todos os 7 itens `verificado`. É condição
  necessária, não suficiente: o ADR-0008 ainda exige o período em paper.

## Fora de escopo (v1)

- Outras estratégias, venda a descoberto, alavancagem, intradiário.
- Rebalanceamento e alocação entre ativos (cabe ao `portfolio-optimizer`).
- Impostos (IR), dividendos como fluxo separado (o preço ajustado já os
  incorpora) e remuneração do caixa.
- Persistência de relatórios e exportação para dashboard (Should do ciclo).
- Universo point-in-time (Should do ciclo 2; investigação 0001).

## Modelo de domínio

- `UniverseDeclaration`: tickers, critério de escolha, data da escolha,
  `point_in_time` (bool).
- `MovingAverageParams`: `short_window`, `long_window`.
- `CostModel`: `cost_bps`, `slippage_bps` (por lado).
- `ValidationConfig`: `oos_fraction`, `walk_forward_folds`,
  `robustness_perturbations` (padrão `(0.1, 0.2)`), `robustness_min_ratio`,
  grade de parâmetros.
- `BacktestConfig`: universo, período (`start`, `end`), `initial_capital`
  (`Decimal`), `CostModel`, `ValidationConfig`.
- `Trade`: ticker, data de entrada e saída, quantidade, preços de execução,
  custos.
- `ChecklistItem`: número, nome, estado, evidência.
- `BacktestReport`: config, parâmetros finais, métricas no período
  in-sample e out-of-sample, resultados por dobra, grade de robustez,
  operações, checklist, `apto_para_paper`, `apto_para_capital_real`.
  Valores monetários do relatório (patrimônio final, custos totais) em
  `Decimal`, convertidos em **um único ponto** (ADR-0004).

## Contrato de API (`backtesting_engine.api`)

```python
def run_backtest(config: BacktestConfig) -> BacktestReport: ...
```

`backtesting_engine` importa apenas `feature_store.api`,
`market_data_lake.api` e `risk_engine.api` — nunca as camadas internas
desses módulos (contratos `forbidden` no import-linter).

## Valores padrão propostos

Declarados no relatório; mudá-los é decisão registrada, não ajuste fino.

| Parâmetro | Padrão | Motivo |
|---|---|---|
| Grade `N` | 5, 10, 20 | Curto prazo, de uma semana a um mês de pregões |
| Grade `M` | 50, 100, 200 | Médio e longo prazo usuais |
| `cost_bps` | 5 por lado | Ordem de grandeza de emolumentos B3 + corretagem baixa; conservador |
| `slippage_bps` | 5 por lado | Ações muito líquidas (PETR4, VALE3, ITUB4) |
| `oos_fraction` | 0,20 | Reserva usual sem sacrificar o treino |
| `walk_forward_folds` | 3 | Mínimo para variação entre dobras com histórico diário de anos |
| `robustness_min_ratio` | 0,5 | "Não destruir a performance" (ADR-0010) tornado verificável |

## Critérios de aceite

1. **Caso conhecido:** numa série sintética pequena, com resultado calculado
   à mão (operações, preços de execução, custos e patrimônio final), o motor
   reproduz o resultado com tolerância de `1e-9` (ADR-0005).
2. **Sem look-ahead:** alterar qualquer barra posterior a `t` não altera
   sinais nem posições até `t`.
3. **Execução:** mudança de sinal em `t` executa na abertura de `t+1`, com
   slippage e custo aplicados nos dois lados.
4. **Aquecimento:** nenhum sinal antes de `M` barras.
5. **Out-of-sample isolado:** alterar as barras do período reservado não
   altera os parâmetros escolhidos.
6. **Walk-forward:** em cada dobra, o parâmetro é escolhido só com dados do
   treino daquela dobra; os períodos de teste não se sobrepõem.
7. **Robustez:** vizinhos calculados e regra de aprovação aplicada conforme
   a tabela de validação.
8. **Checklist completo:** os 7 itens sempre presentes; `apto_para_paper` e
   `apto_para_capital_real` seguem o ADR-0013 em todas as combinações de
   estados (tabela-verdade testada).
9. **Item 7 honesto:** com a fonte atual (sem declaração de ajuste), o item 7
   é `não verificado` e o relatório não é apto para paper.
10. **Custo zero reprova:** `cost_bps = 0` ou `slippage_bps = 0` faz o item 3
    `falhou`.
11. **Determinismo:** mesma configuração e mesmos dados produzem relatório
    idêntico (QA-03 da visão).
12. **Fronteira Decimal:** valores monetários do relatório são `Decimal`; a
    conversão acontece num único ponto, testado com arredondamento conhecido.
13. **Fronteiras de módulo:** import-linter garante que só as três APIs
    públicas são importadas.
14. **Infra real:** testes de integração leem dados via APIs do
    `market-data-lake` e do `feature-store` contra DuckDB real, sem mock de
    armazenamento.

## Rastreabilidade

Caminhos relativos a `backtesting-engine/tests/`. Critério novo entra nesta
tabela no mesmo PR; critério sem teste automatizado precisa de justificativa.

| Critério | Evidência | Tipo |
|---|---|---|
| 1. Caso conhecido | `test_simulate_execution.py::test_caso_conhecido_reproduz_a_conta_feita_a_mao` (abertura ≠ fechamento do sinal, para distinguir os preços) | Unitário |
| 2. Sem look-ahead | `test_simulate_execution.py::test_dados_posteriores_a_t_nao_alteram_sinais_nem_patrimonio_ate_t` | Unitário |
| 3. Execução em `t+1` com custos | `test_simulate_execution.py::test_compra_executa_na_abertura_seguinte_nunca_no_fechamento_do_sinal`; `::test_venda_executa_na_abertura_seguinte_com_slippage_contra`; `::test_sinal_no_ultimo_dia_nao_executa_e_posicao_aberta_e_marcada_a_mercado` | Unitário |
| 4. Aquecimento | `test_signals.py::test_aquecimento_ignora_sma_de_janela_parcial` | Unitário |
| 5. Out-of-sample isolado | `test_validation.py::test_out_of_sample_nao_influencia_a_selecao`; `::test_planejamento_reserva_o_fim_e_dobras_nao_se_sobrepoem` | Integração (via APIs de feature-store e risk-engine) |
| 6. Walk-forward só com treino | `test_validation.py::test_cada_dobra_escolhe_so_com_o_proprio_treino`; `::test_planejamento_reserva_o_fim_e_dobras_nao_se_sobrepoem` | Integração |
| 7. Robustez | `test_validation.py::test_vizinhos_perturbam_n_e_m_em_10_e_20_por_cento`; `::test_vizinhos_invalidos_sao_descartados`; `::test_regra_de_robustez`; `::test_robustez_do_resultado_segue_a_regra_sobre_os_vizinhos_reportados` | Unitário + integração |
| 8 a 14 | Pendentes: fatia 3 (checklist, relatório e API) | — |

Testes validados com defeitos simulados: compra ou venda no fechamento do dia
do sinal (critérios 1 e 3); out-of-sample incluído na seleção final (5);
dobra escolhendo com todo o in-sample (6) — que sobreviveu à primeira versão
do teste, por coincidência do vencedor numa grade pequena, e motivou o
`train_result` em cada dobra; e `>` no lugar de `>=` na regra de robustez (7).
Todos quebram os testes.
