"""Still-image upscaling: any input size, 2x or 4x (chained), ANE."""

import time
from pathlib import Path

import numpy as np
from PIL import Image

from .engines import describe, engine_chain


def upscale_image(src, dst=None, scale=2, route="auto"):
    """Upscale a still 2x/4x. Returns (output PIL image, seconds, route name).

    dst None -> do not write; otherwise save PNG."""
    src, dst = Path(src), (Path(dst) if dst else None)
    img = Image.open(src).convert("RGB")
    w, h = img.size
    chain, dims = engine_chain(h, w, scale, route)
    rgb = np.asarray(img)

    t0 = time.perf_counter()
    up = rgb
    for eng in chain:
        up = eng(up)
    dt = time.perf_counter() - t0

    out_img = Image.fromarray(up)
    if dst:
        dst.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(dst)
    print(
        f"  {src.name}: {w}x{h} -> {' -> '.join(f'{dw}x{dh}' for dh, dw in dims)}  "
        f"route={describe(chain)}  {dt * 1000:.1f} ms"
    )
    return out_img, dt, describe(chain)
