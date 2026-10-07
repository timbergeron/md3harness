"""Run with Blender: blender scene.blend -b --python tools/blender_export.py -- ..."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from md3harness.cli import export_scene, save_json

def extract(args):
    context = bpy.context
    scene = context.scene
    objects = list(scene.objects if args.all else context.selected_objects)
    meshes = sorted((o for o in objects if o.type == "MESH" and not o.hide_render), key=lambda o: o.name)
    tags = sorted((o for o in objects if o.type == "EMPTY" and o.name.startswith("tag_")), key=lambda o: o.name)
    if not meshes:
        raise ValueError("Select at least one renderable mesh, or use --all")
    frame_numbers = list(range(args.start, args.end+1, args.step))
    if not frame_numbers or len(frame_numbers) > 1024 or len(tags) > 16:
        raise ValueError("invalid frame range or too many attachment tags")
    scale = scene.unit_settings.scale_length*args.units_per_metre
    if scale <= 0:
        raise ValueError("scene/unit scale must be positive")
    scene.frame_set(args.start)
    origin = scene.objects[args.origin_object].matrix_world.translation.copy() if args.origin_object else None
    root = Matrix.Translation(-origin) if origin is not None else Matrix.Identity(4)
    result = dict(schema="md3harness.scene.v1", winding="ccw", name=args.output.name,
                  frames=[f"pose{f}" for f in frame_numbers], surfaces=[], tags=[])
    signatures, reference_uv, part_map = {}, {}, {}
    for f in frame_numbers:
        scene.frame_set(f)
        graph = context.evaluated_depsgraph_get()
        for obj in meshes:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
            try:
                mesh.calc_loop_triangles()
                if mesh.uv_layers.active is None:
                    raise ValueError(f"{obj.name}: add a UV map before exporting")
                world = root @ evaluated.matrix_world
                determinant = world.to_3x3().determinant()
                if abs(determinant) < 1e-12:
                    raise ValueError(f"{obj.name}: singular object transform")
                normal_matrix = world.to_3x3().inverted().transposed()
                uv = [(float(p.uv.x), 1-float(p.uv.y)) for p in mesh.uv_layers.active.data]
                signature = (tuple(loop.vertex_index for loop in mesh.loops),
                             tuple((tuple(t.loops), t.material_index) for t in mesh.loop_triangles),
                             determinant < 0)
                changed_uv = obj.name in reference_uv and (len(uv) != len(reference_uv[obj.name]) or
                    any(abs(a-b) > 1e-6 for p, q in zip(uv, reference_uv[obj.name]) for a, b in zip(p, q)))
                if obj.name in signatures and (signature != signatures[obj.name] or changed_uv):
                    raise ValueError(f"{obj.name}: topology, materials, UVs or transform handedness change at frame {f}; MD3 requires fixed topology")
                signatures[obj.name] = signature
                reference_uv.setdefault(obj.name, uv)
                positions = [tuple(float(x)*scale for x in (world @ mesh.vertices[loop.vertex_index].co)) for loop in mesh.loops]
                normals = [tuple((normal_matrix @ n.vector).normalized()) for n in mesh.corner_normals]
                by_material = {}
                for triangle in mesh.loop_triangles:
                    a, b, c = triangle.loops
                    face = (a, c, b) if determinant < 0 else (a, b, c)
                    by_material.setdefault(triangle.material_index, []).append(face)
                for slot, triangles in sorted(by_material.items()):
                    key = (obj.name, slot)
                    if key not in part_map:
                        material = mesh.materials[slot] if slot < len(mesh.materials) else None
                        shader = args.shader or (material.get("md3_shader") if material else None)
                        if not shader:
                            raise ValueError(f"{obj.name}: set material['md3_shader'] to a game-relative texture path, or use --shader")
                        part = dict(name=f"{obj.name}_{slot}", shader=shader, uv=uv, triangles=triangles, poses=[])
                        result["surfaces"].append(part)
                        part_map[key] = part
                    part_map[key]["poses"].append(dict(positions=positions, normals=normals))
            finally:
                evaluated.to_mesh_clear()
        pose_tags = []
        for obj in tags:
            matrix = root @ obj.evaluated_get(graph).matrix_world
            axes = [tuple(matrix.to_3x3().col[i].normalized()) for i in range(3)]
            pose_tags.append(dict(name=obj.name, origin=tuple(float(x)*scale for x in matrix.translation), axes=axes))
        result["tags"].append(pose_tags)
    return result

def main():
    p = argparse.ArgumentParser(description="Export selected Blender objects to validated QSS-M MD3")
    p.add_argument("--profile", choices=("portable", "qssm"), default="portable")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--asset-root", type=Path, required=True)
    p.add_argument("--start", type=int, default=1)
    p.add_argument("--end", type=int, default=1)
    p.add_argument("--step", type=int, default=1)
    p.add_argument("--units-per-metre", type=float, default=32)
    p.add_argument("--origin-object", help="Use this object's first-frame position as a fixed export origin")
    p.add_argument("--shader", help="Override every material with this game-relative shader path")
    p.add_argument("--all", action="store_true", help="Export every visible render mesh and tag_ empty")
    p.add_argument("--scene-json", type=Path, help="Optional reproducible intermediate scene")
    args = p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if args.step <= 0:
        p.error("--step must be positive")
    old_frame = bpy.context.scene.frame_current
    try:
        source = extract(args)
        source["profile"] = args.profile
        if args.scene_json:
            save_json(args.scene_json, source)
        report = export_scene(source, args.output, args.asset_root, profile=args.profile)
        save_json(args.output.with_suffix(".report.json"), report)
        print(f"MD3HARNESS EXPORTED {args.output}: {report['frames']} poses, {report['tags']} tags")
    except Exception as exc:
        print(f"MD3HARNESS EXPORT FAILED: {exc}", file=sys.stderr)
        # Blender otherwise exits successfully after some Python failures.
        raise
    finally:
        bpy.context.scene.frame_set(old_frame)

if __name__ == "__main__":
    main()
