"""Baseline: auditoria de execuções de ingestão.

Revision ID: mdl_0001
Revises:
Create Date: 2026-11-01
"""

from __future__ import annotations

from alembic import op

revision = "mdl_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS só nesta baseline: bancos criados antes do ADR-0012 já têm
    # a tabela (criada pelo próprio repositório) e precisam adotar o histórico
    # sem erro. Migrações seguintes não usam IF NOT EXISTS.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS market_data_lake_ingestion_runs (
            id SERIAL PRIMARY KEY,
            ticker TEXT NOT NULL,
            source TEXT NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            bars_ingested INTEGER NOT NULL,
            status TEXT NOT NULL,
            executed_at TIMESTAMPTZ NOT NULL,
            error_message TEXT
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE market_data_lake_ingestion_runs")
