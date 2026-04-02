"""TLS для gRPC к SmartSpeech: при verify_ssl=False доверяем листовому сертификату сокета.

В Python gRPC нет флага «verify=False»; типовой обход — передать PEM полученного при
непроверенном TLS рукопожатии как ``root_certificates`` (см. обсуждения grpc/grpc).
"""

from __future__ import annotations

import base64
import socket
import ssl
from functools import lru_cache

import grpc


def parse_grpc_target(target: str) -> tuple[str, int]:
    t = (target or "").strip()
    if not t:
        raise ValueError("empty gRPC target")
    if t.startswith("["):
        end = t.find("]")
        if end != -1 and end + 1 < len(t) and t[end + 1] == ":":
            host = t[1:end]
            port_s = t[end + 2 :]
            return host, int(port_s)
    if ":" in t:
        host, _, port_s = t.rpartition(":")
        if port_s.isdigit():
            return host.strip(), int(port_s)
    return t, 443


def _der_cert_to_pem(der: bytes) -> bytes:
    b64 = base64.standard_b64encode(der)
    lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    body = b"\n".join(lines) + b"\n"
    return b"-----BEGIN CERTIFICATE-----\n" + body + b"-----END CERTIFICATE-----\n"


def _fetch_peer_leaf_pem(host: str, port: int, timeout: float = 15.0) -> bytes:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as raw:
        with ctx.wrap_socket(raw, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    if not der:
        raise OSError("TLS: пустой peer certificate")
    return _der_cert_to_pem(der)


@lru_cache(maxsize=32)
def smartspeech_channel_credentials(grpc_target: str, verify_ssl: bool) -> grpc.ChannelCredentials:
    """Кэш по целевому хосту и режиму проверки (повторные потоки не ходят за PEM)."""
    if verify_ssl:
        return grpc.ssl_channel_credentials()
    host, port = parse_grpc_target(grpc_target)
    pem = _fetch_peer_leaf_pem(host, port)
    return grpc.ssl_channel_credentials(root_certificates=pem)
