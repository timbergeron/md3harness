"""Image metadata, original TGA output, and atlas filtering checks."""
from pathlib import Path
import struct

def write_tga(path, width, height, pixels):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 32, 0x28))
    count = 0
    for r, g, b, a in pixels:
        data.extend((b, g, r, a))
        count += 1
    if count != width*height:
        raise ValueError("TGA pixel count mismatch")
    path.write_bytes(data)

def image_info(path):
    path = Path(path)
    with path.open("rb") as stream:
        head = stream.read(32)
    if path.suffix.lower() == ".png" and head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
        width, height = struct.unpack_from(">II", head, 16)
        return dict(width=width, height=height, alpha=head[25] in (4, 6), format="png")
    if path.suffix.lower() == ".tga" and len(head) >= 18 and head[2] in (2, 10):
        width, height, depth = struct.unpack_from("<HHB", head, 12)
        if depth not in (24, 32) or not width or not height:
            raise ValueError("unsupported TGA dimensions/depth")
        if head[2] == 2 and path.stat().st_size < 18+head[0]+width*height*(depth//8):
            raise ValueError("truncated TGA pixels")
        return dict(width=width, height=height, alpha=depth == 32, format="tga")
    raise ValueError("unsupported image header; use true-color TGA or PNG")

def resolve_texture(root, shader):
    for extension in (".tga", ".png"):
        candidate = Path(root)/(shader+extension)
        if candidate.is_file():
            # Prevent a texture symlink escaping the asset package.
            if not candidate.resolve().is_relative_to(Path(root).resolve()):
                raise ValueError("texture symlink escapes the asset root")
            return candidate
    raise ValueError(f"missing texture: {shader}.tga or .png")

def atlas_safe(coords, rectangle, size, mip_level):
    """Conservative bilinear footprint including the requested mip's texels."""
    x0, y0, x1, y1 = rectangle
    w, h = size
    guard = 2**mip_level
    return all(x0+guard <= u*w <= x1-guard and y0+guard <= v*h <= y1-guard for u, v in coords)
