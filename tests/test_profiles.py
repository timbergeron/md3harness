"""QSS-M's larger index budget without weakening binary or portable checks."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest

from md3harness.cli import main
from md3harness.format import FormatError, encode_scene, loads


def source(vertices=4200, repeats=1):
    positions = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]*(vertices//3)
    pose = dict(positions=positions, normals=[(0, 0, 1)]*vertices)
    return dict(schema="md3harness.scene.v1", name="dense.md3", frames=["rest"],
                surfaces=[dict(name="dense", shader="progs/dense", uv=[(0, 0)]*vertices,
                               triangles=[(i, i+1, i+2) for i in range(0, vertices, 3)]*repeats,
                               poses=[pose])])


class Profiles(unittest.TestCase):
    def test_qssm_keeps_large_surface_and_portable_still_splits(self):
        scene = source(repeats=7)
        model = loads(encode_scene(scene, profile="qssm"))
        self.assertEqual((len(model.surfaces), len(model.surfaces[0].uv),
                          len(model.surfaces[0].triangles)), (1, 4200, 9800))
        portable = loads(encode_scene(scene), profile="portable")
        self.assertGreater(len(portable.surfaces), 1)
        self.assertEqual(sum(len(s.triangles) for s in portable.surfaces), 9800)
        with self.assertRaisesRegex(FormatError, "count exceeds"):
            loads(encode_scene(scene, profile="qssm"), profile="portable")

    def test_unsigned_short_boundary_and_hostile_triangle_count(self):
        data = encode_scene(source(65535), profile="qssm")
        self.assertEqual(len(loads(data).surfaces[0].uv), 65535)
        offset = struct.unpack_from("<i", data, 100)[0]
        for field, value in ((80, 65536), (84, 2147483647//3+1)):
            bad = bytearray(data)
            struct.pack_into("<i", bad, offset+field, value)
            with self.assertRaisesRegex(FormatError, "count exceeds"):
                loads(bad)

    def test_profile_cannot_expand_animation_frame_limit(self):
        scene = source(3)
        pose = scene["surfaces"][0]["poses"][0]
        scene["frames"] = [f"f{i}" for i in range(1024)]
        scene["surfaces"][0]["poses"] = [pose]*1024
        self.assertEqual(len(loads(encode_scene(scene, profile="qssm")).frames), 1024)
        scene["frames"].append("overflow")
        scene["surfaces"][0]["poses"].append(pose)
        with self.assertRaises(FormatError):
            encode_scene(scene, profile="qssm")

    def test_scene_and_cli_profiles_are_explicit(self):
        scene = source()
        scene["profile"] = "qssm"
        data = encode_scene(scene)
        self.assertEqual(len(loads(data).surfaces), 1)
        with self.assertRaises(FormatError):
            encode_scene(scene, profile="unknown")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"dense.md3"
            path.write_bytes(data)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["check", str(path), "--profile", "qssm"]), 0)
                self.assertEqual(main(["check", str(path), "--profile", "portable"]), 1)


if __name__ == "__main__":
    unittest.main()
