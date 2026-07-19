"""FastAPI app: serves NOVISNet and the built React frontend.

Run from NOVIS_Model (run.py does this for you):
  uvicorn novis.server.app:app --port 8000

Environment:
  NOVIS_CONFIG  config path relative to NOVIS_Model (default configs/base.yaml)
  NOVIS_CKPT    checkpoint path (default: newest checkpoints/*/best.pt)
  NOVIS_DEVICE  cuda | cpu (default: auto)
"""

from __future__ import annotations

import asyncio
import io
import os
import time
import threading
import uuid
from pathlib import Path

import numpy as np
from fastapi import (Depends, FastAPI, Form, Header, HTTPException,
                     UploadFile, WebSocket, WebSocketDisconnect)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

from novis.data import degradation as D

from .service import InferenceService, ROOT

app = FastAPI(title="NOVIS", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

_service: InferenceService | None = None
_service_lock = threading.Lock()

def service() -> InferenceService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = InferenceService(
                    config=os.environ.get("NOVIS_CONFIG", "configs/base.yaml"),
                    ckpt=os.environ.get("NOVIS_CKPT") or None,
                    device=os.environ.get("NOVIS_DEVICE") or None)
    return _service


class InferRequest(BaseModel):
    sample_id: int | None = None
    seed: int | None = None
    mask: list[bool] | None = None      # [thermal, echo, sonar] override


@app.get("/api/model")
def api_model():
    return service().model_info()


@app.get("/api/samples")
def api_samples():
    return {"samples": service().sample_summaries()}


@app.post("/api/infer")
def api_infer(req: InferRequest):
    svc = service()
    sample = svc.demo_sample(req.sample_id, req.seed)
    if req.mask is not None:
        sample = {**sample,
                  "mask": np.asarray([1.0 if v else 0.0 for v in req.mask],
                                     np.float32)}
    return {
        "inputs": svc.render_inputs(sample),
        "truth": svc.render_truth(sample),
        "outputs": svc.infer(sample),
    }


@app.post("/api/infer/upload")
async def api_infer_upload(file: UploadFile):
    """Run on an uploaded .npz with thermal/echo/sonar (and optional mask)."""
    svc = service()
    raw = await file.read()
    try:
        z = np.load(io.BytesIO(raw))
    except Exception:
        raise HTTPException(400, "not a readable .npz file")
    sample = {
        "thermal": np.zeros((1, 24, 32), np.float32),
        "echo": np.zeros((2, 64, 64), np.float32),
        "sonar": np.zeros(10, np.float32),
        "mask": np.zeros(3, np.float32),
    }
    names = set(z.files)
    try:
        for i, key in enumerate(("thermal", "echo", "sonar")):
            if key in names:
                a = np.asarray(z[key], np.float32)
                if a.shape != sample[key].shape:
                    raise HTTPException(
                        400, f"{key} must have shape {sample[key].shape}, "
                             f"got {tuple(a.shape)}")
                sample[key] = a
                sample["mask"][i] = 1.0
        if "mask" in names:
            sample["mask"] = np.asarray(z["mask"], np.float32).reshape(3)
    finally:
        z.close()
        
    if sample["mask"].sum() == 0:
        raise HTTPException(400, "npz contains none of thermal/echo/sonar")
    return {
        "inputs": svc.render_inputs(sample),
        "truth": None,
        "outputs": svc.infer(sample),
    }


@app.get("/api/runs")
def api_runs():
    return {"runs": service().list_runs(),
            "results": service().results_metrics()}


# -------------------------------------------------------- continual learning

def _require_novis_header(x_novis: str | None = Header(None)):
    """Require a custom header on state-mutating endpoints.

    A custom header turns a cross-origin request into one that needs a
    CORS preflight, which the CORS policy above rejects for foreign
    origins. Without this, a malicious page open in the operator's browser
    could mutate the served model with a simple form POST.
    """
    if x_novis is None:
        raise HTTPException(
            403, "missing X-Novis header; send 'X-Novis: 1' with this request")


@app.post("/api/continual/enable",
          dependencies=[Depends(_require_novis_header)])
def api_continual_enable():
    return service().enable_continual()


@app.post("/api/continual/disable",
          dependencies=[Depends(_require_novis_header)])
def api_continual_disable():
    return service().disable_continual()


@app.get("/api/continual/status")
def api_continual_status():
    return service().continual_status()


@app.post("/api/continual/feedback",
          dependencies=[Depends(_require_novis_header)])
async def api_continual_feedback(file: UploadFile,
                                 infer_id: str | None = Form(None)):
    """Accept a ground-truth photograph for the most recent inference.

    Accepts PNG, JPEG, or any PIL-readable format. The image is EXIF
    orientation corrected, center-cropped to the output aspect ratio,
    resized to the output resolution, and converted to the same CIELAB
    L* luminance target the model was trained on. Pass the ``infer_id``
    returned by the inference being corrected to guard against pairing
    the photograph with a newer inference.
    """
    svc = service()
    raw = await file.read()
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(raw))
        im = ImageOps.exif_transpose(im).convert("RGB")
        H, W = svc.out_hw
        # Center-crop to the output aspect ratio so the target is not
        # anisotropically distorted, then resize.
        w, h = im.size
        if w * H > h * W:                       # wider than target
            new_w = round(h * W / H)
            x0 = (w - new_w) // 2
            im = im.crop((x0, 0, x0 + new_w, h))
        elif w * H < h * W:                     # taller than target
            new_h = round(w * H / W)
            y0 = (h - new_h) // 2
            im = im.crop((0, y0, w, y0 + new_h))
        im = im.resize((W, H), Image.Resampling.LANCZOS)
        rgb = np.asarray(im, dtype=np.float32) / 255.0
        # Same luminance definition as the training targets (CIELAB L*),
        # not the ITU-R 601 luma of PIL's convert("L").
        truth_gray = D.lab_targets(rgb)[0]
    except Exception:
        raise HTTPException(400, "could not read the image file")
    try:
        # The gradient step is seconds of work; keep it off the event loop.
        result = await asyncio.to_thread(
            svc.feedback, truth_gray, None, infer_id)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return result


