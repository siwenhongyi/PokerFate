from __future__ import annotations

import ssl

from pf_intercept.config import SERVER_CERT, SERVER_KEY


def _make_server_ssl() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
    return ctx


def _make_client_ssl() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    # We often connect by selected IP while preserving WSS Host/SNI separately.
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
