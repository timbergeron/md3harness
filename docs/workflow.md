# A repeatable asset review

## Define the asset contract first

Choose its physical size, origin, axes, shader paths, pose names and silhouette budget before adding detail. The beach game uses 32 units per metre; other games may use a different scale. Match the visual mesh to the game's dimensions and separately define its collision. MD3 does not supply collision physics.

Create a contract JSON with dimensions, pose count, static parts and a triangle budget. Use dimensions of the complete exported object, including fittings. An antenna or retaining collar can extend beyond the nominal panel or post.

## Build for the format

MD3 positions land on a 1/64-unit grid. Tiny high-resolution rings can produce zero-area triangles after conversion. The net example uses fewer segments for its smallest eyelets; this preserves visible detail without exporting collapsed faces. Increasing polygon count is useful only when the exported grid and viewing distance can show that detail.

Split corners at UV seams and hard edges. Apply evaluated object transforms to positions and the inverse transpose to normals. Reflections change winding; normals need their own transform. The Blender exporter handles these explicitly and validates the result in every pose. It splits large surfaces at triangle boundaries, retaining the same per-corner data across all poses.

Keep sampled animation topology fixed. Apply topology-generating modifiers before animating if their evaluated output changes between poses. Use skeletal animation, shape keys or stable deformation modifiers to generate the vertex samples; bones are not stored in MD3. Keep attachment empties named `tag_*` and avoid sheared/reflected tag transforms.

For animated characters, review inner elbow/knee folds between key poses as well as at contact. Stable ring bases and consistent split corners help preserve winding and shading through deep bends. Separate first-person camera review from world-model review. The [character animation case study](character-animation.md) covers these failures, compact pose storage, clip contracts and Quake playback timing.

For detailed first-person hands, establish palm/dorsal axes and reflection
conventions before authoring curls. Check the quantized finger creases and the
forearm continuation in the actual camera. The [anatomical hand case study](anatomical-hands.md)
shows why clean attachment rings and a separate forearm UV strip were needed.

For long animations, export validated fixed-topology batches and join their
packed bytes with `md3harness.packed.combine_batches`;
`expand_frames` selects or repeats exact samples with new labels. Both check
layout and frame limits. Run full strict geometry/texture/contract validation
on the assembled candidate before replacing the delivered model.

## Treat the atlas as a filtered image

Filtering can mix neighboring materials into a thin feature. On the net, stretching a large atlas rectangle over a millimetre-scale cord selected coarse mips that mixed pale metal and white fiberglass into dark rope. Small interior UV footprints kept the cord dark at playing distance.

Use separate materials or sufficiently padded atlas islands. Specify protected rectangles and the mip level you want to review in the asset contract. The guard checks bilinear footprints conservatively. Check the model at distance in engine: UV aspect ratio, minification and hardware sampling still affect the actual result. Keep fullbright/glow masks deliberate; they are not inferred or validated here.

## Inspect exported bytes and actual renders

Run `check --strict` with textures and the contract. Review every warning intentionally. Binary validation catches all sampled poses, including a detail that collapses only during deformation, a static part that moves, or a radius that excludes animated vertices.

Then capture both sides, a three-quarter view and a detail view. Include a deformation peak and its return pose. Use the live studio to move around and cycle animation. Review silhouette first, then edge highlights, UV seams, texture contrast, narrow mesh readability and popping between samples. View the asset in its final gameplay lighting before approving it.

The automated preview checks map/model/pose markers, new screenshot creation, dimensions and process completion. It compares every view with a second capture with entity rendering disabled, rejecting images with fewer than 25 visibly changed pixels. It records exact file hashes. A screenshot of Quake's fallback demo or an empty studio cannot become a passing asset capture. Startup settings are in a config file to avoid Quake's command-line argument limit.

Visual bounds matter on the server too. A mesh with its origin below the floor can disappear from the network's visibility set if `setmodel` leaves a zero-sized culling box. The harness supplies the union of the validated pose bounds with `setsize`, while keeping the display entity non-solid. This is distinct from gameplay collision.

## Keep delivery reproducible

Commit source meshes or generation code, textures, contracts, export settings, reports and representative renders. Keep licensed game files, generated runtime configs, tool executables and build directories out of the repository. Document tools and versions so another artist can rebuild and review the asset.

Stage each export/review in a fresh directory, then verify hashes when copying approved assets into a game or source tree. Avoid overlapping writers to final paths, including children left running after a parent is interrupted. Reuse cached reports only while the model and every referenced texture hash match.

CI runs the core failures and rebuilds the net with strict checks. A separate Blender job tests evaluated animation, hard normals, UV seams, reflections and tags, plus rejection of incompatible animation. Engine rendering requires a local Quake installation and is a separate integration check.
