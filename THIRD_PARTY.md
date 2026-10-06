# Sources and tool provenance

The toolkit and original examples are GPL-2.0-or-later, copyright 2026 timbergeron.

- `examples/net_geometry.py`, studio brush/WAD/palette helpers and the preview QuakeC ABI were adapted from the original [quake-beach-volleyball](https://github.com/timbergeron/quake-beach-volleyball) working source following v0.5.0. The net geometry was developed after that tag; it is not present in the tagged v0.5.0 source. These files retain that project's GPL-2.0-or-later terms. No commercial volleyball or Virtua Tennis model/code is used.
- The binary layout and portable MD3 limits follow id Software's [MD3 definitions maintained by ioquake3](https://github.com/ioquake/ioq3/blob/master/code/qcommon/qfiles.h). This repository contains an original Python implementation rather than copied C implementation code.
- QSS-M rendering conventions and the QuakeC system ABI were checked against [QSS-M](https://github.com/timbergeron/QSS-M), particularly `Quake/gl_mesh.c`, `Quake/r_alias.c` and the NetQuake system globals/fields. QSS-M decodes MD3 normal bytes using angles divided by 255. The writer deliberately matches that target.
- The Blender bridge uses the official [Blender Python API](https://docs.blender.org/api/4.5/bpy.types.Mesh.html), evaluated dependency graph meshes and per-corner normals. Blender is an optional external tool; no Blender executable is redistributed here.
- Engine preview builds use external [FTEQCC](https://github.com/fte-team/fteqw) and [ericw-tools](https://github.com/ericwa/ericw-tools). Their executables are not bundled.

- `md3harness/packed.py` adapts the original game's packed batch/pose operations
  from [the anatomical hand commit](https://github.com/timbergeron/quake-beach-volleyball/commit/14b88be45b47213390830268c499e7a97b358cca),
  with generalized layout handling and input checks. It remains GPL-2.0-or-later.
- `docs/evidence/hands` contains actual QSS-M captures of that game's anatomical
  first-person hands. The underlying trimmed mesh, young male anatomy target,
  joint/weight data and cropped skin are CC0 MakeHuman assets at source revision
  `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`:
  [asset license](https://github.com/makehumancommunity/makehuman/blob/a8bc2d54ff0ac92e78ff71431b1023eda42bf482/LICENSE.md),
  [system asset pack](https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html).
  The skin credits Data Collection AB, Joel Palmius and Jonas Hauquier.
  The [CC0 text](docs/evidence/hands/LICENSE.CC0.txt) is preserved with the evidence.
  The original rigging/animations are GPL-2.0-or-later game code; no MakeHuman
  application code, full source character or game executable is included here.

The studio material, net atlas and procedural geometry are original generated assets. The net and Blender fixture screenshots show those original assets in QSS-M; the anatomical hand screenshots are credited above. Preview builds read the palette from a user-supplied Quake installation and link its PAK files into an isolated runtime. No Quake PAKs, palette data, compiled game maps or licensed game assets are committed or distributed by this repository.
