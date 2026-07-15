# NOVIS host

Receives encrypted sensor frames from the NOVIS node over Bluetooth Low Energy,
decrypts and reassembles them, and runs NOVISNet to produce a grayscale image,
depth, color, and a color-confidence map.

## Install

```bat
pip install cryptography bleak
```

`cryptography` provides ChaCha20-Poly1305. `bleak` is the cross-platform BLE
client and is needed only for the live `--source ble` path. The rest of the
pipeline (protocol, crypto, assembly, inference) runs without it.

## Try it without hardware

```bat
python -m host.live_infer --source synthetic --config configs/base.yaml
```

This feeds synthetic frames through the exact deployment path (build frame,
seal, fragment, reassemble, open, parse, assemble, infer) and writes
`results/live_output.npz`. Add `--ckpt checkpoints/<run>/best.pt` to use trained
weights instead of a random model.

## Live from the node

```bat
python -m host.live_infer --source ble --config configs/fusion_full.yaml ^
    --ckpt checkpoints/fusion_full/best.pt
```

The receiver scans for a device named `NOVIS-Node`, subscribes to the stream
characteristic, and prints a summary per assembled frame.

## Files

| File | Role |
|---|---|
| `protocol.py` | frame, message, and fragment formats (mirrors firmware `protocol.h`) |
| `crypto.py` | ChaCha20-Poly1305 seal/open, nonce = counter + salt |
| `assemble.py` | buffers the latest reading per modality, builds the model input |
| `live_infer.py` | loads the model, runs it, offline synthetic demo |
| `receiver.py` | `bleak` BLE client that wires the above together |

## Security note

The skeleton uses a placeholder all-zero session key and salt to match the
firmware skeleton, so the two ends interoperate on the bench. Before any real
deployment, implement the handshake: pair with LE Secure Connections, run an
HKDF key agreement over the control characteristic, and construct the `Session`
from its result. Do not ship the placeholder key.
