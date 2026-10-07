# Texture editing against the delivered MD3

The beach-volleyball density build separated anatomical body skins, first-person
hands and a shared cap/shield atlas. Increasing polygon detail made the quality
of those skins more visible. Its texture-painting handoff supplies the current
atlases, UV overlays, material-region labels and explicit image-editing prompts.
The handoff preserves the existing geometry and animation contracts.

## Export the actual atlas layout

```sh
python3 tools/texture_kit.py GAME/progs/home.md3 GAME/progs/away.md3 \
  --asset-root GAME --output build/texture-kit
```

Use a new or empty output directory. The tool reads MD3 v15 binaries, collects
UV edges by shader across all supplied surfaces/models, and exports one PNG and
SVG guide per shared atlas. Shader subdirectories are retained to avoid equal
basename collisions. `index.html` overlays the guides on the images. The
manifest records source model/texture hashes, dimensions, PNG/guide hashes and
which surfaces use each atlas. It becomes complete only after every output is
written. Runtime files are read only.

Uncompressed 24/32-bit true-color TGAs are converted losslessly, respecting image
IDs, channel order, horizontal/vertical origin and alpha. Existing PNGs are
copied byte for byte; their pixels are not decoded by this tool. RLE and
interleaved TGA require conversion first. The binary reader checks structural
ranges and counts; continue to run the full strict geometry/texture contract
before calling an asset approved. Repeated UVs outside 0–1 extend outside the
guide canvas and need separate tiling review.

## Preserve registration while improving materials

Start image editing with the original atlas attached. Lock it as a base layer;
put the SVG on a separate guide layer. Use masks to edit one island or material
region at a time. Include explicit instructions to preserve canvas dimensions,
orientation, islands, landmarks, alpha and padding. Ask for a flat diffuse
texture under even lighting. Generating a new atlas from a character screenshot
does not reproduce the model's UV registration.

Compare candidate and original at partial opacity. Reapply improved material
detail through the original masks if islands, nails, clothing edges or labels
move. Preserve lettering and flags on separate layers. Hide all guides before
exporting. Keep material colors in existing gutters so mipmapping does not pull
neighboring atlas regions into small geometry. Scale the complete atlas uniformly
if increasing resolution; normalized UVs stay fixed.

The game's MD3 material path uses diffuse color and alias lighting. Its painted
shield reflection stays attached to the texture. Normal/roughness/metallic maps
are not consumed by those materials. Subtle pores, fabric weave and color
variation remain useful; large painted highlights and shadows can compete with
the engine's lighting.

## Review the sampled regions and seams

The first-person forearm extension unwraps circumference across U and length
across V. Match the wrist along the strip's top edge and match the left/right
edges around the arm. Detailed anatomy islands can share UV areas, so a large
asymmetric mark may repeat or mirror.

The ball's longitude edges join and its latitude rows converge at the poles.
Keep the existing panel seams, wordmark and valve registered. Net cords and
fittings sample small central atlas patches for stable distant mipmapping;
artwork elsewhere may never appear. Open net mesh is geometry, so its texture
contains cord material rather than a complete-net photograph.

Edit authoritative source textures or adjust procedural generators. Files in a
generated game directory can be overwritten by the next build. Recompute reports
after changing texture bytes: a valid old model hash alone does not validate a
new skin. Compare loaded/contact/recovery poses in the native first-person
camera and review bodies and equipment at actual playing distance.

The game's [painting instructions and six asset prompts](https://github.com/timbergeron/quake-beach-volleyball/blob/v0.7.0/docs/texture-authoring.md)
record the concrete hand strip, cap/shield and net regions. The
[v0.7.0 release](https://github.com/timbergeron/quake-beach-volleyball/releases/tag/v0.7.0)
distributes its ready-to-edit kit separately from the playable ZIP. The kit
contains the existing validated skins; the proposed image edits are future work.
