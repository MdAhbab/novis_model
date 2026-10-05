"""Turn the dataset's index.html into one self-contained file.

The release's index.html reads its pictures from scenes/ and
augmented_scenes/, so it only works after the whole folder is unzipped. This
writes a copy with every picture embedded (downscaled JPEG, base64), which
opens on its own anywhere - a phone, an email attachment, a chat download -
with no folder beside it.

  python scripts/make_standalone_viewer.py data/NOVIS_dataset_v1
      -> data/NOVIS_dataset_v1/index_standalone.html
"""

import argparse
import base64
import io
import re
from pathlib import Path

from PIL import Image


def data_uri(path: Path, max_w: int, quality: int) -> str:
    im = Image.open(path).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def make_standalone(root: Path, out: Path = None, max_w: int = 640, quality: int = 82) -> Path:
    html = (root / "index.html").read_text(encoding="utf-8")
    cache = {}

    def inline(m):
        src = m.group(1)
        if src.startswith("data:"):
            return m.group(0)
        if src not in cache:
            cache[src] = data_uri(root / src.replace("&amp;", "&"), max_w, quality)
        return f'src="{cache[src]}"'

    html = re.sub(r'src="([^"]+)"', inline, html)
    # The file travels alone, so links to files beside it would be dead.
    html = re.sub(r'<div class="links">.*?</div>', "", html, flags=re.S)
    html = html.replace("<title>NOVIS dataset v1</title>", "<title>NOVIS dataset v1 — viewer</title>")
    out = out or root / "index_standalone.html"
    out.write_text(html, encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="dataset release folder holding index.html")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-width", type=int, default=640)
    args = ap.parse_args()
    out = make_standalone(Path(args.root), Path(args.out) if args.out else None, args.max_width)
    print(f"{out}  {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
