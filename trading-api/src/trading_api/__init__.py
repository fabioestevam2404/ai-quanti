"""trading-api: única porta de saída para a corretora/exchange.

Ponto de entrada externo é sempre `trading_api.api` — nunca importe
`domain`, `application` ou `infrastructure` diretamente de outro módulo
(fronteira validada por import-linter, ver ADR-0001).
"""
