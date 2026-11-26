"""End-to-end smoke tests with synthetic content only.

Model-inference tests require macOS (coremltools prediction does not run on
Linux) and are skipped elsewhere; CI runs them on a macOS runner where the
Neural Engine itself may be unavailable — CoreML falls back to CPU, which
still validates routing, parity and chunking.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ANEUP = [sys.executable, "-m", "aneup.cli"]
darwin = pytest.mark.skipif(sys.platform != "darwin", reason="CoreML predict is macOS-only")
has_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
# The full-frame video model SIGTRAPs (rc=-5, no stderr) inside CI virtual
# machines where the Neural Engine is absent — CoreML does not fall back
# gracefully for its enumerated ANE pipeline. Real Apple Silicon is
# unaffected; tile-model tests stay enabled on CI.


def run(*args, check=True):
    p = subprocess.run(ANEUP + list(args), capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"aneup {' '.join(args)} failed (rc={p.returncode})\n"
            f"--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}"
        )
    return p


def make_clip(path, width=640, height=360, seconds=2):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate=25:duration={seconds}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-pix_fmt", "yuv420p", "-shortest", str(path)],
        check=True, capture_output=True)


def frames(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of",
         "default=nokey=1:noprint_wrappers=1", str(path)],
        check=True, capture_output=True, text=True)
    return int(out.stdout.strip())


def test_version_consistency():
    pyproject = (REPO / "pyproject.toml").read_text()
    init = (REPO / "src" / "aneup" / "__init__.py").read_text()
    import re
    pv = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    iv = re.search(r'^__version__ = "([^"]+)"', init, re.M).group(1)
    assert pv == iv


def test_help_paths():
    for args in (["--help"], ["usage"], ["video", "--help"],
                 ["image", "--help"], ["hevc", "--help"]):
        run(*args)


ci_vm = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="full-frame video model SIGTRAPs on ANE-less CI VMs (works on real Apple Silicon)",
)


@darwin
def test_image_tiled(tmp_path):
    src = tmp_path / "in.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=size=320x240:rate=25:duration=1", "-frames:v", "1", str(src)],
        check=True, capture_output=True)
    out = tmp_path / "out.png"
    run("image", "-i", str(src), "-o", str(out))
    from PIL import Image
    assert Image.open(out).size == (640, 480)


@darwin
@ci_vm
def test_image_pad(tmp_path):
    src = tmp_path / "in.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=size=608x336:rate=25:duration=1", "-frames:v", "1", str(src)],
        check=True, capture_output=True)
    out = tmp_path / "out.png"
    run("image", "-i", str(src), "-o", str(out))
    from PIL import Image
    assert Image.open(out).size == (1216, 672)


@darwin
@has_ffmpeg
@ci_vm
def test_video_chunked_stitch(tmp_path):
    src = tmp_path / "in.mp4"
    make_clip(src, seconds=3)
    out = tmp_path / "out.mp4"
    run("video", "-i", str(src), "-o", str(out), "--chunk-minutes", "0.02")
    assert frames(out) == frames(src)
    parts = sorted(tmp_path.glob("out_part*.mp4"))
    assert len(parts) >= 2  # chunk boundary actually exercised
    assert sum(frames(p) for p in parts) == frames(out)


@darwin
@has_ffmpeg
def test_hevc_frame_parity(tmp_path):
    # model-free: any valid video exercises the HEVC delivery encode + parity
    src = tmp_path / "in.mp4"
    make_clip(src, seconds=1)
    out = tmp_path / "delivery.mp4"
    run("hevc", "-i", str(src), "-o", str(out))
    assert frames(out) == frames(src)
