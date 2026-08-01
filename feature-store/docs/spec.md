# Spec — feature-store

**Status:** Em implementação
**Fase:** 1 — Dados
**Depende de:** `market-data-lake` (via `market_data_lake.api`)
**ADRs relevantes:** [ADR-0001](../../docs/adr/0001-modular-monolith-vs-microservices.md) (fronteiras de módulo), [ADR-0003](../../docs/adr/0003-database-strategy.md) (Redis hot-path)

## Objetivo

Ser o **único ponto de leitura de features** tanto para treino
(`ml-predictions`, `reinforcement-learning`) quanto para simulação
(`backtesting-engine`), evitando train/serve skew (C2: racional das
fronteiras).

## Escopo (v1 — ambiente local/dev)

- Cálculo de features determinísticas derivadas de OHLCV: retorno diário,
  média móvel simples (N dias), volatilidade realizada (desvio padrão
  anualizado de retornos, janela N dias).
- Leitura da série de preços via `market_data_lake.api` — nunca acesso
  direto ao armazenamento do `market-data-lake`.
- Dois modos de leitura:
  - **Treino** (`get_training_features`): recalcula/lê o histórico completo,
    tolera latência maior.
  - **Serving/hot-path** (`get_online_features`): lê do cache **Redis**,
    latência sub-milissegundo, alimentado por um passo de
    "materialização" que grava as features mais recentes no cache.
- API Python pública (`feature_store.api`).

## Fora de escopo (v1)

- Features de streaming em tempo real (via Kafka) — entra quando
  `streaming-engine` existir.
- Feature versionada com schema registry — nesta fase o contrato é o
  dataclass Python, sem versionamento formal.

## Modelo de domínio

- `FeatureVector`: instrumento, data de referência, dicionário
  `{nome_da_feature: valor}` (`float64` — camada analítica, ADR-0004).
- `FeatureDefinition`: nome, janela (N dias), função de cálculo.

## Contrato de API (`feature_store.api`)

```python
def get_training_features(ticker: str, start: date, end: date) -> list[FeatureVector]: ...
def materialize_online_features(ticker: str, as_of: date) -> FeatureVector: ...
def get_online_features(ticker: str) -> FeatureVector | None: ...
```

Consumidores (`backtesting-engine`, `ml-predictions`, `reinforcement-learning`)
só podem importar `feature_store.api` — nunca `domain`/`application`/
`infrastructure` diretamente (fronteira validada por `import-linter`).

## Critérios de aceite

1. `get_training_features` produz o mesmo valor de feature independente de
   ter sido calculado "ao vivo" ou re-calculado depois (determinístico —
   pré-requisito para eliminar train/serve skew).
2. `materialize_online_features` grava em Redis real e `get_online_features`
   lê exatamente o que foi gravado (sem cache local/mock).
3. Pedir features para um `ticker` sem dados no `market-data-lake` retorna
   lista vazia / `None`, nunca lança exceção não tratada.
4. Testes rodam contra Redis real via `docker-compose` — nenhum mock de
   cache.
