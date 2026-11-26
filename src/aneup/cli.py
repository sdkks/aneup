"""aneup command line interface."""

import argparse
from pathlib import Path

from . import __version__
from .hevc import hevc_encode
from .image import upscale_image
from .video import render_video

PROGRAM = "aneup"

# Short-manpage guide. Shared by --help (as the main-parser epilog) and the
# `usage` subcommand; subparser epilogs carry their own example blocks.
OVERVIEW = """\
aneup — ANE-native upscaler for Apple Silicon

Upscales videos and still images with CoreML super-resolution models
scheduled onto the Apple Neural Engine; the separate 'hevc' command
delivers hardware-encoded HEVC via macOS VideoToolbox. Models are bundled
in the repository; nothing is downloaded at runtime.

Commands:
  video   Upscale a video 2x or 4x (4 = two chained 2x passes)
  image   Upscale a still image 2x or 4x
  hevc    VideoToolbox HEVC delivery encode (10-bit main10)
  usage   Print the full program guide

Routes (--route):
  auto    Exact supported frame shape -> full-frame (1 predict per frame);
          otherwise a reflect-padded supported shape (up to 40% pad waste,
          still 1 predict per frame); otherwise overlapping 256px tiles
          (works with any size).
  pad     Full-frame only: exact shapes pass through unpadded; otherwise
          pad to the smallest fitting supported shape; fails (exit 1)
          when nothing fits within the budget.
  tiled   Tile unless the frame exactly matches a supported shape; never
          pads.
Printed route names: full-frame | pad-fullframe | tiled.

Supported full-frame shapes (HxW, landscape then portrait): 360x640,
480x854, 720x1280, 640x360, 854x480, 1280x720.

Scale: the models upscale exactly 2x. --scale 4 runs two chained 2x
passes; routing is re-evaluated on each pass's dimensions.

Chunking (--chunk-minutes): video rendering is split into frame-exact
parts named <output-stem>_partNNN.mp4 that are stitched losslessly.
Completed parts are kept on disk for inspection. The final 'hevc' pass
re-encodes audio as one continuous stream, removing chunk seams.

Environment:
  ANEUP_MODELS_DIR   Directory holding the *.mlpackage models
                     (default: <repo>/models)

Exit codes:
  0  success
  1  runtime failure (missing model, impossible route, ffmpeg error,
     frame-parity check)
  2  command-line usage error

Examples:
  aneup video -i clip.mp4                         # clip_2x.mp4, auto route
  aneup video -i movie.mp4 --scale 4 --chunk-minutes 4
  aneup video -i clip.mp4 --limit 48              # smoke test: 48 frames
  aneup image -i photo.jpg                        # photo_2x.png
  aneup hevc -i clip_2x.mp4                       # 10-bit HEVC, 14 Mbps
  aneup hevc -i clip_2x.mp4 -o delivery.mp4 --bitrate 16M
"""


def _parser():
    ap = argparse.ArgumentParser(
        prog=PROGRAM,
        description="ANE-native upscaler. Run 'aneup usage' for the full guide.",
        epilog=OVERVIEW,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--version", action="version", version=f"{PROGRAM} {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="command")

    v = sub.add_parser(
        "video", help="upscale a video 2x/4x (ANE)",
        description="Upscale a video 2x (or 4x via two chained 2x passes). "
                    "Output is CFR H.264 (CRF 17) with frame-exact timing; "
                    "rotation metadata is honoured and the decoder tail is "
                    "drained so no frames are dropped.",
        epilog="Examples:\n"
               "  aneup video -i clip.mp4 --scale 2 --chunk-minutes 4\n"
               "  aneup video -i clip.mp4 --limit 48   # smoke test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    v.add_argument("-i", "--input", required=True, help="input video (any size)")
    v.add_argument("-o", "--output", default=None,
                   help="output MP4 (default: <stem>_<scale>x.mp4 next to input)")
    v.add_argument("--scale", type=int, default=2, choices=(2, 4),
                   help="upscale factor (default: 2)")
    v.add_argument("--route", default="auto", choices=("auto", "pad", "tiled"),
                   help="engine routing (default: auto; see 'aneup usage')")
    v.add_argument("--chunk-minutes", type=float, default=None,
                   help="frame-exact chunks of this many minutes, "
                        "stitched losslessly (recommended for long jobs)")
    v.add_argument("--limit", type=int, default=None,
                   help="process only the first N frames (smoke test)")

    im = sub.add_parser(
        "image", help="upscale a still image 2x/4x (ANE)",
        description="Upscale a still image 2x (or 4x via two chained 2x "
                    "passes). Any input size; large images are tiled.",
        epilog="Examples:\n  aneup image -i photo.jpg\n  aneup image -i photo.jpg --scale 4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    im.add_argument("-i", "--input", required=True, help="input image")
    im.add_argument("-o", "--output", default=None,
                    help="output PNG (default: <stem>_<scale>x.png next to input)")
    im.add_argument("--scale", type=int, default=2, choices=(2, 4),
                    help="upscale factor (default: 2)")
    im.add_argument("--route", default="auto", choices=("auto", "pad", "tiled"),
                    help="engine routing (default: auto; see 'aneup usage')")

    h = sub.add_parser(
        "hevc", help="VideoToolbox HEVC delivery encode (10-bit)",
        description="Hardware HEVC delivery encode via macOS VideoToolbox. "
                    "10-bit main10 at a fixed bitrate target; audio is "
                    "re-encoded as one continuous AAC stream. Frame parity "
                    "against the input is verified automatically.",
        epilog="Examples:\n"
               "  aneup hevc -i clip_2x.mp4\n"
               "  aneup hevc -i clip_2x.mp4 -o delivery.mp4\n"
               "  aneup hevc -i clip_2x.mp4 --bitrate 16M",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    h.add_argument("-i", "--input", required=True, help="input video")
    h.add_argument("-o", "--output", default=None,
                   help="output MP4 (default: <stem>_hevc.mp4 next to input)")
    h.add_argument("--bitrate", default="14M",
                   help="HEVC video bitrate, ffmpeg -b:v syntax (default: 14M)")

    u = sub.add_parser(
        "usage", help="print the full program guide (the overview)",
        description="Print the full program guide (the same guide shown at "
                    "the end of 'aneup --help').",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    return ap


def main(argv=None):
    ap = _parser()
    args = ap.parse_args(argv)

    if args.cmd == "usage":
        print(OVERVIEW)
        return 0

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
    return 0


if __name__ == "__main__":
    sys_exit = main()
    raise SystemExit(sys_exit or 0)
