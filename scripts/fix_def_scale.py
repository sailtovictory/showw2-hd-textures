r"""Keep ground decals (roads, tracks, craters, stamps) at their original size after an upscale.

usage: python fix_def_scale.py <resource_root> <hd_out_root> <subfolder> [--only-from DIR] [--dry-run] [--report FILE]
e.g.   python fix_def_scale.py C:\work\resource C:\work\hd_out entity

The engine draws a decal at (image pixels x scale), so a 2x image shows up twice as wide. For every
{Sprite "x.ebm" ...} block in a .def under <subfolder>, this script finds the sprite's image (the
.ebm's {Frame}), compares the original width with the upscaled file in <hd_out_root>, and divides
the block's scale by that ratio:
  * every {Scale N}, {PreScaleX N} and {PreScaleY N} in the block is divided by the ratio
  * a block with none of them gets a new {Scale 1/ratio } (the engine default is 1.0)
Sprites whose image was not upscaled (for example the shared /properties/shadow/round.ebm) are
skipped. Run it over the whole entity folder: BMP-converted decals need it as much as TGA ones.

The edited .def is written into <hd_out_root>; <resource_root> is never modified. The original .def is
always the input, so running it again gives the same result. CRLF and latin-1 are preserved.
--only-from DIR limits it to sprites whose image also exists under DIR (for example a folder that
holds only one batch). Skipped sprites are listed in the report (default: def_scale_report.txt).
Exit code: 0 on success, 1 if a root or <resource_root>\<subfolder> is not a folder."""
import argparse
import pathlib
import re
import struct
import sys

SPRITE = re.compile(r'\{Sprite\s+"([^"]+)"', re.I)
SCALE = re.compile(r'(\{(?:Scale|PreScaleX|PreScaleY)\s+)(-?[0-9]*\.?[0-9]+)(\s*\})', re.I)
FRAME = re.compile(r'\{Frame\s+"([^"]+)"', re.I)


def img_size(p):
    """(w, h) from a TGA or BMP header, else None."""
    try:
        with open(p, 'rb') as f:
            b = f.read(30)
    except OSError:
        return None
    if p.suffix.lower() == '.tga' and len(b) >= 18:
        return struct.unpack_from('<HH', b, 12)
    if b[:2] == b'BM' and len(b) >= 26:
        w, h = struct.unpack_from('<ii', b, 18)
        return w, abs(h)
    return None


def block_end(txt, start):
    """Index just after the brace that closes the block opening at `start`, or None."""
    depth = 0
    for i in range(start, len(txt)):
        if txt[i] == '{':
            depth += 1
        elif txt[i] == '}':
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def fmt(v):
    return f'{v:.6g}'


def rescale_block(block, ratio):
    """-> (new block text, 'scaled' or 'added')"""
    if SCALE.search(block):
        return SCALE.sub(lambda s: s.group(1) + fmt(float(s.group(2)) / ratio) + s.group(3), block), 'scaled'
    hdr = SPRITE.match(block)
    rest = block[hdr.end():]
    line = re.match(r'([ \t]*)(\r?\n)([ \t]*)', rest)
    scale = '{Scale ' + fmt(1 / ratio) + ' }'
    if line:                                             # multi-line block: new line after the header
        indent = line.group(3) or '\t'
        return block[:hdr.end()] + line.group(1) + line.group(2) + indent + scale + rest[len(line.group(1)):], 'added'
    return block[:hdr.end()] + ' ' + scale + rest, 'added'   # one-line block


def sprite_ratio(d, sprite, res, out, only):
    """-> (ratio, None) or (None, reason to skip) or (None, None) to ignore silently."""
    ebm = d.parent / sprite
    if not ebm.is_file():
        return None, f'sprite file not found: {sprite}'
    fm = FRAME.search(ebm.read_bytes().decode('latin-1'))
    if not fm:
        return None, f'no Frame in {sprite}'
    try:
        rel_img = (ebm.parent / fm.group(1)).relative_to(res)
    except ValueError:
        return None, f'frame outside the resource tree: {sprite}'
    if only and not (only / rel_img).is_file():
        return None, None
    osz = img_size(res / rel_img)
    nsz = img_size(out / rel_img) or img_size((out / rel_img).with_suffix('.tga'))
    if not osz or not nsz or not osz[0]:
        return None, f'no upscaled image for {rel_img}'
    ratio = nsz[0] / osz[0]
    if abs(ratio - 1) < 1e-6:
        return None, None
    return ratio, None


def fix(res, out, sub, only=None, dry=False):
    """-> (stats, skipped reasons, change samples)"""
    stats = dict(files_changed=0, blocks_scaled=0, blocks_added=0, skipped=0)
    why, samples = [], []
    for d in sorted((res / sub).rglob('*.def')):
        txt = d.read_bytes().decode('latin-1')
        edits = []                                       # (start, end, new_text)
        for m in SPRITE.finditer(txt):
            end = block_end(txt, m.start())
            if end is None:
                continue
            ratio, reason = sprite_ratio(d, m.group(1), res, out, only)
            if reason:
                stats['skipped'] += 1
                why.append(f'{d.relative_to(res)}: {reason}')
            if ratio is None:
                continue
            new, kind = rescale_block(txt[m.start():end], ratio)
            stats['blocks_' + kind] += 1
            edits.append((m.start(), end, new))
            samples.append(f'{d.name}: {kind} (ratio {ratio:g})')
        if not edits:
            continue
        stats['files_changed'] += 1
        for s, e, n in sorted(edits, reverse=True):
            txt = txt[:s] + n + txt[e:]
        if not dry:
            o = out / d.relative_to(res)
            o.parent.mkdir(parents=True, exist_ok=True)
            o.write_bytes(txt.encode('latin-1'))
    return stats, why, samples


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('resource_root', type=pathlib.Path, help='extracted resource tree (read only)')
    ap.add_argument('hd_out_root', type=pathlib.Path, help='upscaled output tree; edited .def files go here')
    ap.add_argument('subfolder', help=r'folder under resource_root to scan, e.g. entity')
    ap.add_argument('--only-from', type=pathlib.Path, metavar='DIR',
                    help='only sprites whose image also exists under DIR')
    ap.add_argument('--dry-run', action='store_true', help='report only, write nothing')
    ap.add_argument('--report', type=pathlib.Path, default=pathlib.Path('def_scale_report.txt'),
                    help='report file (default: def_scale_report.txt in the current folder)')
    a = ap.parse_args(argv)
    for r in (a.resource_root, a.hd_out_root, a.resource_root / a.subfolder):
        if not r.is_dir():
            print(f'error: not a folder: {r}', file=sys.stderr)
            return 1
    stats, why, samples = fix(a.resource_root, a.hd_out_root, a.subfolder, a.only_from, a.dry_run)
    for w in why[:6]:
        print('  skipped:', w)
    for s in samples[:6]:
        print('  ', s)
    a.report.write_text('\n'.join(['== skipped =='] + why + ['', '== changed =='] + samples), encoding='utf-8')
    print(stats, '(dry run: nothing written)' if a.dry_run else '')
    return 0


if __name__ == '__main__':
    sys.exit(main())
