"""Read the non-interlaced 8-bit RGB/RGBA PNGs written by QSS-M."""
from pathlib import Path
import struct
import zlib

def read_rgb(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("expected a PNG capture")
    offset, compressed, width, height, channels = 8, bytearray(), 0, 0, 0
    while offset+12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+size]
        if offset+size+12 > len(data):
            raise ValueError("truncated PNG chunk")
        crc = struct.unpack_from(">I", data, offset+8+size)[0]
        if zlib.crc32(kind+payload) & 0xffffffff != crc:
            raise ValueError("PNG checksum mismatch")
        if kind == b"IHDR":
            width, height, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if depth != 8 or colour not in (2, 6) or compression or filtering or interlace or not 0 < width <= 4096 or not 0 < height <= 4096:
                raise ValueError("unsupported PNG capture format")
            channels = 3 if colour == 2 else 4
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
        offset += size+12
    if not channels:
        raise ValueError("missing PNG header")
    stride = width*channels
    expected = (stride+1)*height
    decoder = zlib.decompressobj()
    packed = decoder.decompress(compressed, expected+1)
    if len(packed) != expected or not decoder.eof:
        raise ValueError("invalid PNG pixel length")
    output = bytearray()
    previous = bytearray(stride)
    for y in range(height):
        start = y*(stride+1)
        method = packed[start]
        row = bytearray(packed[start+1:start+1+stride])
        if method not in range(5):
            raise ValueError("invalid PNG filter")
        if method:
            for i in range(stride):
                a = row[i-channels] if i >= channels else 0
                b = previous[i]
                c = previous[i-channels] if i >= channels else 0
                if method == 1:
                    value = a
                elif method == 2:
                    value = b
                elif method == 3:
                    value = (a+b)//2
                else:
                    p = a+b-c
                    pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                    value = a if pa <= pb and pa <= pc else b if pb <= pc else c
                row[i] = (row[i]+value) & 255
        if channels == 3:
            output.extend(row)
        else:
            for i in range(0, stride, 4):
                output.extend(row[i:i+3])
        previous = row
    return width, height, output

def changed_pixels(first, second, threshold=8):
    w, h, a = read_rgb(first)
    w2, h2, b = read_rgb(second)
    if (w, h) != (w2, h2):
        raise ValueError("capture/baseline dimensions differ")
    return sum(max(abs(a[i+j]-b[i+j]) for j in range(3)) >= threshold for i in range(0, len(a), 3))
