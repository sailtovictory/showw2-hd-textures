r"""Stage BMPs for chaiNNer so no alpha is lost.

usage: python bmp_stage.py <src_root> <dst_alpha> <dst_opaque> [--report FILE] [--no-mark-dirs]

  dst_alpha  : 32 bpp BMPs with real alpha (BI_RGB or BI_BITFIELDS) -> 32 bpp TGA, alpha kept
  dst_opaque : 24 bpp BMPs and 32 bpp BMPs with no varying alpha -> copied unchanged
  Skipped    : any side under 16 px (likely data bitmaps) and unsupported formats.

Folders whose name looks like an image (for example fx\_bmp\explosion\faerog.bmp\) are written as
NAME.bmp__dir so chaiNNer's glob does not try to open the folder ("[Errno 13] Permission denied").
Rename them back in the output tree (unmark-dirs.ps1) before running fix_descriptors.py.
--no-mark-dirs keeps the original folder names.

<src_root> is only read. Everything skipped is listed in the report (default: bmp_report.txt).
Exit code: 0 on success, 1 if <src_root> is not a folder."""
import argparse
import pathlib
import shutil
import struct
import sys

MIN_SIDE = 16
STD = (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
BADDIR = ('.tga', '.bmp', '.tif', '.tiff', '.png', '.jpg', '.jpeg')
DIR_MARK = '__dir'


def mark_dirs(rel):
    """Append __dir to every folder part of `rel` whose name ends in an image extension."""
    parts = [p + DIR_MARK if p.lower().endswith(BADDIR) else p for p in rel.parts[:-1]]
    return pathlib.Path(*parts, rel.name)


def shift8(m):
    """Shift for an 8-bit contiguous mask, else None."""
    if m == 0:
        return None
    s = (m & -m).bit_length() - 1
    return s if (m >> s) == 0xFF else None


def to_bgra(data, masks):
    """data: w*h*4 bytes as stored -> BGRA bytes (alpha 255 if no alpha mask), or None if unsupported."""
    if masks == STD:
        return data
    rm, gm, bm, am = masks
    sr, sg, sb = shift8(rm), shift8(gm), shift8(bm)
    sa = shift8(am) if am else None
    if None in (sr, sg, sb) or (am and sa is None):
        return None
    out = bytearray(len(data))
    for i in range(0, len(data), 4):
        v = data[i] | data[i + 1] << 8 | data[i + 2] << 16 | data[i + 3] << 24
        out[i] = (v & bm) >> sb
        out[i + 1] = (v & gm) >> sg
        out[i + 2] = (v & rm) >> sr
        out[i + 3] = ((v & am) >> sa) if am else 255
    return bytes(out)


def tga_bytes(w, h, bgra):
    """Uncompressed 32 bpp TGA, bottom-left origin, 8 alpha bits. `bgra` rows bottom-up."""
    return struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, w, h, 32, 0x08) + bgra


def stage(src, dst_a, dst_o, mark=True):
    """Stage every .bmp under src. Returns (counts, report_lines, marked_dir_count)."""
    counts = {'alpha_tga': 0, 'opaque_copy': 0, 'small_skipped': 0, 'other_skipped': 0}
    report = []
    marked = set()

    def out_rel(rel):
        if not mark:
            return rel
        m = mark_dirs(rel)
        if m != rel:
            marked.add(rel.parent)
        return m

    def copy_opaque(p, rel):
        out = dst_o / out_rel(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        counts['opaque_copy'] += 1

    for p in sorted(src.rglob('*')):
        if not p.is_file() or p.suffix.lower() != '.bmp':
            continue
        rel = p.relative_to(src)
        b = p.read_bytes()
        if b[:2] != b'BM' or len(b) < 54:
            counts['other_skipped'] += 1
            report.append(f'other (not BMP)\t{rel}')
            continue
        off, = struct.unpack_from('<I', b, 10)
        hdr, = struct.unpack_from('<I', b, 14)
        w, h = struct.unpack_from('<ii', b, 18)
        bpp, = struct.unpack_from('<H', b, 28)
        comp, = struct.unpack_from('<I', b, 30)
        ah = abs(h)
        if min(w, ah) < MIN_SIDE:
            counts['small_skipped'] += 1
            report.append(f'small {w}x{ah} {bpp}bpp\t{rel}')
            continue
        if bpp == 24 and comp == 0:
            copy_opaque(p, rel)
            continue
        if bpp == 32 and comp in (0, 3):
            if comp == 0:
                masks = STD
            else:
                rm, gm, bm = struct.unpack_from('<III', b, 54)
                am = struct.unpack_from('<I', b, 66)[0] if hdr >= 56 else 0
                masks = (rm, gm, bm, am)
            data = b[off:off + w * ah * 4]
            if len(data) != w * ah * 4:
                counts['other_skipped'] += 1
                report.append(f'other (short data)\t{rel}')
                continue
            bgra = to_bgra(data, masks)
            if bgra is None:
                counts['other_skipped'] += 1
                report.append(f'other (masks {[hex(m) for m in masks]})\t{rel}')
                continue
            if min(bgra[3::4]) == 255:
                copy_opaque(p, rel)
                report.append(f'no varying alpha 32bpp (copied to opaque)\t{rel}')
                continue
            if h < 0:                                    # top-down BMP: TGA rows must be bottom-up
                rows = [bgra[i * w * 4:(i + 1) * w * 4] for i in range(ah)]
                bgra = b''.join(reversed(rows))
            out = (dst_a / out_rel(rel)).with_suffix('.tga')
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(tga_bytes(w, ah, bgra))
            counts['alpha_tga'] += 1
            continue
        counts['other_skipped'] += 1
        report.append(f'other {bpp}bpp comp={comp}\t{rel}')
    for d in sorted(marked):
        report.append(f'folder marked __dir\t{d}')
    return counts, report, len(marked)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src_root', type=pathlib.Path, help='extracted resource tree (read only)')
    ap.add_argument('dst_alpha', type=pathlib.Path, help='output for 32 bpp TGAs with alpha')
    ap.add_argument('dst_opaque', type=pathlib.Path, help='output for opaque BMPs')
    ap.add_argument('--report', type=pathlib.Path, default=pathlib.Path('bmp_report.txt'),
                    help='report file (default: bmp_report.txt in the current folder)')
    ap.add_argument('--no-mark-dirs', action='store_true',
                    help='do not rename image-named folders to NAME.ext__dir')
    a = ap.parse_args(argv)
    if not a.src_root.is_dir():
        print(f'error: not a folder: {a.src_root}', file=sys.stderr)
        return 1
    counts, report, nmarked = stage(a.src_root, a.dst_alpha, a.dst_opaque, mark=not a.no_mark_dirs)
    a.report.write_text('\n'.join(report), encoding='utf-8')
    print(counts, f'-> details in {a.report}')
    if nmarked:
        print(f'{nmarked} image-named folder(s) written as NAME.ext__dir: run unmark-dirs.ps1 on hd_out after chaiNNer')
    return 0


if __name__ == '__main__':
    sys.exit(main())
