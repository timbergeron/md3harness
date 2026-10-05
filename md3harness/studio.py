"""Studio brush/texture helpers adapted from quake-beach-volleyball (GPL-2.0-or-later)."""
import struct
from pathlib import Path

def pak_entry(pak, name):
    with Path(pak).open("rb") as stream:
        magic, offset, length = struct.unpack("<4sii", stream.read(12))
        if magic != b"PACK" or length % 64:
            raise ValueError(f"invalid PAK: {pak}")
        stream.seek(offset)
        directory = stream.read(length)
        for cursor in range(0, length, 64):
            raw, start, size = struct.unpack_from("<56sii", directory, cursor)
            if raw.split(b"\0", 1)[0].decode("ascii") == name:
                stream.seek(start)
                return stream.read(size)
    raise ValueError(f"{name} missing from {pak}")


def palette_from(base):
    for name in ("pak0.pak", "pak1.pak"):
        path = Path(base) / "id1" / name
        if path.is_file():
            try:
                data = pak_entry(path, "gfx/palette.lmp")
                if len(data) == 768:
                    return [tuple(data[i:i + 3]) for i in range(0, 768, 3)]
            except ValueError:
                pass
    loose = Path(base) / "id1/gfx/palette.lmp"
    if loose.is_file():
        data = loose.read_bytes()
        if len(data) == 768:
            return [tuple(data[i:i + 3]) for i in range(0, 768, 3)]
    raise ValueError("a Quake id1 palette is required to build the assets")


def nearest(palette, color, fullbright=False):
    indices = range(224, 255) if fullbright else range(224)
    return min(indices, key=lambda i: sum((a - b) ** 2
               for a, b in zip(palette[i], color)))


def texture(name, width, height, pixels):
    offsets = [40]
    levels = []
    for level in range(4):
        step = 1 << level
        levels.append(bytes(pixels[y * width + x]
                            for y in range(0, height, step)
                            for x in range(0, width, step)))
        if level < 3:
            offsets.append(offsets[-1] + len(levels[-1]))
    return struct.pack("<16s6I", name.encode(), width, height, *offsets) + b"".join(levels)


def write_wad(path, textures):
    offset = 12
    body = bytearray()
    directory = bytearray()
    for name, data in textures.items():
        directory.extend(struct.pack("<iiiBB2x16s", offset, len(data), len(data),
                                     68, 0, name.encode()))
        body.extend(data)
        offset += len(data)
    path.write_bytes(struct.pack("<4sii", b"WAD2", len(textures), offset) + body + directory)


def brush(mins, maxs, material, scale=1):
    """Classic MAP planes use cross(p0-p1, p2-p1) as the outward normal."""
    x0, y0, z0 = mins
    x1, y1, z1 = maxs
    planes = (
        ((x0, y0, z0), (x0, y1, z0), (x0, y0, z1)),
        ((x1, y0, z0), (x1, y0, z1), (x1, y1, z0)),
        ((x0, y0, z0), (x0, y0, z1), (x1, y0, z0)),
        ((x0, y1, z0), (x1, y1, z0), (x0, y1, z1)),
        ((x0, y0, z0), (x1, y0, z0), (x0, y1, z0)),
        ((x0, y0, z1), (x0, y1, z1), (x1, y0, z1)),
    )
    lines = ["{"]
    for points in planes:
        line = " ".join("( %g %g %g )" % point for point in points)
        lines.append(f"{line} {material} 0 0 0 {scale} {scale}")
    return "\n".join(lines + ["}"])
