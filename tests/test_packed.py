"""Regressions from bounded-memory anatomical hand exports."""
import copy
import unittest

from md3harness.format import HEADER, SURFACE, FormatError, encode_scene, loads
from md3harness.packed import combine_batches, expand_frames
from md3harness.quality import check


def fixture():
    surfaces = []
    for index in range(2):
        poses = []
        for frame in range(4):
            z = index+frame/4
            poses.append(dict(positions=[(0, 0, z), (1, 0, z), (0, 1, z)], normals=[(0, 0, 1)]*3))
        surfaces.append(dict(name=f"hand{index}", shader=f"progs/skin{index}",
                             uv=[(0, 0), (1, 0), (0, 1)], triangles=[(0, 1, 2)], poses=poses))
    tags = [[dict(name="tag_wrist", origin=(frame/4, 0, 0),
                  axes=((1, 0, 0), (0, 1, 0), (0, 0, 1)))] for frame in range(4)]
    return dict(schema="md3harness.scene.v1", name="hands.md3", frames=[f"pose{i}" for i in range(4)],
                tags=tags, surfaces=surfaces)


def select(source, indices, names=None):
    return dict(source, frames=names or [source["frames"][i] for i in indices],
                tags=[source["tags"][i] for i in indices],
                surfaces=[dict(s, poses=[s["poses"][i] for i in indices]) for s in source["surfaces"]])


class PackedFrames(unittest.TestCase):
    def test_join_preserves_all_surfaces_tags_bounds_and_packed_normals(self):
        source = fixture()
        batches = (encode_scene(select(source, indices)) for indices in ([0], [1, 2], [3]))
        result = combine_batches(batches)
        self.assertEqual(result, encode_scene(source))
        self.assertTrue(check(loads(result))["passed"])

    def test_expansion_reorders_and_repeats_complete_poses(self):
        source = fixture()
        indices, names = [3, 0, 3, 1], ["contact", "rest", "held", "recover"]
        result = expand_frames(encode_scene(source), indices, names)
        self.assertEqual(result, encode_scene(select(source, indices, names)))
        model = loads(result)
        self.assertEqual(model.tags[0], model.tags[2])
        self.assertEqual(model.surfaces[0].pose(0), model.surfaces[0].pose(2))

    def test_frame_indices_above_255_and_frame_limits(self):
        source = select(fixture(), [0])
        data = encode_scene(source)
        names = [f"pose{i}" for i in range(402)]
        repeated = expand_frames(data, [0]*402, names)
        model = loads(repeated)
        self.assertEqual(model.frames[392]["name"], "pose392")
        self.assertEqual(model.tags[392], model.tags[0])
        self.assertEqual(model.surfaces[1].pose(392), model.surfaces[1].pose(0))
        maximum = expand_frames(data, [0]*1024, ["held"]*1024)
        self.assertEqual(len(loads(maximum).frames), 1024)
        with self.assertRaisesRegex(FormatError, "exceeds MD3 limits"):
            combine_batches([maximum, data])

    def test_batch_topology_material_metadata_and_tags_must_match(self):
        original = fixture()
        first = encode_scene(select(original, [0]))
        for change in ("name", "surface-name", "shader", "uv", "triangle", "tag"):
            source = copy.deepcopy(select(original, [1]))
            if change == "name":
                source["name"] = "other.md3"
            elif change == "surface-name":
                source["surfaces"][0]["name"] = "other"
            elif change == "shader":
                source["surfaces"][0]["shader"] = "progs/other"
            elif change == "uv":
                source["surfaces"][0]["uv"][0] = (.25, 0)
            elif change == "triangle":
                source["surfaces"][0]["triangles"] = [(0, 2, 1)]
            else:
                source["tags"][0][0]["name"] = "tag_other"
            with self.subTest(change=change), self.assertRaises(FormatError):
                combine_batches([first, encode_scene(source)])

    def test_empty_inputs_bad_indices_and_labels_are_rejected(self):
        data = encode_scene(fixture())
        with self.assertRaises(FormatError):
            combine_batches([])
        for indices, names in (([], []), ([0], []), ([-1], ["bad"]), ([4], ["bad"]),
                               ([True], ["bad"]), ([1.0], ["bad"]), ([0], ["x"*16]),
                               ([0], [""]), ([0], ["n\u00e4me"]), ([0]*1025, ["held"]*1025)):
            with self.subTest(indices=indices[:2], names=names[:2]), self.assertRaises(FormatError):
                expand_frames(data, indices, names)

    def test_corrupt_input_and_changing_attachment_order_are_rejected(self):
        data = encode_scene(fixture())
        for bad in (data[:-1], b"invalid"):
            with self.assertRaises(FormatError):
                combine_batches([bad])
            with self.assertRaises(FormatError):
                expand_frames(bad, [0], ["rest"])
        source = fixture()
        source["tags"][2][0]["name"] = "tag_other"
        bad = encode_scene(source)
        with self.assertRaisesRegex(FormatError, "names/order change"):
            combine_batches([bad])
        with self.assertRaisesRegex(FormatError, "names/order change"):
            expand_frames(bad, [0], ["rest"])

    def test_alternative_valid_block_layout_is_canonicalized(self):
        source = select(fixture(), [0])
        data = encode_scene(source)
        head = list(HEADER.unpack_from(data))
        tag_size = head[10]-head[9]
        frames, tags = data[head[8]:head[9]], data[head[9]:head[10]]
        head[9], head[8] = HEADER.size, HEADER.size+tag_size
        shifted = HEADER.pack(*head)+tags+frames+data[head[10]:]
        self.assertEqual(len(shifted), len(data))
        self.assertEqual(combine_batches([shifted]), data)
        self.assertEqual(expand_frames(shifted, [0], ["pose0"]), data)
        # Padding between fixed surface data and poses is legal binary layout.
        head = list(HEADER.unpack_from(data))
        offset = head[10]
        sh = list(SURFACE.unpack_from(data, offset))
        vertex_start = offset+sh[10]
        sh[10] += 8
        sh[11] += 8
        padded = bytearray(data[:vertex_start]+b"padding!"+data[vertex_start:])
        head[11] += 8
        HEADER.pack_into(padded, 0, *head)
        SURFACE.pack_into(padded, offset, *sh)
        self.assertEqual(combine_batches([bytes(padded)]), data)

    def test_helpers_preserve_geometry_errors_for_full_quality_check(self):
        source = fixture()
        source["surfaces"][0]["poses"][2]["positions"][2] = (0, 0, .5)
        data = encode_scene(source)
        for result in (combine_batches([data]), expand_frames(data, [2], ["fold"])):
            issues = check(loads(result))["issues"]
            self.assertIn("geometry.collapsed", {issue["code"] for issue in issues})


if __name__ == "__main__":
    unittest.main()
