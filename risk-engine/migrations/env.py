"""Ambiente Alembic do risk-engine (ADR-0012).

Migrações em SQL explícito (`op.execute`): o módulo usa psycopg direto, sem
modelos SQLAlchemy, então não há autogenerate. Tabela de versão própria —
cada módulo é dono do seu schema (ADR-0001).
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine

DEFAULT_DSN = "postgresql://quant:quant@localhost:5432/quant_platform"
VERSION_TABLE = "risk_engine_alembic_version"


def _sqlalchemy_url() -> str:
    # Testes passam o DSN por `config.attributes`; a CLI usa a variável da aplicação.
    dsn = context.config.attributes.get("dsn") or os.environ.get("RISK_ENGINE_PG_DSN", DEFAULT_DSN)
    return str(dsn).replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    context.configure(url=_sqlalchemy_url(), literal_binds=True, version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_sqlalchemy_url())
    with engine.connect() as connection:
        context.configure(connection=connection, version_table=VERSION_TABLE)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
