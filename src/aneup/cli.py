"""aneup command line interface."""

import argparse
from pathlib import Path

from . import __version__
from .hevc import hevc_encode
from .image import upscale_image
from .video import render_video


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="aneup",
        description="ANE-native 2x/4x upscaler for Apple Silicon "
                    "(Neural Engine inference, VideoToolbox HEVC delivery)",
    )
    ap.add_argument("--version", action="version", version=f"aneup {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("video", help="upscale a video 2x/4x (ANE)")
    v.add_argument("-i", "--input", required=True)
    v.add_argument("-o", "--output", default=None,
                   help="output MP4 (default: <stem>_<scale>x.mp4 next to input)")
    v.add_argument("--scale", type=int, default=2, choices=(2, 4),
                   help="4 = two chained 2x passes")
    v.add_argument("--route", default="auto", choices=("auto", "tiled", "pad"),
                   help="auto = exact/pad/tiled, tiled = never pad, pad = require pad")
    v.add_argument("--chunk-minutes", type=float, default=None,
                   help="frame-exact chunks of this many minutes, stitched losslessly")
    v.add_argument("--limit", type=int, default=None,
                   help="process only the first N frames (smoke test)")

    im = sub.add_parser("image", help="upscale a still image 2x/4x (ANE)")
    im.add_argument("-i", "--input", required=True)
    im.add_argument("-o", "--output", default=None, help="output PNG (default: <stem>_<scale>x.png)")
    im.add_argument("--scale", type=int, default=2, choices=(2, 4))
    im.add_argument("--route", default="auto", choices=("auto", "tiled", "pad"))

    h = sub.add_parser("hevc", help="VideoToolbox HEVC delivery encode (10-bit)")
    h.add_argument("-i", "--input", required=True)
    h.add_argument("-o", "--output", default=None, help="default: <stem>_hevc.mp4")
    h.add_argument("--bitrate", default="14M", help="HEVC video bitrate (default: 14M)")

    args = ap.parse_args(argv)

    if args.cmd == "video":
        out = Path(args.output) if args.output else \
            Path(args.input).with_name(f"{Path(args.input).stem}_{args.scale}x.mp4")
        render_video(args.input, out, scale=args.scale, route=args.route,
                     chunk_seconds=args.chunk_minutes * 60 if args.chunk_minutes else None,
                     limit=args.limit)
    elif args.cmd == "image":
        out = Path(args.output) if args.output else \
            Path(args.input).with_name(f"{Path(args.input).stem}_{args.scale}x.png")
        upscale_image(args.input, out, scale=args.scale, route=args.route)
    elif args.cmd == "hevc":
        hevc_encode(args.input, args.output, bitrate=args.bitrate)


if __name__ == "__main__":
    main()
