#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 timbergeron
"""Build an original, regulation-sized beach net with real cords and fittings."""

import math
from dataclasses import dataclass, field
from pathlib import Path


METRE = 32
TOP = 2.43 * METRE
BOTTOM = TOP - METRE
HALF_LENGTH = 8.5 * METRE / 2
HALF_COURT = 4 * METRE
POST_Y = HALF_COURT + METRE
POST_HEIGHT = 2.55 * METRE
POST_RADIUS = 0.11 * METRE
ANTENNA_X = 0.24
ANTENNA_Y = HALF_COURT + 0.16
ANTENNA_RADIUS = 0.005 * METRE
ANTENNA_TOP = TOP + 0.8 * METRE
BAND = 0.1 * METRE
SIDE_BAND = 0.05 * METRE
CORD_RADIUS = 0.002 * METRE
CELL = 0.1 * METRE
TEXTURE_SIZE = 1024
SHADER = "progs/bv_net"
# Six decay poses for each of three impact locations, from either side.
PULSE = (0.7, 1.0, 0.25, -0.28, 0.12, 0.0)
FRAME_COUNT = 1 + 3 * 2 * len(PULSE)
REGIONS = {"canvas": (0, 0, 512, 512), "cord": (512, 0, 1024, 256),
           "metal": (512, 256, 1024, 512), "padding": (0, 512, 512, 1024),
           "red": (512, 512, 1024, 768), "white": (512, 768, 1024, 1024)}


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, scale):
    return tuple(x * scale for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def unit(a):
    return mul(a, 1 / math.sqrt(dot(a, a)))


def uv(material, u, v):
    x0, y0, x1, y1 = REGIONS[material]
    # Thin rods need a small texel footprint. Spreading half the atlas over
    # a millimetre-scale cord chooses distant mip levels that average other
    # materials into it, making the far net flicker pale. Sample an interior
    # patch so filtering stays inside the intended material at playing range.
    if material in ("canvas", "cord", "metal", "red", "white"):
        footprint = {"canvas": (64, 64), "cord": (8, 32)}
        width, height = footprint.get(material, (32, 32))
        return (((x0 + x1) / 2 + (u - 0.5) * width) / TEXTURE_SIZE,
                ((y0 + y1) / 2 + (v - 0.5) * height) / TEXTURE_SIZE)
    # Insets prevent filtering from pulling another material into an edge.
    return ((x0 + 2 + u * (x1 - x0 - 4)) / TEXTURE_SIZE,
            (y0 + 2 + v * (y1 - y0 - 4)) / TEXTURE_SIZE)


@dataclass
class Surface:
    name: str
    vertices: list = field(default_factory=list)
    normals: list = field(default_factory=list)
    coords: list = field(default_factory=list)
    moving: list = field(default_factory=list)
    triangles: list = field(default_factory=list)


class Assembly:
    def __init__(self):
        self.surfaces = []
        self.parts = {}

    def append(self, name, vertices, normals, coords, triangles, moving=False):
        surface = self.parts.get(name)
        if surface is None or len(surface.vertices) + len(vertices) > 4096:
            surface = Surface(f"{name}_{sum(s.name.startswith(name + '_') for s in self.surfaces)}")
            self.surfaces.append(surface)
            self.parts[name] = surface
        if len(vertices) > 4096:
            raise ValueError("primitive exceeds MD3 surface limits")
        offset = len(surface.vertices)
        surface.vertices.extend(vertices)
        surface.normals.extend(normals)
        surface.coords.extend(coords)
        surface.moving.extend([moving] * len(vertices))
        for a, b, c in triangles:
            # Quake alias models use clockwise outward faces.
            face_normal = cross(sub(vertices[b], vertices[a]), sub(vertices[c], vertices[a]))
            average = add(add(normals[a], normals[b]), normals[c])
            if dot(face_normal, average) > 0:
                b, c = c, b
            surface.triangles.append((offset + a, offset + b, offset + c))

    def tube(self, name, points, radius, material, sides=8, moving=False, caps=False):
        vertices, normals, coords, triangles = [], [], [], []
        for i, point in enumerate(points):
            tangent = unit(sub(points[min(i + 1, len(points) - 1)], points[max(0, i - 1)]))
            reference = (0, 0, 1) if abs(tangent[2]) < 0.9 else (1, 0, 0)
            u = unit(cross(tangent, reference))
            v = cross(tangent, u)
            for j in range(sides + 1):
                angle = math.tau * j / sides
                normal = add(mul(u, math.cos(angle)), mul(v, math.sin(angle)))
                vertices.append(add(point, mul(normal, radius)))
                normals.append(normal)
                coords.append(uv(material, j / sides, i % 2))
        for i in range(len(points) - 1):
            for j in range(sides):
                a = i * (sides + 1) + j
                b = a + sides + 1
                triangles.extend(((a, b, a + 1), (a + 1, b, b + 1)))
        if caps:
            for end in (0, len(points) - 1):
                normal = unit(sub(points[end], points[1 if end == 0 else -2]))
                centre = len(vertices)
                vertices.append(points[end])
                normals.append(normal)
                coords.append(uv(material, 0.5, 0.5))
                for j in range(sides + 1):
                    vertices.append(vertices[end * (sides + 1) + j])
                    normals.append(normal)
                    coords.append(uv(material, 0.5, 0.5))
                triangles.extend((centre, centre + j + 1, centre + j + 2) for j in range(sides))
        self.append(name, vertices, normals, coords, triangles, moving)

    def ribbon(self, name, start, end, width, material="canvas", moving=False):
        # Bevelled cloth, including front/back faces and sewn folded edges.
        tangent = unit(sub(end, start))
        across = unit(cross((1, 0, 0), tangent))
        edge = width / 2
        bevel = min(0.06, width / 8)
        section = ((0.12, -edge + bevel), (0.12, edge - bevel),
                   (0.06, edge), (-0.06, edge), (-0.12, edge - bevel),
                   (-0.12, -edge + bevel), (-0.06, -edge), (0.06, -edge))
        vertices, normals, coords, triangles = [], [], [], []
        steps = max(1, math.ceil(math.sqrt(dot(sub(end, start), sub(end, start))) / CELL))
        for i in range(steps + 1):
            centre = add(start, mul(sub(end, start), i / steps))
            for x, height in section:
                vertices.append(add(centre, add((x, 0, 0), mul(across, height))))
                normal = unit(add((x / 0.12, 0, 0), mul(across, height / edge)))
                # Flat faces need flat normals; corner shoulders remain rounded.
                if abs(x) == 0.12:
                    normal = (1 if x > 0 else -1, 0, 0)
                normals.append(normal)
                coords.append(uv(material, i % 2, (height + edge) / width))
        for i in range(steps):
            for j in range(8):
                a, c = i * 8 + j, i * 8 + (j + 1) % 8
                b, d = a + 8, c + 8
                triangles.extend(((a, b, c), (c, b, d)))
        self.append(name, vertices, normals, coords, triangles, moving)

    def torus(self, name, centre, axis, major, minor, material="metal", rings=12, sides=4):
        axis = unit(axis)
        u = unit(cross(axis, (0, 0, 1) if abs(axis[2]) < 0.9 else (1, 0, 0)))
        v = cross(axis, u)
        vertices, normals, coords, triangles = [], [], [], []
        for i in range(rings + 1):
            radial = add(mul(u, math.cos(math.tau * i / rings)), mul(v, math.sin(math.tau * i / rings)))
            for j in range(sides + 1):
                angle = math.tau * j / sides
                normal = add(mul(radial, math.cos(angle)), mul(axis, math.sin(angle)))
                vertices.append(add(centre, add(mul(radial, major), mul(normal, minor))))
                normals.append(normal)
                coords.append(uv(material, j / sides, i / rings))
        for i in range(rings):
            for j in range(sides):
                a = i * (sides + 1) + j
                b = a + sides + 1
                triangles.extend(((a, b, a + 1), (a + 1, b, b + 1)))
        self.append(name, vertices, normals, coords, triangles)


def padded_post(mesh, y):
    # A capsule silhouette: no square timber and no exposed sharp post tops.
    profile = []
    for i in range(1, 7):
        angle = -math.pi / 2 + i * math.pi / 12
        profile.append((POST_RADIUS + POST_RADIUS * math.sin(angle),
                        POST_RADIUS * math.cos(angle), math.sin(angle), math.cos(angle)))
    for i in range(1, 7):
        profile.append((POST_RADIUS + (POST_HEIGHT - 2 * POST_RADIUS) * i / 6, POST_RADIUS, 0, 1))
    for i in range(1, 6):
        angle = i * math.pi / 12
        profile.append((POST_HEIGHT - POST_RADIUS + POST_RADIUS * math.sin(angle),
                        POST_RADIUS * math.cos(angle), math.sin(angle), math.cos(angle)))
    sides = 24
    vertices, normals, coords, triangles = [], [], [], []
    for z, radius, nz, nr in profile:
        for j in range(sides + 1):
            angle = math.tau * j / sides
            vertices.append((radius * math.cos(angle), y + radius * math.sin(angle), z))
            normals.append((nr * math.cos(angle), nr * math.sin(angle), nz))
            coords.append(uv("padding", j / sides, z / POST_HEIGHT))
    for i in range(len(profile) - 1):
        for j in range(sides):
            a = i * (sides + 1) + j
            b = a + sides + 1
            triangles.extend(((a, b, a + 1), (a + 1, b, b + 1)))
    for end, z, normal in ((0, 0, (0, 0, -1)), (len(profile) - 1, POST_HEIGHT, (0, 0, 1))):
        centre = len(vertices)
        vertices.append((0, y, z))
        normals.append(normal)
        coords.append(uv("padding", 0.5, z / POST_HEIGHT))
        triangles.extend((centre, end * (sides + 1) + j, end * (sides + 1) + j + 1) for j in range(sides))
    mesh.append("padded_posts", vertices, normals, coords, triangles)
    # Canvas retaining collars sit flush against the pad.
    for z in (BAND, BOTTOM + BAND / 2, TOP - BAND / 2):
        mesh.torus("pad_collars", (0, y, z), (0, 0, 1), POST_RADIUS + 0.015, 0.06, "canvas", rings=24, sides=4)


def net_mesh():
    mesh = Assembly()
    low, high = BOTTOM + BAND, TOP - BAND
    for column in range(86):
        y = -HALF_LENGTH + column * CELL
        points = [(0, y, low + i * CELL) for i in range(9)]
        mesh.tube("vertical_cords", points, CORD_RADIUS, "cord", sides=6, moving=True)
    for row in range(9):
        z = low + row * CELL
        # Offset crossing strands slightly to give the mesh a woven surface.
        points = [(0.035, -HALF_LENGTH + i * CELL, z) for i in range(86)]
        mesh.tube("horizontal_cords", points, CORD_RADIUS, "cord", sides=6, moving=True)
    for z in (BOTTOM + BAND / 2, TOP - BAND / 2):
        mesh.ribbon("horizontal_bands", (0, -HALF_LENGTH, z), (0, HALF_LENGTH, z), BAND)
    for side in (-1, 1):
        # Side bands lie inside the court edge; antennas sit at their outer edge.
        y = side * (HALF_COURT - SIDE_BAND / 2)
        mesh.ribbon("side_bands", (0, y, BOTTOM), (0, y, TOP), SIDE_BAND, moving=True)
        mesh.ribbon("end_bindings", (0, side * (HALF_LENGTH - 0.24), BOTTOM),
                    (0, side * (HALF_LENGTH - 0.24), TOP), 0.48, moving=True)
        padded_post(mesh, side * POST_Y)
        for z in (BOTTOM + BAND / 2, TOP - BAND / 2):
            net_y = side * (HALF_LENGTH - 0.8)
            post_y = side * (POST_Y - POST_RADIUS)
            mesh.tube("tension_cords", [(0, side * HALF_LENGTH, z), (0, post_y, z)],
                      0.055, "cord", sides=8)
            for x in (-0.15, 0.15):
                mesh.torus("eyelets", (x, net_y, z), (1, 0, 0), 0.24, 0.055)
            for position in (net_y, post_y):
                mesh.torus("anchor_eyes", (0, position, z), (1, 0, 0), 0.26, 0.065)
            centre = side * (HALF_LENGTH + POST_Y - POST_RADIUS) / 2
            mesh.tube("turnbuckles", [(0, centre - 0.65, z), (0, centre + 0.65, z)],
                      0.17, "metal", sides=12, caps=True)
        # Opposite faces of the net carry the two antenna rods.
        x, y = side * ANTENNA_X, side * ANTENNA_Y
        mesh.tube("antenna_base", [(x, y, BOTTOM), (x, y, TOP)],
                  ANTENNA_RADIUS, "white", sides=12, caps=True)
        for stripe in range(8):
            z = TOP + stripe * CELL
            mesh.tube("antenna_stripes", [(x, y, z), (x, y, z + CELL)], ANTENNA_RADIUS,
                      "red" if stripe % 2 == 0 else "white", sides=12, caps=stripe == 7)
        for z in (BOTTOM + 1.2, TOP - 1.2):
            mesh.torus("antenna_clips", (x, y, z), (0, 0, 1), ANTENNA_RADIUS + 0.035,
                       0.045, "metal", rings=12)
    return mesh


def deformation(vertex, normal, frame, moving):
    if not frame or not moving:
        return vertex, normal
    group, phase = divmod(frame - 1, len(PULSE))
    region, direction = divmod(group, 2)
    centre = (-90, 0, 90)[region]
    y, z = vertex[1], vertex[2]
    vertical = math.pi * max(0, min(1, (z - BOTTOM) / (TOP - BOTTOM)))
    envelope = math.exp(-((y - centre) / 62) ** 2)
    strength = PULSE[phase] * (1 if direction == 0 else -1)
    displacement = strength * envelope * math.sin(vertical)
    dy = displacement * (-2 * (y - centre) / (62 * 62))
    dz = strength * envelope * math.cos(vertical) * math.pi / (TOP - BOTTOM)
    return (vertex[0] + displacement, y, z), unit((normal[0], normal[1] - dy * normal[0],
                                                normal[2] - dz * normal[0]))


def net_skin():
    """Original woven canvas, braided cord, pad seams, metal and fibreglass."""
    pixels = []
    for y in range(TEXTURE_SIZE):
        for x in range(TEXTURE_SIZE):
            grain = ((x * 73 + y * 37 + (x ^ y) * 19) % 11 - 5) * 0.35
            if x < 512 and y < 512:
                weave = (2 if x % 4 < 2 else -2) + (1 if y % 4 < 2 else -1)
                colour = (31 + weave, 66 + weave, 94 + weave)
                if y in (226, 227, 284, 285) and x % 12 < 7:
                    colour = (143, 161, 166)
                elif y in (225, 230, 281, 286):
                    colour = (20, 42, 60)
            elif x >= 512 and y < 256:
                braid = 3 * math.sin((x + y * 1.7) * 0.24)
                colour = (22 + braid, 30 + braid, 34 + braid)
            elif x >= 512 and y < 512:
                satin = 8 * math.sin(x * 0.045) + 2 * math.sin(y * 1.7)
                colour = (137 + satin, 150 + satin, 158 + satin)
            elif x < 512:
                weave = (1 if x % 3 else -1) + (1 if y % 3 else -1)
                colour = (25 + weave, 55 + weave, 78 + weave)
                if x in (14, 15, 496, 497) and y % 10 < 6:
                    colour = (101, 125, 139)
                elif 475 <= x <= 479:
                    colour = (14, 29, 42)
                elif x in (480, 482) and y % 5 < 3:
                    colour = (106, 118, 122)
            elif y < 768:
                colour = (218, 41, 43)
            else:
                colour = (239, 239, 225)
            pixels.append((*[max(0, min(255, round(c + grain))) for c in colour], 255))
    return pixels
