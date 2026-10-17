"""Scene-linear light packages as RGBA16 PNGs holding IEEE half-float bits.

The PNG stores the bits, not display-encoded colour: the panel's loader
recovers them and uploads Rgba16Float, and AgX stays a runtime operation.
Shared by the knob-ring and plate-title packagers; numpy only, so it runs in
Blender's Python and in the dev shell alike.
"""
import struct
import zlib

import numpy as np


def half_png(path, array):
    """Write an H x W x 4 float array as half-float bits in a 16-bit RGBA PNG."""
    array = np.ascontiguousarray(array, dtype=np.float16)
    h, w, _ = array.shape
    bits = array.view(np.uint16).astype('>u2').tobytes()
    raw = b''.join(b'\x00' + bits[y * w * 8:(y + 1) * w * 8] for y in range(h))

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 16, 6, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
