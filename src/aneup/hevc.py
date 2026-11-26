"""HEVC delivery encode via macOS VideoToolbox (hardware).

Settings verified empirically on Apple Silicon (M2 Pro, ffmpeg 9.x):
- 10-bit main10 (p010le) for gradient headroom
- bitrate target rather than -q:v: q65 measured at ~half the source bitrate,
  q100 ran away to ~117 Mbps; a fixed target stays predictable
- hvc1 tag so Apple players recognise the stream
"""

import subprocess
import time
from pathlib import Path


def hevc_encode(src, dst=None, bitrate="14M", audio="aac", verify_frames=True):
    """Transcode src to HEVC with VideoToolbox. Returns (dst path, seconds).

    dst None -> <stem>_hevc.mp4 next to src. Audio defaults to one
    continuous AAC re-encode, which also removes any chunk-seam risk."""
    src, dst = Path(src), Path(dst) if dst else Path(src).with_name(f"{Path(src).stem}_hevc.mp4")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(src),
        "-c:v",
        "hevc_videotoolbox",
        "-b:v",
        bitrate,
        "-pix_fmt",
        "p010le",
        "-profile:v",
        "main10",
        "-tag:v",
        "hvc1",
        "-c:a",
        audio,
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(dst),
    ]
    t0 = time.time()
    subprocess.run(cmd, check=True)
    dt = time.time() - t0
    if verify_frames:
        _verify(src, dst)
    print(f"  {src.name} -> {dst.name} ({bitrate}, 10-bit) in {dt:.1f}s")
    return dst, dt


def _verify(src, dst):
    def frames(path):
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-count_frames",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=nb_read_frames",
                "-of",
                "default=nokey=1:noprint_wrappers=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return int(out.stdout.strip())

    a, b = frames(src), frames(dst)
    if a != b:
        raise RuntimeError(f"frame parity broken: {src.name}={a}, {dst.name}={b}")
    print(f"  frame parity ok ({b} frames)")
