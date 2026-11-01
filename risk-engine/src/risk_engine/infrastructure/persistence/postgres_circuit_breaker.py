from __future__ import annotations

import os
from datetime import UTC, date, datetime

import psycopg

from risk_engine.domain.entities import CircuitBreakerState

DEFAULT_DSN = "postgresql://quant:quant@localhost:5432/quant_platform"
_SINGLETON_ID = 1


class PostgresCircuitBreaker:
    """Estado do circuit breaker — persistido, nunca resetado automaticamente
    (ADR-0006: reset manual ou a data vira, ver `CircuitBreakerState.is_tripped_on`).

    Tabela e linha singleton vêm das migrações em `risk-engine/migrations`
    (ADR-0012); o repositório não cria schema.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("RISK_ENGINE_PG_DSN", DEFAULT_DSN)

    def get_state(self) -> CircuitBreakerState:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                "SELECT tripped, tripped_date, tripped_reason "
                "FROM risk_circuit_breaker_state WHERE id = %s",
                (_SINGLETON_ID,),
            ).fetchone()
            if row is None:
                raise RuntimeError("linha singleton do circuit breaker ausente — schema corrompido")
            return CircuitBreakerState(tripped=row[0], tripped_date=row[1], tripped_reason=row[2])

    def trip(self, reason: str, as_of: date) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                UPDATE risk_circuit_breaker_state
                SET tripped = TRUE, tripped_date = %s, tripped_reason = %s
                WHERE id = %s
                """,
                (as_of, reason, _SINGLETON_ID),
            )
            conn.commit()

    def reset(self, actor: str) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                UPDATE risk_circuit_breaker_state
                SET tripped = FALSE, reset_at = %s, reset_by = %s
                WHERE id = %s
                """,
                (datetime.now(UTC), actor, _SINGLETON_ID),
            )
            conn.commit()
