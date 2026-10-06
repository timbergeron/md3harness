# Validation evidence

Locally verified on 2026-10-05, Linux x86-64:

- **21 core regression tests passed at the initial validation.** They include hostile/truncated binary data, overlapping offsets, out-of-range indices, later-pose collapse, bounds/radius errors, winding, tag transforms, surface splitting, atlas footprints, PNG filtering/checksums, empty captures and camera framing.
- **Blender 4.5.10 LTS passed the integration checks.** The exported fixture has three poses, two surfaces and an animated attachment tag. Evaluated transforms preserve hard edges and UV seams, including a reflected object. Animated topology and UVs are rejected. The official Linux archive was verified against SHA-256 `198a4248b38899af661aa9241cebd746394eaddbfafbeb53152440de80b118f7`.
- **The procedural beach net passed strict validation in all 37 poses**, including dimensions, static parts and protected atlas regions. The generated net has 16 surfaces. Small torus fittings use a grid-compatible resolution; no faces are silently removed by the exporter.
- **12 actual QSS-M captures passed**, each with a paired background capture. The Blender fixture covers front/back/quarter/detail at pose 0 plus poses 1 and 2. The net covers the same four angles at pose 0 plus impact poses 2 and 8. Every capture has visibly changed foreground pixels; the minimum measured count is 13,900, above the 25-pixel rejection threshold.
- **The Python wheel built and installed into an isolated local target.** Its command/module and packaged QuakeC ABI were checked.

Open the [net gallery](evidence/net/index.html) and [Blender gallery](evidence/blender/index.html) from a local checkout. The paired baseline captures and JSON reports are included alongside each gallery. GitHub displays the individual images; the HTML galleries work offline in a browser.

Reports include exact engine, model, textures, compiled preview QuakeC, BSP and screenshot hashes. These identify the local renderer/build used for the evidence, rather than promising identical images on every driver. QSS-M preview used the local engine executable with software OpenGL, 1280×720, four-sample MSAA and a fixed 0.02-second timestep. No licensed game data or compiled maps are included in this evidence.

CI is configured for Python 3.10, 3.12 and 3.13, the strict net rebuild and a separate Blender 4.5.10 export job. These are repository automation checks; the local engine render check still needs a user-supplied Quake installation.

## Character production follow-up

The October 5–6 volleyball player build passed strict validation for both body
kits and the final first-person arms across all 389 poses. The bodies have
5,004 triangles each; the arms have 1,496. The [player gallery](evidence/player/index.html)
contains 11 actual QSS-M body captures and paired baselines. Both kit reports,
the arm report and before/after first-person framing captures are included.
The [case study](character-animation.md) links the exact game source commit.

Three additional core regressions cover middle-pose winding failures, compact
indexed source sequences and binary pose indices above 255. These are separate
from the game's 249 QC assertions and live rally checks. All **24 core tests
passed on 2026-10-06**. Earlier Blender/net
evidence remains the original validation; this follow-up does not claim to rerun
those engine or Blender jobs.


## Anatomical hand production follow-up

The October 6 hand build passed strict validation across **402 poses**, with
6,808 triangles, two wrist tags and a 512×2048 skin atlas. The [case study](anatomical-hands.md)
links the exact beach source commit. The [engine gallery](evidence/hands/index.html)
contains seven actual first-person QSS-M captures, including extended frame 392,
with model/skin/engine/screenshot hashes. These captures use a fixed 0.05-second
simulation timestep, 1280×720 and four-sample MSAA. They do not include paired
empty-studio baseline captures. The full strict report and game verification
summaries accompany the gallery.

Eight new regressions cover packed batch joining and frame expansion: byte
identity with direct multi-surface/tagged export, repeated and reordered frames,
extended indices, frame limits, metadata/topology/material mismatches, malformed
inputs, alternate valid block layouts and preservation of geometry errors for
full quality review. All **32 core tests passed on 2026-10-06**. The new helpers
also [matched the actual six hand batches and their compact exports](evidence/hands/packed-verification.json)
byte-for-byte, producing the delivered 55,545,052-byte model.

The game's own tests passed four hand regressions and 14 existing asset/launcher
tests. Its actual QC VM passed 257 gameplay assertions, three live float-serve
checks and two live receive/set/attack checks. The offline reviewer exercised
all 32 clips without browser errors. Earlier body/net/Blender evidence remains
its recorded validation; this follow-up does not claim to rerun those engine
or Blender jobs.
