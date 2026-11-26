"""Model engines: load the CoreML super-resolution models and route frames
to the fastest path the Apple Neural Engine offers.

Three engines share two weights bundles:

- FullFrame       frame matches an ANE-enumerated shape exactly (1 predict)
- PaddedFullFrame reflect-pads the frame into a supported shape, predicts,
                  crops back to exact 2x geometry (1 predict, no resampling)
- Tiled           fresh MIT implementation of the standard overlapping-tile
                  inference pattern (reflect-pad -> tile grid -> predict ->
                  keep tile centers) for any input size

Routing picks the first engine that fits; bigger frames cost more tiles.
"""

import os
from pathlib import Path

import coremltools as ct
import numpy as np
from PIL import Image

_PKG_DIR = Path(__file__).resolve().parent
MODELS_DIR = Path(os.environ.get("ANEUP_MODELS_DIR") or (_PKG_DIR / "models"))

TILE_MODEL = "PiperSR_2x"
TILE_MODEL_256 = "PiperSR_2x_256"
FULLFRAME_MODEL = "PiperSR_2x_video_720p"

# (height, width) shapes the full-frame model enumerates in its spec
FULLFRAME_SHAPES = {
    (360, 640),
    (480, 854),
    (720, 1280),  # landscape
    (640, 360),
    (854, 480),
    (1280, 720),  # portrait
}

_CACHE = {}


def load_model(name):
    """Load (and memoize) a CoreML model pinned to CPU+NeuralEngine."""
    if name not in _CACHE:
        path = MODELS_DIR / f"{name}.mlpackage"
        if not path.exists():
            raise FileNotFoundError(
                f"model {name}.mlpackage not found in {MODELS_DIR}; "
                "set ANEUP_MODELS_DIR or run from a repo checkout"
            )
        _CACHE[name] = ct.models.MLModel(str(path), compute_units=ct.ComputeUnit.CPU_AND_NE)
    return _CACHE[name]


class FullFrame:
    """Whole frame in one predict. Input/output: float NCHW in [0, 1]."""

    def __init__(self):
        self.model = load_model(FULLFRAME_MODEL)
        spec = self.model.get_spec()
        self.in_name = spec.description.input[0].name
        self.out_name = spec.description.output[0].name

    def __call__(self, rgb):
        x = np.transpose(rgb.astype(np.float32) / 255.0, (2, 0, 1))[None]
        y = self.model.predict({self.in_name: x})[self.out_name]
        y = np.clip(np.squeeze(y, axis=0).transpose(1, 2, 0), 0.0, 1.0)
        out = (y * 255.0 + 0.5).astype(np.uint8)
        h, w = rgb.shape[:2]
        if out.shape[:2] != (h * 2, w * 2):
            raise RuntimeError(f"model returned {out.shape}, expected {h * 2}x{w * 2}")
        return out


class PaddedFullFrame:
    """Reflect-pad into a supported shape, predict once, crop back to exact
    2x of the source geometry. Reflected context (never black) keeps frame
    borders free of edge artifacts."""

    def __init__(self, target_hw):
        self.target = target_hw
        self._ff = FullFrame()

    def __call__(self, rgb):
        h, w = rgb.shape[:2]
        th, tw = self.target
        pt, pb = (th - h) // 2, th - h - (th - h) // 2
        pl, pr = (tw - w) // 2, tw - w - (tw - w) // 2
        out = self._ff(np.pad(rgb, ((pt, pb), (pl, pr), (0, 0)), mode="reflect"))
        H, W = out.shape[:2]
        return out[pt * 2 : H - pb * 2, pl * 2 : W - pr * 2]


class Tiled:
    """Any frame size via overlapping tiles of the bundled tile model.

    Independent implementation of the classic overlapping-tile pattern:
    a reflect-padded canvas covers a grid of `tile - 2*overlap` steps,
    each tile is predicted, and only tile centers are kept so pixels near
    seams still see neighbouring context."""

    TILE_MODEL_NAME = TILE_MODEL_256  # bigger tiles -> fewer predicts

    def __init__(self):
        self.model = load_model(self.TILE_MODEL_NAME)
        spec = self.model.get_spec()
        self.in_name = spec.description.input[0].name
        self.out_name = spec.description.output[0].name
        in_w = spec.description.input[0].type.imageType.width
        out_w = spec.description.output[0].type.imageType.width
        if out_w % in_w:
            raise RuntimeError("tile model is not an integer scale")
        self.scale = out_w // in_w
        self.tile = in_w
        self.overlap = 8

    def __call__(self, rgb):
        t, ov, s = self.tile, self.overlap, self.scale
        step = t - 2 * ov
        if step <= 0:
            raise RuntimeError("overlap too large for tile size")
        h, w = rgb.shape[:2]
        nx = -(-w // step)
        ny = -(-h // step)
        canvas = np.pad(
            rgb,
            ((ov, ny * step - h + ov), (ov, nx * step - w + ov), (0, 0)),
            mode="reflect",
        )
        out = np.empty((ny * step * s, nx * step * s, 3), dtype=np.uint8)
        m = ov * s
        for j in range(ny):
            for i in range(nx):
                x0, y0 = i * step, j * step
                tile = Image.fromarray(canvas[y0 : y0 + t, x0 : x0 + t])
                r = self.model.predict({self.in_name: tile})[self.out_name]
                if not isinstance(r, Image.Image):
                    r = Image.fromarray(np.asarray(r))
                # imageType outputs may come back RGBA; normalise to RGB
                arr = np.asarray(r.convert("RGB"))
                out[y0 * s : (y0 + step) * s, x0 * s : (x0 + step) * s] = arr[
                    m : m + step * s, m : m + step * s
                ]
        return out[: h * s, : w * s]


def _pad_shape_for(h, w, max_waste=1.40):
    """Smallest supported shape (same orientation) that contains the frame
    within the pad-waste budget; None when nothing fits."""
    landscape = h <= w
    best = None
    for th, tw in FULLFRAME_SHAPES:
        if (th <= tw) != landscape:
            continue
        if (
            h <= th
            and w <= tw
            and (th * tw) / (h * w) <= max_waste
            and (best is None or th * tw < best[0] * best[1])
        ):
            best = (th, tw)
    return best


def engine_chain(h, w, scale=2, route="auto"):
    """One engine per 2x pass; each pass re-routes on its own input dims.

    route: 'auto'  exact match, then padding path, then tiles
           'pad'   require the padding path (fail if impossible)
           'tiled' never pad
    Returns (engines, output_dims_per_pass)."""
    if scale not in (2, 4):
        raise ValueError("scale must be 2 or 4")
    chain, dims = [], []
    for _ in range(max(1, scale // 2)):
        hh, ww = dims[-1] if dims else (h, w)
        if (hh, ww) in FULLFRAME_SHAPES:
            eng = FullFrame()
        elif route in ("auto", "pad"):
            target = _pad_shape_for(hh, ww)
            if target is not None:
                eng = PaddedFullFrame(target)
            elif route == "pad":
                raise SystemExit(f"no supported full-frame shape contains {ww}x{hh}")
            else:
                eng = Tiled()
        else:
            eng = Tiled()
        chain.append(eng)
        dims.append((hh * 2, ww * 2))
    return chain, dims


def describe(chain):
    """Human-readable route names for a chain."""
    return "+".join(
        "full-frame"
        if isinstance(e, FullFrame)
        else "pad-fullframe"
        if isinstance(e, PaddedFullFrame)
        else "tiled"
        for e in chain
    )
