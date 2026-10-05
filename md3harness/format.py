"""Strict MD3 v15 reader and deterministic QSS-M writer.

Decoded poses are streamed from packed bytes; a many-frame model does not
allocate millions of Python vectors just to check its header.
"""
from dataclasses import dataclass
import math
from pathlib import Path, PurePosixPath
import struct

from .math3 import dot, unit

HEADER = struct.Struct("<4si64s9i")
FRAME = struct.Struct("<10f16s")
TAG = struct.Struct("<64s12f")
SURFACE = struct.Struct("<4s64s10i")
VERTEX = struct.Struct("<3h2B")
LIMITS = dict(frames=1024, tags=16, surfaces=32, vertices=4096, triangles=8192, shaders=256)

class FormatError(ValueError):
    pass

def string(value, size=64):
    try:
        data = value.encode("ascii")
    except (AttributeError, UnicodeError) as exc:
        raise FormatError("MD3 names must be ASCII strings") from exc
    if not data or len(data) >= size or b"\0" in data:
        raise FormatError(f"name must occupy 1..{size-1} ASCII bytes: {value!r}")
    return data.ljust(size, b"\0")

def read_string(data):
    if b"\0" not in data:
        raise FormatError("unterminated MD3 name")
    try:
        return data.split(b"\0", 1)[0].decode("ascii")
    except UnicodeError as exc:
        raise FormatError("non-ASCII MD3 name") from exc

def shader_path(value):
    string(value)
    p = PurePosixPath(value)
    if "/" not in value or p.is_absolute() or "\\" in value or any(x in ("..", ".", "") for x in value.split("/")):
        raise FormatError(f"shader must be a safe game-relative path: {value!r}")
    if p.suffix:
        raise FormatError("QSS-M shader paths must omit the image extension")
    return value

def normal_bytes(normal):
    x, y, z = unit(normal)
    return (round(math.acos(max(-1, min(1, z)))*255/math.tau) & 255,
            round((math.atan2(y, x) % math.tau)*255/math.tau) & 255)

def decode_normal(polar, azimuth):
    a, b = polar*math.tau/255, azimuth*math.tau/255
    return (math.sin(a)*math.cos(b), math.sin(a)*math.sin(b), math.cos(a))

def finite(values, label):
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in values):
        raise FormatError(f"{label} contains a non-finite number")

def regions(limit, entries, label):
    used = []
    for start, count, stride in entries:
        end = start + count*stride
        if start < 108 or count < 0 or end > limit:
            raise FormatError(f"{label}: data range outside its container")
        if count:
            if any(start < b and end > a for a, b in used):
                raise FormatError(f"{label}: overlapping data ranges")
            used.append((start, end))

@dataclass(frozen=True)
class SurfaceData:
    name: str
    shaders: tuple
    triangles: tuple
    uv: tuple
    num_frames: int
    packed: bytes

    def pose(self, frame):
        if not 0 <= frame < self.num_frames:
            raise IndexError(frame)
        start = frame*len(self.uv)*8
        positions, normals = [], []
        for x, y, z, a, b in VERTEX.iter_unpack(self.packed[start:start+len(self.uv)*8]):
            positions.append((x/64, y/64, z/64))
            normals.append(decode_normal(a, b))
        return positions, normals

@dataclass(frozen=True)
class Model:
    name: str
    frames: tuple
    tags: tuple
    surfaces: tuple
    byte_length: int

