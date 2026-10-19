"""Update .ebm / .tex descriptors after upscaling.

usage: python fix_descriptors.py <resource_root> <hd_out_root> [--no-axis] [--dry-run] [--report FILE]

For every upscaled image in <hd_out_root> (.tga/.bmp) it finds the original in <resource_root>
(a .tga in hd_out whose original is a .bmp counts as a BMP->TGA conversion), computes the real
scale ratio, then rewrites every .ebm/.tex whose {Frame "..."} points at that image:
  * Frame extension .bmp -> .tga for converted images
  * {Axis x y} scaled by the ratio (.ebm only; skip with --no-axis)
Edited descriptors are written into <hd_out_root> with the same relative path; <resource_root> is
never modified. Descriptors are read and written as latin-1 bytes, so CRLF line ends and accented
characters are kept. Lines starting with ';' are comments and are left alone.
Other text files that mention a converted BMP by name are only REPORTED (not edited).
Run unmark-dirs.ps1 on <hd_out_root> first if a staging script renamed folders to NAME.ext__dir.
Exit code: 0 on success, 1 if a root is not a folder."""
import argparse
import pathlib
import re
import struct
import sys

FRAME = re.compile(r'(\{Frame\s+")([^"]+)(")', re.I)
AXIS = re.compile(r'(\{Axis\s+)(\d+)(\s+)(\d+)', re.I)
SKIP_SCAN = ('.ebm', '.tex', '.tga', '.bmp', '.wav', '.ply', '.mdl', '.anm', '.vol')
STOP = set(' \t\r\n"{}<>|')


def img_size(p):
    """(w, h) from a TGA or BMP header, else None."""
    try:
        with open(p, 'rb') as f:
            b = f.read(30)
        if p.suffix.lower() == '.tga':
            return struct.unpack_from('<HH', b, 12)
        if b[:2] == b'BM':
            w, h = struct.unpack_from('<ii', b, 18)
            return w, abs(h)
    except (OSError, struct.error):
        pass
    return None


def match_originals(res, out):
    """original image (relative, lowercase) -> (new relative path, ratio x, ratio y, renamed)"""
    info = {}
    for p in out.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in ('.tga', '.bmp'):
            continue
        rel = p.relative_to(out)
        cands = [rel] + ([rel.with_suffix('.bmp')] if p.suffix.lower() == '.tga' else [])
        for c in cands:
            osz = img_size(res / c)
            if osz:
                nsz = img_size(p)
                if nsz and osz[0] and osz[1]:
                    info[str(c).lower()] = (rel, nsz[0] / osz[0], nsz[1] / osz[1], c != rel)
                break
    return info


def rewrite_descriptor(d, res, info, do_axis, stats, referenced, unresolved, warn):
    """-> new text if the descriptor changed, else None. Updates stats and the report lists."""
    txt = d.read_bytes().decode('latin-1')
    ratio = None
    changed = False
    new_lines = []
    ratios = []                                          # ratios of the frames on the current line

    def fr(m):
        nonlocal changed
        target = d.parent / m.group(2)
        if not target.exists():
            stats['frame_unresolved'] += 1
            hint = [e for e in ('.bmp', '.tga', '.tif') if (d.parent / (m.group(2) + e)).exists()]
            unresolved.append(f'{d.relative_to(res)}\tFrame "{m.group(2)}"\t'
                              f'file with appended ext exists: {hint or "no"}')
            return m.group(0)
        key = str(target.relative_to(res)).lower()
        hit = info.get(key)
        if not hit:
            return m.group(0)
        referenced.add(key)
        ratios.append((hit[1], hit[2]))
        if hit[3]:
            stats['frames_renamed'] += 1
            changed = True
            new = str(pathlib.PurePath(m.group(2)).with_suffix('.tga')).replace('\\', '/')
            return m.group(1) + new + m.group(3)
        return m.group(0)

    for line in txt.split('\n'):                        # '\r' stays at the end of each line
        if line.lstrip().startswith(';'):
            new_lines.append(line)
            continue
        ratios.clear()
        line2 = FRAME.sub(fr, line)
        if ratios:
            r = ratios[0]
            if ratio and (abs(ratio[0] - r[0]) > 1e-6 or abs(ratio[1] - r[1]) > 1e-6):
                stats['mixed_ratio'] += 1
                warn.append(f'mixed frame ratios: {d.relative_to(res)}')
            ratio = ratio or r
        new_lines.append(line2)
    if do_axis and d.suffix.lower() == '.ebm' and ratio and (abs(ratio[0] - 1) > 1e-6 or abs(ratio[1] - 1) > 1e-6):
        def ax(m):
            return (m.group(1) + str(round(int(m.group(2)) * ratio[0])) + m.group(3)
                    + str(round(int(m.group(4)) * ratio[1])))
        for i, line in enumerate(new_lines):            # first {Axis} outside a comment line
            if line.lstrip().startswith(';'):
                continue
            scaled = AXIS.sub(ax, line, count=1)
            if scaled != line:
                stats['axis_scaled'] += 1
                new_lines[i] = scaled
                changed = True
                break
    return '\n'.join(new_lines) if changed else None