# -------------------------------------------------------- model bundle export

def _remove_quiet(path: Path):
    try:
        os.remove(path)
    except OSError:
        pass


@app.get("/api/export/bundle")
def api_export_bundle():
    """Download a portable zip bundle of the current model state."""
    from .bundle import create_bundle
    svc = service()
    if not svc.trained:
        raise HTTPException(
            409, "no trained checkpoint is loaded; refusing to export "
                 "untrained weights")
    # Per-request file: concurrent exports cannot truncate a zip that is
    # still streaming to another client. Deleted after the response.
    out_path = ROOT / "results" / f"novis_bundle_{uuid.uuid4().hex[:8]}.zip"
    create_bundle(svc, out_path)
    return FileResponse(
        path=str(out_path),
        media_type="application/zip",
        filename="novis_bundle.zip",
        background=BackgroundTask(_remove_quiet, out_path),
    )


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    """Streams the animated demo scene through the model."""
    await ws.accept()
    svc = service()
    t0 = time.perf_counter()
    try:
        while True:
            t = time.perf_counter() - t0
            sample = svc.animated_sample(t)
            # cache=False: synthetic live frames must never become the
            # target of a continual-learning correction.
            frame = await asyncio.to_thread(svc.infer, sample, None, False)
            frame["t"] = round(t, 2)
            frame["thermal_png"] = svc.render_inputs(sample)["thermal_png"]
            frame["truth_gray_png"] = svc.render_truth(sample)["gray_png"]
            await ws.send_json(frame)
            # Pace the stream; account for inference and JSON encoding latency.
            elapsed = time.perf_counter() - (t0 + t)
            await asyncio.sleep(max(0.05, 0.25 - elapsed))
    except (WebSocketDisconnect, RuntimeError):
        return


# Serve the built frontend when it exists (python run.py builds it).
_dist = ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="app")

