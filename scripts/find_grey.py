"""Flag greyscale images (likely data maps such as masks and light maps) in the staging folders.

usage: python find_grey.py <staging_root> [<staging_root2> ...] [--move <hold_dir>] [--report FILE]

Samples about 2000 pixels per file. Reads 24 bpp BMP and uncompressed 32 bpp TGA only; other
formats are not checked. Pixels with alpha < 16 are ignored. An image is flagged when >= 98% of
sampled pixels have R, G and B within 6 of each other.
Writes the list to the report (default: grey_candidates.txt) and prints a per-folder summary.
--move relocates flagged files to <hold_dir>\\<staging_root name>\\<relative path>.
Exit code: 0 on success, 1 if a staging root is not a folder."""
import argparse
import pathlib
import shutil
import struct
import sys
from collections import defaultdict

TOL, FRAC, N = 6, 0.98, 2000


def _bmp24_getter(b):
    off, = struct.unpack_from('<I', b, 10)
    w, h = struct.unpack_from('<ii', b, 18)
    bpp, = struct.unpack_from('<H', b, 28)
    if bpp != 24:
        return None
    stride = (w * 3 + 3) & ~3

    def get(x, y):
        o = off + y * stride + x * 3
        return b[o + 2], b[o + 1], b[o], 255
    return w, abs(h), get


def _tga32_getter(b):
    w, h = struct.unpack_from('<HH', b, 12)
    off = 18 + b[0]
    stride = w * 4

    def get(x, y):
        o = off + y * stride + x * 4
        return b[o + 2], b[o + 1], b[o], b[o + 3]
    return w, h, get


def sample_grey(p):
    """Fraction of sampled opaque pixels that are grey, or None if the file is not checked."""
    b = p.read_bytes()
    ext = p.suffix.lower()
    if ext == '.bmp' and b[:2] == b'BM':
        g = _bmp24_getter(b)
    elif ext == '.tga' and len(b) > 18 and b[2] == 2 and b[16] == 32:
        g = _tga32_getter(b)
    else:
        return None
    if g is None:
        return None
    w, h, get = g
    if w < 1 or h < 1:
        return None
    step = max(1, int((w * h / N) ** 0.5))
    tot = grey = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, gr, bl, a = get(x, y)
            if a < 16:
                continue
            tot += 1
            if max(r, gr, bl) - min(r, gr, bl) <= TOL:
                grey += 1
    return None if tot == 0 else grey / tot


def scan(roots):
    """-> (summary {folder key: [total, flagged]}, flagged [(root, rel, fraction)])"""
    summary = defaultdict(lambda: [0, 0])
    flagged = []
    for root in roots:
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in ('.bmp', '.tga'):
                continue
            rel = p.relative_to(root)
            key = f'{root.name}\\' + '\\'.join(rel.parts[:2])
            summary[key][0] += 1
            f = sample_grey(p)
            if f is not None and f >= FRAC:
                summary[key][1] += 1
                flagged.append((root, rel, f))
    return summary, flagged


def move_flagged(flagged, hold):
    for r, rel, _ in flagged:
        dst = hold / r.name / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(r / rel), str(dst))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('roots', nargs='+', type=pathlib.Path, metavar='staging_root')
    ap.add_argument('--move', type=pathlib.Path, metavar='hold_dir', help='move flagged files here')
    ap.add_argument('--report', type=pathlib.Path, default=pathlib.Path('grey_candidates.txt'),
                    help='report file (default: grey_candidates.txt in the current folder)')
    a = ap.parse_args(argv)
    for r in a.roots:
        if not r.is_dir():
            print(f'error: not a folder: {r}', file=sys.stderr)
            return 1
    summary, flagged = scan(a.roots)
    for k in sorted(summary, key=lambda k: -summary[k][1]):
        if summary[k][1]:
            print(f'{summary[k][1]:5d} of {summary[k][0]:5d} greyscale   {k}')
    a.report.write_text('\n'.join(f'{r.name}\t{rel}\t{f:.3f}' for r, rel, f in flagged), encoding='utf-8')
    print(f'flagged {len(flagged)} greyscale files -> {a.report}')
    if a.move and flagged:
        move_flagged(flagged, a.move)
        print(f'moved to {a.move}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
