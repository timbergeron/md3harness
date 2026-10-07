import json
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib

from md3harness.format import encode_scene
from md3harness.materials import write_tga
from test_pipeline import scene
from tools.texture_kit import generate, png_bytes, texture_png


def pixels(data):
    at, compressed = 8, bytearray()
    while at < len(data):
        length = struct.unpack_from(">I", data, at)[0]
        if data[at+4:at+8] == b"IDAT":
            compressed.extend(data[at+8:at+8+length])
        at += length+12
    return zlib.decompress(compressed)


class TextureKit(unittest.TestCase):
    def test_shared_atlas_uses_all_model_uvs_without_flipping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = scene()
            original = encode_scene(source)
            (root/"a.md3").write_bytes(original)
            source["surfaces"][0]["uv"] = [(0.25, 0.5), (0.75, 0.5), (0.25, 1)]
            (root/"b.md3").write_bytes(encode_scene(source))
            write_tga(root/"progs/test.tga", 8, 4, [(10, 20, 30, 255)]*32)
            report = generate([root/"a.md3", root/"b.md3"], root, root/"kit")
            self.assertTrue(report["complete"])
            self.assertEqual(len(report["atlases"]), 1)
            atlas = report["atlases"][0]
            self.assertEqual(len(atlas["used_by"]), 2)
            svg = ET.parse(root/"kit"/atlas["uv"]).getroot()
            path = svg.find("{http://www.w3.org/2000/svg}path").attrib["d"]
            self.assertIn("M2.0000,2.0000L2.0000,4.0000", path)
            self.assertEqual((root/"a.md3").read_bytes(), original)
            self.assertEqual(json.loads((root/"kit/manifest.json").read_text()), report)

    def test_rgb_bottom_right_origin_and_image_id_convert_losslessly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"test.tga"
            # Top-left red, top-right green, bottom-left blue, bottom-right white.
            head = struct.pack("<BBBHHBHHHHBB", 3, 0, 2, 0, 0, 0, 0, 0, 2, 2, 24, 0x10)
            path.write_bytes(head+b"id!"+bytes((255,255,255,255,0,0,0,255,0,0,0,255)))
            self.assertEqual(pixels(texture_png(path)),
                b"\0"+bytes((255,0,0,255,0,255,0,255))+b"\0"+bytes((0,0,255,255,255,255,255,255)))

    def test_png_and_rgba_alpha_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rgba = bytes((5,10,15,37,20,25,30,249))
            write_tga(root/"test.tga", 2, 1, [tuple(rgba[:4]),tuple(rgba[4:])])
            png = texture_png(root/"test.tga")
            self.assertEqual(pixels(png), b"\0"+rgba)
            (root/"test.png").write_bytes(png)
            self.assertEqual(texture_png(root/"test.png"), png)

    def test_existing_output_and_truncated_texture_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root/"kit"
            output.mkdir(); (output/"keep").write_text("preserve")
            with self.assertRaisesRegex(ValueError, "new or empty"):
                generate([], root, output)
            self.assertEqual((output/"keep").read_text(), "preserve")
            write_tga(root/"bad.tga", 1, 1, [(0,0,0,255)])
            (root/"bad.tga").write_bytes((root/"bad.tga").read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError, "truncated"):
                texture_png(root/"bad.tga")


if __name__ == "__main__":
    unittest.main()
