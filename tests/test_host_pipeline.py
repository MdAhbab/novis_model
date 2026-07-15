"""End-to-end host pipeline test, no hardware or BLE required.

Exercises the full path a real frame takes:
  build_frame -> seal (AEAD) -> fragment -> reassemble -> open -> parse_frame
  -> FrameAssembler -> NOVISNet forward

Run from NOVIS_Model:  python tests/test_host_pipeline.py
(Also pytest-compatible.) Needs `cryptography` and `torch`.
"""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from host import protocol as P  # noqa: E402
from host.assemble import FrameAssembler  # noqa: E402
from host.crypto import Session  # noqa: E402
from novis.models import NOVISNet  # noqa: E402


def _make_frames():
    therm = np.full((24, 32), 2000, dtype="<i2")
    therm[11:16, :] += 800
    pcm = np.zeros(P.ECHO_SAMPLES, dtype="<i2")
    pcm[200:230] = 8000
    son = struct.pack("<HHBBBB", 1500, 2200, 0x03, 0, 0, 0)
    return [
        P.build_frame(P.THERMAL, 0, 123, therm.tobytes()),
        P.build_frame(P.ECHO, 0, 124, pcm.tobytes()),
        P.build_frame(P.SONAR, 0, 125, son),
    ]


def test_frame_roundtrip_through_crypto_and_fragmentation():
    session = Session(bytes(range(32)), b"\x01\x02\x03\x04")
    reasm = P.Reassembler()
    asm = FrameAssembler()

    for msg_id, frame in enumerate(_make_frames()):
        sealed = session.seal(counter=msg_id, frame=frame)
        recovered = None
        for chunk in P.fragment(sealed, msg_id):
            got = reasm.push(chunk)
            if got is not None:
                recovered = got
        assert recovered == sealed, "fragmentation round-trip failed"
        opened = session.open(recovered)
        assert opened == frame, "AEAD round-trip failed"
        asm.update(P.parse_frame(opened))

    assert asm.seen == {"thermal": True, "echo": True, "sonar": True}
    print("crypto + fragmentation + parse round-trip ok")


def test_bad_tag_rejected():
    session = Session(bytes(range(32)), b"\x01\x02\x03\x04")
    sealed = bytearray(session.seal(1, _make_frames()[0]))
    sealed[-1] ^= 0xFF  # corrupt the Poly1305 tag
    try:
        session.open(bytes(sealed))
        raise AssertionError("corrupted tag was not rejected")
    except Exception:
        print("corrupted tag correctly rejected")


def test_assembled_input_runs_through_model():
    asm = FrameAssembler()
    for frame in _make_frames():
        asm.update(P.parse_frame(frame))
    x = asm.model_input()
    assert x["thermal"].shape == (1, 1, 24, 32)
    assert x["echo"].shape == (1, 2, 64, 64)
    assert x["sonar"].shape == (1, 10)
    assert tuple(x["mask"][0].tolist()) == (1.0, 1.0, 1.0)

    torch.manual_seed(0)
    model = NOVISNet(dim=128, depth=6, heads=4, decoder_chs=(96, 64, 48)).eval()
    with torch.no_grad():
        out = model(x["thermal"], x["echo"], x["sonar"], x["mask"])
    assert out["gray"].shape == (1, 1, 96, 128)
    assert out["ab"].shape == (1, 2, 96, 128)
    assert torch.isfinite(out["gray"]).all()
    print("assembled input runs through NOVISNet ok")


if __name__ == "__main__":
    test_frame_roundtrip_through_crypto_and_fragmentation()
    test_bad_tag_rejected()
    test_assembled_input_runs_through_model()
    print("ALL HOST PIPELINE TESTS PASSED")
