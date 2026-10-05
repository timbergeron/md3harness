"""Run on the generated studio.blend to exercise real bpy export behavior."""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export import extract
from md3harness.format import encode_scene, loads
from md3harness.quality import check

args = argparse.Namespace(all=True, start=1, end=3, step=1, units_per_metre=32,
                          origin_object=None, shader=None, output=Path("studio.md3"))
source = extract(args)
model = loads(encode_scene(source))
assert check(model)["passed"]
assert len(model.frames) == 3 and len(model.tags[0]) == 1
assert model.tags[0][0]["axes"] != model.tags[2][0]["axes"]
body = next(s for s in source["surfaces"] if s["name"].startswith("bevel_case"))
assert body["poses"][0]["positions"] != body["poses"][1]["positions"]
assert body["poses"][0]["positions"] == body["poses"][2]["positions"]
corners = defaultdict(list)
for position, normal, uv in zip(body["poses"][0]["positions"], body["poses"][0]["normals"], body["uv"]):
    corners[tuple(round(x, 5) for x in position)].append((normal, uv))
assert any(len({tuple(round(x, 3) for x in n) for n, _ in entries}) > 1 for entries in corners.values()), "hard normals lost"
assert any(len({tuple(round(x, 3) for x in uv) for _, uv in entries}) > 1 for entries in corners.values()), "UV seams lost"
print("PASS animated poses, attachment tags, reflected transform, hard edges and UV seams")

obj = bpy.data.objects["bevel_case"]
array = obj.modifiers.new("Invalid animated topology", "ARRAY")
array.count = 1
array.keyframe_insert(data_path="count", frame=1)
array.count = 2
array.keyframe_insert(data_path="count", frame=2)
try:
    extract(args)
except ValueError as exc:
    assert "topology" in str(exc)
    print("PASS topology-changing modifier rejected")
else:
    raise AssertionError("animated topology should fail")
finally:
    obj.modifiers.remove(array)

uv = obj.data.uv_layers.active.data[0]
original = uv.uv.copy()
def animated_uv(scene):
    uv.uv.x = original.x + .05*(scene.frame_current-1)
bpy.app.handlers.frame_change_post.append(animated_uv)
try:
    extract(args)
except ValueError as exc:
    assert "UVs" in str(exc)
    print("PASS animated UV rejected")
else:
    raise AssertionError("animated UV should fail")
finally:
    bpy.app.handlers.frame_change_post.remove(animated_uv)
    uv.uv = original
print("MD3HARNESS BLENDER CHECKS PASSED")
