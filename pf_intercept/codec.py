"""
Protobuf encode / decode for PokerFate messages.

Requires compiled _pb2 modules.  Run once:

    cd pf_reverse/output/proto
    python -m grpc_tools.protoc -I Proto --python_out=../../../pf_intercept/pb Proto/*.proto

Then `from pf_intercept.pb import CSHoldem_pb2, CSGame_pb2, ...`

encode() returns None if the type is unknown or parsing fails; otherwise bytes (possibly empty for messages with no fields, e.g. StandUpREQ).
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

from google.protobuf import message as _msg
from google.protobuf.json_format import MessageToDict, ParseDict

_registry: dict[str, type] = {}   # "pb.ActionREQ" -> pb2 message class


def _register_pb2_module(module) -> None:
    """Register all message classes from a compiled _pb2 module."""
    for name in dir(module):
        cls = getattr(module, name)
        try:
            if isinstance(cls, type) and issubclass(cls, _msg.Message):
                full_name = f"pb.{name}"
                _registry[full_name] = cls
        except TypeError:
            pass


def _load_pb2_modules() -> None:
    """Try to import compiled pb2 modules (best-effort)."""
    try:
        pb_pkg = importlib.import_module("pf_intercept.pb")

        # Generated pb2 files may use top-level imports like `import X_pb2`.
        # Ensure those imports resolve while loading package modules.
        pb_dir = str(Path(pb_pkg.__path__[0]).resolve())
        added_pb_dir = False
        if pb_dir not in sys.path:
            sys.path.insert(0, pb_dir)
            added_pb_dir = True
        try:
            for _, modname, _ in pkgutil.iter_modules(pb_pkg.__path__):
                mod = importlib.import_module(f"pf_intercept.pb.{modname}")
                _register_pb2_module(mod)
        finally:
            if added_pb_dir and pb_dir in sys.path:
                sys.path.remove(pb_dir)
    except Exception:
        pass   # pb2 not compiled yet – codec will work in raw mode


_load_pb2_modules()


def _message_to_dict_compat(msg) -> dict:
    """
    Convert protobuf message to dict across protobuf 4/5/6 runtimes.
    """
    try:
        return MessageToDict(
            msg,
            preserving_proto_field_name=True,
            including_default_value_fields=False,
        )
    except TypeError:
        # protobuf>=6 removed `including_default_value_fields`.
        return MessageToDict(msg, preserving_proto_field_name=True)


def decode(type_name: str, pb_body: bytes) -> dict | None:
    """
    Decode a protobuf body into a dict.
    Returns None if the message class is not registered or decoding fails.
    """
    cls = _registry.get(type_name)
    if cls is None:
        return None
    try:
        msg = cls()
        msg.ParseFromString(pb_body)
        return _message_to_dict_compat(msg)
    except Exception:
        return None


def encode(type_name: str, fields: dict) -> bytes | None:
    """
    Encode a dict into a protobuf body.

    Returns:
        bytes — success (may be b"" for messages with no fields, e.g. StandUpREQ)
        None — unknown type or ParseDict / serialize error
    """
    cls = _registry.get(type_name)
    if cls is None:
        return None
    try:
        msg = ParseDict(fields, cls())
        return msg.SerializeToString()
    except Exception:
        return None
