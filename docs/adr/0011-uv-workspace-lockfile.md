# ADR-0011: Ambiente reproduzível com uv workspace e lockfile único

**Status:** Aceito
**Data:** 2026-11-01
**Contexto do módulo:** Plataforma inteira (todos os módulos Python implementados)

## Contexto

Até aqui cada módulo era instalado com `pip install -e ./<modulo>[dev]`, com
dependências declaradas só como piso (`duckdb>=1.0.0`, `psycopg>=3.1`...) e
ferramentas de qualidade (`ruff`, `mypy`, `bandit`, `pip-audit`) instaladas
no CI sem versão. Consequências observadas:

- O conjunto de versões instalado dependia do dia da instalação: um release
  novo de qualquer dependência podia quebrar o CI sem nenhum commit no repo.
- A versão do Python não era fixada: local rodava 3.11, CI rodava 3.12.
- A dependência entre módulos (`risk-engine`/`feature-store` usam
  `market_data_lake.api`) dependia de lembrar de instalar os dois no mesmo
  venv, documentado só em comentário.

Para uma plataforma que trata reprodutibilidade como requisito (backtests e
métricas de risco precisam ser determinísticos, ADR-0010), o ambiente também
precisa ser.

## Decisão

- **uv workspace na raiz** (`pyproject.toml` sem `[project]`, só
  `[tool.uv.workspace]`) com os módulos implementados como `members`.
  Novo módulo com código entra na lista no mesmo PR que cria seu
  `pyproject.toml`.
- **Um único `uv.lock` versionado** para toda a plataforma: todos os módulos
  rodam com o mesmo conjunto resolvido, coerente com o monólito modular
  (ADR-0001), que é implantado como uma unidade.
- **`.python-version` = 3.12** na raiz, usado local e no CI.
  `requires-python = ">=3.11"` continua nos módulos como piso de
  compatibilidade (mesmo alvo de `mypy.ini` e `ruff.toml`).
- **Ferramentas de desenvolvimento num `[dependency-groups] dev` da raiz**,
  travadas pelo lockfile; os extras `[dev]` por módulo deixam de existir.
- **CI usa `uv sync --locked --all-packages` e `uv run --locked`**: lockfile
  desatualizado em relação aos `pyproject.toml` falha o pipeline em vez de
  ser resolvido silenciosamente.
- Dependência entre módulos **continua não declarada** em
  `[project.dependencies]`: `--all-packages` instala todos os membros no
  mesmo ambiente, e as fronteiras seguem garantidas pelo import-linter.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Manter pip + pins exatos (`==`) nos `pyproject.toml` | Nenhuma ferramenta nova | Pins não cobrem dependências transitivas; atualização manual e sujeita a erro | Não garante reprodutibilidade completa |
| pip-tools (`requirements.txt` compilado) | Lock com transitivas, maduro | Um arquivo por contexto (dev/prod/módulo), sem noção de workspace, Python não fixado | Mais peças para manter do que o uv |
| Poetry | Lockfile e grupos de dependência | Suporte a monorepo/workspace via plugins; mais lento | uv resolve workspace nativamente |
| Um `uv.lock` por módulo | Módulos realmente independentes | Versões podem divergir entre módulos que rodam no mesmo processo | Contradiz o monólito modular (ADR-0001) |
| Declarar `market-data-lake` como dependência com `{ workspace = true }` | Grafo de dependências explícito | Quem instalar um módulo isolado com pip consultaria o PyPI por um nome que não publicamos (risco de dependency confusion) | Revisitar quando houver publicação ou deploy por módulo |

## Consequências

- **Positivas:** clone limpo + `uv sync --all-packages` reproduz exatamente o
  ambiente do CI (mesmas versões, mesmo Python). Atualizar dependências vira
  uma mudança explícita e revisável (`uv lock --upgrade` em PR próprio, com
  CI verde). `pip-audit` audita sempre o mesmo conjunto que roda nos testes.
- **Negativas / trade-offs aceitos:** uv passa a ser pré-requisito de
  desenvolvimento. `pip install -e` de um módulo isolado deixa de ser o
  caminho suportado. Em redes com inspeção TLS (proxy/antivírus corporativo),
  é preciso `UV_SYSTEM_CERTS=1` para o uv confiar no repositório de
  certificados do sistema — nunca desligar a verificação.
- **Impacto em outros módulos:** todo módulo novo com código entra em
  `members` e no CI pelo mesmo comando (`--all-packages`), sem editar a lista
  de instalação do workflow. Revisitar este ADR se algum módulo passar a ser
  implantado separadamente (ex.: `trading-api` como serviço próprio), o que
  exigiria lock/artefato por módulo.
