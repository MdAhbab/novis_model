/** Confidence-gated colorization, composed client-side on a canvas.
 *
 * The model's color is inferred, not measured. The gate blends the color
 * reconstruction over the grayscale one only where the predicted confidence
 * clears the threshold, with a soft edge so the boundary does not shimmer.
 */

import { useEffect, useRef } from "react";

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = reject;
    im.src = src;
  });
}

let offscreenCanvas: HTMLCanvasElement | null = null;
let offscreenCtx: CanvasRenderingContext2D | null = null;

function drawToData(im: HTMLImageElement): ImageData {
  if (!offscreenCanvas) {
    offscreenCanvas = document.createElement("canvas");
    offscreenCtx = offscreenCanvas.getContext("2d", { willReadFrequently: true })!;
  }
  const c = offscreenCanvas;
  const ctx = offscreenCtx!;
  if (c.width !== im.naturalWidth || c.height !== im.naturalHeight) {
    c.width = im.naturalWidth;
    c.height = im.naturalHeight;
  }
  ctx.clearRect(0, 0, c.width, c.height);
  ctx.drawImage(im, 0, 0);
  return ctx.getImageData(0, 0, c.width, c.height);
}

export function useGatedColor(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  grayUrl: string | undefined,
  colorUrl: string | undefined,
  confUrl: string | undefined,
  showColor: boolean,
  threshold: number,
) {
  const cache = useRef<{
    key: string;
    gray: ImageData;
    color: ImageData;
    conf: ImageData;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const canvas = canvasRef.current;
    if (!canvas || !grayUrl) return;

    (async () => {
      const grayIm = await loadImage(grayUrl);
      if (cancelled) return;
      const w = grayIm.naturalWidth;
      const h = grayIm.naturalHeight;
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d")!;

      if (!showColor || !colorUrl || !confUrl) {
        ctx.drawImage(grayIm, 0, 0);
        return;
      }

      const key = grayUrl.slice(-48) + colorUrl.slice(-48);
      if (!cache.current || cache.current.key !== key) {
        const [colorIm, confIm] = await Promise.all([
          loadImage(colorUrl),
          loadImage(confUrl),
        ]);
        if (cancelled) return;
        cache.current = {
          key,
          gray: drawToData(grayIm),
          color: drawToData(colorIm),
          conf: drawToData(confIm),
        };
      }
      const { gray, color, conf } = cache.current;
      const out = ctx.createImageData(w, h);
      const soft = 0.08; // soft edge width in confidence units
      for (let i = 0; i < out.data.length; i += 4) {
        const c01 = conf.data[i] / 255;
        let a = (c01 - threshold) / soft;
        a = a < 0 ? 0 : a > 1 ? 1 : a;
        a = a * a * (3 - 2 * a); // smoothstep
        out.data[i] = gray.data[i] * (1 - a) + color.data[i] * a;
        out.data[i + 1] = gray.data[i + 1] * (1 - a) + color.data[i + 1] * a;
        out.data[i + 2] = gray.data[i + 2] * (1 - a) + color.data[i + 2] * a;
        out.data[i + 3] = 255;
      }
      ctx.putImageData(out, 0, 0);
    })().catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [canvasRef, grayUrl, colorUrl, confUrl, showColor, threshold]);
}
