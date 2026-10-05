# Validation evidence

Locally verified on 2026-10-05, Linux x86-64:

- **21 core regression tests passed.** They include hostile/truncated binary data, overlapping offsets, out-of-range indices, later-pose collapse, bounds/radius errors, winding, tag transforms, surface splitting, atlas footprints, PNG filtering/checksums, empty captures and camera framing.
- **Blender 4.5.10 LTS passed the integration checks.** The exported fixture has three poses, two surfaces and an animated attachment tag. Evaluated transforms preserve hard edges and UV seams, including a reflected object. Animated topology and UVs are rejected. The official Linux archive was verified against SHA-256 `198a4248b38899af661aa9241cebd746394eaddbfafbeb53152440de80b118f7`.
- **The procedural beach net passed strict validation in all 37 poses**, including dimensions, static parts and protected atlas regions. The generated net has 16 surfaces. Small torus fittings use a grid-compatible resolution; no faces are silently removed by the exporter.
- **12 actual QSS-M captures passed**, each with a paired background capture. The Blender fixture covers front/back/quarter/detail at pose 0 plus poses 1 and 2. The net covers the same four angles at pose 0 plus impact poses 2 and 8. Every capture has visibly changed foreground pixels; the minimum measured count is 13,900, above the 25-pixel rejection threshold.
- **The Python wheel built and installed into an isolated local target.** Its command/module and packaged QuakeC ABI were checked.

Open the [net gallery](evidence/net/index.html) and [Blender gallery](evidence/blender/index.html) from a local checkout. The paired baseline captures and JSON reports are included alongside each gallery. GitHub displays the individual images; the HTML galleries work offline in a browser.

Reports include exact engine, model, textures, compiled preview QuakeC, BSP and screenshot hashes. These identify the local renderer/build used for the evidence, rather than promising identical images on every driver. QSS-M preview used the local engine executable with software OpenGL, 1280×720, four-sample MSAA and a fixed 0.02-second timestep. No licensed game data or compiled maps are included in this evidence.

CI is configured for Python 3.10, 3.12 and 3.13, the strict net rebuild and a separate Blender 4.5.10 export job. These are repository automation checks; the local engine render check still needs a user-supplied Quake installation.
