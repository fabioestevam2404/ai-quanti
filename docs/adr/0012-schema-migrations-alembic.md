# ADR-0012: Migrações de schema versionadas com Alembic, por módulo

**Status:** Aceito
**Data:** 2026-11-01
**Contexto do módulo:** `market-data-lake`, `risk-engine` (todo módulo com schema em Postgres)

## Contexto

Até aqui cada repositório Postgres criava as próprias tabelas no construtor
(`CREATE TABLE IF NOT EXISTS` em `_ensure_schema`). Funciona enquanto o
schema não muda, mas:

- **Não há como evoluir o schema.** `IF NOT EXISTS` ignora a tabela existente:
  uma coluna nova no ledger de risco nunca chegaria a um banco já criado.
- **Não há histórico.** Não dá para saber qual versão do schema um banco tem,
  nem reconstruí-lo de forma reproduzível.
- **DDL no caminho quente.** Todo `PostgresPositionLedger()` executava DDL —
  inclusive dentro do gate pré-trade (ADR-0006).

O `risk-engine` guarda exposição e P&L que decidem se uma ordem passa. Mudar
esse schema sem histórico e sem ensaio de reversão é o tipo de risco que os
ADRs 0006/0007 existem para evitar.

## Decisão

- **Alembic, com um diretório de migrações por módulo** (`<modulo>/migrations`,
  `<modulo>/alembic.ini`) e **tabela de versão própria**
  (`market_data_lake_alembic_version`, `risk_engine_alembic_version`). Cada
  módulo é dono do seu schema (ADR-0001), mesmo compartilhando a instância de
  Postgres.
- **SQL explícito** (`op.execute`), sem autogenerate: os módulos usam psycopg
  direto, sem modelos SQLAlchemy. O SQLAlchemy entra só como driver do
  Alembic (`postgresql+psycopg`).
- **Repositórios não criam mais schema.** O construtor só guarda o DSN; a
  linha singleton do circuit breaker passa a ser dado de schema, inserida
  pela migração.
- **Baseline adota bancos existentes**: só a primeira migração de cada módulo
  usa `IF NOT EXISTS`, reproduzindo exatamente o schema anterior. Melhorias
  (constraints, índices) entram como migrações seguintes, sem `IF NOT EXISTS`.
- **Toda migração tem `downgrade`.** O CI aplica `upgrade → downgrade →
  upgrade` num Postgres vazio a cada PR; os testes de integração aplicam
  `upgrade head` no banco de teste antes de rodar.
- O banco alvo vem da mesma variável da aplicação
  (`MARKET_DATA_LAKE_PG_DSN`, `RISK_ENGINE_PG_DSN`).
- **DuckDB do `market-data-lake` fica fora** deste ADR: é armazenamento
  analítico local e reconstruível por reingestão, não fonte de verdade
  transacional.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Manter `CREATE TABLE IF NOT EXISTS` | Zero ferramenta nova | Não evolui schema existente; sem histórico | É o problema que este ADR resolve |
| Um diretório de migrações compartilhado | Um único comando de upgrade | Histórico de um módulo acoplado ao de outro; fronteira do ADR-0001 furada no schema | Contradiz a posse de schema por módulo |
| Scripts SQL numerados à mão | Simples e transparente | Sem registro de versão aplicada, sem downgrade padronizado | Reimplementaria o Alembic |
| yoyo-migrations / dbmate | Leves, SQL puro | Ecossistema menor; dbmate é binário fora do workspace Python | Alembic é o padrão do ecossistema e roda via `uv run` |
| Schemas Postgres separados por módulo (`risk.*`, `mdl.*`) | Isolamento mais forte | Muda os nomes das tabelas em uso — mudança de comportamento junto com a adoção da ferramenta | Pode vir depois, como migração própria |

## Consequências

- **Positivas:** schema reconstruível do zero e verificado a cada PR;
  mudanças de schema viram arquivos revisáveis com reversão ensaiada; o gate
  pré-trade deixa de executar DDL a cada instanciação.
- **Negativas / trade-offs aceitos:** aplicar migrações vira passo explícito
  de setup e de deploy (`alembic upgrade head` por módulo). Sem ele, a
  ingestão falha com tabela inexistente e o gate de risco **bloqueia** por
  fail-closed (ADR-0006) — falha segura, mas falha. Migrações ficam fora de
  `src/`, então não vão num wheel; aceitável enquanto a plataforma é
  implantada a partir do repositório (ADR-0011).
- **Impacto em outros módulos:** todo módulo novo com tabelas em Postgres
  segue o mesmo padrão (diretório e tabela de versão próprios) e entra no
  passo de migrações do CI. Testes que dependem do schema de outro módulo
  aplicam as migrações desse módulo na fixture.
