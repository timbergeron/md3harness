"""Export editable PNG atlases and UV guides from validated MD3 binaries."""
import argparse
from collections import defaultdict
import hashlib
import html
import json
import math
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from md3harness.format import FormatError, load, shader_path
from md3harness.materials import image_info, resolve_texture


def png_bytes(width, height, rgba):
    def chunk(kind, body):
        return (struct.pack(">I", len(body))+kind+body
                +struct.pack(">I", zlib.crc32(kind+body) & 0xffffffff))
    rows = b"".join(b"\0"+rgba[y*width*4:(y+1)*width*4] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            +chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            +chunk(b"IDAT", zlib.compress(rows, 9))+chunk(b"IEND", b""))


def texture_png(path):
    """Copy PNG bytes; losslessly convert uncompressed 24/32-bit true-color TGA."""
    path = Path(path)
    info = image_info(path)
    data = path.read_bytes()
    if info["format"] == "png":
        return data
    if data[1] or data[2] != 2 or data[17] & 0xc0:
        raise ValueError("texture kit needs PNG or non-interleaved, uncompressed true-color TGA")
    width, height, depth = struct.unpack_from("<HHB", data, 12)
    stride, start = depth//8, 18+data[0]
    if len(data) < start+width*height*stride:
        raise ValueError("truncated TGA pixels")
    rgba = bytearray(width*height*4)
    for y in range(height):
        source_y = y if data[17] & 0x20 else height-1-y
        for x in range(width):
            source_x = width-1-x if data[17] & 0x10 else x
            at = start+(source_y*width+source_x)*stride
            b, g, r = data[at:at+3]
            a = data[at+3] if stride == 4 else 255
            target = (y*width+x)*4
            rgba[target:target+4] = bytes((r, g, b, a))
    return png_bytes(width, height, rgba)


def generate(models, asset_root, output):
    """Deduplicate shared shaders across models; leave the runtime assets intact."""
    output, asset_root = Path(output), Path(asset_root)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("texture kit output must be new or empty")
    if not models:
        raise ValueError("provide at least one MD3")
    edges, used_by, sources = defaultdict(set), defaultdict(list), []
    for path in models:
        path = Path(path)
        model = load(path)
        sources.append(dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        for surface in model.surfaces:
            if not all(math.isfinite(value) for uv in surface.uv for value in uv):
                raise ValueError("non-finite texture coordinates")
            for shader in surface.shaders:
                shader_path(shader)
                used_by[shader].append(dict(model=path.name, surface=surface.name))
                for triangle in surface.triangles:
                    for a, b in zip(triangle, triangle[1:]+triangle[:1]):
                        edges[shader].add(tuple(sorted((surface.uv[a], surface.uv[b]))))
        del model
    # Resolve and check every input before creating output files.
    textures = {shader: resolve_texture(asset_root, shader) for shader in edges}
    for path in textures.values():
        image_info(path)
    output.mkdir(parents=True, exist_ok=True)
    manifest = dict(schema="md3harness.texture-kit.v1", complete=False, models=sources, atlases=[])
    metadata = output/"manifest.json"
    metadata.write_text(json.dumps(manifest, indent=2)+"\n")
    cards = []
    for shader in sorted(edges):
        texture = textures[shader]
        info = image_info(texture)
        width, height = info["width"], info["height"]
        # Retain shader subdirectories: equal basenames must not collide.
        base = output/shader
        base.parent.mkdir(parents=True, exist_ok=True)
        png, svg = Path(str(base)+".png"), Path(str(base)+"_uv.svg")
        png.write_bytes(texture_png(texture))
        lines = " ".join(f"M{a[0]*width:.4f},{a[1]*height:.4f}L{b[0]*width:.4f},{b[1]*height:.4f}"
                         for a, b in sorted(edges[shader]))
        title = html.escape(shader)
        svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                       f'viewBox="0 0 {width} {height}"><title>{title}: MD3 UV edges</title>'
                       f'<path fill="none" stroke="#00eaff" stroke-opacity="0.7" stroke-width="0.5" d="{lines}"/></svg>\n')
        png_rel, svg_rel = png.relative_to(output).as_posix(), svg.relative_to(output).as_posix()
        manifest["atlases"].append(dict(shader=shader, width=width, height=height,
            source=texture.relative_to(asset_root).as_posix(),
            source_sha256=hashlib.sha256(texture.read_bytes()).hexdigest(),
            png=png_rel, png_sha256=hashlib.sha256(png.read_bytes()).hexdigest(),
            uv=svg_rel, uv_sha256=hashlib.sha256(svg.read_bytes()).hexdigest(),
            edge_count=len(edges[shader]), used_by=used_by[shader]))
        png_url, svg_url = html.escape(png_rel), html.escape(svg_rel)
        cards.append(f'<article><h2>{title} — {width} × {height}</h2>'
                     f'<div class="atlas" style="aspect-ratio:{width}/{height}">'
                     f'<img src="{png_url}"/><object data="{svg_url}" type="image/svg+xml"></object></div>'
                     f'<p><a href="{png_url}">Original PNG</a> · <a href="{svg_url}">UV guide</a></p></article>')
    (output/"index.html").write_text('<!doctype html><meta charset="utf-8"><title>MD3 texture kit</title>'
        '<style>body{background:#15202b;color:#e8edf1;font:16px system-ui;margin:24px}'
        'a{color:#69deff}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}'
        '.atlas{position:relative}.atlas img,.atlas object{position:absolute;inset:0;width:100%;height:100%}'
        'object{pointer-events:none}body.hide object{display:none}button{padding:10px;margin-bottom:24px}</style>'
        '<h1>Texture atlases and UV guides</h1><p>Blue lines show UV edges. Hide guides before export. '
        'Images use a top-left origin; repeated UVs outside 0–1 extend beyond the canvas.</p>'
        '<button onclick="document.body.classList.toggle(\'hide\')">Toggle guides</button><main>'
        +"".join(cards)+'</main>')
    manifest["complete"] = True
    metadata.write_text(json.dumps(manifest, indent=2)+"\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", type=Path)
    parser.add_argument("--asset-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = generate(args.models, args.asset_root, args.output)
    except (FormatError, ValueError, OSError) as exc:
        parser.exit(1, f"texture kit: {exc}\n")
    print(f"Texture kit: {args.output} ({len(report['atlases'])} atlases)")


if __name__ == "__main__":
    main()
