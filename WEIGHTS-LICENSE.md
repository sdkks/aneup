# Model weights license and provenance

The bundled CoreML models (`models/*.mlpackage`) are copies of the
**PiperSR-2x** weights, originally published by ModelPiper:

- Source: https://huggingface.co/ModelPiper/PiperSR-2x
- Project: https://modelpiper.com — https://github.com/ModelPiper/PiperSR
- Weights license: **CC BY 4.0** (fully permissive with attribution)

Required attribution line (please keep visible when redistributing outputs
built with these weights):

```
Powered by PiperSR from ModelPiper — https://modelpiper.com
```

The *code* in this repository is MIT-licensed and independent of the
weights license (see `LICENSE`).

## Integrity (SHA256, per copy in `models/`)

| File | SHA256 |
|---|---|
| `PiperSR_2x.mlpackage/.../model.mlmodel` | `df7fcedd18b75f7e87a9d782e65efb00a946947f30a877ee5e6ba6e23d263a9f` |
| `PiperSR_2x.mlpackage/.../weight.bin` | `470924d59790b031487863da4f0df0a394c05cb959455300e78484754841e060` |
| `PiperSR_2x_256.mlpackage/.../model.mlmodel` | `f83c7f57a6dfb7ddcf5e1df243b9dcdf7583cd3e777301817424188ad0e02e86` |
| `PiperSR_2x_256.mlpackage/.../weight.bin` | `470924d59790b031487863da4f0df0a394c05cb959455300e78484754841e060` |
| `PiperSR_2x_video_720p.mlpackage/.../model.mlmodel` | `5db1b32bb9fb02a2feebb724a59b44b53dc2024e45aec1734482b7dd97d1b7a5` |
| `PiperSR_2x_video_720p.mlpackage/.../weight.bin` | `cadece5739d80dd17aa96ac760455cee5c9318e097057e40c69111d84de68252` |

Note: the 256-tile variant ships byte-identical weights to the 128-tile
model — same network, re-exported at a different tile size.
