# Spec — market-data-lake

**Status:** v1 implementada; [v2 (REQ-01: COTAHIST e ajuste por proventos)](#v2--req-01-cotahist-e-ajuste-por-proventos) implementada (fatias 1 a 3) — aprovada em 2026-11-02
**Fase:** 1 — Dados
**Depende de:** nenhum módulo interno (fonte de verdade histórica)
**ADRs relevantes:** [ADR-0001](../../docs/adr/0001-modular-monolith-vs-microservices.md) (fronteiras de módulo), [ADR-0003](../../docs/adr/0003-database-strategy.md) (DuckDB local / ClickHouse produção), [ADR-0002](../../docs/adr/0002-language-per-module.md) (Python)

## Objetivo

Ingerir, versionar e servir dados históricos de mercado (OHLCV diário) de forma
batch, para consumo por `feature-store`, `backtesting-engine` e `risk-engine`.
É a fonte de verdade histórica da plataforma (C2: "batch, versionada").

## Escopo (v1 — ambiente local/dev)

- Ingestão batch de barras diárias OHLCV para uma lista de instrumentos (ex:
  ações B3).
- Persistência em **DuckDB** (arquivo local, conforme ADR-0003 para dev).
- Registro de auditoria de cada execução de ingestão (quando rodou, quantas
  barras, de qual fonte, sucesso/falha) em **PostgreSQL**.
- Um provider real (Alpha Vantage) e um provider mock/determinístico para
  rodar sem chave de API — a plataforma deve funcionar em dev sem depender de
  uma API externa paga.
- API Python pública (`market_data_lake.api`) — único ponto de leitura/escrita
  exposto a outros módulos, conforme fronteira do ADR-0001.

## Fora de escopo (v1)

- Streaming/tempo real (é responsabilidade do `streaming-engine`).
- Order book / tick data (apenas OHLCV diário nesta fase).
- ClickHouse (fica para quando houver ambiente de produção real — ADR-0003).
- Múltiplas fontes com reconciliação/redundância.

## Modelo de domínio

- `Instrument`: identificador do ativo (ticker, exchange, moeda).
- `OHLCVBar`: instrumento, data, open, high, low, close, volume. Preços em
  `float64` internamente (camada analítica — ADR-0004); a conversão para
  `Decimal` acontece apenas na fronteira de módulos financeiros que precisem
  (ex: `trading-api`), não aqui.
- `IngestionRun`: metadado de auditoria de uma execução de ingestão
  (id, instrumento, fonte, período, nº de barras, status, timestamp).

## Contrato de API (`market_data_lake.api`)

```python
def ingest_daily_bars(ticker: str, start: date, end: date, source: str) -> IngestionRun: ...
def get_price_series(ticker: str, start: date, end: date) -> list[OHLCVBar]: ...
```

Nenhum outro módulo deve importar de `market_data_lake.domain`,
`market_data_lake.application` ou `market_data_lake.infrastructure`
diretamente — apenas de `market_data_lake.api` (fronteira validada por
`import-linter` no CI).

## Critérios de aceite

1. `ingest_daily_bars` com `source="mock"` funciona sem nenhuma variável de
   ambiente configurada (dev sem chave de API).
2. Barras ingeridas ficam disponíveis via `get_price_series` no mesmo
   processo e em execuções subsequentes (persistência real em disco).
3. Toda execução de ingestão gera um `IngestionRun` auditável em Postgres,
   mesmo em caso de falha do provider.
4. Testes rodam contra DuckDB (arquivo real) e Postgres real via
   `docker-compose` — nenhum mock de banco.

## Rastreabilidade

Cada critério de aceite e o teste que o comprova (caminhos relativos a
`market-data-lake/tests/`). Critério novo entra nesta tabela no mesmo PR;
critério sem teste automatizado precisa de justificativa aqui.

| Critério | Evidência | Tipo |
|---|---|---|
| 1. Mock sem variável de ambiente | `test_ingest_daily_bars_use_case.py::test_api_ingere_com_mock_sem_chave_de_api` | Integração (via `api`) |
| 2. Persistência no processo e entre execuções | `test_duckdb_bar_repository.py::test_persiste_entre_conexoes_diferentes`; `test_ingest_daily_bars_use_case.py::test_api_ingere_com_mock_sem_chave_de_api` (leitura via `get_price_series`) | Integração |
| 3. Auditoria em Postgres, inclusive em falha | `test_ingest_daily_bars_use_case.py::test_ingestao_com_sucesso_persiste_barras_e_auditoria`; `::test_ingestao_com_falha_registra_auditoria_e_propaga_erro` (contam linhas na tabela de auditoria) | Integração |
| 4. Infra real, sem mock de banco | Estrutural: fixtures `duckdb_path` (arquivo em disco) e `postgres_dsn` (Postgres real, schema via migrações — ADR-0012); no CI, infra indisponível falha a suíte (`QUANT_REQUIRE_INTEGRATION=1`) | Estrutural |

---

## v2 — REQ-01: COTAHIST e ajuste por proventos

**Requisito:** REQ-01 da [visão do ciclo 1](../../docs/vision.md) (decisão 4).
**Base:** [investigação 0001](../../docs/research/0001-vies-de-sobrevivencia-e-ajuste-de-precos.md),
[investigação 0002](../../docs/research/0002-fonte-de-proventos.md) (R1 a R5
aceitas), item 7 do checklist ([ADR-0013](../../docs/adr/0013-universo-declarado-no-checklist.md)).

### Objetivo

Servir preços reais da B3 **ajustados por proventos**, com o método declarado
e uma reconciliação que prove o ajuste. O `backtesting-engine` só marca o item
7 como `verificado` quando a série de cada ativo vier declarada como ajustada
e sem pendências.

### Escopo

**1. Preços: COTAHIST anual da B3** (`source="cotahist"`)

- Download do arquivo anual `COTAHIST_A{ano}.ZIP`, guardado em cache local
  (`data/raw/cotahist/`); arquivo já baixado não é baixado de novo.
- Retentativa com espera crescente em falha de rede (observada: conexão
  encerrada pelo servidor no meio do download); arquivo parcial é descartado.
- Leitura do registro `01` pelo layout oficial: só mercado à vista
  (`TPMERC = 010`) e o código de negociação exato (o fracionário tem sufixo
  `F`). Preços divididos por `FATCOT` (cotação por lote de mil vira unitária).
- O ISIN de cada barra (`CODISI`) é guardado: liga o ticker à classe de ação
  dos eventos (ex.: PETR4 → `BRPETRACNPR6`).
- Barras **brutas** persistidas no DuckDB; o ajuste é calculado na leitura
  (determinístico, e um evento novo não deixa série ajustada desatualizada).

**2. Eventos: rotas da B3 com snapshot** (R1)

- `GetListedCashDividends` (paginada) e `GetListedSupplementCompany`
  (`stockDividends`), uma requisição por segundo no máximo.
- Resposta bruta guardada como snapshot JSON com a data da coleta
  (`data/raw/b3_events/{empresa}/{data}.json`). O ajuste lê sempre de um
  snapshot: os testes usam snapshots versionados, sem rede.
- Eventos filtrados pelo ISIN da série.

**3. Tabela de correções curada** (R3)

`market-data-lake/reference/corporate_events_corrections.csv`, versionada,
uma linha por evento ausente ou errado na B3, com `ticker`, `ex_date`, `tipo`,
`price_factor`, `fonte` (link) e `nota`. Linhas iniciais:

| Ticker | Data ex | Tipo | Fator de preço | Fonte |
|---|---|---|---|---|
| PETR4 | 2005-09-01 | desdobramento 1:4 | 0,25 | investigação 0002 (salto no COTAHIST) + [AlphaSpread](https://www.alphaspread.com/security/bovespa/petr4/investor-returns/i/stock-splits) |
| ITUB4 | 2021-10-04 | cisão (XP) | 0,8246 | ajuste de −17,54% informado pela B3 ([InfoMoney](https://www.infomoney.com.br/mercados/bdrs-da-xp-passarao-a-ser-negociados-na-b3-nesta-2a-apos-incorporacao-da-xpart-acoes-do-itau-passam-por-reajuste/)) |

A linha de correção prevalece sobre o evento da B3 na mesma data e ativo.

**4. Ajuste: multiplicativo, para trás**

- Data ex = pregão seguinte à data-com informada pela B3.
- Fator de preço por evento (sentido confirmado na investigação 0002):

| Tipo de evento (B3) | Fator de preço aplicado antes da data ex |
|---|---|
| Desdobramento, bonificação | `1 / (1 + factor/100)` |
| Grupamento | `1 / factor` |
| Dividendo, JCP, rendimento | `1 − corporateActionPrice/100` |
| Cisão, outros | Só pela tabela de correções; sem linha, vira pendência |

- Cada preço anterior à data ex é multiplicado pelo produto dos fatores dos
  eventos posteriores a ele. O último preço da série não muda.
- `open`, `high`, `low` e `close` são ajustados; volume não (declarado).

**5. Reconciliação contra o COTAHIST** (R2)

| Verificação | Regra | Falha vira |
|---|---|---|
| Evento de capital | `abertura(ex) / fechamento(com)` dentro de ±10% do fator esperado | pendência |
| Salto sem evento | `abertura(t) / fechamento(t−1)` fora de [0,75; 1,33] sem evento ou correção na data | pendência |
| Provento em dinheiro | `corporateActionPrice` coerente com `valueCash / closingPricePriorExDate` (±0,01 ponto percentual) e fechamento da data-com igual ao do COTAHIST (±0,5%) | pendência |

Tolerâncias declaradas na declaração de ajuste. A ITUB4 mostrou a
necessidade: o fator oficial da cisão é 0,8246 e a razão observada foi 0,834.

**6. Declaração de ajuste** (R4)

Por série, exposta na API: ajustada (sim/não), método, snapshot e tabela de
correções usados, eventos aplicados por tipo, tolerâncias e lista de
pendências. `verificada` só com zero pendências.

**7. `backtesting-engine`: item 7 lê a declaração**

O item 7 passa a `verificado` quando todos os ativos do universo têm série
ajustada e declaração `verificada`; senão, `não verificado`, com as
pendências como evidência. Fontes sem declaração (mock) continuam
`não verificado`.

**8. Alpha Vantage retirada**

O `AlphaVantageProvider` sai (plano gratuito insuficiente, investigação 0001)
junto com `ALPHA_VANTAGE_API_KEY` do `.env.example`.

### Fora de escopo (v2)

- Universo point-in-time e ativos deslistados (ciclo 2).
- Ajuste de volume e de preço intradiário.
- Atualização automática agendada dos snapshots (Should do ciclo).

### Contrato de API (adições)

```python
def ingest_daily_bars(ticker, start, end, source: str) -> IngestionRun: ...  # aceita "cotahist"
def refresh_corporate_events(ticker: str) -> CorporateEventsSnapshot: ...
def get_price_series(ticker, start, end, adjusted: bool = False) -> list[OHLCVBar]: ...
def get_adjustment_declaration(ticker, start, end) -> AdjustmentDeclaration: ...
```

`adjusted=False` é o padrão para não mudar o comportamento atual; o
`backtesting-engine` passa `adjusted=True`.

### Critérios de aceite (v2)

5. **COTAHIST:** um arquivo de amostra versionado (recorte do layout real) é
   lido com os preços certos, incluindo `FATCOT = 1000` e o filtro de mercado
   à vista.
6. **Cache e retentativa:** ano já baixado não é baixado de novo; falha de
   rede no meio do download não deixa arquivo parcial no cache.
7. **Snapshot:** o ajuste lê de um snapshot; sem rede, um snapshot versionado
   reproduz exatamente a mesma série ajustada.
8. **Sentido do fator:** desdobramento de 2008 e grupamento de 2000 da PETR4
   (dados reais em amostra) geram série ajustada sem salto na data ex.
9. **Correção prevalece:** com o desdobramento de 2005 só na tabela de
   correções, a série da PETR4 fica sem salto em 01/09/2005; sem a linha, a
   reconciliação acusa pendência nessa data.
10. **Cisão:** a ITUB4 com a linha de correção não tem salto em 04/10/2021 e
    a reconciliação aceita a razão observada 0,834 contra o fator 0,8246.
11. **Proventos em dinheiro:** o ajuste reproduz o fator da B3 evento a
    evento; incoerência entre `corporateActionPrice` e o valor por ação vira
    pendência.
12. **Último preço intacto:** a série ajustada termina no mesmo preço da bruta.
13. **Item 7 honesto:** o `backtesting-engine` marca o item 7 `verificado`
    só com todas as declarações verificadas; uma pendência em qualquer ativo
    mantém `não verificado`, com a pendência na evidência.
14. **Compatibilidade:** `get_price_series` sem `adjusted` devolve as mesmas
    barras de antes; a suíte v1 continua verde.
15. **Sem rede nos testes:** toda a suíte roda com snapshots e amostras
    versionados; nenhum teste depende da B3 estar no ar.

### Rastreabilidade (v2)

Caminhos relativos a `market-data-lake/tests/`. A amostra
`fixtures/cotahist/` tem linhas reais dos arquivos de 2000 e 2008, sem
alteração; variações sintéticas são montadas nos próprios testes.

| Critério | Evidência | Tipo |
|---|---|---|
| 5. Leitura do COTAHIST | `test_cotahist_parser.py::test_le_precos_do_desdobramento_de_2008`; `::test_fatcot_1000_vira_preco_por_acao`; `::test_ignora_cabecalho_e_rodape`; `::test_mercado_fracionario_tem_codigo_e_mercado_proprios`; `::test_filtro_vem_antes_do_calculo_de_preco`; `::test_fatcot_zero_na_linha_pedida_e_erro_explicito`; `test_cotahist_provider.py::test_so_mercado_a_vista_do_ticker_pedido`; `::test_mesmo_codigo_em_outro_mercado_fica_fora` | Unitário |
| 6. Cache e retentativa | `test_cotahist_provider.py::test_ano_ja_baixado_nao_e_baixado_de_novo`; `::test_falha_no_meio_do_download_nao_deixa_arquivo_parcial`; `::test_todas_as_tentativas_falham_e_erro_cita_a_url`; `::test_resposta_de_sucesso_que_nao_e_zip_nao_entra_no_cache`; `::test_cache_corrompido_e_baixado_de_novo`; `::test_ano_corrente_vale_so_por_um_dia` | Unitário |
| 7. Snapshot | `test_adjusted_series.py::test_api_ajusta_a_partir_do_snapshot_sem_rede`; `test_corporate_events_sources.py::test_store_guarda_e_le_o_snapshot_mais_recente` | Integração |
| 8. Sentido do fator | `test_adjusted_series.py::test_desdobramento_de_2008_e_grupamento_de_2000_sem_salto`; `test_corporate_events_sources.py::test_desdobramento_e_grupamento_da_petr4_com_o_fator_de_preco_certo`; `test_adjustment.py::test_desdobramento_divide_os_precos_anteriores`; `::test_grupamento_multiplica_os_precos_anteriores` | Integração + unitário |
| 9. Correção prevalece | `test_adjusted_series.py::test_desdobramento_de_2005_so_existe_na_tabela_de_correcoes`; `test_adjustment.py::test_correcao_prevalece_sobre_evento_de_capital_da_b3_na_mesma_data_ex`; `test_corporate_events_sources.py::test_tabela_de_correcoes_versionada`; sem a linha, pendência: `test_reconciliation.py::test_sem_a_correcao_de_2005_a_reconciliacao_acusa_o_salto` | Integração + unitário |
| 10. Cisão | `test_adjusted_series.py::test_cisao_da_itub4_ajustada_pela_correcao`; `test_adjustment.py::test_evento_sem_fator_e_sem_correcao_fica_como_nao_suportado`; `test_reconciliation.py::test_cisao_sem_correcao_vira_pendencia_e_com_correcao_nao`; `::test_tolerancia_absorve_o_movimento_do_dia` | Integração + unitário |
| 11. Proventos em dinheiro | `test_adjustment.py::test_provento_em_dinheiro_aplica_o_fator_da_b3`; `test_corporate_events_sources.py::test_proventos_em_dinheiro_usam_o_percentual_da_b3`; `::test_percentual_ausente_e_derivado_pela_formula_da_b3`; `::test_valor_e_fechamento_por_lote_viram_por_acao`; `test_reconciliation.py::test_provento_com_percentual_incoerente_com_o_valor_gera_pendencia`; `::test_fechamento_da_data_com_diferente_do_cotahist_gera_pendencia` | Unitário |
| 12. Último preço intacto | `test_adjusted_series.py::test_ultimo_preco_igual_ao_bruto`; `test_adjustment.py::test_ultimo_preco_da_serie_nunca_muda` | Integração + unitário |
| 13. Item 7 honesto | `test_adjustment_declaration.py::test_serie_real_com_eventos_e_declarada_verificada`; `::test_serie_do_mock_nao_e_declarada_ajustada`; `::test_sem_snapshot_a_serie_nao_e_declarada_ajustada`; `::test_pendencia_impede_a_declaracao_verificada`. Lado do consumidor: testes do item 7 na rastreabilidade da [spec do `backtesting-engine`](../../backtesting-engine/docs/spec.md#rastreabilidade) (critério 9) | Integração + unitário |
| 14. Compatibilidade | Suíte v1 inalterada e verde; `test_cotahist_ingestion.py::test_ingere_do_cotahist_e_le_pela_api` | Integração |
| 15. Sem rede nos testes | Estrutural nesta fatia: downloads substituídos por funções que copiam a amostra; cache pré-preenchido na integração | Estrutural |

Fixado na implementação (fatia 1): o arquivo do **ano em curso** vale por um
dia no cache (cresce a cada pregão); anos anteriores são baixados uma vez. O
filtro por código e mercado vem **antes** da conversão de preços: o COTAHIST
real de 2007 tem 4 opções com `FATCOT = 0`, que derrubariam a leitura — achado
na verificação manual com download real, não pela amostra.

Fixado na implementação (fatia 2):

- **ISIN no `Instrument`** (opcional; `None` no mock) e coluna `isin` no
  DuckDB, criada por `ALTER ... ADD COLUMN IF NOT EXISTS` (DuckDB fora do
  Alembic, ADR-0012). Eventos de capital casam por ISIN; proventos em dinheiro
  (a rota completa não traz ISIN) casam pela classe (`typeStock`: final 3 =
  ON, 4 = PN); correções, pelo ticker.
- **Data ex na série:** evento da B3 vale a partir do primeiro pregão depois da
  data-com; correção, a partir do primeiro pregão na data ex ou depois. Evento
  sem pregão antes dele na série não tem efeito.
- **Linhas idênticas da B3 contam uma vez** (a cisão do Itaú aparece repetida);
  proventos distintos na mesma data-com somam.
- **Percentual ausente:** quando a B3 não informa `corporateActionPrice`, o
  fator é `1 − valueCash / closingPricePriorExDate` (a mesma conta do
  percentual, conferida nos eventos que o têm) e o evento fica marcado como
  derivado. Caso real: três RENDIMENTO da PETR4 de valor simbólico
  (R$ 0,0000000001).
- `refresh_corporate_events` devolve a data da coleta.

Fixado na implementação (fatia 3):

- **Reconciliação** (`domain/reconciliation`) com as tolerâncias da seção 5;
  o salto sem evento é medido na série **ajustada** (pega tanto salto bruto sem
  evento quanto fator aplicado errado); datas com evento de capital são
  conferidas contra o fator, não contra a faixa.
- **`quotedPerShares`:** antes de 2000 a B3 cotava por lote de mil; valor e
  fechamento dos proventos são divididos por esse campo (o percentual não
  muda). Sem isso, quatro pendências falsas em 23/03/2000 na PETR4.
- **Nome do membro do ZIP:** `COTAHIST.A2000` (layout antigo) e
  `COTAHIST_A2005.TXT` em diante; o leitor aceita os dois.
- **Declaração** (`get_adjustment_declaration`): série sem ISIN (mock), sem
  barras ou sem snapshot é declarada **não ajustada**, com o motivo; o
  `backtesting-engine` lê a série bruta nesses casos e o item 7 mostra o motivo.
- **Alpha Vantage retirada** (provider, fonte `alpha_vantage` e variável).

Reconciliação com anos inteiros de dados reais (fora da suíte): PETR4 de 2000
a 2008 (2.231 pregões, 51 eventos), VALE3 em 2007 (245 pregões, 6 eventos) e
ITUB4 em 2021 (247 pregões, 20 eventos) — **zero pendências**.

Verificação com anos inteiros de dados reais (fora da suíte): PETR4 de 2005 a
2008 tem exatamente dois saltos de abertura fora de [0,75; 1,33] na série
bruta (01/09/2005 e 28/04/2008) e nenhum na ajustada; ITUB4 em 2021, nenhum
evento sem suporte. Último preço igual ao bruto nas duas.

Testes validados com defeitos simulados: ignorar `FATCOT`, não apagar arquivo
parcial, ano corrente sem expirar e sem retentativa quebram os testes. "Sem
filtro de mercado à vista" e "ZIP baixado sem validação" sobreviveram à
primeira versão dos testes e motivaram `test_mesmo_codigo_em_outro_mercado_fica_fora`
e `test_resposta_de_sucesso_que_nao_e_zip_nao_entra_no_cache`. Na fatia 2, os
8 defeitos simulados quebram os testes na primeira versão: fator de
desdobramento sem `/100`, grupamento sem inverter, percentual sem `/100`,
correção sem prevalecer, linhas repetidas contando duas vezes, data ex um dia
antes, fator aplicado no próprio dia ex e ISIN ignorado. Na fatia 3, os 8
defeitos simulados quebram os testes: conferência do evento de capital,
salto sem evento, coerência do provento e fechamento da data-com desligados,
evento sem fator sem pendência, declaração verificada com pendência, item 7
ignorando pendências e backtest sem pedir a série ajustada.
