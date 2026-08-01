# ADR-0007: trading-api — camadas de segurança obrigatórias para capital real

**Status:** Aceito
**Data:** 2026-07-31
**Contexto do módulo:** `trading-api`

## Contexto

O design original de `trading-api` (C2/C3) cobria roteamento de ordens e
consulta de portfólio, mas não considerava os modos de falha específicos de
enviar ordens para uma corretora com dinheiro real: retry duplicando
ordens, estado interno divergindo do estado real na corretora, e ausência
de um botão de emergência. Nenhum desses riscos existe em backtest ou em
paper trading isolado — todos aparecem só quando há execução real.

## Decisão

`trading-api` implementa quatro camadas, todas obrigatórias antes de
qualquer ordem real ser enviada (não opcionais, não incrementais):

1. **Kill switch manual** — endpoint/flag operável por um humano
   (`quant`/`pm`) que interrompe **imediatamente** o envio de qualquer nova
   ordem. Estado do kill switch é persistido (Postgres), não em memória —
   sobrevive a restart do processo. Reset exige ação explícita, nunca
   automático.
2. **Idempotência de ordens** — toda ordem carrega um `client_order_id`
   determinístico (gerado a partir de estratégia + sinal + timestamp,
   nunca aleatório a cada tentativa). Antes de enviar, `trading-api`
   verifica se aquele `client_order_id` já foi processado (Postgres,
   `UNIQUE` constraint). Retry de rede nunca gera ordem duplicada.
3. **Reconciliação periódica** — job agendado (frequência mínima: a cada
   fechamento de pregão; idealmente também intraday) que compara posição e
   ordens em aberto que a plataforma acredita ter (Postgres) contra o que a
   corretora efetivamente reporta (API de posições). Divergência gera
   alerta e, se acima de um limiar configurável, aciona o kill switch
   automaticamente — divergência de reconciliação é tratada como incidente
   de segurança, não como bug de relatório.
4. **Position limits hard-coded** — última linha de defesa, independente do
   `risk-engine` (ADR-0006). Um limite absoluto de exposição por ativo e de
   ordens por minuto vive como constante no código do `trading-api`
   (revisão via PR, não via config dinâmica) — protege mesmo se
   `risk-engine` estiver fora do ar, com bug, ou mal configurado.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Confiar só no `risk-engine` (ADR-0006) para limites | Uma fonte única de regra | Single point of failure — bug ou indisponibilidade do risk-engine remove toda proteção | Defesa em profundidade é o padrão da indústria para sistemas que movem dinheiro real |
| Idempotência via "checar se já existe posição parecida" (heurística) | Mais simples de implementar | Falso negativo/positivo real; não é determinístico | Idempotência tem que ser garantida por chave, não inferida |
| Reconciliação só sob demanda (manual) | Menos código | Divergência pode ficar não detectada por dias | Inaceitável com capital real — motivo original desta ADR |

## Consequências

- **Positivas:** cada camada cobre um modo de falha diferente e
  independente — mesmo que uma falhe, as outras seguram o risco de perda
  descontrolada.
- **Negativas / trade-offs aceitos:** mais complexidade e mais testes
  (inclusive testes de caos: simular corretora fora do ar, resposta
  duplicada, timeout) antes de `trading-api` poder tocar dinheiro real.
  Isso atrasa a Fase 4, mas é o próprio objetivo desta ADR.
- **Impacto em outros módulos:** depende de [ADR-0006](0006-risk-engine-pre-trade-gate.md)
  (gate síncrono) e é pré-requisito para sair de paper trading (ver
  [ADR-0008](0008-paper-trading-gate.md)). Kill switch e estado de
  reconciliação precisam ser visíveis no `trading-dashboard`.
