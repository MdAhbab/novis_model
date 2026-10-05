"""Render every slide of the deck to PNG for visual QA (Aspose.Slides).

  python render.py ../NOVIS_Presentation.pptx out_dir [slide numbers...]
"""
import sys
from pathlib import Path

import aspose.slides as slides

src, out = sys.argv[1], Path(sys.argv[2])
only = {int(a) for a in sys.argv[3:]}
out.mkdir(parents=True, exist_ok=True)
with slides.Presentation(src) as p:
    for i, sl in enumerate(p.slides, start=1):
        if only and i not in only:
            continue
        img = sl.get_image(1.5, 1.5)  # 1.5x of 96 dpi -> 1920x1080
        img.save(str(out / f"s{i:02d}.png"), slides.ImageFormat.PNG)
print("rendered to", out)
