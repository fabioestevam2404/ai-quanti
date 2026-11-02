# Architecture Decision Records (ADRs)

Registro das decisões arquiteturais relevantes da Quant AI Platform.
Formato: [template.md](template.md).

| # | Título | Status |
|---|---|---|
| [0001](0001-modular-monolith-vs-microservices.md) | Monólito modular vs. Microsserviços | ✅ Aceito |
| [0002](0002-language-per-module.md) | Linguagem por módulo | ✅ Aceito |
| [0003](0003-database-strategy.md) | Estratégia de banco de dados por caso de uso | ✅ Aceito |
| [0004](0004-money-precision-standard.md) | Padrão de precisão numérica (Decimal vs float) | ✅ Aceito |
| [0005](0005-custom-backtesting-engine.md) | Motor de backtesting próprio vs. Backtrader/Zipline | ✅ Aceito |
| [0006](0006-risk-engine-pre-trade-gate.md) | risk-engine: de métricas pós-fato para gate pré-trade | ✅ Aceito |
| [0007](0007-trading-api-safety-layers.md) | trading-api: camadas de segurança para capital real | ✅ Aceito |
| [0008](0008-paper-trading-gate.md) | Paper trading como gate formal e obrigatório | ✅ Aceito |
| [0009](0009-secrets-management.md) | Gestão de segredos para credenciais de corretora | ✅ Aceito |
| [0010](0010-backtesting-validation-checklist.md) | Checklist de validação (overfitting/look-ahead) no backtesting-engine | ✅ Aceito |
| [0011](0011-uv-workspace-lockfile.md) | Ambiente reproduzível com uv workspace e lockfile único | ✅ Aceito |
| [0012](0012-schema-migrations-alembic.md) | Migrações de schema versionadas com Alembic, por módulo | ✅ Aceito |
| [0013](0013-universo-declarado-no-checklist.md) | Universo declarado e preços ajustados no checklist de backtest | 📝 Proposto |

## Convenções

- Numeração sequencial, nunca reutilizada (mesmo ADRs supersedidos mantêm o número).
- Status possíveis: `Proposto`, `Aceito`, `Supersedido por ADR-XXXX`, `Rejeitado`.
- Toda decisão que afeta mais de um módulo, ou que seria cara de reverter,
  vira ADR — não fica só em discussão de PR.
