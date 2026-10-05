#!/usr/bin/env python3
"""Rebuild the original beach net through the shared, validated exporter."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from md3harness.cli import export_scene, save_json
from md3harness.materials import write_tga
from net_geometry import FRAME_COUNT, SHADER, TEXTURE_SIZE, deformation, net_mesh, net_skin

def build(root):
    mesh = net_mesh()
    # Primitive resolution must suit the 1/64-unit grid. The harness never
    # silently deletes faces that collapse during export.
    scene = dict(schema="md3harness.scene.v1", winding="cw", name="bv_net.md3",
                 frames=[f"net{f}" for f in range(FRAME_COUNT)], surfaces=[])
    for part in mesh.surfaces:
        poses = []
        for f in range(FRAME_COUNT):
            pairs = [deformation(v, n, f, m) for v, n, m in zip(part.vertices, part.normals, part.moving)]
            poses.append(dict(positions=[p[0] for p in pairs], normals=[p[1] for p in pairs]))
        scene["surfaces"].append(dict(name=part.name, shader=SHADER, uv=part.coords, triangles=part.triangles, poses=poses))
    write_tga(root/"progs/bv_net.tga", TEXTURE_SIZE, TEXTURE_SIZE, net_skin())
    contract = json.loads(Path(__file__).with_name("net.contract.json").read_text())
    report = export_scene(scene, root/"progs/bv_net.md3", root, contract, strict=True)
    save_json(root/"net.report.json", report)
    print(f"Built net: {report['frames']} poses, {len(report['surfaces'])} surfaces, no quality issues")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("build/net"))
    build(p.parse_args().output)
