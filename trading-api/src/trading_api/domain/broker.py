from __future__ import annotations

from typing import Protocol

from trading_api.domain.entities import AccountBalance, OrderRequest, OrderState, Position


class BrokerError(Exception):
    """Base para erros do adapter de corretora — nunca deixe um erro de broker
    propagar como `Exception` genérica (spec: erros são tipados)."""


class BrokerConnectionError(BrokerError):
    """Falha transitória (rede, timeout). Seguro reenviar com o mesmo
    `client_order_id` — o contrato de idempotência do `BrokerAdapter` garante
    que isso não duplica ordem."""


class BrokerRejectionError(BrokerError):
    """Corretora recusou a ordem por motivo de negócio (saldo insuficiente,
    símbolo inválido, mercado fechado). Definitivo — retry automático sem
    mudar a ordem não faz sentido."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class BrokerAuthenticationError(BrokerError):
    """Credencial inválida, expirada ou revogada. Crítico — nunca deve ser
    engolido silenciosamente; deve propagar para acionar alerta (ADR-0009)."""


class BrokerAdapter(Protocol):
    """Port de execução de ordens — implementado por `SimulatedBrokerAdapter`
    (paper trading, ADR-0008) e, futuramente, por um adapter de corretora
    real. Nenhum código de orquestração (`trading-api.application`) deve
    depender de detalhes de uma corretora específica, só deste contrato.

    Regras que **toda** implementação precisa respeitar (ver docs/spec.md):
    1. `submit_order` é idempotente por `client_order_id` — reenviar o
       mesmo id nunca cria ordem duplicada.
    2. `cancel_order` de ordem já `FILLED`/`CANCELLED` não é erro.
    3. `get_order_state` devolve `None` só se o id nunca foi submetido;
       resultado ambíguo é `OrderState(status=UNKNOWN)`, nunca `None`.
    4. Erros são sempre uma subclasse de `BrokerError`.
    """

    def submit_order(self, request: OrderRequest) -> OrderState: ...

    def get_order_state(self, client_order_id: str) -> OrderState | None: ...

    def cancel_order(self, client_order_id: str) -> OrderState: ...

    def list_open_orders(self) -> list[OrderState]: ...

    def get_positions(self) -> list[Position]: ...

    def get_account_balance(self) -> AccountBalance: ...
