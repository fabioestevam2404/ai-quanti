from __future__ import annotations

from datetime import date

from risk_engine.infrastructure.persistence.postgres_circuit_breaker import PostgresCircuitBreaker


def test_estado_inicial_nao_esta_disparado(postgres_dsn: str) -> None:
    breaker = PostgresCircuitBreaker(dsn=postgres_dsn)

    state = breaker.get_state()

    assert state.tripped is False
    assert state.is_tripped_on(date(2026, 8, 3)) is False


def test_trip_marca_disparado_na_data(postgres_dsn: str) -> None:
    breaker = PostgresCircuitBreaker(dsn=postgres_dsn)
    today = date(2026, 8, 3)

    breaker.trip(reason="daily_loss_limit", as_of=today)
    state = breaker.get_state()

    assert state.is_tripped_on(today) is True
    assert state.tripped_reason == "daily_loss_limit"


def test_disparo_nao_vale_para_outro_dia(postgres_dsn: str) -> None:
    breaker = PostgresCircuitBreaker(dsn=postgres_dsn)
    breaker.trip(reason="daily_loss_limit", as_of=date(2026, 8, 3))

    state = breaker.get_state()

    assert state.is_tripped_on(date(2026, 8, 4)) is False


def test_reset_manual_limpa_o_disparo(postgres_dsn: str) -> None:
    breaker = PostgresCircuitBreaker(dsn=postgres_dsn)
    today = date(2026, 8, 3)
    breaker.trip(reason="daily_loss_limit", as_of=today)

    breaker.reset(actor="quant@example.com")
    state = breaker.get_state()

    assert state.is_tripped_on(today) is False
