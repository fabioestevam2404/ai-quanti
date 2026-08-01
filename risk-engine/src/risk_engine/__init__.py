"""risk-engine: métricas de risco (analítico) e gate pré-trade (síncrono).

Ponto de entrada externo é sempre `risk_engine.api` — nunca importe
`domain`, `application` ou `infrastructure` diretamente de outro módulo
(fronteira validada por import-linter, ver ADR-0001).
"""
