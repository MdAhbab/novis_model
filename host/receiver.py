"""BLE receiver: connect to the NOVIS node, decrypt, assemble, and infer.

Uses `bleak`, a cross-platform BLE client (pip install bleak). This module is
imported only when --source ble is chosen, so the offline pipeline test does
not require bleak or hardware.

Handshake note: this skeleton uses a placeholder all-zero key and salt to match
the firmware skeleton. Before real use, implement the HKDF handshake over the
control characteristic and set the Session from its result. Do not ship the
placeholder key.
"""

from __future__ import annotations

import asyncio

from . import protocol as P
from .assemble import FrameAssembler
from .crypto import Session
from .live_infer import infer


async def _run(model, address_or_name: str = "NOVIS-Node",
               infer_every: int = 8):
    from bleak import BleakClient, BleakScanner

    print(f"scanning for {address_or_name} ...")
    device = await BleakScanner.find_device_by_name(address_or_name)
    if device is None:
        raise RuntimeError(f"device {address_or_name!r} not found")

    session = Session(bytes(P.KEY_BYTES), bytes(P.SALT_BYTES))  # placeholder
    reasm = P.Reassembler()
    asm = FrameAssembler()
    frames_since = 0

    def on_notify(_char, data: bytearray):
        nonlocal frames_since
        msg = reasm.push(bytes(data))
        if msg is None:
            return
        try:
            frame = P.parse_frame(session.open(msg))
        except Exception as e:            # bad tag, dropped fragment, etc.
            print("frame dropped:", e)
            return
        asm.update(frame)
        frames_since += 1
        if frames_since >= infer_every and asm.ready():
            frames_since = 0
            out = infer(model, asm)
            gray = out["gray"][0]
            print(f"frame: gray mean {gray.mean():.3f} "
                  f"depth {out['depth_m'].mean():.2f} m")

    async with BleakClient(device) as client:
        await client.start_notify(P.STREAM_UUID, on_notify)
        print("connected; receiving. Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1.0)


def run_ble(model, address_or_name: str = "NOVIS-Node"):
    try:
        asyncio.run(_run(model, address_or_name))
    except KeyboardInterrupt:
        print("stopped.")
