r"""Stage the game's ORIGINAL .tga files for chaiNNer.

usage: python tga_stage.py <resource_root> <stage_dir> <hold_dir> [--hd-out <hd_out>] [--exclude interface,sound]
                           [--max-side 1024] [--dry-run] [--report FILE]

Copies each .tga FILE to <stage_dir> (same relative path) unless it belongs in one of these groups,
which go to <hold_dir>\<group>\... instead (or are only reported):
  excluded   top-level folder named in --exclude (default: interface)   -> reported only
  dirnamed   file lives inside a folder whose name ends in .tga/.bmp/... -> <hold>\dirnamed\... with each such folder
             renamed NAME.tga -> NAME.tga__dir (so chaiNNer's glob does not mistake the folder for an image;
             upscale <hold>\dirnamed with its own graph, then run unmark-dirs.ps1 on hd_out)
  small      shorter side < 16 px                                         -> reported only
  big        longer side > --max-side (default 1024)                      -> <hold>\big\...
  grey       >= 98% of sampled pixels are grey (likely data maps)         -> <hold>\grey\...
  conflict   hd_out already holds a file at that path (e.g. a BMP->TGA)   -> reported only
  unreadable header cannot be parsed                                      -> reported only
The resource tree is never modified. Writes the non-staged list to the report (default: tga_report.txt)
and prints a per-folder summary.
Exit code: 0 on success, 1 if <resource_root> is not a folder."""
import argparse
import pathlib
import shutil
import struct
import sys
from collections import Counter, defaultdict

BADDIR = ('.tga', '.bmp', '.tif', '.tiff', '.png', '.jpg', '.jpeg')
DIR_MARK = '__dir'
MIN_SIDE = 16
TOL, FRAC, N = 6, 0.98, 2000


def mark_dirs(rel):
    """Append __dir to every folder part of `rel` whose name ends in an image extension."""
    parts = [p + DIR_MARK if p.lower().endswith(BADDIR) else p for p in rel.parts[:-1]]
    return pathlib.Path(*parts, rel.name)


