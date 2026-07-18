"""One-command launcher: model server + browser interface.

  python run.py                 serve the built frontend + API on one port
  python run.py --build         rebuild the frontend first, then serve
  python run.py --dev           hot-reload dev mode (vite on 5173, API on 8000)
  python run.py --config configs/debug_tiny.yaml --ckpt checkpoints/debug_tiny/best.pt

The server picks the newest matching checkpoints/*/best.pt automatically when
--ckpt is omitted; with no checkpoint at all it serves untrained weights and
the interface says so.
"""

import argparse
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def _npm() -> str:
    npm = shutil.which("npm")
    if not npm:
        sys.exit("npm not found. Install Node.js (https://nodejs.org) and retry.")
    return npm


def ensure_frontend_built(force: bool) -> None:
    if not (FRONTEND / "node_modules").exists():
        print("[run] installing frontend dependencies (first run only)...")
        subprocess.run([_npm(), "install"], cwd=FRONTEND, check=True)
    if force or not (FRONTEND / "dist" / "index.html").exists():
        print("[run] building frontend...")
        subprocess.run([_npm(), "run", "build"], cwd=FRONTEND, check=True)


def open_browser_later(url: str, enabled: bool) -> None:
    if enabled:
        threading.Timer(1.8, lambda: webbrowser.open(url)).start()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/base.yaml")
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--device", default=None, help="cuda | cpu (default auto)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--dev", action="store_true",
                    help="vite dev server with hot reload")
    ap.add_argument("--build", action="store_true",
                    help="rebuild the frontend before serving")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    os.environ["NOVIS_CONFIG"] = args.config
    if args.ckpt:
        os.environ["NOVIS_CKPT"] = args.ckpt
    if args.device:
        os.environ["NOVIS_DEVICE"] = args.device
    sys.path.insert(0, str(ROOT / "src"))
    os.chdir(ROOT)

    import uvicorn  # imported late so --help stays fast

    if args.dev:
        print("[run] dev mode: vite on :5173, API on :%d" % args.port)
        if not (FRONTEND / "node_modules").exists():
            subprocess.run([_npm(), "install"], cwd=FRONTEND, check=True)
        vite = subprocess.Popen([_npm(), "run", "dev"], cwd=FRONTEND)
        open_browser_later("http://127.0.0.1:5173", not args.no_browser)
        try:
            uvicorn.run("novis.server.app:app", host="127.0.0.1",
                        port=args.port, log_level="info")
        finally:
            vite.terminate()
        return

    ensure_frontend_built(args.build)
    url = f"http://127.0.0.1:{args.port}"
    print(f"[run] serving NOVIS at {url}")
    open_browser_later(url, not args.no_browser)
    uvicorn.run("novis.server.app:app", host="127.0.0.1", port=args.port,
                log_level="info")


if __name__ == "__main__":
    main()
