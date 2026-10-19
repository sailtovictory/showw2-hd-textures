r"""Compare original and upscaled TGAs: did the upscale change how much a sprite covers?

usage: python compare_alpha.py <original_root> <upscaled_root> <subfolder> [--limit 40]
e.g.   python compare_alpha.py C:\work\resource C:\work\hd_out entity\landscape\stamp\Roads

For every .tga under <upscaled_root>\<subfolder> that also exists under <original_root>, prints:
  size before/after, mean alpha before/after, share of pixels with alpha > 128 before/after,
  and mean brightness of the visible pixels before/after.
Alpha and coverage do not depend on image size, so a clean 2x upscale should leave them nearly unchanged.
A summary line shows the median change. Uncompressed and RLE 24/32 bpp TGAs are supported.
Read only: nothing is written.
Exit code: 0 on success (also when nothing matches), 1 if a folder does not exist."""
import argparse
import pathlib
import statistics
import struct
import sys


def read_tga(p):
    """-> (w, h, bytes per pixel, raw BGR(A) bytes) or None if unsupported."""
    b = p.read_bytes()
    if len(b) < 18:
        return None
    idl, cmt, typ = b[0], b[1], b[2]
    if cmt or typ not in (2, 10):
        return None
    w, h = struct.unpack_from('<HH', b, 12)
    bpp = b[16]
    if bpp not in (24, 32):
        return None
    px = bpp // 8
    need = w * h * px
    i = 18 + idl
    if typ == 2:
        raw = b[i:i + need]
    else:                                                # RLE
        out = bytearray()
        while len(out) < need and i < len(b):
            c = b[i]
            i += 1
            n = (c & 0x7f) + 1
            if c & 0x80:
                out += b[i:i + px] * n
                i += px
            else:
                out += b[i:i + n * px]
                i += n * px
        raw = bytes(out[:need])
    if len(raw) < need:
        return None
    return w, h, px, raw


def stats(raw, px):
    """-> (mean alpha, share of pixels with alpha > 128, mean brightness of those pixels)"""
    n = len(raw) // px
    step = max(1, n // 40000)
    a_sum = cov = 0
    br = 0.0
    cnt = 0
    for k in range(0, n, step):
        o = k * px
        a = raw[o + 3] if px == 4 else 255
        cnt += 1
        a_sum += a
        if a > 128:
            cov += 1
            br += (raw[o] + raw[o + 1] + raw[o + 2]) / 3
    return a_sum / cnt, cov / cnt, (br / cov if cov else 0.0)


def compare(orig, new, sub):
    """-> rows (relative name, old size, new size, old stats, new stats)"""
    rows = []
    for p in sorted((new / sub).rglob('*.tga')):
        o = orig / p.relative_to(new)
        if not o.is_file():
            continue
        a, b = read_tga(o), read_tga(p)
        if not a or not b:
            continue
        rows.append((str(p.relative_to(new / sub)), f'{a[0]}x{a[1]}', f'{b[0]}x{b[1]}',
                     stats(a[3], a[2]), stats(b[3], b[2])))
    return rows


def median_change(rows, i):
    return statistics.median(r[4][i] / r[3][i] if r[3][i] else 1 for r in rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('original_root', type=pathlib.Path)
    ap.add_argument('upscaled_root', type=pathlib.Path)
    ap.add_argument('subfolder')
    ap.add_argument('--limit', type=int, default=40, help='rows to print (default: 40)')
    a = ap.parse_args(argv)
    for r in (a.original_root, a.upscaled_root):
        if not r.is_dir():
            print(f'error: not a folder: {r}', file=sys.stderr)
            return 1
    rows = compare(a.original_root, a.upscaled_root, a.subfolder)
    print(f'{"file":38s} {"size":>9s} -> {"size":>9s}  alpha mean   coverage(a>128)   brightness')
    for r in rows[:a.limit]:
        print(f'{r[0][:38]:38s} {r[1]:>9s} -> {r[2]:>9s}  {r[3][0]:5.1f}->{r[4][0]:5.1f}   '
              f'{r[3][1] * 100:5.1f}%->{r[4][1] * 100:5.1f}%   {r[3][2]:5.1f}->{r[4][2]:5.1f}')
    if rows:
        print(f'\n{len(rows)} files. Median change: alpha mean x{median_change(rows, 0):.2f}, '
              f'coverage x{median_change(rows, 1):.2f}, brightness x{median_change(rows, 2):.2f}')
    else:
        print('no matching files found')
    return 0


if __name__ == '__main__':
    sys.exit(main())
