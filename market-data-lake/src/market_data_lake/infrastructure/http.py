"""Sessão HTTP com o repositório de certificados do sistema operacional.

Funciona em rede com inspeção TLS (proxy/antivírus corporativo) sem desligar
a verificação de certificado: o mesmo princípio do UV_SYSTEM_CERTS no uv.
"""

from __future__ import annotations

import ssl
from typing import Any

import requests
import truststore
from requests.adapters import HTTPAdapter


class _SystemTrustAdapter(HTTPAdapter):
    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        kwargs["ssl_context"] = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        super().init_poolmanager(*args, **kwargs)


def system_trust_session() -> requests.Session:
    session = requests.Session()
    session.mount("https://", _SystemTrustAdapter())
    return session