def loads(data):
    if len(data) < 108:
        raise FormatError("truncated header")
    ident, version, name, flags, nf, nt, ns, skins, of, ot, os, end = HEADER.unpack_from(data)
    if ident != b"IDP3" or version != 15:
        raise FormatError("expected MD3 IDP3 version 15")
    if not 1 <= nf <= LIMITS["frames"] or not 0 <= nt <= LIMITS["tags"] or not 1 <= ns <= LIMITS["surfaces"]:
        raise FormatError("frame, tag or surface count exceeds MD3 limits")
    if end != len(data):
        raise FormatError("file end does not match its byte length")
    regions(end, [(of, nf, 56), (ot, nt*nf, 112), (os, end-os, 1)], "header")
    frames = []
    for f in range(nf):
        row = FRAME.unpack_from(data, of+f*56)
        finite(row[:10], "frame")
        frames.append(dict(min=row[:3], max=row[3:6], origin=row[6:9], radius=row[9], name=read_string(row[10])))
    tags = []
    for f in range(nf):
        pose = []
        for t in range(nt):
            row = TAG.unpack_from(data, ot+(f*nt+t)*112)
            finite(row[1:], "tag")
            pose.append(dict(name=read_string(row[0]), origin=row[1:4], axes=(row[4:7], row[7:10], row[10:13])))
        tags.append(tuple(pose))
    surfaces = []
    offset = os
    for _ in range(ns):
        if offset+108 > end:
            raise FormatError("truncated surface header")
        ident, sn, sf, snf, nsh, nv, ntri, tri, sh, uv, xyz, se = SURFACE.unpack_from(data, offset)
        if ident != b"IDP3" or snf != nf:
            raise FormatError("surface ident or frame count mismatch")
        if not 1 <= nv <= LIMITS["vertices"] or not 1 <= ntri <= LIMITS["triangles"] or not 1 <= nsh <= LIMITS["shaders"]:
            raise FormatError("surface vertex, triangle or shader count exceeds MD3 limits")
        if se < 108 or offset+se > end:
            raise FormatError("invalid surface end")
        regions(se, [(tri, ntri, 12), (sh, nsh, 68), (uv, nv, 8), (xyz, nv*nf, 8)], "surface")
        faces = tuple(struct.iter_unpack("<3i", data[offset+tri:offset+tri+ntri*12]))
        if any(i < 0 or i >= nv for face in faces for i in face):
            raise FormatError("triangle index outside the surface")
        shaders = tuple(read_string(struct.unpack_from("<64si", data, offset+sh+i*68)[0]) for i in range(nsh))
        coords = tuple(struct.iter_unpack("<2f", data[offset+uv:offset+uv+nv*8]))
        finite([x for pair in coords for x in pair], "UV")
        surfaces.append(SurfaceData(read_string(sn), shaders, faces, coords, nf, data[offset+xyz:offset+xyz+nv*nf*8]))
        offset += se
    if offset != end:
        raise FormatError("unaccounted bytes after the last surface")
    return Model(read_string(name), tuple(frames), tuple(tags), tuple(surfaces), end)

def load(path, max_bytes=128*1024*1024):
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise FormatError(f"model exceeds inspection byte budget ({max_bytes})")
    return loads(path.read_bytes())

def partition(surface, max_vertices=4096, max_triangles=8192):
    """Split at triangle boundaries, keeping UVs and every pose aligned."""
    output, mapping, faces = [], {}, []
    def finish():
        if not faces:
            return
        indices = list(mapping)
        output.append(dict(name=f"{surface['name']}_{len(output)}", shader=surface["shader"],
            uv=[surface["uv"][i] for i in indices], triangles=list(faces),
            poses=[dict(positions=[p["positions"][i] for i in indices], normals=[p["normals"][i] for i in indices]) for p in surface["poses"]]))
    for face in surface["triangles"]:
        if len(face) != 3 or any(type(i) is not int or i < 0 or i >= len(surface["uv"]) for i in face):
            raise FormatError("invalid source triangle")
        if len(mapping)+len(set(face)-mapping.keys()) > max_vertices or len(faces) >= max_triangles:
            finish()
            mapping, faces = {}, []
        local = []
        for i in face:
            if i not in mapping:
                mapping[i] = len(mapping)
            local.append(mapping[i])
        faces.append(tuple(local))
    finish()
    return output

