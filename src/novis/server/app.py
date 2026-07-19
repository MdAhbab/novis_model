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
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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

@app.post("/api/continual/enable")
def api_continual_enable():
    return service().enable_continual()


@app.post("/api/continual/disable")
def api_continual_disable():
    return service().disable_continual()


@app.get("/api/continual/status")
def api_continual_status():
    return service().continual_status()


@app.post("/api/continual/feedback")
async def api_continual_feedback(file: UploadFile):
    """Accept a ground-truth grayscale image for the most recent inference.

    The image is resized to match the model output resolution and used for
    one supervised gradient step. Accepts PNG, JPEG, or any PIL-readable
    format. The image is converted to single-channel grayscale and normalized
    to [0, 1].
    """
    svc = service()
    raw = await file.read()
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("L")
        H, W = svc.out_hw
        if im.size != (W, H):
            im = im.resize((W, H), Image.LANCZOS)
        truth_gray = np.asarray(im, dtype=np.float32) / 255.0
    except Exception:
        raise HTTPException(400, "could not read the image file")
    try:
        result = svc.feedback(truth_gray)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return result


# -------------------------------------------------------- model bundle export

@app.get("/api/export/bundle")
def api_export_bundle():
    """Download a portable zip bundle of the current model state."""
    from .bundle import create_bundle
    svc = service()
    out_path = ROOT / "results" / "novis_bundle.zip"
    create_bundle(svc, out_path)
    return FileResponse(
        path=str(out_path),
        media_type="application/zip",
        filename="novis_bundle.zip",
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
            frame = await asyncio.to_thread(svc.infer, sample)
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

