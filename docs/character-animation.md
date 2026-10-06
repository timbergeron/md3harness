# Lessons from an animated beach athlete

This records the original procedural athlete/arm build. The subsequent
[anatomical first-person hands](anatomical-hands.md) replace the arm model with
a 402-pose library and add further rigging, UV and export lessons.

The [volleyball player build](https://github.com/timbergeron/quake-beach-volleyball/commit/faae37e985276f63badbce647872cfe0fbc7ab16)
used this harness to export an original Norway-inspired male athlete, two kit
atlases and a separate first-person arm model. The library has 31 clips and
389 sampled poses at 24 Hz. Each body has 5,004 triangles; the final arm model
has 1,496. All three MD3s passed strict checks in every sampled pose.

The generation code remains in the game repository:
[player_assets.py](https://github.com/timbergeron/quake-beach-volleyball/blob/faae37e985276f63badbce647872cfe0fbc7ab16/player_assets.py).
This case study records reusable authoring and integration lessons; the harness
does not implement a character rig, volleyball rules or a game's animation
state machine.

## Deep folds need continuous geometry and crease-aware normals

Separate cylinders and joint spheres made elbows and knees read as disconnected
parts. A continuous tube with rings before, through and after the joint gave a
better silhouette. Two-bone IK kept world-model limb lengths stable.

Independently choosing a ring basis from a global helper axis could twist
neighboring rings during a bow-and-arrow draw. A shared bend-plane axis kept
their angular correspondence stable. Compressing the inner radius around a
deep bend reduced the chance of the inner wall turning inside out while
preserving width across the bend plane. Nearly straight limbs still need a
stable fallback when the bend-plane cross product is close to zero.

Smoothed normals can point through the surface at a sharp inner crease, even
when a key pose looks acceptable. Derive normals from the deformed faces and
split corners where a shared normal disagrees with the face. Keep the same
split-corner layout in every pose; changing topology just when the elbow folds
breaks vertex animation. The character generator uses consistent corner
duplication and selects crease normals per pose.

A winding error is a reason to inspect the reported face, bend and normal.
Reversing all triangles or weakening the validator would hide this deformation
problem. Validate the quantized bytes: small fingers and crease triangles can
behave differently after the 1/64-unit conversion.

## Check between key poses, then watch interpolation

The loaded set and pancake key poses looked valid, but intermediate source
samples at frames 117 and 354 exposed invalid inner folds. Checking only rest,
contact and recovery would have missed them. The harness already checks every
exported pose; the fixes belonged in the character generator.

Export the complete clip inventory and keep strict validation enabled. Add a
small regression for the specific failed in-between pose in the asset's own
tests. The harness now also has a minimal three-pose regression whose endpoints
are valid and whose middle pose has incorrect winding.

Sampled validation does not prove that every renderer-interpolated position
between samples is valid. Review whole strokes continuously, at normal speed
and in slow motion, and inspect both loaded and follow-through silhouettes.

## Long exports need a memory budget as well as a triangle budget

A 389-pose character repeats millions of position and normal components.
Lists of Python tuples and floats can consume substantially more memory than
the final MD3. The production generator stores components in `array('f')` and
provides an indexed sequence of three-component vectors to the Python exporter.
The harness regression verifies that this produces the same bytes as ordinary
lists for an exactly representable fixture.

This applies to the direct Python API. A JSON scene still requires JSON-compatible
values. Account for the writer, partitioned data and validator as well as the
source scene; compact source arrays do not make the entire pipeline streaming.
Export kit variants from the same body scene, release that scene before building
the arms, and avoid concurrent full character rebuilds on a small machine.

## Source sampling and live playback are separate contracts

MD3 stores samples, not clip boundaries or skeletal animation. Keep a manifest
of each clip's start, count, duration, looping flag and contact phase. Generate
game constants from it and share the ranges between body and view models.
Clamp held/recovery poses inside their own clip; loops must wrap without entering
the next clip. In-place clips leave court movement and jump height to physics.

The QSS-M renderer used for this build blends ordinary alias pose changes over
0.1 seconds. Publishing a new pose every server tick kept restarting that blend.
The game therefore publishes samples at that cadence while selecting from the
24 Hz source poses. Confirm the target renderer's behavior before adopting this
cadence elsewhere. The harness's live studio FPS control is a review aid, not a
replacement for the game's animation scheduler.

Locomotion phase follows distance traveled so stopping and changing speed do
not reset the stride. Preparation holds its loaded pose; contact starts the
follow-through. Input chooses the actual stroke before team-plan hints: a
grounded set must not become attack preparation because the team calls for an
attack. Those selection/recovery checks run in the game's actual QC VM.

The dive starts at frame 338. Test indices above 255 in both binary roundtrips
and real game/client playback; format capacity alone does not establish protocol
or view-model support. The harness regression covers 389 binary poses, while
the game repository retains the live extended-frame checks.

## First-person arms require their own camera review

Translating the world arms toward the camera also moved shoulder caps beside
the eye. They became large discs that obscured the ball despite valid bounds,
normals and third-person renders. The final view rig brings the upper arms in
from below and behind the camera, removes the shoulder caps, and retains the
stroke's hand poses and timing with adjusted camera-space wrist/elbow framing.

Compare the [initial serve framing](evidence/player/view-arms-before.png) with
the [final framing](evidence/player/view-arms-after.png); the
[framing report](evidence/player/framing.json) records their model and image
hashes. Check neutral arms,
loaded setting, serves and dives through the actual first-person renderer, with
the normal FOV, HUD and camera height. A third-person studio render of a view
model does not establish that the hands leave the ball readable in play.

## Preserve exact evidence and isolate each export

The [body gallery](evidence/player/index.html) contains 11 actual QSS-M captures
and their paired empty-studio baselines: front/back/quarter/detail plus loaded
setting, release, backswing, bow, strike, pike and dive samples. The reports
record exact model, texture, tool and screenshot hashes. Structural reports for
both kits and the final arms accompany them; the body gallery does not claim
first-person camera coverage.

Export into a fresh staging directory, validate and review that exact MD3, then
copy approved bytes to game and source-asset locations and compare hashes.
An interrupted parent process can leave a child exporter running; do not start
another writer against the same final paths. Confirm completion or use a fresh
staging directory so a late write cannot replace reviewed assets.

Cached validation is reusable only when the model and all referenced texture
hashes still match. Generated galleries should embed or identify the exported
bytes they show. Keep reusable code and evidence in source control; keep licensed
Quake data, tool executables and temporary runtime directories out.