def encode_scene(scene):
    """Scene v1 uses CCW outward triangles, Z up, and already-scaled units."""
    if scene.get("schema") != "md3harness.scene.v1" or scene.get("winding", "ccw") not in ("ccw", "cw"):
        raise FormatError("expected md3harness.scene.v1 with ccw or cw winding")
    names = scene["frames"]
    nf = len(names)
    if not 1 <= nf <= 1024:
        raise FormatError("invalid source frame count")
    bounds = [[([math.inf]*3), ([-math.inf]*3), 0] for _ in names]
    parts = []
    for source in scene["surfaces"]:
        nv = len(source["uv"])
        if not nv or len(source["poses"]) != nf:
            raise FormatError("empty surface or mismatched source pose count")
        for pair in source["uv"]:
            if len(pair) != 2:
                raise FormatError("UV must have two components")
            finite(pair, "UV")
        for pose in source["poses"]:
            if len(pose["positions"]) != nv or len(pose["normals"]) != nv:
                raise FormatError("topology/normal count changes between poses")
        shader_path(source["shader"])
        parts.extend(partition(source))
    if not 1 <= len(parts) <= 32:
        raise FormatError("export needs 1..32 surfaces after splitting")
    output = []
    for part in parts:
        packed = bytearray()
        for f, pose in enumerate(part["poses"]):
            for position, normal in zip(pose["positions"], pose["normals"]):
                if len(position) != 3:
                    raise FormatError("position must have three components")
                finite(position, "position")
                xyz = tuple(round(x*64) for x in position)
                if any(x < -32768 or x > 32767 for x in xyz):
                    raise FormatError("position outside MD3 range: -512..511.984375 units")
                quantized = tuple(x/64 for x in xyz)
                for a in range(3):
                    bounds[f][0][a] = min(bounds[f][0][a], quantized[a])
                    bounds[f][1][a] = max(bounds[f][1][a], quantized[a])
                bounds[f][2] = max(bounds[f][2], math.sqrt(dot(quantized, quantized)))
                packed.extend(VERTEX.pack(*xyz, *normal_bytes(normal)))
        faces = part["triangles"]
        if scene.get("winding", "ccw") == "ccw":
            faces = [(a, c, b) for a, b, c in faces]
        tri = 108
        sh = tri+len(faces)*12
        uv = sh+68
        xyz = uv+len(part["uv"])*8
        end = xyz+len(packed)
        output.append(SURFACE.pack(b"IDP3", string(part["name"]), 0, nf, 1, len(part["uv"]), len(faces), tri, sh, uv, xyz, end)
            + b"".join(struct.pack("<3i", *face) for face in faces)
            + struct.pack("<64si", string(part["shader"]), 0)
            + b"".join(struct.pack("<2f", *pair) for pair in part["uv"]) + packed)
    tags = scene.get("tags", [[] for _ in names])
    if len(tags) != nf or any(len(p) != len(tags[0]) for p in tags) or len(tags[0]) > 16:
        raise FormatError("invalid source tag counts")
    tag_data = bytearray()
    for pose in tags:
        for tag in pose:
            if len(tag["origin"]) != 3 or len(tag["axes"]) != 3 or any(len(a) != 3 for a in tag["axes"]):
                raise FormatError("invalid source tag transform")
            values = list(tag["origin"]) + [x for a in tag["axes"] for x in a]
            finite(values, "tag")
            tag_data.extend(TAG.pack(string(tag["name"]), *values))
    of = 108
    ot = of+nf*56
    os = ot+len(tag_data)
    return (HEADER.pack(b"IDP3", 15, string(scene["name"]), 0, nf, len(tags[0]), len(output), 0, of, ot, os, os+sum(map(len, output)))
        + b"".join(FRAME.pack(*lo, *hi, 0, 0, 0, radius, string(name, 16)) for name, (lo, hi, radius) in zip(names, bounds))
        + tag_data + b"".join(output))
