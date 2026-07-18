# NOVIS_Model

Training and inference code, the browser interface, the sensor-node firmware,
and the host receiver for **NOVIS** (Non-Optical Visual Inference System):
reconstructing grayscale images, metric depth, and optionally inferred color
(with a confidence map) from a 32x24 thermopile array, ultrasonic ranges, and
active chirp echoes. No camera at inference time.

The model is a workstation-class research system: it trains and serves on a
single consumer GPU (an RTX 5070 Ti) and is used from a browser. A compact
edge variant (`configs/edge_small.yaml`) is kept for future phone-class
deployment work but is not part of the current results.

This repository holds the complete system: the model, the training and export
pipeline, the FastAPI server plus React frontend (`src/novis/server/`,
`frontend/`), the nRF52840 node firmware (`firmware/`), and the Python host
that receives, decrypts, and runs inference (`host/`). The research paper and
its design documents live in a separate companion project.

## Setup on the training PC (Windows, RTX 5070 Ti)

The RTX 5070 Ti is a Blackwell GPU: it needs PyTorch built for CUDA 12.8 or
newer. Python 3.11+ and Node.js 20+ (for the frontend) recommended.

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

## Quick start: the browser interface

```bat
python run.py
```

That builds the React frontend on first use (npm install + build), starts the
FastAPI server, loads the newest `checkpoints/*/best.pt` that matches the
config, and opens the console in your browser:

- **Reconstruct** - run demo scenes or uploaded `.npz` recordings through the
  model; toggle sensors on and off; optionally colorize with a confidence
  gate (color is inferred, not measured, and is off by default).
- **Live stream** - an animated scene reconstructed continuously over a
  WebSocket.
- **Training** - loss and metric curves for every run under `checkpoints/`.
- **Model** - architecture, parameters, device, and the resolved config.

Useful flags: `--dev` (vite hot reload), `--build` (rebuild frontend),
`--config`, `--ckpt`, `--port`, `--no-browser`.

With no trained checkpoint the interface still works but shows an
"untrained weights" banner and the reconstructions are noise.

## Verify the full loop without downloads

```bat
python train.py --config configs/debug_tiny.yaml --data synthetic
python eval.py  --config configs/debug_tiny.yaml --ckpt checkpoints/debug_tiny/best.pt --data synthetic
python export.py --config configs/debug_tiny.yaml --ckpt checkpoints/debug_tiny/best.pt
python run.py --config configs/debug_tiny.yaml
```

`eval.py` writes `results/metrics.json` and a visual grid at
`results/samples/eval_grid.png`.

## Real training (the paper runs)

1. Download datasets per `data/raw/README.md` and run the prepare scripts
   (they emit shards at 192x256, matching `data.out_hw`).
2. Stage A (thermal): `python train.py --config configs/thermal_llvip.yaml --data shards --train-shards data/processed/llvip/train --val-shards data/processed/llvip/val`
3. Stage B (echoes): same with `configs/echo_batvision.yaml` and the
   batvision shards.
4. Stage C (fusion): `configs/fusion_full.yaml` on the combined shard folders,
   seeded from Stage A/B weights via `--init-from`. This stage enables the
   perceptual and adversarial terms.
5. Stage D (prototype fine-tune) runs after the real capture exists.

Interrupted runs continue with `--resume checkpoints/<run>/latest.pt`.
Training uses bfloat16 autocast, TF32, channels-last, fused AdamW, and an EMA
of the weights; `best.pt` holds the EMA (release) weights and is what eval,
export, and the server load. Batch 32 at 192x256 fits comfortably in the
5070 Ti's 16 GB.

## Model at a glance

Thermal 24x32 -> 192 grid tokens (plus a 24x32 skip map); echo spectrograms
-> 24 tokens; sonar -> 4 tokens. Learned mask tokens stand in for absent
modalities (modality dropout 0.3 during fusion training). Fourteen sandwich
blocks (depthwise local mixing + 8-head attention + gated FFN, dim 320) fuse
the 220 tokens; a 4-stage PixelShuffle decoder with squeeze-excitation
upsamples 12x16 -> 192x256 and injects the thermal skip at 24x32. Heads:
grayscale and inverse depth always; ab color and a color log-variance
(confidence) behind `model.color_head`. About 27 M parameters. Losses:
L1 + SSIM + VGG16 perceptual on grayscale, masked L1 + smoothness on inverse
depth, heteroscedastic L1 on color, optional PatchGAN hinge term in the
fusion stage. Sources for the design choices are cited in the methodology.

Color is a prediction, not a measurement: none of the sensors observe
reflectance, so the color head learns scene priors and reports per-pixel
confidence. The interface renders color only when asked, gated by that
confidence.

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
  run.py              one-command launcher (server + frontend)
  configs/            base + per-stage YAML configs (+ edge_small for future work)
  data/raw/           dataset downloads (see its README)
  data/processed/     .npz training shards written by scripts/
  data/real_capture/  prototype recordings (Stage D)
  scripts/            dataset -> shard converters
  src/novis/          package: data, models, losses, metrics, engine, server
  frontend/           React + Vite browser console
  firmware/novis_node/ nRF52840 node firmware skeleton
  host/               BLE receiver, AEAD, frame assembly, live inference
  tests/              smoke test + host pipeline test
  train.py eval.py export.py
  checkpoints/<run>/  best.pt latest.pt log.csv history.json
  results/            metrics.json, samples/, exported ONNX
```

## Future work

Phone-class deployment (the `edge_small` variant, int8 quantization, Core ML
/ mobile runtimes, and a companion mobile app) is deliberately out of scope
for this version; the ONNX export from `export.py` is the starting point.
