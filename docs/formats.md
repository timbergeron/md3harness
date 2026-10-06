# Scene and asset contracts

## Scene v1

`python3 -m md3harness build scene.json output.md3 --asset-root GAME_ROOT` accepts a scene with these fields:

```json
{
  "schema": "md3harness.scene.v1",
  "name": "panel.md3",
  "winding": "ccw",
  "frames": ["rest"],
  "surfaces": [{
    "name": "canvas",
    "shader": "progs/canvas",
    "uv": [[0, 0], [1, 0], [0, 1]],
    "triangles": [[0, 1, 2]],
    "poses": [{
      "positions": [[0, 0, 0], [32, 0, 0], [0, 32, 0]],
      "normals": [[0, 0, 1], [0, 0, 1], [0, 0, 1]]
    }]
  }],
  "tags": [[]]
}
```

Coordinates are already in game units, Z up. UV `v=0` is the top of the image; the Blender bridge flips Blender's V axis. `winding` is `ccw` by default, describing outward source faces. The QSS-M writer converts them to clockwise. `cw` supports generators already using that convention. Normals describe outward lighting directions.

Every surface has one shader and the same number of poses as the model. All poses have the same corner count and shared UV/triangle arrays. Each tag pose contains `{ "name": "tag_hand", "origin": [x,y,z], "axes": [[x,y,z],[x,y,z],[x,y,z]] }`; axes are the tag's local X, Y and Z directions in model space. Tag order and names stay fixed.

Names are ASCII, fewer than 64 bytes; pose names are fewer than 16 bytes. Shader paths include a game-relative directory and omit extensions. Paths cannot contain traversal, absolute components or backslashes. The writer splits surfaces exceeding 4096 vertices or 8192 triangles; at most 32 resulting surfaces, 1024 poses and 16 tags are supported.

## Packed-frame Python API

`md3harness.packed.combine_batches(batches)` accepts an iterable of MD3 byte
strings and returns one MD3 byte string. Each batch must share exact model and
surface metadata, shader records, UVs, triangle indices and attachment names/order.
Frame labels, bounds, transforms, positions and encoded normals are preserved.

`md3harness.packed.expand_frames(data, indices, names)` returns an MD3 with one
frame per zero-based integer index and one ASCII name per frame. Selection can
reorder or repeat samples; the complete packed sample and its attachments are
copied without decoding/re-encoding geometry. An empty result, invalid index,
label-count mismatch, invalid label or more than 1,024 output frames is rejected.

Both helpers validate input/output binary layout, canonicalize valid alternative
block offsets and reject changing attachment topology. They do not perform
geometry, texture or asset-contract validation. Run `check`/`inspect` on the
result with the final contract and asset root; reject warnings for strict delivery.
Use a candidate output so failure preserves the previous model. These operations
use packed input/output buffers rather than a streaming file writer. See the
[hand production example](anatomical-hands.md#export-long-pose-libraries-in-bounded-batches).

## Contract JSON

All fields are optional. Units match the exported scene. Dimensions refer to the complete rest-pose bounds. Prefixes refer to exported surface names, which acquire partition suffixes.

```json
{
  "frames": 12,
  "dimensions": [32, 64, 96],
  "dimension_tolerance": 0.05,
  "triangle_budget": 5000,
  "static_surfaces": ["base"],
  "atlas_regions": [{
    "surface_prefix": "rope",
    "rect": [512, 0, 1024, 256],
    "mip_level": 6
  }]
}
```

Atlas rectangles are pixel coordinates in the surface's first shader image. The guard extends `2^mip_level` texels around UV samples and checks the protected region. Without a contract there is no real-world size assertion or atlas protection assertion. The default triangle review budget is 20,000 per model.

## Reports

`md3harness.report.v1` records counts, actual quantized bounds for each pose, texture dimensions/hashes and issues with severity/code/location. `passed` means no errors; strict CLI mode additionally rejects warnings. For binary input, the model hash identifies the exact inspected bytes.

`md3harness.preview.v1` records model, texture, engine, compiled QuakeC and BSP hashes, capture poses/views, screenshot/baseline hashes and changed foreground pixel counts. `complete` becomes true only after every requested capture passes. The HTML page is an offline visual index of those renders.
