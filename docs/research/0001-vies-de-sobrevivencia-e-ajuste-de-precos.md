# Investigação 0001: viés de sobrevivência e ajuste de preços no universo B3

**Data:** 2026-11-02
**Motivação:** maior risco do ciclo 1 ([vision.md](../vision.md#riscos-e-hipóteses)).
O item 2 do [ADR-0010](../adr/0010-backtesting-validation-checklist.md) exige
universo sem viés de sobrevivência; "não verificado" bloqueia a entrada em
paper trading.
**Decide:** como a spec do `backtesting-engine` (REQ-02) e a ingestão real
(REQ-01) tratam universo e preços.

## Perguntas

1. A Alpha Vantage oferece ativos deslistados da B3 e seus preços?
2. Existe fonte de preços da B3 que inclua ativos que deixaram a bolsa?
3. Existe a composição histórica do Ibovespa (universo point-in-time)?
4. Os preços que a plataforma ingere hoje servem para backtest?

## Achados

### 1. Alpha Vantage não resolve o viés de sobrevivência

- O endpoint `LISTING_STATUS` (ativos ativos e deslistados por data) é
  documentado para ações e ETFs **dos EUA**; não há indicação de cobertura da
  B3 ([documentação](https://www.alphavantage.co/documentation/);
  [Macroption](https://www.macroption.com/alpha-vantage-delisted-stocks/)).
- Mesmo para os EUA, há relato de que o endpoint lista o símbolo deslistado,
  mas o histórico de preços dele não é servido
  ([issue](https://github.com/l3a0/quantitative-trading/issues/303), não verificado).
- O formato de símbolo da B3 (sufixo `.SAO`) **não foi confirmado** nas
  fontes; precisa de chamada de teste com a chave.

### 2. B3 COTAHIST: fonte oficial que inclui ativos deslistados

- As séries históricas oficiais da B3 (COTAHIST) trazem, por ano, as
  cotações de **todos os papéis negociados naquele ano**, desde 1986, em
  arquivos anuais, mensais e diários de layout fixo
  ([layout oficial](https://www.b3.com.br/data/files/C8/F3/08/B4/297BE410F816C9E492D828A8/SeriesHistoricas_Layout.pdf);
  [b3-fetcher](https://github.com/Quantilica/b3-fetcher);
  [rb3](https://docs.ropensci.org/rb3/)).
- Como cada arquivo registra o que foi negociado no ano, um ativo deslistado
  depois continua presente nos anos em que negociou: a fonte de **preços** é
  livre de sobrevivência.
- Os preços **não são ajustados** por proventos
  ([b3-fetcher](https://github.com/Quantilica/b3-fetcher)).
- A B3 também publica a lista de empresas com listagem cancelada
  ([B3](https://sistemaswebb3-listados.b3.com.br/canceledCompaniesPage/canceled-companies?language=pt-br)).

### 3. Universo point-in-time: possível, mas trabalhoso

- A carteira do Ibovespa é rebalanceada a cada quatro meses (janeiro, maio
  e setembro) e a B3 publica a carteira vigente para download
  ([B3](https://bvmf.bmfbovespa.com.br/indices/ResumoIndice.aspx?Indice=Ibovespa&Idioma=pt-br)).
- **Não foi confirmado** um download oficial em lote das carteiras
  anteriores; há projetos de terceiros que capturam a carteira ao longo do
  tempo ([royopa/ibovespa-carteira-teorica](https://github.com/royopa/ibovespa-carteira-teorica)),
  sem garantia de cobertura histórica completa.

### 4. Os preços ingeridos hoje não servem para backtest — achado novo

- O provider atual usa `TIME_SERIES_DAILY`, que devolve preços **sem ajuste
  por proventos**; a série ajustada é outra função
  (`TIME_SERIES_DAILY_ADJUSTED`), apontada como premium em uma fonte
  ([Airbyte](https://docs.airbyte.com/integrations/sources/alpha-vantage), a confirmar).
- Sem ajuste, desdobramentos e grupamentos aparecem como saltos de preço, e
  dividendos somem do retorno. Um cruzamento de médias móveis gera sinais
  falsos nesses saltos e o backtest mede o retorno errado
  ([PUC-Rio](https://www.maxwell.vrac.puc-rio.br/16807/16807_6.PDF);
  [FMP](https://site.financialmodelingprep.com/insights/enterprise/how-corporate-actions-distort-backtests-and-how-to-correct-for-them)).
- Série ajustada também tem armadilha: somar dividendos a um preço que já os
  incorpora conta o provento duas vezes
  ([brapi](https://brapi.dev/blog/preco-ajustado-acoes-dividendos-splits-b3)).
- O checklist do ADR-0010 não tem item explícito para ajuste de preços.

## Conclusões

1. **Para o universo do MVP (PETR4, VALE3, ITUB4), nenhuma fonte elimina o
   viés.** O viés não está nos preços, está na **escolha**: são ações que
   sobreviveram até hoje. Sem universo point-in-time, o item 2 do ADR-0010
   fica "não verificado" — e, pela regra atual, isso bloqueia o paper trading
   do MVP.
2. **Um universo sem viés é viável num ciclo futuro:** COTAHIST (preços
   incluindo deslistados) + carteiras históricas do Ibovespa (universo por
   data) + proventos para ajuste. É trabalho de dados maior que o MVP.
3. **Ajuste por proventos é pré-requisito do REQ-01**, independente do viés:
   backtest sobre preço bruto mede retorno errado mesmo com universo perfeito.

## Recomendações

| # | Recomendação | Onde |
|---|---|---|
| R1 | Separar, no item 2 do ADR-0010, "verificado" de "**limitação declarada**": universo fixo, escolhido antes do backtest e registrado no relatório, permite **paper trading** (sem capital), mas continua bloqueando a promoção a **capital real** (ADR-0008) | [ADR-0013](../adr/0013-universo-declarado-no-checklist.md) (proposto) |
| R2 | Acrescentar ao checklist do ADR-0010 a exigência de **preços ajustados por proventos**, com método declarado e verificação em data de evento conhecida | ADR-0013 |
| R3 | REQ-01 decide a fonte de preço ajustado: Alpha Vantage ajustado (se disponível no plano gratuito) ou COTAHIST + ajuste próprio. Validar com uma chamada de teste antes da spec do REQ-01 | Spec do REQ-01 |
| R4 | Universo point-in-time (COTAHIST + carteiras do Ibovespa) entra como **Should do ciclo 2**, pré-requisito para capital real | `vision.md` (revisão do ciclo) |

## Limitações desta investigação

- Baseada em documentação e fontes secundárias; nenhuma chamada real à
  Alpha Vantage (sem chave) nem download do COTAHIST foi feito.
- Itens marcados "a confirmar" ou "não verificado" acima precisam de teste
  prático antes de virar requisito.
