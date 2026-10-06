import copy
import contextlib
import io
import json
from array import array
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from md3harness.cli import export_scene, main
from md3harness.format import FormatError, decode_normal, encode_scene, loads, normal_bytes, partition
from md3harness.materials import atlas_safe, image_info, write_tga
from md3harness.preview import cameras, stage_paks
from md3harness.png import changed_pixels, read_rgb
from md3harness.quality import check

def scene():
    pose = dict(positions=[(0, 0, 0), (1, 0, 0), (0, 1, 0)], normals=[(0, 0, 1)]*3)
    return dict(schema="md3harness.scene.v1", name="fixture.md3", frames=["rest", "move"],
                surfaces=[dict(name="panel", shader="progs/test", uv=[(0, 0), (1, 0), (0, 1)],
                               triangles=[(0, 1, 2)], poses=[pose, copy.deepcopy(pose)])])

def codes(model, **kwargs):
    return {i["code"] for i in check(model, **kwargs)["issues"]}

class Pipeline(unittest.TestCase):
    def test_determinism_and_roundtrip(self):
        source = scene()
        data = encode_scene(source)
        self.assertEqual(data, encode_scene(source))
        model = loads(data)
        self.assertEqual(model.frames[0]["max"], (1, 1, 0))
        self.assertEqual(model.surfaces[0].triangles, ((0, 2, 1),))
        self.assertEqual(model.surfaces[0].pose(1)[0], source["surfaces"][0]["poses"][1]["positions"])
        self.assertTrue(check(model)["passed"])

    def test_truncation_and_hostile_counts(self):
        data = encode_scene(scene())
        for end in (0, 20, 107, 120, len(data)-1):
            with self.assertRaises(FormatError):
                loads(data[:end])
        bad = bytearray(data)
        struct.pack_into("<i", bad, 76, 2**30)
        with self.assertRaises(FormatError):
            loads(bad)

    def test_overlapping_surface_blocks(self):
        data = bytearray(encode_scene(scene()))
        offset = struct.unpack_from("<i", data, 100)[0]
        triangles = struct.unpack_from("<i", data, offset+88)[0]
        struct.pack_into("<i", data, offset+96, triangles)
        with self.assertRaisesRegex(FormatError, "overlapping"):
            loads(data)

    def test_out_of_range_triangle_index(self):
        data = bytearray(encode_scene(scene()))
        offset = struct.unpack_from("<i", data, 100)[0]
        struct.pack_into("<i", data, offset+108, 99)
        with self.assertRaisesRegex(FormatError, "index"):
            loads(data)

    def test_collapsed_later_pose_is_rejected_and_previous_export_preserved(self):
        source = scene()
        source["surfaces"][0]["poses"][1]["positions"][2] = (0, .001, 0)
        self.assertIn("geometry.collapsed", codes(loads(encode_scene(source))))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"existing.md3"
            output.write_bytes(b"previous good asset")
            with self.assertRaisesRegex(ValueError, "geometry.collapsed"):
                export_scene(source, output)
            self.assertEqual(output.read_bytes(), b"previous good asset")

    def test_wrong_winding_is_caught(self):
        source = scene()
        source["winding"] = "cw"
        self.assertIn("geometry.winding", codes(loads(encode_scene(source))))

    def test_intermediate_fold_winding_is_rejected(self):
        source = scene()
        rest = source["surfaces"][0]["poses"][0]
        folded = copy.deepcopy(rest)
        folded["positions"][2] = (0, -1, 0)
        source["frames"] = ["rest", "fold", "return"]
        source["surfaces"][0]["poses"] = [rest, folded, copy.deepcopy(rest)]
        model = loads(encode_scene(source))
        self.assertEqual(model.surfaces[0].pose(0), model.surfaces[0].pose(2))
        failures = [i for i in check(model)["issues"] if i["code"] == "geometry.winding"]
        self.assertEqual(len(failures), 1)
        self.assertEqual((failures[0]["frame"], failures[0]["triangle"], failures[0]["count"]), (1, 0, 1))

    def test_compact_indexed_pose_sequences_roundtrip(self):
        class Vectors:
            def __init__(self, values):
                self.data = array("f", (component for vector in values for component in vector))

            def __len__(self):
                return len(self.data)//3

            def __getitem__(self, index):
                if not 0 <= index < len(self):
                    raise IndexError(index)
                offset = index*3
                return tuple(self.data[offset:offset+3])

        source = scene()
        expected = encode_scene(source)
        for pose in source["surfaces"][0]["poses"]:
            for key in ("positions", "normals"):
                pose[key] = Vectors(pose[key])
        self.assertEqual(encode_scene(source), expected)

    def test_pose_indices_above_255_roundtrip(self):
        source = scene()
        rest = source["surfaces"][0]["poses"][0]
        source["frames"] = [f"pose{i}" for i in range(389)]
        source["surfaces"][0]["poses"] = [copy.deepcopy(rest) for _ in source["frames"]]
        source["surfaces"][0]["poses"][338]["positions"][2] = (0, 2, 0)
        model = loads(encode_scene(source))
        self.assertEqual(len(model.frames), 389)
        self.assertEqual(model.surfaces[0].pose(338)[0][2], (0, 2, 0))
        self.assertEqual(model.surfaces[0].pose(388)[0][2], (0, 1, 0))
        self.assertTrue(check(model)["passed"])

    def test_changed_static_component_and_dimension_contract(self):
        source = scene()
        source["surfaces"][0]["poses"][1]["positions"][0] = (0, 0, -1)
        result = codes(loads(encode_scene(source)), manifest={"static_surfaces": ["panel"], "dimensions": [10, 10, 10]})
        self.assertIn("animation.static", result)
        self.assertIn("scale.dimensions", result)

    def test_invalid_later_frame_bounds_and_radius(self):
        data = bytearray(encode_scene(scene()))
        struct.pack_into("<f", data, 108+56+12, .1)
        struct.pack_into("<f", data, 108+56+36, 0)
        result = codes(loads(data))
        self.assertIn("bounds.frame", result)
        self.assertIn("bounds.radius", result)

    def test_coordinate_range_finite_uvs_and_zero_normals(self):
        for bad in (512, float("nan"), float("inf")):
            source = scene()
            source["surfaces"][0]["poses"][0]["positions"][0] = (bad, 0, 0)
            with self.assertRaises(ValueError):
                encode_scene(source)
        source = scene()
        source["surfaces"][0]["poses"][0]["normals"][0] = (0, 0, 0)
        with self.assertRaises(ValueError):
            encode_scene(source)
        source = scene()
        source["surfaces"][0]["uv"][0] = (float("nan"), 0)
        with self.assertRaises(ValueError):
            encode_scene(source)

    def test_surface_partition_preserves_every_pose_and_corner_uv(self):
        source = scene()["surfaces"][0]
        source["triangles"] = [(0, 1, 2)]*4
        parts = partition(source, max_vertices=4096, max_triangles=1)
        self.assertEqual(len(parts), 4)
        for part in parts:
            self.assertEqual(part["uv"], source["uv"])
            self.assertEqual(part["poses"], source["poses"])
        source["uv"] = [(i/5000, 0) for i in range(4200)]
        for pose in source["poses"]:
            pose["positions"] = [(i, 0, 0) for i in range(4200)]
            pose["normals"] = [(0, 0, 1)]*4200
        source["triangles"] = [(i, i+1, i+2) for i in range(0, 4200, 3)]
        parts = partition(source)
        self.assertEqual(sum(len(p["triangles"]) for p in parts), 1400)
        self.assertTrue(all(len(p["uv"]) <= 4096 for p in parts))
        self.assertEqual(parts[1]["poses"][1]["positions"][0], (4095, 0, 0))

    def test_normal_encoding_matches_qssm_255_convention(self):
        self.assertEqual(normal_bytes((0, 0, 1)), (0, 0))
        for normal in ((1, 0, 0), (0, 1, 0), (0, 0, -1), (.3, -.4, .5)):
            decoded = decode_normal(*normal_bytes(normal))
            from md3harness.math3 import dot, unit
            self.assertGreater(dot(decoded, unit(normal)), .999)

    def test_tags_are_animated_and_bad_axes_are_rejected(self):
        source = scene()
        tag = dict(name="tag_hand", origin=(1, 2, 3), axes=((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        source["tags"] = [[tag], [copy.deepcopy(tag)]]
        source["tags"][1][0]["origin"] = (2, 2, 3)
        model = loads(encode_scene(source))
        self.assertEqual(model.tags[1][0]["origin"], (2, 2, 3))
        self.assertNotIn("tag.axes", codes(model))
        source["tags"][1][0]["axes"] = ((-1, 0, 0), (0, 1, 0), (0, 0, 1))
        self.assertIn("tag.axes", codes(loads(encode_scene(source))))

    def test_changing_tag_names_are_rejected(self):
        source = scene()
        tag = dict(name="tag_hand", origin=(0, 0, 0), axes=((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        source["tags"] = [[tag], [dict(tag, name="tag_other")]]
        self.assertIn("tag.topology", codes(loads(encode_scene(source))))

    def test_shader_traversal_and_long_names_rejected(self):
        for value in ("../private", "/absolute", "progs/../private", "progs/test.png", "bare_name", "x"*64):
            source = scene()
            source["surfaces"][0]["shader"] = value
            with self.assertRaises(FormatError):
                encode_scene(source)

    def test_texture_presence_metadata_and_truncation(self):
        model = loads(encode_scene(scene()))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIn("texture.invalid", codes(model, asset_root=root))
            texture = root/"progs/test.tga"
            write_tga(texture, 32, 32, [(10, 20, 30, 255)]*1024)
            self.assertTrue(check(model, asset_root=root)["passed"])
            self.assertEqual(image_info(texture)["width"], 32)
            texture.write_bytes(texture.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError, "truncated"):
                image_info(texture)

    def test_atlas_checks_filter_footprint(self):
        self.assertTrue(atlas_safe([(0.75, .125)], [512, 0, 1024, 256], (1024, 1024), 6))
        self.assertFalse(atlas_safe([(.501, .125)], [512, 0, 1024, 256], (1024, 1024), 6))

    def test_preview_uses_isolated_paks_and_cameras(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root/"base"
            (base/"id1").mkdir(parents=True)
            pak = base/"id1/pak0.pak"
            pak.write_bytes(b"user data")
            runtime = root/"runtime"
            runtime.mkdir()
            stage_paks(base, root/"engine/qssm", runtime)
            self.assertTrue((runtime/"id1/pak0.pak").is_symlink())
            self.assertEqual(pak.read_bytes(), b"user data")
            self.assertFalse((base/"config.cfg").exists())
        origin, views = cameras(loads(encode_scene(scene())))
        self.assertEqual(len(views), 4)
        self.assertEqual(origin, (-.5, -.5, 0))

    def test_cli_writes_report_and_strict_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root/"test.md3"
            model.write_bytes(encode_scene(scene()))
            report = root/"report.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["check", str(model), "--json", str(report), "--strict"]), 1)
            self.assertEqual(json.loads(report.read_text())["frames"], 2)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["check", str(model)]), 0)

    def test_png_filters_and_checksum(self):
        def chunk(kind, data):
            return struct.pack(">I", len(data))+kind+data+struct.pack(">I", zlib.crc32(kind+data) & 0xffffffff)
        header = struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)
        raw = bytes((10, 20, 30, 40, 50, 60))
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp)/"capture.png"
            for method in range(5):
                # First row: up/upper-left are zero; left predictor applies
                # for Sub, Average and Paeth, exercising every filter type.
                filtered = bytearray()
                for i, value in enumerate(raw):
                    a = raw[i-3] if i >= 3 else 0
                    predictor = a if method in (1, 4) else a//2 if method == 3 else 0
                    filtered.append((value-predictor) & 255)
                png = b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", header)+chunk(b"IDAT", zlib.compress(bytes([method])+filtered))+chunk(b"IEND", b"")
                image.write_bytes(png)
                self.assertEqual(read_rgb(image), (2, 1, bytearray(raw)))
            image.write_bytes(png[:-1]+b"x")
            with self.assertRaisesRegex(ValueError, "checksum"):
                read_rgb(image)

    def test_blank_capture_has_no_foreground(self):
        def png(rgb):
            def chunk(kind, payload):
                return struct.pack(">I", len(payload))+kind+payload+struct.pack(">I", zlib.crc32(kind+payload) & 0xffffffff)
            return (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                    +chunk(b"IDAT", zlib.compress(bytes([0])+bytes(rgb)))+chunk(b"IEND", b""))
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp)/"first.png", Path(tmp)/"second.png"
            first.write_bytes(png((100, 100, 100)))
            second.write_bytes(png((100, 100, 100)))
            self.assertEqual(changed_pixels(first, second), 0)
            second.write_bytes(png((10, 40, 60)))
            self.assertEqual(changed_pixels(first, second), 1)

    def test_overview_cameras_fit_tall_model_with_real_fov(self):
        import math
        from md3harness.math3 import cross, dot, sub, unit
        source = scene()
        for pose in source["surfaces"][0]["poses"]:
            pose["positions"] = [(0, 0, 0), (32, 0, 0), (0, 32, 96)]
        model = loads(encode_scene(source))
        origin, views = cameras(model)
        points = [tuple(a+b for a, b in zip(p, origin)) for p in source["surfaces"][0]["poses"][0]["positions"]]
        for name, position, angles in views[:3]:
            pitch, yaw = map(math.radians, angles[:2])
            forward = (math.cos(pitch)*math.cos(yaw), math.cos(pitch)*math.sin(yaw), -math.sin(pitch))
            right = unit(cross(forward, (0, 0, 1)))
            up = cross(right, forward)
            for point in points:
                delta = sub(point, position)
                depth = dot(delta, forward)
                self.assertGreater(depth, 0, name)
                self.assertLess(abs(dot(delta, right))/depth, math.tan(math.radians(37.5)), name)
                self.assertLess(abs(dot(delta, up))/depth, math.tan(math.radians(37.5))*720/1280, name)

if __name__ == "__main__":
    unittest.main()
