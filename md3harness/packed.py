"""Rearrange already exported MD3 poses without decoding or re-encoding them.

These helpers validate binary layout and fixed topology. Run the full quality
check, with textures and the final frame contract, before delivering the result.
SPDX-License-Identifier: GPL-2.0-or-later
"""
from .format import FRAME, HEADER, LIMITS, SURFACE, TAG, VERTEX, FormatError, loads, string


def _parts(data):
    model = loads(data)
    tag_names = tuple(t["name"] for t in model.tags[0])
    if any(tuple(t["name"] for t in pose) != tag_names for pose in model.tags):
        raise FormatError("attachment names/order change between frames")
    view = memoryview(data)
    head = list(HEADER.unpack_from(view))
    frames = view[head[8]:head[8]+head[4]*FRAME.size]
    tags = view[head[9]:head[9]+head[4]*head[5]*TAG.size]
    offset, surfaces = head[10], []
    for _ in range(head[6]):
        sh = list(SURFACE.unpack_from(view, offset))
        surfaces.append((sh,
            view[offset+sh[7]:offset+sh[7]+sh[6]*12],
            view[offset+sh[8]:offset+sh[8]+sh[4]*68],
            view[offset+sh[9]:offset+sh[9]+sh[5]*8],
            view[offset+sh[10]:offset+sh[10]+sh[3]*sh[5]*VERTEX.size]))
        offset += sh[11]
    return head, frames, tags, surfaces, tag_names


def _assemble(head, count, frames, tags, surfaces):
    blocks = []
    for original, triangles, shaders, uv, poses in surfaces:
        sh = list(original)
        sh[3], sh[7] = count, SURFACE.size
        sh[8] = sh[7]+len(triangles)
        sh[9] = sh[8]+len(shaders)
        sh[10] = sh[9]+len(uv)
        sh[11] = sh[10]+sum(len(p) for p in poses)
        blocks.append(b"".join((SURFACE.pack(*sh), triangles, shaders, uv, *poses)))
    frame_data, tag_data = b"".join(frames), b"".join(tags)
    head = list(head)
    head[4], head[8] = count, HEADER.size
    head[9] = head[8]+len(frame_data)
    head[10] = head[9]+len(tag_data)
    head[11] = head[10]+sum(len(b) for b in blocks)
    result = b"".join((HEADER.pack(*head), frame_data, tag_data, *blocks))
    loads(result)
    return result


def combine_batches(batches):
    """Return bytes joining an iterable of fixed-topology MD3 byte strings.

    Model/surface metadata, shaders, UVs, triangles and attachment names/order
    must match exactly. Bounds, labels, tags and packed pose bytes are retained.
    Layout offsets may differ; the returned layout is canonical. The combined
    model must fit the same MD3 frame limit as an ordinary export.
    """
    parts, count = [], 0
    for data in batches:
        part = _parts(data)
        head, _, _, surfaces, tag_names = part
        count += head[4]
        if count > LIMITS["frames"]:
            raise FormatError("combined frame count exceeds MD3 limits")
        if parts:
            first = parts[0]
            if head[:4]+head[5:8] != first[0][:4]+first[0][5:8]:
                raise FormatError("batch model metadata differ")
            if tag_names != first[4]:
                raise FormatError("batch attachment names/order differ")
            for current, reference in zip(surfaces, first[3]):
                sh, rh = current[0], reference[0]
                if sh[:3]+sh[4:7] != rh[:3]+rh[4:7] or current[1:4] != reference[1:4]:
                    raise FormatError("batch surface topology/materials differ")
        parts.append(part)
    if not parts:
        raise FormatError("at least one batch is required")
    surfaces = []
    for index, first in enumerate(parts[0][3]):
        surfaces.append((*first[:4], [part[3][index][4] for part in parts]))
    return _assemble(parts[0][0], count, [p[1] for p in parts], [p[2] for p in parts], surfaces)


def expand_frames(data, indices, names):
    """Return bytes selecting/repeating poses, with one label per output frame.

    Indices are zero-based integers. Repeated entries copy exact packed geometry,
    normals, bounds and tags; this performs no approximate deduplication. Labels
    obey the writer's 1..15 ASCII-byte frame-name contract.
    """
    head, frames, tags, source_surfaces, _ = _parts(data)
    indices, names = list(indices), list(names)
    if not 1 <= len(indices) <= LIMITS["frames"] or len(names) != len(indices):
        raise FormatError("expanded frame count or label count is invalid")
    if any(type(i) is not int or not 0 <= i < head[4] for i in indices):
        raise FormatError("frame index outside the source model")
    labels = [string(name, 16) for name in names]
    frame_data = [b"".join((frames[i*FRAME.size:i*FRAME.size+40], label))
                  for i, label in zip(indices, labels)]
    tag_stride = head[5]*TAG.size
    tag_data = [tags[i*tag_stride:(i+1)*tag_stride] for i in indices]
    surfaces = []
    for sh, triangles, shaders, uv, packed in source_surfaces:
        stride = sh[5]*VERTEX.size
        poses = [packed[i*stride:(i+1)*stride] for i in indices]
        surfaces.append((sh, triangles, shaders, uv, poses))
    return _assemble(head, len(indices), frame_data, tag_data, surfaces)
