"""
PokerFate wire frame encode / decode.

Frame layout (derived from Net.lua packNetData / onRecv):

    [4B total_len BE] [2B type_len BE] [N B type_name] [4B room_id BE] [M B pb_body]

    total_len = 2 + len(type_name) + 4 + len(pb_body)
    full frame = 4 + total_len bytes
"""

import struct
from dataclasses import dataclass


@dataclass
class Frame:
    type_name: str   # e.g. "pb.ActionREQ"
    room_id:   int
    pb_body:   bytes


def decode_frame(data: bytes) -> tuple[Frame, bytes] | tuple[None, bytes]:
    """
    Try to decode one frame from the front of `data`.
    Returns (Frame, remaining_bytes) or (None, data) if incomplete.
    """
    if len(data) < 6:
        return None, data

    total_len = struct.unpack_from(">I", data, 0)[0]
    full_len  = 4 + total_len

    if len(data) < full_len:
        return None, data

    type_len  = struct.unpack_from(">H", data, 4)[0]
    name_end  = 6 + type_len
    type_name = data[6:name_end].decode("utf-8")
    room_id   = struct.unpack_from(">I", data, name_end)[0]
    pb_body   = data[name_end + 4:full_len]

    return Frame(type_name, room_id, pb_body), data[full_len:]


def encode_frame(type_name: str, room_id: int, pb_body: bytes) -> bytes:
    """Encode one frame ready to send on the wire."""
    t         = type_name.encode("utf-8")
    total_len = 2 + len(t) + 4 + len(pb_body)
    return (
        struct.pack(">IH", total_len, len(t))
        + t
        + struct.pack(">I", room_id)
        + pb_body
    )


class FrameBuffer:
    """Accumulates incoming bytes and yields complete frames."""

    def __init__(self) -> None:
        self._buf = b""

    @property
    def pending(self) -> bytes:
        """Trailing bytes that are not yet a complete frame (forward verbatim)."""
        return self._buf

    def feed(self, data: bytes) -> list[Frame]:
        self._buf += data
        frames: list[Frame] = []
        while True:
            frame, self._buf = decode_frame(self._buf)
            if frame is None:
                break
            frames.append(frame)
        return frames
