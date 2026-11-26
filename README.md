# aneup: 2x and 4x video upscaling on the Apple Neural Engine

**aneup** upscales videos and images 2x or 4x, entirely on your Mac. The
CoreML models run on the Apple Neural Engine, the output is delivered as
hardware HEVC through VideoToolbox, and the models ship inside this
repository: nothing is downloaded at runtime and nothing leaves the
machine.

It exists because most neural super resolution tools assume CUDA GPUs or
a cloud API. On a Mac that leaves you with slow CPU inference, or with
sending your files somewhere else. The fastest ML silicon in an Apple
Silicon Mac is the Neural Engine, and almost nobody targets it for super
resolution. This project does, end to end: the bundled PiperSR-2x model
(928 KB, 453K parameters) was designed around ANE constraints, the router
keeps every frame on it, and a dedicated media engine encodes the result.

Measured on an M2 Pro: a 320x134 clip upscaled to 2560x1072 in 149
seconds through four chained passes, 360p to 720p video at roughly 20 to
23 fps, 400x300 stills in about 29 ms.

```
Powered by PiperSR from ModelPiper: https://modelpiper.com
```

## Why this exists

Super resolution research mostly ships as CUDA code. The Mac path has
been: install a heavy Python stack, run the network on CPU, and wait. Or
worse, upload your footage to someone else's GPU. aneup takes the
opposite route: a tiny model built for the Neural Engine, bundled weights,
on-device inference, and a one-command delivery encode. The result is
private, fast, and needs no NVIDIA hardware.

What that means in practice:

- Old or low-resolution videos scale to watchable sizes at interactive
  speeds.
- 4x is possible by chaining passes, with each pass re-routed to the
  fastest path for its own frame size.
- Your files never leave the machine.

## What you get

- `video`: upscale any video 2x/4x. Auto-routing picks the fastest ANE
  path per pass (by frame shape): exact supported shape gives 1 predict
  per frame, near-fit sizes use a reflect-padded full-frame, anything
  else goes through overlapping tiles. Rotation metadata is honoured and
  zero frames are dropped.
- `image`: the same engines for stills, any input size.
- `hevc`: VideoToolbox delivery encode (10-bit main10, hardware), with
  automatic frame-parity verification against the input.
- `testdata/charge-10s`: a frame-aligned upscaling study corpus (CC BY,
  five source tiers from 320x134 to 4K, rendered outputs included).

## Quick start

```sh
git clone https://github.com/sdkks/aneup
cd aneup
uv venv .venv --python 3.13 --seed
source .venv/bin/activate
uv pip install -e .
aneup video -i clip.mp4 --scale 2
```

Or install from PyPI: `pip install aneup`.

## How routing works

The models upscale exactly 2x. Each frame is sent down the cheapest path
that fits:

1. **Exact supported shape** (360x640, 480x854, 720x1280 and the portrait
   counterparts): the whole frame is one ANE predict.
2. **Near fit** (within about 40% pad waste): the frame is reflect-padded
   into a supported shape, predicted, and cropped back to exact 2x
   geometry. Still one predict per frame.
3. **Anything else**: overlapping 256px tiles, any input size.

`--scale 4` runs two chained passes and re-evaluates the route for each
pass's dimensions, so a 4x render can mix routes.

## Usage

```sh
# video, 2x, frame-exact 4-minute chunks (long jobs)
aneup video -i input.mp4 --scale 2 --chunk-minutes 4

# video, 4x (two chained 2x passes)
aneup video -i input.mp4 --scale 4

# smoke test: first 48 frames only
aneup video -i input.mp4 --limit 48

# still image
aneup image -i photo.jpg

# HEVC delivery encode (hardware, 10-bit main10, frame-parity verified)
aneup hevc -i input_2x.mp4
```

Routes: `--route auto` (default) picks exact/pad/tiled per pass; `tiled`
never pads; `pad` requires the padding path (fails if the frame doesn't
fit a supported shape). `aneup usage` prints the full guide.

## Chunked rendering

`--chunk-minutes N` renders frame-exact parts named
`<output-stem>_partNNN.mp4` next to the output (e.g. `clip_2x_part000.mp4`)
and stitches them losslessly; the master's frame count equals the sum of
parts and the parts are kept for inspection. A failed job leaves completed
parts on disk. The final `hevc` step re-encodes audio as one continuous
stream, so no chunk seams survive into the delivery file.

## Requirements

- Apple Silicon Mac, macOS with VideoToolbox
- Python **3.10-3.13** (coremltools ships no 3.14 wheels yet)
- [uv](https://docs.astral.sh/uv/) and ffmpeg (both: `brew install uv ffmpeg`)

**exFAT / FAT volumes:** these filesystems don't support symlinks, so a
`.venv` inside the repo cannot work. Put the environment on an APFS
volume instead:

```sh
UV_PROJECT_ENVIRONMENT=~/.venvs/aneup uv sync --python 3.13
source ~/.venvs/aneup/bin/activate
```

## Development and releasing

```sh
make test                        # pytest (model-inference tests need macOS)
make build                       # sdist + wheel into dist/
make bump-version BUMP=patch     # or VERSION=0.2.0; stamps CHANGELOG, never commits
make release BUMP=patch          # bump + test + commit + tag vX.Y.Z (never pushes)
```

Pushing a `vX.Y.Z` tag triggers `.github/workflows/release.yml`:
version guard, tests on ubuntu and macOS, build, then PyPI publish via
Trusted Publishing (no tokens). Configure the PyPI project once with
owner / repository / workflow name `release.yml` / environment `pypi`.

### Secret and PII scanning

This repo ships `.gitleaks.toml` and tracked hooks in `.githooks/`.
After cloning, activate them (one repo-local setting; global config
untouched):

```sh
git config core.hooksPath .githooks
```

Staged content and commit messages are then scanned on every commit;
gitleaks must be on PATH (`brew install gitleaks`).

## Licenses

- Code: MIT (`LICENSE`)
- Bundled model weights: CC BY 4.0 with attribution, see
  `WEIGHTS-LICENSE.md` (includes per-file SHA256 provenance)
