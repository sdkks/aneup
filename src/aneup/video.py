"""Video rendering: decode -> ANE upscale -> encode, with the hardening the
pipeline earned the hard way:

- display-matrix rotation honoured (PyAV does not auto-rotate like ffmpeg CLI)
- decoder reorder buffer drained at EOF (no dropped tail frames)
- peek runs on a separate container handle (main decoder state untouched)
- frame-exact chunked rendering with lossless concat (resumable, no gaps)
- audio re-stamped per chunk so stitched durations stay exact
"""

import subprocess
import time
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from .engines import describe, engine_chain


def _rotation_k(frame):
    """np.rot90 quarter-turns reproducing ffmpeg's auto-rotation convention."""
    rot = float(frame.rotation or 0.0)
    return round(rot / 90.0) % 4


def render_video(
    src, dst, scale=2, route="auto", chunk_seconds=None, limit=None, on_part_done=None
):
    """Upscale a video 2x (or 4x via chained passes) to an MP4.

    With chunk_seconds set, rendering is split into frame-exact parts
    (<stem>_partNNN.mp4) that are losslessly concatenated into dst at the
    end; the parts are kept for inspection and any single part can be
    re-rendered without redoing the whole job.

    Returns a small result dict (frames, seconds, route name, dims)."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    inp = av.open(str(src))
    vin = inp.streams.video[0]
    astream = next((s for s in inp.streams if s.type == "audio"), None)

    # Peek rotation/dims on a separate handle: decoding into the main handle
    # here would shift its h264 decoder state and drop a frame at the seam.
    with av.open(str(src)) as peek_in:
        probe = next(iter(peek_in.decode(video=0)), None)
    if probe is None:
        raise RuntimeError(f"no video frames in {src}")
    k = _rotation_k(probe)
    h, w = np.rot90(probe.to_ndarray(format="rgb24"), k=k).shape[:2]

    chain, dims = engine_chain(h, w, scale, route)
    t0 = time.perf_counter()
    frames_per_chunk = round(chunk_seconds * float(vin.average_rate)) if chunk_seconds else None

    st = {
        "n": 0,
        "part": 0,
        "part_start": 0,
        "audio_offset": 0,
        "out": None,
        "vout": None,
        "aout": None,
        "pdst": None,
    }

    def open_part():
        st["pdst"] = dst.parent / f"{dst.stem}_part{st['part']:03d}.mp4" if chunk_seconds else dst
        out = av.open(str(st["pdst"]), "w")
        vout = out.add_stream("libx264", rate=vin.average_rate)
        vout.width, vout.height = w * scale, h * scale
        vout.pix_fmt = "yuv420p"
        vout.options = {"crf": "17"}
        vout.time_base = Fraction(1, 1) / vin.average_rate
        aout = None
        if astream is not None:
            aout = out.add_stream_from_template(astream)
            st["audio_offset"] = round(st["n"] / float(vin.average_rate) / float(astream.time_base))
        st.update(out=out, vout=vout, aout=aout, part_start=st["n"])

    def close_part():
        for p in st["vout"].encode():
            st["out"].mux(p)
        st["out"].close()

    def emit(rgb):
        if chunk_seconds and st["n"] > 0 and st["n"] % frames_per_chunk == 0:
            close_part()
            st["part"] += 1
            open_part()
        up = rgb
        for eng in chain:
            up = eng(up)
        vf = av.VideoFrame.from_ndarray(up, format="rgb24")
        vf.pts = st["n"] - st["part_start"]
        for p in st["vout"].encode(vf):
            st["out"].mux(p)
        st["n"] += 1

    def raw_to_rgb(frame):
        raw = frame.to_ndarray(format="rgb24")
        return np.rot90(raw, k=k) if k else raw

    open_part()
    audio_cut = 0.0

    for packet in inp.demux():
        if packet.dts is None:
            continue
        if packet.stream.type == "video":
            for frame in packet.decode():
                emit(raw_to_rgb(frame))
                if chunk_seconds and st["n"] % frames_per_chunk == 0:
                    audio_cut = st["n"] / float(vin.average_rate)
                if limit and st["n"] >= limit:
                    break
            if limit and st["n"] >= limit:
                break
        elif st["aout"] is not None:
            if (
                limit
                and packet.pts is not None
                and packet.pts * astream.time_base > limit / float(vin.average_rate)
            ):
                continue
            if chunk_seconds and packet.pts is not None:
                t = float(packet.pts * astream.time_base)
                if t < audio_cut:
                    continue
                packet.pts -= st["audio_offset"]
                if packet.dts is not None:
                    packet.dts -= st["audio_offset"]
            packet.stream = st["aout"]
            st["out"].mux(packet)
    if not (limit and st["n"] >= limit):
        for frame in vin.decode(None):  # drain reorder buffer: no lost tail
            emit(raw_to_rgb(frame))
    close_part()
    inp.close()

    n = st["n"]
    parts = sorted(dst.parent.glob(f"{dst.stem}_part*.mp4")) if chunk_seconds else [dst]
    if chunk_seconds and len(parts) > 1:
        list_file = dst.parent / f"{dst.stem}_concat.txt"
        list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(dst),
            ],
            check=True,
        )
        list_file.unlink()
        print(f"  stitched {len(parts)} parts -> {dst.name} (parts kept)")
        if on_part_done:
            on_part_done(parts)

    dt = time.perf_counter() - t0
    route_name = describe(chain)
    print(
        f"  {src.name}: {w}x{h} -> {' -> '.join(f'{dw}x{dh}' for dh, dw in dims)}  "
        f"route={route_name}  {n} frames in {dt:.1f}s ({n / dt:.1f} fps)"
    )
    return {"frames": n, "seconds": dt, "route": route_name, "dims": dims}