def find_other_mentions(res, renamed_names, progress=False):
    """Files other than descriptors/images that name a converted BMP: {relative file: {names}}"""
    others = {}
    files = [f for f in res.rglob('*')
             if f.is_file() and f.suffix.lower() not in SKIP_SCAN and f.stat().st_size < 2_000_000]
    for n, f in enumerate(files, 1):
        if progress and n % 500 == 0:
            print(f'  scanning other files... {n}/{len(files)}', flush=True)
        try:
            t = f.read_bytes().decode('latin-1').lower()
        except OSError:
            continue
        i = t.find('.bmp')
        while i != -1:                                   # linear scan, no regex backtracking
            j = i
            while j > 0 and i - j < 200 and t[j - 1] not in STOP:
                j -= 1
            name = t[j:i + 4].replace('\\', '/')
            if pathlib.PurePosixPath(name).name in renamed_names:
                others.setdefault(str(f.relative_to(res)), set()).add(name)
            i = t.find('.bmp', i + 4)
    return others


def fix(res, out, do_axis=True, dry=False, progress=False):
    """Run all steps. -> dict with stats, info, orphans, others, unresolved, warn."""
    info = match_originals(res, out)
    renamed_names = {pathlib.PurePath(k).name for k, v in info.items() if v[3]}
    if progress:
        print(f'upscaled images matched to originals: {len(info)}  (BMP->TGA conversions: {len(renamed_names)})')
    stats = dict(written=0, frames_renamed=0, axis_scaled=0, mixed_ratio=0, frame_unresolved=0)
    referenced, unresolved, warn = set(), [], []
    for d in res.rglob('*'):
        if not d.is_file() or d.suffix.lower() not in ('.ebm', '.tex'):
            continue
        new = rewrite_descriptor(d, res, info, do_axis, stats, referenced, unresolved, warn)
        if new is None:
            continue
        stats['written'] += 1
        if not dry:
            o = out / d.relative_to(res)
            o.parent.mkdir(parents=True, exist_ok=True)
            o.write_bytes(new.encode('latin-1'))
    orphans = [k for k in info if k not in referenced]
    others = find_other_mentions(res, renamed_names, progress) if renamed_names else {}
    return dict(stats=stats, info=info, orphans=orphans, others=others, unresolved=unresolved, warn=warn)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('resource_root', type=pathlib.Path, help='extracted resource tree (read only)')
    ap.add_argument('hd_out_root', type=pathlib.Path, help='upscaled output tree; edited descriptors go here')
    ap.add_argument('--no-axis', action='store_true', help='do not scale {Axis x y} in .ebm files')
    ap.add_argument('--dry-run', action='store_true', help='report only, write nothing')
    ap.add_argument('--report', type=pathlib.Path, default=pathlib.Path('descriptor_report.txt'),
                    help='report file (default: descriptor_report.txt in the current folder)')
    a = ap.parse_args(argv)
    for r in (a.resource_root, a.hd_out_root):
        if not r.is_dir():
            print(f'error: not a folder: {r}', file=sys.stderr)
            return 1
    r = fix(a.resource_root, a.hd_out_root, do_axis=not a.no_axis, dry=a.dry_run, progress=True)
    lines = [f'{k}: {sorted(v)[:5]}' for k, v in r['others'].items()]
    rep = (['== images with no .ebm/.tex pointing at them =='] + r['orphans']
           + ['', '== other files mentioning converted BMPs (NOT edited) =='] + lines
           + ['', '== unresolved frames (descriptor, frame, hint) =='] + r['unresolved'] + [''] + r['warn'])
    a.report.write_text('\n'.join(rep), encoding='utf-8')
    print(r['stats'])
    print(f"orphan images: {len(r['orphans'])}   other files naming converted BMPs: {len(r['others'])}"
          f'   -> {a.report}')
    if a.dry_run:
        print('(dry run: nothing written)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
