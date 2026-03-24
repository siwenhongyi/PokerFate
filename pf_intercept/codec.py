"""
Protobuf encode / decode for PokerFate messages.

Requires compiled _pb2 modules.  Run once:

    cd pf_reverse/output/proto
    python -m grpc_tools.protoc -I Proto --python_out=../../../pf_intercept/pb Proto/*.proto

Then `from pf_intercept.pb import CSHoldem_pb2, CSGame_pb2, ...`

Until the pb2 files are generated this module falls back to returning raw bytes.
"""

from __future__ import annotations

_registry: dict[str, type] = {}   # "pb.ActionREQ" -> pb2 message class


def _register_pb2_module(module) -> None:
    """Register all message classes from a compiled _pb2 module."""
    import google.protobuf.message as _msg
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
        from pf_intercept import pb as pb_pkg
        import importlib, pkgutil
        for _, modname, _ in pkgutil.iter_modules(pb_pkg.__path__):
            mod = importlib.import_module(f"pf_intercept.pb.{modname}")
            _register_pb2_module(mod)
    except Exception:
        pass   # pb2 not compiled yet – codec will work in raw mode


_load_pb2_modules()


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
        from google.protobuf.json_format import MessageToDict
        return MessageToDict(msg, preserving_proto_field_name=True, including_default_value_fields=False)
    except Exception:
        return None


def encode(type_name: str, fields: dict) -> bytes:
    """
    Encode a dict into a protobuf body.
    Returns empty bytes if the message class is not registered or encoding fails.
    """
    cls = _registry.get(type_name)
    if cls is None:
        return b""
    try:
        from google.protobuf.json_format import ParseDict
        msg = ParseDict(fields, cls())
        return msg.SerializeToString()
    except Exception:
        return b""
