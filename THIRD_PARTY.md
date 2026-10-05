# Sources and tool provenance

The toolkit and original examples are GPL-2.0-or-later, copyright 2026 timbergeron.

- `examples/net_geometry.py`, studio brush/WAD/palette helpers and the preview QuakeC ABI were adapted from the original [quake-beach-volleyball](https://github.com/timbergeron/quake-beach-volleyball) working source following v0.5.0. The net geometry was developed after that tag; it is not present in the tagged v0.5.0 source. These files retain that project's GPL-2.0-or-later terms. No commercial volleyball or Virtua Tennis model/code is used.
- The binary layout and portable MD3 limits follow id Software's [MD3 definitions maintained by ioquake3](https://github.com/ioquake/ioq3/blob/master/code/qcommon/qfiles.h). This repository contains an original Python implementation rather than copied C implementation code.
- QSS-M rendering conventions and the QuakeC system ABI were checked against [QSS-M](https://github.com/timbergeron/QSS-M), particularly `Quake/gl_mesh.c`, `Quake/r_alias.c` and the NetQuake system globals/fields. QSS-M decodes MD3 normal bytes using angles divided by 255. The writer deliberately matches that target.
- The Blender bridge uses the official [Blender Python API](https://docs.blender.org/api/4.5/bpy.types.Mesh.html), evaluated dependency graph meshes and per-corner normals. Blender is an optional external tool; no Blender executable is redistributed here.
- Engine preview builds use external [FTEQCC](https://github.com/fte-team/fteqw) and [ericw-tools](https://github.com/ericwa/ericw-tools). Their executables are not bundled.

The studio material, net atlas and procedural geometry are original generated assets. Preview screenshots show those original assets in QSS-M. Preview builds read the palette from a user-supplied Quake installation and link its PAK files into an isolated runtime. No Quake PAKs, palette data, compiled game maps or licensed game assets are committed or distributed by this repository.
