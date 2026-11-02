"""backtesting-engine: simulação histórica com checklist de validação.

Ponto de entrada externo é sempre `backtesting_engine.api` — nunca importe
`domain`, `application` ou `infrastructure` diretamente de outro módulo
(fronteira validada por import-linter, ver ADR-0001).
"""
