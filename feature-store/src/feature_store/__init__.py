"""feature-store: features versionadas para treino e inferência (hot-path).

Ponto de entrada externo é sempre `feature_store.api` — nunca importe
`domain`, `application` ou `infrastructure` diretamente de outro módulo
(fronteira validada por import-linter, ver ADR-0001).
"""
