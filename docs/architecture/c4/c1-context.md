# C4 — Nível 1: Diagrama de Contexto

Mostra a Quant AI Platform como uma caixa única, seus usuários e os sistemas
externos com os quais ela troca dados.

```mermaid
C4Context
    title Diagrama de Contexto — Quant AI Platform

    Person(quant, "Quant Researcher / Trader", "Desenvolve, testa e monitora estratégias quantitativas")
    Person(pm, "Portfolio Manager", "Acompanha risco e performance da carteira")

    System(platform, "Quant AI Platform", "Coleta dados, gera sinais, faz backtesting, avalia risco e executa ordens")

    System_Ext(marketdata, "Provedores de Dados de Mercado", "Preços, order book, dados históricos (ex: B3, exchanges, data vendors)")
    System_Ext(broker, "Corretora / Exchange", "API de execução de ordens (ex: B3, Binance, Interactive Brokers)")
    System_Ext(news, "Notícias e Redes Sociais", "Feeds de notícias e sentimento de mercado")
    System_Ext(altdata, "Dados Alternativos", "Clima, satélite, cartão de crédito, etc.")
    System_Ext(llm, "Provedor de LLM", "Claude API — geração de insights e RAG")
    System_Ext(cloud, "Cloud Provider", "Armazenamento, compute e observabilidade (AWS/Azure/GCP)")

    Rel(quant, platform, "Desenvolve estratégias, roda backtests, consulta modelos")
    Rel(pm, platform, "Consulta risco, performance e alocação via dashboard")

    Rel(platform, marketdata, "Consome preços e dados históricos", "REST/WebSocket")
    Rel(platform, broker, "Envia e monitora ordens", "REST/FIX")
    Rel(platform, news, "Consome notícias e sentimento", "REST/Stream")
    Rel(platform, altdata, "Consome dados alternativos", "REST/Batch")
    Rel(platform, llm, "Gera insights, resumos e respostas do copiloto", "API")
    Rel(platform, cloud, "Armazena dados, executa workloads, observa o sistema", "SDK/API")
```

## Atores

| Ator | Descrição |
|---|---|
| Quant Researcher / Trader | Constrói e valida estratégias; interage com backtesting e feature store |
| Portfolio Manager | Consome dashboards de risco e performance; não escreve código |

## Sistemas externos

| Sistema | Papel | Observação |
|---|---|---|
| Provedores de Dados de Mercado | Fonte de preços/OHLCV/order book | Pode ser multi-fonte (redundância) |
| Corretora / Exchange | Execução real de ordens | Isolado atrás de um `trading-api` — nunca acoplado direto às estratégias |
| Notícias e Redes Sociais | Sinal de sentimento | Usado por `financial-rag` e `ml-predictions` |
| Dados Alternativos | Sinais não convencionais | Opcional, fase avançada |
| Provedor de LLM (Claude) | Geração de linguagem natural | Usado no `investment-copilot` e `financial-rag` |
| Cloud Provider | Infra base | Definido em `infrastructure/` |
