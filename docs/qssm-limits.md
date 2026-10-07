# Dense MD3 assets in QSS-M

QSS-M supports larger surfaces than the original Quake III MD3 recommendations.
Use an explicit export profile; a dense asset is not automatically portable.

| Limit | Portable export | QSS-M export |
| --- | ---: | ---: |
| Vertices per surface | 4,096 | 65,535 |
| Triangles per surface | 8,192 | 715,827,882 theoretical loader ceiling |
| Frames per model | 1,024 | 1,024 |
| Surfaces / tags | 32 / 16 | 32 / 16 conservative toolkit limits |
| Coordinate grid | 1/64 unit | 1/64 unit |
| Coordinate range | −512 to 511.984375 | −512 to 511.984375 |

The engine limits were inspected at QSS-M revision
`9714f766ecb844ada219f8988c946bbaf4a5594c`, in
[`Mod_ValidateMD3Model` and `Mod_LoadMD3Model`](https://github.com/timbergeron/QSS-M/blob/9714f766ecb844ada219f8988c946bbaf4a5594c/Quake/gl_mesh.c)
and [`MAXALIASFRAMES`](https://github.com/timbergeron/QSS-M/blob/9714f766ecb844ada219f8988c946bbaf4a5594c/Quake/gl_model.h).
Indices use unsigned shorts. The triangle ceiling guards an integer product;
file offsets, allocation limits, memory and rendering cost impose much smaller
practical budgets. This is not a recommendation to approach that triangle count.

```sh
python3 -m md3harness build source.scene.json dense.md3 --profile qssm
python3 -m md3harness check dense.md3 --profile qssm --asset-root GAME \
  --manifest asset.contract.json --strict
```

Scene JSON may set `"profile": "qssm"`. Export defaults to `portable`, and an
explicit argument overrides the scene. Inspection defaults to `qssm`; pass
`--profile portable` to reject extended surfaces. Blender accepts the same
`--profile qssm` option. Both writers still split surfaces at their chosen
vertex and triangle limits, while preserving UV seams and every pose.

Dense animated assets cost much more than static meshes. Disk geometry costs
`8 × exported_vertices × frames` bytes; QSS-M's pose VBO costs another
`12 × exported_vertices × frames` bytes. UV seams and crease normals increase
the exported vertex count. Loaded CPU model data, indices, textures and maps
add further memory. A 25,000-vertex, 389-pose character needs about 74 MiB of
packed pose data and 111 MiB for its pose VBO alone. Instances can share a model,
but a separate away-kit MD3 is a separate loaded model.

QSS-M's default heap is 384 MiB. Large animated files must also fit a contiguous
hunk allocation. Measure the full game and select `-heapsize` (kilobytes) when
needed; do not infer usable density from the index ceiling alone.

At 32 units per metre, the position grid is about 0.49 mm. Subdividing nail
bevels, thin net cords or sharply folded skin can produce collapsed faces.
Spend samples on silhouettes and curved anatomy, preserve small source faces,
and validate **all** quantized poses. Keep a fixed topology and reserve only
the crease corners whose exported normals disagree with a face. Broadly
splitting every weighted corner can multiply file and VBO size with no visible
benefit. Use bounded pose batches and packed joining for long clips.

The beach-volleyball production example uses these principles for continuous
anatomical athletes, refined first-person hands, an icosphere ball and rounded
net equipment. Its committed quality reports and QSS-M captures identify the
exact final bytes; see the game's [density notes](https://github.com/timbergeron/quake-beach-volleyball/blob/main/docs/model-detail.md).

QSS-M also guards its loaded surface chain in
[`R_DrawAliasModel`](https://github.com/timbergeron/QSS-M/blob/9714f766ecb844ada219f8988c946bbaf4a5594c/Quake/r_alias.c):
a next-surface offset above 64 MiB stops traversal. Very large early surfaces
can therefore prevent later parts from rendering. The profile's count ceilings
do not guarantee that all maximum counts can be combined. Keep individual
loaded surfaces comfortably below that guard, split large animated surfaces,
and check the actual engine log and complete appearance. The delivered body's
largest surface contains about 54.55 MiB of packed poses, leaving room for its
frame, mesh, index and material metadata.
