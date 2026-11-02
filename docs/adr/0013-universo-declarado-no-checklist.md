# ADR-0013: Universo declarado e preços ajustados no checklist de backtest

**Status:** Aceito
**Data:** 2026-11-02
**Contexto do módulo:** `backtesting-engine`, `trading-api` (promoção de estratégia)
**Altera:** [ADR-0010](0010-backtesting-validation-checklist.md) (itens do checklist)

## Contexto

A [investigação 0001](../research/0001-vies-de-sobrevivencia-e-ajuste-de-precos.md)
mostrou que:

- Para o universo do MVP (PETR4, VALE3, ITUB4, decisão 2 da
  [visão](../vision.md#decisões-do-ciclo)), não há como verificar ausência de
  viés de sobrevivência: o viés está na escolha de ações que existem hoje.
  Um universo point-in-time exige COTAHIST + carteiras históricas do
  Ibovespa + proventos — trabalho maior que o ciclo 1.
- Pela regra atual do ADR-0010, "não verificado" no item 2 bloqueia a
  **entrada em paper trading**. Isso impede o MVP de chegar ao REQ-03, embora
  paper trading não arrisque capital.
- O checklist não exige preços ajustados por proventos. O provider atual usa
  série sem ajuste, o que distorce sinais e retornos mesmo com universo
  perfeito.

O objetivo do ADR-0010 é impedir que uma estratégia com resultado inflado
**chegue a capital real**. Paper trading é justamente a etapa que valida o
sistema sem esse risco.

## Decisão

1. **Item 2 do checklist passa a ter três estados:** `verificado`,
   `limitação declarada` e `não verificado`/`falhou`.
   - `limitação declarada` exige: universo fixado **antes** de rodar o
     backtest, lista de ativos e critério de escolha no relatório, e o texto
     da limitação ("universo escolhido entre ativos listados hoje; resultado
     pode estar inflado por viés de sobrevivência").
   - `limitação declarada` **permite paper trading**, mas **bloqueia a
     promoção a capital real** (ADR-0008) até o item ser `verificado`.
   - `não verificado` e `falhou` continuam bloqueando paper trading.
2. **Novo item 7 no checklist: preços ajustados por proventos.** O relatório
   declara a fonte, o método de ajuste (desdobramento, grupamento,
   bonificação, dividendos) e uma verificação em data de evento conhecida.
   Sem isso, o item é `não verificado` e bloqueia paper trading.
3. Os demais itens do ADR-0010 não mudam.

## Alternativas consideradas

| Alternativa | Prós | Contras | Motivo da rejeição |
|---|---|---|---|
| Manter o ADR-0010 como está | Nenhuma exceção | MVP não chega ao paper trading; incentiva marcar "verificado" sem prova | Bloqueia sem proteger capital (paper não usa capital) |
| Construir universo point-in-time já no ciclo 1 | Resolve o viés de fato | COTAHIST + carteiras + proventos: escopo maior que o ciclo | Vira Should do ciclo 2, pré-requisito de capital real |
| Marcar o item 2 como "verificado" para universos fixos | Simples | Afirma algo falso no relatório | Contraria o propósito do checklist |
| Deixar o ajuste de preços como boa prática | Sem mudança de contrato | Mesmo modo de falha que motivou o ADR-0010 | Precisa ser item verificável |

## Consequências

- **Positivas:** o MVP pode validar o sistema em paper trading sem afirmar
  algo falso; a limitação fica visível no relatório e continua impedindo
  capital real. O ajuste de preços passa a ser exigência verificável.
- **Negativas / trade-offs aceitos:** resultados de paper trading com
  `limitação declarada` não valem como prova de que a estratégia funciona —
  só de que o sistema funciona. O relatório precisa deixar isso explícito.
- **Impacto em outros módulos:** `backtesting-engine.api` expõe o estado de
  cada item (três estados no item 2) e o item 7; `market-data-lake` precisa
  fornecer preço ajustado (REQ-01); o processo de promoção do ADR-0008 passa
  a recusar estratégia com qualquer `limitação declarada`.
