"""market-data-lake: ingestão e armazenamento histórico de dados de mercado.

Ponto de entrada externo é sempre `market_data_lake.api` — nunca importe
`domain`, `application` ou `infrastructure` diretamente de outro módulo
(fronteira validada por import-linter, ver ADR-0001).
"""
