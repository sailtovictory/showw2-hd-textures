"""Synthetic image and descriptor builders. No game files are used anywhere in the tests."""
import pathlib
import struct
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'scripts'))


def colour(x, y):
    """A clearly non-grey RGBA pattern."""
    return (200 + x % 50, 20 + y % 30, 90, 255)


def grey(x, y):
    v = (x * 7 + y * 3) % 256
    return (v, v, v, 255)


def bmp24(w, h, px=colour):
    stride = (w * 3 + 3) & ~3
    rows = []
    for y in range(h - 1, -1, -1):                      # bottom-up
        row = b''.join(bytes((px(x, y)[2], px(x, y)[1], px(x, y)[0])) for x in range(w))
        rows.append(row + b'\0' * (stride - w * 3))
    data = b''.join(rows)
    hdr = struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0, len(data), 2835, 2835, 0, 0)
    return b'BM' + struct.pack('<IHHI', 14 + 40 + len(data), 0, 0, 54) + hdr + data


def pack_px(r, g, b, a, masks):
    """Pack 8-bit channels into a 32-bit little-endian word using the given masks."""
    v = 0
    for val, m in zip((r, g, b, a), masks):
        if m:
            v |= val << ((m & -m).bit_length() - 1)
    return struct.pack('<I', v)


def bmp32(w, h, px=colour, top_down=False, masks=None, alpha_mask=True):
    """32 bpp BMP. masks=None -> BI_RGB (BGRA). masks=(r,g,b,a) -> BI_BITFIELDS.
    alpha_mask=False writes a 40-byte header + 3 masks (no alpha mask)."""
    order = range(h) if top_down else range(h - 1, -1, -1)
    if masks is None:
        data = b''.join(bytes((px(x, y)[2], px(x, y)[1], px(x, y)[0], px(x, y)[3])) for y in order for x in range(w))
        hsize, comp, extra = 40, 0, b''
    else:
        use = masks if alpha_mask else masks[:3] + (0,)
        data = b''.join(pack_px(*px(x, y), use) for y in order for x in range(w))
        comp = 3
        if alpha_mask:
            hsize, extra = 56, struct.pack('<IIII', *masks)
        else:
            hsize, extra = 40, struct.pack('<III', *masks[:3])
    hh = -h if top_down else h
    hdr = struct.pack('<IiiHHIIiiII', hsize, w, hh, 1, 32, comp, len(data), 2835, 2835, 0, 0)
    if hsize > 40:
        hdr += extra
        extra = b''
    off = 14 + len(hdr) + len(extra)
    return b'BM' + struct.pack('<IHHI', off + len(data), 0, 0, off) + hdr + extra + data


def tga(w, h, px=colour, bpp=32, typ=2, rle=False):
    """Uncompressed (type 2/3) or RLE (type 10) TGA, bottom-up rows."""
    nb = bpp // 8

    def pix(x, y):
        r, g, b, a = px(x, y)
        if typ in (3, 11):
            return bytes((r,))
        return bytes((b, g, r, a))[:nb]
    raw = b''.join(pix(x, y) for y in range(h - 1, -1, -1) for x in range(w))
    if rle:
        typ = {2: 10, 3: 11}[typ]
        out = bytearray()
        for i in range(0, len(raw), nb):                 # raw packets of one pixel each
            out += b'\x00' + raw[i:i + nb]
        raw = bytes(out)
    desc = 0x08 if bpp == 32 else 0
    return struct.pack('<BBBHHBHHHHBB', 0, 0, typ, 0, 0, 0, 0, 0, w, h, bpp, desc) + raw


def write(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def tree_snapshot(root):
    """{relative path: bytes} for every file under root."""
    return {p.relative_to(root): p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    """Run in tmp_path so default report files land there."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
