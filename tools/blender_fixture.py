"""Build an original animated material/shading fixture for exporter verification."""
import argparse
from pathlib import Path
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from md3harness.materials import write_tga

p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, required=True)
args = p.parse_args(sys.argv[sys.argv.index("--")+1:])
root = args.output.resolve()
root.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1
scene.frame_end = 3
material = bpy.data.materials.new("Navy woven canvas")
material["md3_shader"] = "progs/studio"
material.diffuse_color = (.08, .26, .4, 1)
write_tga(root/"progs/studio.tga", 256, 256,
          ((28+(x%4), 77+(y%4), 108+(x+y)%3, 255) for y in range(256) for x in range(256)))
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .65))
body = bpy.context.object
body.name = "bevel_case"
body.scale = (.7, 1.8, 1.2)
body.data.materials.append(material)
bevel = body.modifiers.new("Real edge highlights", "BEVEL")
bevel.width = .08
bevel.segments = 3
bevel.affect = "EDGES"
body.location.x = 0
body.keyframe_insert(data_path="location", frame=1)
body.location.x = .2
body.keyframe_insert(data_path="location", frame=2)
body.location.x = 0
body.keyframe_insert(data_path="location", frame=3)
# Smooth cylindrical form and a reflected object exercise inverse-transpose normals.
bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=.34, location=(0, 0, 1.6))
sphere = bpy.context.object
sphere.name = "smooth_cap"
sphere.scale.x = -1
sphere.data.materials.append(material)
for polygon in sphere.data.polygons:
    polygon.use_smooth = True
bpy.ops.object.empty_add(type="ARROWS", location=(0, 0, 1.94))
bpy.context.object.name = "tag_top"
bpy.context.object.rotation_euler.z = .2
bpy.context.object.keyframe_insert(data_path="rotation_euler", frame=1)
bpy.context.object.rotation_euler.z = .8
bpy.context.object.keyframe_insert(data_path="rotation_euler", frame=3)
bpy.ops.object.select_all(action="SELECT")
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(root/"studio.blend"))
print("MD3HARNESS BLENDER FIXTURE READY")
