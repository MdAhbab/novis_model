# NOVIS_Model

Training and inference code, plus the sensor-node firmware and host receiver,
for **NOVIS** (Non-Optical Visual Inference System): reconstructing grayscale
images, metric depth, and inferred color (with a confidence map) from a 32x24
thermopile array, ultrasonic ranges, and active chirp echoes. No camera at
inference time.

This repository holds the complete system: the model, the training and export
pipeline, the nRF52840 node firmware (`firmware/`), and the Python host that
receives, decrypts, and runs inference (`host/`). The research paper and its
design documents (methodology, literature review, figures) live in a separate
companion project and are not part of this repository.

## Setup on the training PC (Windows, RTX 5070 Ti)

The RTX 5070 Ti is a Blackwell GPU: it needs PyTorch built for CUDA 12.8 or
newer. Python 3.11 or 3.12 recommended.

```bat
cd NOVIS_Model
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```

Verify the GPU is seen, then run the smoke test:

```bat
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
python tests/test_smoke.py
```

Expected: `True`, the 5070 Ti name, and `ALL SMOKE TESTS PASSED`.

If `cuda.is_available()` is False: update the NVIDIA driver first, and make
sure torch came from the cu128 index URL above (a plain `pip install torch`
on Windows installs the CPU build).

## Quick start (no downloads needed)

Train on the built-in synthetic debug scenes to confirm the full loop:

```bat
python train.py --config configs/fusion_full.yaml --data synthetic --epochs 3
python eval.py  --config configs/fusion_full.yaml --ckpt checkpoints/fusion_full/best.pt --data synthetic
python export.py --config configs/fusion_full.yaml --ckpt checkpoints/fusion_full/best.pt
```

`eval.py` writes `results/metrics.json` and a visual grid at
`results/samples/eval_grid.png` (rows: thermal input upsampled, predicted
gray, target gray, predicted inverse depth).

## Real training (the paper runs)

1. Download datasets per `data/raw/README.md` and run the prepare scripts.
2. Stage A (thermal): `python train.py --config configs/thermal_llvip.yaml --data shards --train-shards data/processed/llvip/train --val-shards data/processed/llvip/val`
3. Stage B (echoes): same with `configs/echo_batvision.yaml` and the batvision shards.
4. Stage C (fusion): `configs/fusion_full.yaml` on the combined shard folders
   (put or symlink all shards into one train/ and one val/ folder).
5. Stage D (prototype fine-tune) runs after the real capture exists.

Training defaults (batch 64, bfloat16 autocast) fit comfortably in the
5070 Ti's 16 GB at the 96x128 output resolution.

## Prototype system (firmware and host)

The node firmware and the host receiver implement the two ends of the same
encrypted BLE protocol, defined once in `firmware/novis_node/protocol.h` and
mirrored in `host/protocol.py`.

- `firmware/novis_node/` is an nRF52840 Arduino skeleton: sensor driver stubs,
  frame building, ChaCha20-Poly1305 sealing, fragmentation, and a BLE notify
  characteristic. See `firmware/README.md`.
- `host/` receives fragments, reassembles and decrypts them, buffers the latest
  reading per modality, and runs NOVISNet. Try it without hardware:
  `python -m host.live_infer --source synthetic --config configs/base.yaml`.
  See `host/README.md`.

```bat
python tests/test_host_pipeline.py
```

exercises the whole host path (build frame, seal, fragment, reassemble, open,
parse, assemble, infer) and checks that a corrupted authentication tag is
rejected.

## Layout

```
NOVIS_Model/
  configs/            base + per-stage YAML configs
  data/raw/           dataset downloads (see its README)
  data/processed/     .npz training shards written by scripts/
  data/real_capture/  prototype recordings (Stage D)
  scripts/            dataset -> shard converters
  src/novis/          package: data, models, losses, metrics, engine
  firmware/novis_node/ nRF52840 node firmware skeleton
  host/               BLE receiver, AEAD, frame assembly, live inference
  tests/              smoke test + host pipeline test
  train.py eval.py export.py
  checkpoints/<run>/  best.pt latest.pt log.csv history.json
  results/            metrics.json, samples/, exported ONNX
```

## Model at a glance

Thermal 24x32 -> 192 grid tokens; echo spectrograms -> 24 tokens; sonar -> 4
tokens. Learned mask tokens stand in for absent modalities (modality dropout
0.3 during fusion training). Six sandwich blocks (depthwise local mixing +
4-head attention + gated FFN) fuse the 220 tokens; a 3-stage depthwise
decoder with squeeze-excitation upsamples 12x16 -> 96x128 into four heads:
gray, inverse depth, ab color, and color log-variance (confidence).
Sources for the design choices are cited in the methodology.
