# ADR-0009: Gestão de segredos para credenciais de corretora

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** `trading-api`, `infrastructure`, `monitoring`, plataforma inteira (logging)

## Contexto

Até aqui, o único segredo da plataforma era `ALPHA_VANTAGE_API_KEY` — uma
chave de leitura de dados de mercado, sem capacidade de mover dinheiro.
Tratá-la como env var de dev (`.env` git-ignored) é proporcional ao risco
que ela representa.

Credencial de corretora é outra categoria: dá capacidade de **executar
ordens com dinheiro real**. Vazamento não é um incidente de dados, é perda
financeira direta. `.env`, variável de ambiente em texto plano no
Kubernetes, ou log estruturado sem redação — nenhum é aceitável para esse
tipo de segredo.

## Decisão

- **Credenciais capazes de executar ordens (corretora) nunca ficam em
  `.env`, config file, variável de ambiente em texto plano ou secret do
  Kubernetes sem criptografia em repouso.** Vivem em um **secrets manager
  gerenciado** — **AWS Secrets Manager** como padrão (consistente com o
  Cloud Provider já referenciado em `infrastructure/`); **HashiCorp Vault**
  fica como alternativa válida se a plataforma migrar para infraestrutura
  self-hosted ou multi-cloud — decisão a revisitar nesta ADR se isso
  acontecer, não uma decisão paralela.
- **Rotação obrigatória**: credencial de corretora rotaciona no máximo a
  cada 90 dias, automatizada via rotation Lambda (AWS Secrets Manager) ou
  dynamic secrets (Vault) — nunca rotação manual como único mecanismo.
  Rotação imediata (fora do ciclo) é obrigatória em caso de suspeita de
  vazamento.
- **`ALPHA_VANTAGE_API_KEY` e chaves equivalentes (só leitura, sem
  execução) continuam via `.env` git-ignored em dev** — proporcional ao
  risco (ver `market-data-lake/docs/spec.md`). A distinção não é
  "segredo vs. não-segredo", é "capacidade de executar ordem vs. não".
- **Redação obrigatória em qualquer log, em qualquer módulo** — inclusive
  os logs estruturados de custo de LLM (`investment-copilot`,
  `financial-rag`) usados no padrão já validado no Norte. Isso é
  implementado como filtro/middleware **na configuração central de
  logging** (ver `monitoring/`), não como disciplina de cada call site:
  qualquer campo cujo nome bata com um padrão conhecido (`*_key`,
  `*_token`, `*_secret`, `authorization`, etc.) é redigido antes de
  qualquer sink (stdout, arquivo, agregador de logs). Testado com um caso
  de teste que injeta um segredo de mentira e verifica que ele nunca chega
  ao sink.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Kubernetes Secrets nativo (sem gerenciador externo) | Já integrado ao cluster, zero custo adicional | Base64, não criptografia real; sem rotação automática; sem audit trail de acesso | Insuficiente para credencial de execução de ordens |
| Vault self-hosted desde o início | Portável entre clouds, controle total | Mais um sistema para operar/manter com time de 1 pessoa (mesmo argumento do ADR-0001 contra microsserviços) | Overhead operacional não se justifica ainda; revisitar se sair de AWS |
| Redação de log por disciplina manual em cada call site | Simples de começar | Um único `logger.info(f"...{api_key}...")` esquecido vaza o segredo — falha silenciosa e catastrófica | Redação tem que ser estrutural (filtro central), não depender de disciplina individual |

## Consequências

- **Positivas:** vazamento de credencial de execução exige comprometer o
  secrets manager (com seu próprio audit trail), não só um grep em log ou
  repositório.
- **Negativas / trade-offs aceitos:** dependência adicional de AWS Secrets
  Manager antes mesmo de `infrastructure/` ter um ADR de cloud provider
  formal — aceito porque segurança de credencial de execução não pode
  esperar essa decisão amadurecer.
- **Impacto em outros módulos:** `trading-api` só pode ler credencial de
  corretora via SDK do secrets manager, nunca via variável de ambiente
  direta; `monitoring/` implementa o filtro de redação central usado por
  toda a plataforma; `infrastructure/` provisiona o secrets manager via
  Terraform como parte do setup de produção (fora do escopo do
  `docker-compose.local.yml`, que continua só com Postgres/Redis para dev).
