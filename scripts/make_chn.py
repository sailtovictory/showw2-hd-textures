#!/usr/bin/env python3
r"""Create one chaiNNer graph (.chn) from a template graph you saved yourself.

A .chn file is JSON: {version, content:{nodes,edges,viewport}, timestamp, checksum, migration}.
The checksum is the MD5 of the compact JSON of `content`, so it has to be recomputed after any edit.

Build the template once in chaiNNer (Load Images -> Load Model -> Upscale Image -> Save Image, with
Custom Scale 2 and Separate Alpha ticked), save it as template.chn, then:

  python make_chn.py template.chn out.chn --load-dir C:\work\stage_alpha\entity --glob "**/*.tga" \
         --save-dir C:\work\hd_out\entity --format tga

Only the options you pass are changed; everything else (model path, scale, tile size) is kept.
To make all graphs at once from a folder list, use make_graphs.py.
Exit code: 0 on success, 1 if the template is unreadable or lacks the Load Images / Save Image node."""
import argparse
import copy
import hashlib
import json
import pathlib
import sys

LOAD, SAVE, MODEL = 'chainner:image:load_images', 'chainner:image:save', 'chainner:pytorch:load_model'


class TemplateError(ValueError):
    pass


def checksum(content):
    return hashlib.md5(json.dumps(content, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def make_graph(template, load_dir=None, glob=None, save_dir=None, fmt=None, no_limit=False, model=None):
    g = copy.deepcopy(template)
    found = {LOAD: 0, SAVE: 0}
    for node in g['content']['nodes']:
        sid, inp = node['data']['schemaId'], node['data'].get('inputData', {})
        if sid == LOAD:
            found[LOAD] += 1
            if load_dir is not None:
                inp['0'] = load_dir
            if glob is not None:
                inp['3'] = glob
            if no_limit:
                inp['4'] = 0                             # "Use limit" off
        elif sid == SAVE:
            found[SAVE] += 1
            if save_dir is not None:
                inp['1'] = save_dir
            if fmt is not None:
                inp['4'] = fmt
        elif sid == MODEL and model is not None:
            inp['0'] = model
    if found[LOAD] != 1 or found[SAVE] != 1:
        raise TemplateError(f'template must have exactly one Load Images and one Save Image node (found {found})')
    g['checksum'] = checksum(g['content'])
    return g


def load_template(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise TemplateError(f'cannot read template {path}: {e}') from e


def write_graph(g, path):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(g, ensure_ascii=False), encoding='utf-8')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('template')
    ap.add_argument('out')
    ap.add_argument('--load-dir')
    ap.add_argument('--glob')
    ap.add_argument('--save-dir')
    ap.add_argument('--format', dest='fmt', help='png, tga, bmp, ...')
    ap.add_argument('--no-limit', action='store_true', help='turn "Use limit" off on Load Images')
    ap.add_argument('--model', help='path to the .pth model file')
    a = ap.parse_args(argv)
    try:
        g = make_graph(load_template(a.template), a.load_dir, a.glob, a.save_dir, a.fmt, a.no_limit, a.model)
    except TemplateError as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    write_graph(g, a.out)
    print('wrote', a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
