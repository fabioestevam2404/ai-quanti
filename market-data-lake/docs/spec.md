# Spec — market-data-lake

**Status:** Em implementação
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
def ingest_daily_bars(ticker: str, start: date, end: date, source: str = "mock") -> IngestionRun: ...
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
