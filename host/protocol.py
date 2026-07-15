"""NOVIS wire protocol (host side).

Byte-for-byte mirror of firmware/novis_node/protocol.h. If one changes, change
both. Layering, outermost last:

  frame     = 12-byte header + payload            (plaintext)
  message   = 8-byte counter + AEAD(frame) + tag  (encrypted, see crypto.py)
  fragment  = 4-byte transport header + chunk      (BLE notification unit)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# Frame types
THERMAL = 0x01
ECHO = 0x02
SONAR = 0x03

HEADER_BYTES = 12
THERMAL_PIXELS = 768
THERMAL_BYTES = THERMAL_PIXELS * 2
ECHO_SAMPLES = 960
ECHO_BYTES = ECHO_SAMPLES * 2
SONAR_BYTES = 8

TAG_BYTES = 16
COUNTER_BYTES = 8
SALT_BYTES = 4
KEY_BYTES = 32

FRAG_HEADER_BYTES = 4
FRAG_PAYLOAD_MAX = 180

SERVICE_UUID = "4e4f5649-5300-4000-8000-000000000001"
STREAM_UUID = "4e4f5649-5300-4000-8000-000000000002"
CONTROL_UUID = "4e4f5649-5300-4000-8000-000000000003"

PAYLOAD_BYTES = {THERMAL: THERMAL_BYTES, ECHO: ECHO_BYTES, SONAR: SONAR_BYTES}


@dataclass
class Frame:
    type: int
    seq: int
    ts_ms: int
    payload: bytes


def build_frame(ftype: int, seq: int, ts_ms: int, payload: bytes) -> bytes:
    """Header (12 bytes LE) + payload. ts_ms is truncated to 48 bits."""
    hdr = bytearray(HEADER_BYTES)
    hdr[0] = ftype & 0xFF
    hdr[1] = 0
    struct.pack_into("<I", hdr, 2, seq & 0xFFFFFFFF)
    ts = ts_ms & ((1 << 48) - 1)
    for i in range(6):
        hdr[6 + i] = (ts >> (8 * i)) & 0xFF
    return bytes(hdr) + payload


def parse_frame(frame: bytes) -> Frame:
    if len(frame) < HEADER_BYTES:
        raise ValueError("frame shorter than header")
    ftype = frame[0]
    seq = struct.unpack_from("<I", frame, 2)[0]
    ts = 0
    for i in range(6):
        ts |= frame[6 + i] << (8 * i)
    return Frame(ftype, seq, ts, frame[HEADER_BYTES:])


def fragment(msg: bytes, msg_id: int) -> list[bytes]:
    """Split an encrypted message into BLE-notification-sized chunks."""
    n = len(msg)
    count = (n + FRAG_PAYLOAD_MAX - 1) // FRAG_PAYLOAD_MAX
    out = []
    for i in range(count):
        off = i * FRAG_PAYLOAD_MAX
        chunk = msg[off: off + FRAG_PAYLOAD_MAX]
        hdr = struct.pack("<HBB", msg_id & 0xFFFF, i, count)
        out.append(hdr + chunk)
    return out


class Reassembler:
    """Collects fragments by msg_id and returns a full message when complete."""

    def __init__(self):
        self._parts: dict[int, dict[int, bytes]] = {}
        self._counts: dict[int, int] = {}

    def push(self, chunk: bytes) -> bytes | None:
        if len(chunk) < FRAG_HEADER_BYTES:
            return None
        msg_id, idx, count = struct.unpack_from("<HBB", chunk, 0)
        data = chunk[FRAG_HEADER_BYTES:]
        parts = self._parts.setdefault(msg_id, {})
        parts[idx] = data
        self._counts[msg_id] = count
        if len(parts) == count:
            msg = b"".join(parts[i] for i in range(count))
            del self._parts[msg_id]
            del self._counts[msg_id]
            return msg
        return None
