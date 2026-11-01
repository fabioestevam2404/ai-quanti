"""Baseline: ledger de exposição/P&L diário e estado do circuit breaker.

Revision ID: risk_0001
Revises:
Create Date: 2026-11-01
"""

from __future__ import annotations

from alembic import op

revision = "risk_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS só nesta baseline: bancos criados antes do ADR-0012 já têm
    # as tabelas (criadas pelos próprios repositórios) e precisam adotar o
    # histórico sem erro. Migrações seguintes não usam IF NOT EXISTS.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS risk_positions (
            ticker TEXT PRIMARY KEY,
            exposure NUMERIC(20, 8) NOT NULL DEFAULT 0
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS risk_daily_pnl (
            pnl_date DATE PRIMARY KEY,
            realized_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS risk_circuit_breaker_state (
            id INTEGER PRIMARY KEY,
            tripped BOOLEAN NOT NULL DEFAULT FALSE,
            tripped_date DATE,
            tripped_reason TEXT,
            reset_at TIMESTAMPTZ,
            reset_by TEXT
        )
        """
    )
    # Linha singleton: sem ela, get_state() falha — e o gate bloqueia por
    # fail-closed (ADR-0006). Faz parte do schema, não do runtime.
    op.execute(
        """
        INSERT INTO risk_circuit_breaker_state (id, tripped)
        VALUES (1, FALSE)
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE risk_circuit_breaker_state")
    op.execute("DROP TABLE risk_daily_pnl")
    op.execute("DROP TABLE risk_positions")