def read_tga(p):
    """-> dict(w, h, bpp, type, raw), raw = decoded pixel bytes (None if not decodable); None if no valid header."""
    b = p.read_bytes()
    if len(b) < 18:
        return None
    idl, cmt, typ = b[0], b[1], b[2]
    cmlen, cmdep = struct.unpack_from('<HB', b, 5)
    w, h = struct.unpack_from('<HH', b, 12)
    bpp = b[16]
    if w < 1 or h < 1 or bpp not in (8, 15, 16, 24, 32) or typ not in (1, 2, 3, 9, 10, 11):
        return None
    off = 18 + idl + (cmlen * ((cmdep + 7) // 8) if cmt else 0)
    px = (bpp + 7) // 8
    need = w * h * px
    d = dict(w=w, h=h, bpp=bpp, type=typ, raw=None)
    if typ in (1, 2, 3):
        d['raw'] = b[off:off + need] if len(b) >= off + need else None
    else:                                                # RLE
        out = bytearray()
        i, n = off, len(b)
        while len(out) < need and i < n:
            c = b[i]
            i += 1
            cnt = (c & 0x7f) + 1
            if c & 0x80:
                out += b[i:i + px] * cnt
                i += px
            else:
                out += b[i:i + cnt * px]
                i += cnt * px
        d['raw'] = bytes(out[:need]) if len(out) >= need else None
    return d


def grey_fraction(d):
    raw, w, h, bpp, typ = d['raw'], d['w'], d['h'], d['bpp'], d['type']
    if raw is None:
        return None
    if typ in (3, 11):                                   # greyscale image types
        return 1.0
    if typ in (1, 9) or bpp not in (24, 32):
        return None
    px = bpp // 8
    step = max(1, int((w * h / N) ** 0.5))
    tot = g = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            o = (y * w + x) * px
            if px == 4 and raw[o + 3] < 16:
                continue
            bl, gr, r = raw[o], raw[o + 1], raw[o + 2]
            tot += 1
            if max(r, gr, bl) - min(r, gr, bl) <= TOL:
                g += 1
    return None if tot == 0 else g / tot


def classify(p, rel, exclude, max_side, hd_out, types):
    """-> (group or None for staged, extra text)"""
    if rel.parts[0].lower() in exclude:
        return 'excluded', ''
    if any(part.lower().endswith(BADDIR) for part in rel.parts[:-1]):
        return 'dirnamed', ''
    try:
        d = read_tga(p)
    except OSError:
        d = None
    if d is None:
        return 'unreadable', ''
    types[(d['type'], d['bpp'])] += 1
    if min(d['w'], d['h']) < MIN_SIDE:
        return 'small', ''
    if max(d['w'], d['h']) > max_side:
        return 'big', f"{d['w']}x{d['h']}"
    f = grey_fraction(d)
    if f is not None and f >= FRAC:
        return 'grey', ''
    if hd_out and (hd_out / rel).exists():
        return 'conflict', ''
    return None, ''


def stage(res, stage_dir, hold, exclude=frozenset({'interface'}), max_side=1024, hd_out=None, dry=False,
          progress=False):
    """-> (counts {folder key: Counter(group)}, report rows, Counter of (type, bpp) seen)"""
    counts = defaultdict(Counter)
    rows = []
    types = Counter()
    files = sorted(p for p in res.rglob('*') if p.is_file() and p.suffix.lower() == '.tga')
    for n, p in enumerate(files, 1):
        if progress and n % 500 == 0:
            print(f'  ...{n}/{len(files)}', flush=True)
        rel = p.relative_to(res)
        key = '\\'.join(rel.parts[:2]) if len(rel.parts) > 2 else rel.parts[0]
        group, extra = classify(p, rel, exclude, max_side, hd_out, types)
        counts[key][group or 'staged'] += 1
        if group:
            rows.append(f'{group}\t{rel}\t{extra}')
        if dry:
            continue
        if group == 'dirnamed':
            dst = hold / 'dirnamed' / mark_dirs(rel)
        elif group in ('big', 'grey'):
            dst = hold / group / rel
        elif group is None:
            dst = stage_dir / rel
        else:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
    return counts, rows, types


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('resource_root', type=pathlib.Path, help='extracted resource tree (read only)')
    ap.add_argument('stage_dir', type=pathlib.Path, help='output for TGAs to upscale')
    ap.add_argument('hold_dir', type=pathlib.Path, help='output for dirnamed / big / grey TGAs')
    ap.add_argument('--hd-out', type=pathlib.Path, help='existing upscale output; files already there are skipped')
    ap.add_argument('--exclude', default='interface', help='comma-separated top-level folders (default: interface)')
    ap.add_argument('--max-side', type=int, default=1024, help='skip images with a longer side (default: 1024)')
    ap.add_argument('--dry-run', action='store_true', help='report only, copy nothing')
    ap.add_argument('--report', type=pathlib.Path, default=pathlib.Path('tga_report.txt'),
                    help='report file (default: tga_report.txt in the current folder)')
    a = ap.parse_args(argv)
    if not a.resource_root.is_dir():
        print(f'error: not a folder: {a.resource_root}', file=sys.stderr)
        return 1
    exclude = {e.strip().lower() for e in a.exclude.split(',') if e.strip()}
    counts, rows, types = stage(a.resource_root, a.stage_dir, a.hold_dir, exclude, a.max_side, a.hd_out,
                                a.dry_run, progress=True)
    tot = Counter()
    print(f'{"folder":40s} staged  other')
    for k in sorted(counts):
        c = counts[k]
        o = {g: v for g, v in c.items() if g != 'staged'}
        for g, v in c.items():
            tot[g] += v
        print(f'{k:40s} {c["staged"]:6d}  {o if o else ""}')
    print('TOTAL', dict(tot))
    print('TGA types seen (type,bpp):', dict(types))
    a.report.write_text('\n'.join(rows), encoding='utf-8')
    print(f'non-staged list -> {a.report}' + ('   (dry run: nothing copied)' if a.dry_run else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
