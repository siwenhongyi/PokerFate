import logging

import websockets.exceptions

from pf_intercept.proxy import _ExpectedHandshakeNoiseFilter


def _record(exc: BaseException) -> logging.LogRecord:
    return logging.LogRecord(
        name="pf_proxy.websockets",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="opening handshake failed",
        args=(),
        exc_info=(type(exc), exc, exc.__traceback__),
    )


def test_expected_handshake_eof_noise_is_suppressed():
    exc = websockets.exceptions.InvalidMessage(
        "did not receive a valid HTTP request"
    )
    exc.__cause__ = EOFError("connection closed while reading HTTP request line")

    assert not _ExpectedHandshakeNoiseFilter().filter(_record(exc))


def test_unexpected_handshake_errors_are_kept():
    exc = websockets.exceptions.InvalidMessage("unsupported HTTP version")

    assert _ExpectedHandshakeNoiseFilter().filter(_record(exc))
