# CHARGE upscaling study corpus

Ten seconds (1:33–1:43, 240 frames @ 24 fps, no audio) of **CHARGE**, a
Blender Open Movie:

> "CHARGE" © Blender Foundation — https://studio.blender.org/films/charge/
> Released under Creative Commons Attribution.
> Source: 4K AV1 (3840×1608), downscaled with lanczos to five tiers.

This folder is a self-contained study: for each source tier, `aneup`
2x/4x outputs sit next to the downscaled originals, so SR-vs-alternative
comparisons can be made frame-aligned (every clip covers the same 240
frames).

## Ladder

| Tier | Source | 2x output | 2x route | 4x output |
|---|---|---|---|---|
| `xs` | 320×134 | 640×268 | tiled | 1280×536 (tiled+pad) |
| `s` | 640×268 | 1280×536 | pad-fullframe | 2560×1072 (pad+pad) |
| `m` | 1280×536 | 2560×1072 | pad-fullframe | — |
| `l` | 1920×804 | 3840×1608 | tiled | — |
| `xl` | 3840×1608 (native) | — (reference) | — | — |

Frame-aligned comparison pairs (same dimensions, same 240 frames):

- `xs/src_2x.mp4` vs `s/src.mp4`
- `xs/src_4x.mp4` vs `m/src.mp4`
- `s/src_2x.mp4` vs `m/src.mp4`
- `s/src_4x.mp4` vs `m/src_2x.mp4`
- `l/src_2x.mp4` vs `xl/src.mp4` (2x SR vs native 4K — the headline pair)

## Encoding notes

- Sources: x264 CRF 19 (lanczos downscale from the native extract)
- SR outputs: x264 CRF 17 (aneup default) — outputs therefore carry a
  slightly higher bitrate than sources by design
- No audio (study is visual only)

## Regeneration

```sh
ffmpeg -ss 93 -t 10 -i CHARGE.webm -vf scale=1920:-2:flags=lanczos \
       -an -c:v libx264 -crf 19 -preset medium l/src.mp4   # (repeat per tier)
aneup video -i l/src.mp4 -o l/src_2x.mp4 --scale 2
```
