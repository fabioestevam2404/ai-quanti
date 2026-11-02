# Investigação 0002: fonte de proventos para ajustar o COTAHIST

**Data:** 2026-11-02
**Motivação:** a decisão 4 da [visão](../vision.md#decisões-do-ciclo) escolheu
o COTAHIST da B3, que traz preços **sem ajuste**. O item 7 do checklist
([ADR-0013](../adr/0013-universo-declarado-no-checklist.md)) exige preço
ajustado com método declarado e verificado. Sem isso, nenhum backtest fica
apto para paper.
**Decide:** de onde vêm os eventos (desdobramento, grupamento, bonificação,
dividendos, JCP) do REQ-01, e como garantir que estão certos.

## Perguntas

1. Existe fonte oficial e gratuita, com histórico, dos eventos de capital e
   dos proventos em dinheiro de PETR4, VALE3 e ITUB4?
2. Ela informa o que o ajuste precisa: data ex, valor por ação ou fator?
3. Os eventos batem com os saltos reais de preço no COTAHIST?

## Achados

Todos verificados com chamadas e downloads reais nesta data, salvo indicação.

### 1. CVM, Formulário de Referência: não serve

O FRE tinha as tabelas `capital_social_desdobramento` e
`distribuicao_dividendos` ([CVM dados abertos](https://dados.cvm.gov.br/dataset/cia_aberta-doc-fre)).
Baixados os anos 2021, 2022, 2023 e 2025:

- **Cobertura rasa:** cada formulário traz só eventos recentes. Para as três
  empresas, 2021 e 2022 juntos têm **um** evento (Itaú, 2018). O
  desdobramento da PETR4 de 2008 não aparece.
- **Data errada para ajuste:** só `Data_Aprovacao`; o ajuste precisa da data ex.
- **Dividendos agregados** por exercício (`Dividendo_Distribuido_Total`),
  sem data ex nem valor por ação.
- **Descontinuado:** 2023 tem 2 linhas de desdobramento no total; o FRE de
  2025 (36 arquivos) não tem nenhuma das duas tabelas.

Os comunicados eventuais (IPE, [CVM](https://dados.cvm.gov.br/dataset/cia_aberta-doc-ipe))
são documentos, não dados estruturados — descartados para uso automático.

### 2. B3, portal de empresas listadas: tem o que o ajuste precisa

Duas rotas públicas do `listedCompaniesProxy`, **não documentadas**
oficialmente; o portal de desenvolvedores da B3 diz que suas APIs são para
clientes B2B ([B3](https://developers.b3.com.br/apis/api-listados); uso
relatado por terceiros em [Medium](https://fabiomt.medium.com/como-obter-o-hist%C3%B3rico-de-dividendos-e-outros-proventos-com-python-direto-do-site-da-b3-90a507623418)
e [GitHub](https://github.com/guilhermegor/filings-b3/issues/248)).

| Rota | Conteúdo | PETR4 | VALE3 | ITUB4 |
|---|---|---|---|---|
| `GetListedCashDividends` | Dividendos e JCP, por evento: classe (ON/PN), valor por ação, data-com, fechamento na data-com e `corporateActionPrice` | 343 eventos (2007–2026) | 152 | 960 |
| `GetListedSupplementCompany` → `stockDividends` | Desdobramento, grupamento, bonificação, cisão: ISIN, `factor`, data-com | 6 (desde 1994) | 6 (desde 1996) | 10 |

- `corporateActionPrice` é o percentual de ajuste calculado pela B3:
  0,67407131 ÷ 49,34 = 1,3662%, igual ao informado.
- Data ex = pregão seguinte à data-com (`lastDatePriorEx`).

### 3. Confronto com o COTAHIST: a fonte da B3 está incompleta

Preços de PETR4 no mercado à vista (`TPMERC=010`), normalizados por `FATCOT`:

| Evento (B3) | Último fechamento com direito | Primeira abertura ex | Razão | Esperado |
|---|---|---|---|---|
| Desdobramento, 25/04/2008, `factor=100` | R$ 84,30 | R$ 42,58 | 0,505 | 1/(1+100%) = 0,5 ✅ |
| Grupamento, 21/06/2000, `factor=0,01` | R$ 0,515 | R$ 51,60 | 100,2 | 1/0,01 = 100 ✅ |
| **Nenhum evento na B3**, 31/08/2005 | R$ 130,00 | R$ 32,51 | **0,250** | — ❌ |

- **Sentido do `factor` depende do tipo:** em desdobramento e bonificação é o
  percentual de ações novas (multiplicador `1 + f/100`); em grupamento é o
  multiplicador direto (`f`). Confirmado pelos saltos acima.
- **Evento ausente:** houve um desdobramento de 1 para 4 em 01/09/2005
  (também citado por [AlphaSpread](https://www.alphaspread.com/security/bovespa/petr4/investor-returns/i/stock-splits)),
  que a B3 não lista. Sem conferência, o backtest veria uma queda de 75% num
  dia e o item 7 seria "verificado" sem ser verdade.
- **`FATCOT` é obrigatório:** no grupamento de 2000, a cotação passou de lote
  de mil para unitária no mesmo dia; o preço bruto foi de 515 para 51,6.
  Ignorar o campo mostraria uma queda de 90% inexistente.

### 4. ITUB4: cisão em 2021

`stockDividends` do Itaú tem `CIS RED CAP` (cisão com redução de capital) em
01/10/2021 — a separação da participação na XP. O ajuste de uma cisão depende
do valor do ativo entregue, que a rota não informa: não é um fator simples.

**Fator encontrado (decisão A, 2026-11-02):** a B3 informou ajuste de
−17,54% na ITUB4 a partir de 04/10/2021, com preço de referência de abertura
de R$ 24,4654999
([InfoMoney](https://www.infomoney.com.br/mercados/bdrs-da-xp-passarao-a-ser-negociados-na-b3-nesta-2a-apos-incorporacao-da-xpart-acoes-do-itau-passam-por-reajuste/);
[Suno](https://www.suno.com.br/noticias/acoes-itau-itub4-reajuste-bdr-xp-xpbr31/)).
Conferido no COTAHIST de 2021: fechamento de 01/10 (R$ 29,67) × 0,8246 =
R$ 24,4659, contra os R$ 24,4655 de referência. A abertura real foi R$ 24,75
(razão 0,834): o salto observado mistura o evento com o movimento do dia, e a
reconciliação precisa de tolerância.

## Conclusões

1. **A B3 é a única fonte gratuita com o detalhe necessário** (evento a
   evento, com data e fator), mas por rotas não documentadas.
2. **Nenhuma fonte de eventos é confiável sozinha.** A da B3 omite o
   desdobramento de 2005 da PETR4. O ajuste só é verificável se cada evento
   for confrontado com o salto real de preço no COTAHIST, e se saltos sem
   evento forem detectados.
3. **O REQ-01 tem duas partes de natureza diferente:** eventos de capital
   (raros, criam saltos grandes, verificáveis pelo preço) e proventos em
   dinheiro (frequentes, pequenos, verificáveis pelo percentual da B3).
4. **Cisão não se ajusta com fator simples:** ITUB4 exige decisão própria.

## Recomendações

| # | Recomendação | Onde |
|---|---|---|
| R1 | Fonte primária: rotas da B3, com resposta bruta guardada como **snapshot versionado** (data da coleta), para reprodutibilidade e para não depender de a rota continuar no ar | Spec do REQ-01 |
| R2 | **Reconciliação obrigatória** contra o COTAHIST: cada evento de capital precisa produzir o salto esperado (tolerância declarada), e todo salto de abertura acima de um limiar sem evento correspondente é reportado | Spec do REQ-01 |
| R3 | **Tabela de correções curada e versionada** no repositório, com fonte (fato relevante, comunicado) por linha, para eventos ausentes ou errados — começando pelo desdobramento de 2005 da PETR4 | Spec do REQ-01 |
| R4 | O `market-data-lake` declara, por série: ajustada ou não, método e resultado da reconciliação. O item 7 só fica `verificado` com reconciliação sem pendências | Spec do REQ-01; item 7 do checklist |
| R5 | Decidir o tratamento da cisão de 2021 da ITUB4 (ver abaixo). **Decidido em 2026-11-02: opção A**, com o fator da B3 na tabela de correções | `vision.md`, decisão 2 |

**R1 a R4 aceitas em 2026-11-02**, incluindo o uso das rotas não documentadas
da B3, com os dados guardados localmente.

### Opções para a ITUB4

| Opção | Prós | Contras |
|---|---|---|
| A. Manter ITUB4 e ajustar a cisão com o fator oficial divulgado pelo Itaú, pela tabela curada (R3) | Universo da decisão 2 intacto | Depende de achar o documento oficial com o fator; tipo de evento a mais para implementar |
| B. Trocar ITUB4 por outra ação líquida sem eventos complexos no período | Ajuste mais simples | Muda a decisão 2; a nova ação também precisa da investigação de eventos |
| C. Começar o período do backtest depois de out/2021 | Nenhum ajuste de cisão | Cerca de 4 anos de histórico: pouco para M=200, walk-forward e out-of-sample |

## Limitações desta investigação

- Confronto com o COTAHIST feito para PETR4 em três eventos; VALE3 e ITUB4
  ficam para a reconciliação automática do REQ-01 (R2).
- As rotas da B3 podem mudar sem aviso; a mitigação é o snapshot (R1).
- Termos de uso das rotas não documentadas não foram confirmados para uso
  não comercial; o uso aqui é de estudo, com dados guardados localmente.
