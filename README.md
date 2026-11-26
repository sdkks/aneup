# macos-ane-video-upscaler (aneup)

**aneup** is a fast **2x / 4x upscaler for Apple Silicon**. CoreML models
run on the Apple Neural Engine; delivery encoding uses macOS
**VideoToolbox** HEVC (hardware). Self-contained: models are bundled in
this repo, no external model downloads.

```
Powered by PiperSR from ModelPiper — https://modelpiper.com
```

## What's inside

- `video` — upscale any video 2x/4x. Auto-routing picks the fastest ANE
  path per pass (by frame shape): exact supported shape → 1 predict/frame;
  near-fit sizes → reflect-padded full-frame; anything else → overlapping
  tiles. Handles rotation metadata, guarantees zero dropped frames, and
  supports frame-exact **chunked rendering** (parts kept for inspection).
- `image` — same engines for stills, any input size.
- `hevc` — VideoToolbox delivery encode (10-bit main10, hardware), with
  automatic frame-parity verification against the input.

Supported full-frame shapes (HxW): 360x640, 480x854, 720x1280, 640x360,
854x480, 1280x720. Anything within ~40% pad-waste of a supported shape
uses the padding fast path; everything else tiles.

## Requirements

- Apple Silicon Mac, macOS with VideoToolbox
- Python **3.10–3.13** (coremltools ships no 3.14 wheels yet)
- [uv](https://docs.astral.sh/uv/) and ffmpeg (both: `brew install uv ffmpeg`)

## Setup

```sh
uv venv .venv --python 3.13 --seed
source .venv/bin/activate
uv pip install -e .
```

**exFAT / FAT volumes:** these filesystems don't support symlinks, so a
`.venv` inside the repo cannot work. Put the environment on an APFS volume
instead:

```sh
UV_PROJECT_ENVIRONMENT=~/.venvs/aneup uv sync --python 3.13
source ~/.venvs/aneup/bin/activate
```

(or `uv venv ~/.venvs/aneup --python 3.13 --seed` +
`uv pip install -e . --python ~/.venvs/aneup/bin/python`).

### Secret/PII scanning (gitleaks)

This repo ships `.gitleaks.toml` and tracked hooks in `.githooks/`. After
cloning, activate them (one repo-local setting; global config untouched):

```sh
git config core.hooksPath .githooks
```

Staged content and commit messages are then scanned on every commit;
gitleaks must be on PATH (`brew install gitleaks`).

## Usage

```sh
# video, 2x, fastest route, resumable 4-minute chunks (long jobs)
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
fit a supported shape).

## Chunked rendering

`--chunk-minutes N` renders frame-exact parts named
`<output-stem>_partNNN.mp4` next to the output (e.g. `clip_2x_part000.mp4`)
and stitches them losslessly; the master's frame count equals the sum of
parts and the parts are kept for inspection. A failed job leaves completed
parts on disk. The final `hevc` step re-encodes audio as one continuous
stream, so no chunk seams survive into the delivery file.

## Licenses

- Code: MIT (`LICENSE`)
- Bundled model weights: CC BY 4.0 with attribution — see
  `WEIGHTS-LICENSE.md` (includes per-file SHA256 provenance)
