"""Inspect the exported bytes, in every pose, rather than trusting source data."""
import hashlib
import math
from pathlib import Path

from .format import FormatError, shader_path
from .materials import atlas_safe, image_info, resolve_texture
from .math3 import cross, dot, sub

def check(model, asset_root=None, manifest=None):
    manifest = manifest or {}
    issues = []
    def issue(severity, code, message, **where):
        issues.append(dict(severity=severity, code=code, message=message, **where))
    low = [[math.inf]*3 for _ in model.frames]
    high = [[-math.inf]*3 for _ in model.frames]
    radii = [0.0 for _ in model.frames]
    surfaces, textures = [], {}
    if len({s.name for s in model.surfaces}) != len(model.surfaces):
        issue("error", "surface.names", "Surface names must be unique")
    for surface in model.surfaces:
        record = dict(name=surface.name, vertices=len(surface.uv), triangles=len(surface.triangles), shaders=list(surface.shaders))
        surfaces.append(record)
        if not surface.name:
            issue("error", "surface.name", "Empty surface name")
        if len(surface.shaders) != 1:
            issue("warning", "shader.multiple", "QSS-M preview uses the first shader; review alternate skins", surface=surface.name)
        for shader in surface.shaders:
            try:
                shader_path(shader)
                if asset_root is not None and shader not in textures:
                    path = resolve_texture(asset_root, shader)
                    info = image_info(path)
                    info.update(path=path.relative_to(asset_root).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                    textures[shader] = info
                    w, h = info["width"], info["height"]
                    if w <= 0 or h <= 0 or w > 4096 or h > 4096:
                        issue("error", "texture.dimensions", f"Invalid or over-budget image dimensions: {w}x{h}", shader=shader)
                    elif w & (w-1) or h & (h-1):
                        issue("warning", "texture.npot", f"Review non-power-of-two texture {w}x{h}", shader=shader)
            except (ValueError, OSError) as exc:
                issue("error", "texture.invalid", str(exc), surface=surface.name, shader=shader)
        outside = sum(not (0 <= u <= 1 and 0 <= v <= 1) for u, v in surface.uv)
        if outside:
            issue("warning", "uv.repeat", f"{outside} vertices use repeating UVs; check the texture is tileable", surface=surface.name)
        failures = {}
        def failure(code, frame, triangle):
            entry = failures.setdefault(code, dict(count=0, frame=frame, triangle=triangle))
            entry["count"] += 1
        base_positions, base_normals = surface.pose(0)
        for f in range(len(model.frames)):
            positions, normals = surface.pose(f)
            for p in positions:
                for a in range(3):
                    low[f][a] = min(low[f][a], p[a])
                    high[f][a] = max(high[f][a], p[a])
                delta = sub(p, model.frames[f]["origin"])
                radii[f] = max(radii[f], math.sqrt(dot(delta, delta)))
            if any(surface.name.startswith(prefix) for prefix in manifest.get("static_surfaces", [])) and (positions != base_positions or normals != base_normals):
                failure("animation.static", f, None)
            for t, (a, b, c) in enumerate(surface.triangles):
                face = cross(sub(positions[b], positions[a]), sub(positions[c], positions[a]))
                area2 = dot(face, face)
                if area2 < 1e-18:
                    failure("geometry.collapsed", f, t)
                    continue
                average = tuple(normals[a][i]+normals[b][i]+normals[c][i] for i in range(3))
                if dot(face, average) > .05*math.sqrt(area2*dot(average, average)):
                    failure("geometry.winding", f, t)
        messages = {"geometry.collapsed": "Triangle collapses in exported coordinates; enlarge or rebuild this detail",
                    "geometry.winding": "Clockwise face disagrees with outward normals; inspect winding, transforms and shading",
                    "animation.static": "A declared static surface changes position or normals"}
        for code, detail in failures.items():
            issue("error", code, messages[code], surface=surface.name, **detail)
        for rule in manifest.get("atlas_regions", []):
            if surface.name.startswith(rule["surface_prefix"]):
                shader = surface.shaders[0]
                if shader in textures:
                    info = textures[shader]
                    if not atlas_safe(surface.uv, rule["rect"], (info["width"], info["height"]), rule.get("mip_level", 0)):
                        issue("warning", "texture.atlas_bleed", "UV footprint reaches outside the protected atlas region at the requested mip level", surface=surface.name)
    for f, frame in enumerate(model.frames):
        if any(frame["min"][a] > low[f][a]+.001 or frame["max"][a] < high[f][a]-.001 or frame["min"][a] > frame["max"][a] for a in range(3)):
            issue("error", "bounds.frame", "Frame bounds do not contain every exported vertex", frame=f)
        if frame["radius"] < radii[f]-.001:
            issue("error", "bounds.radius", "Frame radius does not contain every exported vertex", frame=f)
        if len({t["name"] for t in model.tags[f]}) != len(model.tags[f]):
            issue("error", "tag.duplicate", "Duplicate attachment tag", frame=f)
        if [t["name"] for t in model.tags[f]] != [t["name"] for t in model.tags[0]]:
            issue("error", "tag.topology", "Attachment names/order change between poses", frame=f)
        for tag in model.tags[f]:
            axes = tag["axes"]
            if any(abs(dot(a, a)-1) > .001 for a in axes) or any(abs(dot(axes[a], axes[b])) > .001 for a, b in ((0, 1), (0, 2), (1, 2))) or dot(cross(axes[0], axes[1]), axes[2]) < .999:
                issue("error", "tag.axes", "Tag transform must be orthonormal and right handed", frame=f, tag=tag["name"])
    dimensions = [high[0][a]-low[0][a] for a in range(3)]
    if "dimensions" in manifest:
        expected = manifest["dimensions"]
        if len(expected) != 3 or any(abs(a-b) > manifest.get("dimension_tolerance", .05) for a, b in zip(dimensions, expected)):
            issue("error", "scale.dimensions", f"Rest dimensions {dimensions} differ from the asset contract {expected}")
    if "frames" in manifest and manifest["frames"] != len(model.frames):
        issue("error", "animation.frames", "Frame count differs from asset contract")
    total_triangles = sum(len(s.triangles) for s in model.surfaces)
    if total_triangles > manifest.get("triangle_budget", 20000):
        issue("warning", "budget.triangles", f"{total_triangles} triangles exceed the review budget")
    if asset_root is None:
        issue("warning", "texture.unchecked", "Textures were not inspected; supply an asset root")
    return dict(schema="md3harness.report.v1", profile="qssm", name=model.name,
                passed=not any(i["severity"] == "error" for i in issues), frames=len(model.frames),
                tags=len(model.tags[0]), bytes=model.byte_length, dimensions=dimensions,
                surfaces=surfaces, textures=textures, issues=issues,
                pose_bounds=[dict(min=lo, max=hi) for lo, hi in zip(low, high)])

def inspect(path, asset_root=None, manifest=None):
    from .format import loads
    path = Path(path)
    if path.stat().st_size > 128*1024*1024:
        raise FormatError("model exceeds the 128 MiB inspection budget")
    data = path.read_bytes()
    report = check(loads(data), asset_root, manifest)
    report.update(model=path.name, sha256=hashlib.sha256(data).hexdigest())
    return report
