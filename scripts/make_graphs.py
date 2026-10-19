#!/usr/bin/env python3
r"""Create every per-folder chaiNNer graph from one template and a JSON folder list.

usage: python make_graphs.py <config.json> [--template FILE] [--out-dir DIR]

Config (see graphs/folders.example.json):
  {
    "template": "template.chn",                 relative to the config file; optional if --template is given
    "work_dir": "C:\\work",                    holds stage_alpha, stage_opaque, hd_out
    "model":    "C:\\models\\4x-UltraSharp.pth",  optional; otherwise the template's model is kept
    "jobs": [
      {"lane": "alpha",  "folder": "entity\\-human"},
      {"lane": "opaque", "folder": "texture"},
      {"lane": "custom", "name": "dirnamed", "load_dir": "C:\\work\\tga_hold\\dirnamed",
       "glob": "**/*.tga", "save_dir": "C:\\work\\hd_out", "format": "tga"}
    ]
  }

Lanes:
  alpha   load <work_dir>\stage_alpha\<folder>,  glob **/*.tga, save TGA to <work_dir>\hd_out\<folder>
  opaque  load <work_dir>\stage_opaque\<folder>, glob **/*.bmp, save BMP to <work_dir>\hd_out\<folder>
  custom  every path and setting given explicitly
The save folder ends in the same subfolder as the load folder because chaiNNer's Subdirectory Path is
relative to the loaded folder. "Use limit" on Load Images is turned off unless a job sets "no_limit": false.
Relative paths in the config are relative to the config file.

Graphs are written to <out-dir> (default: graphs/local next to this repo's scripts folder) as
NN_<lane>_<folder>.chn, plus graphs.txt listing them in run order.
Exit code: 0 on success, 1 on a bad config or template."""
import argparse
import json
import pathlib
import re
import sys
from pathlib import PureWindowsPath

from make_chn import TemplateError, load_template, make_graph, write_graph

LANES = {
    'alpha': ('stage_alpha', '**/*.tga', 'tga'),
    'opaque': ('stage_opaque', '**/*.bmp', 'bmp'),
}
DEFAULT_OUT = pathlib.Path(__file__).resolve().parent.parent / 'graphs' / 'local'


class ConfigError(ValueError):
    pass


def slug(text):
    return re.sub(r'[\\/:*?"<>| ]+', '_', text).strip('_') or 'root'


def plan_jobs(cfg):
    """-> list of dicts: name, load_dir, glob, save_dir, fmt, no_limit (Windows paths as strings)."""
    jobs = cfg.get('jobs')
    if not isinstance(jobs, list) or not jobs:
        raise ConfigError('config needs a non-empty "jobs" list')
    work = cfg.get('work_dir')
    out = []
    for n, job in enumerate(jobs, 1):
        lane = job.get('lane')
        if lane in LANES:
            if not work:
                raise ConfigError(f'job {n}: lane "{lane}" needs "work_dir" in the config')
            if 'folder' not in job:
                raise ConfigError(f'job {n}: lane "{lane}" needs "folder"')
            stage, glob, fmt = LANES[lane]
            folder = PureWindowsPath(job['folder'])
            spec = dict(load_dir=str(PureWindowsPath(work, stage, folder)),
                        glob=job.get('glob', glob),
                        save_dir=str(PureWindowsPath(work, 'hd_out', folder)),
                        fmt=job.get('format', fmt))
            name = f'{lane}_{slug(str(folder))}'
        elif lane == 'custom':
            missing = [k for k in ('name', 'load_dir', 'glob', 'save_dir', 'format') if k not in job]
            if missing:
                raise ConfigError(f'job {n}: lane "custom" is missing {missing}')
            spec = dict(load_dir=job['load_dir'], glob=job['glob'], save_dir=job['save_dir'], fmt=job['format'])
            name = f'custom_{slug(job["name"])}'
        else:
            raise ConfigError(f'job {n}: unknown lane {lane!r} (use alpha, opaque or custom)')
        spec['no_limit'] = job.get('no_limit', True)
        spec['name'] = f'{n:02d}_{name}'
        out.append(spec)
    return out


def build(cfg, template, out_dir):
    """Write all graphs and graphs.txt. -> list of written paths."""
    model = cfg.get('model')
    written = []
    for spec in plan_jobs(cfg):
        g = make_graph(template, spec['load_dir'], spec['glob'], spec['save_dir'], spec['fmt'],
                       spec['no_limit'], model)
        path = out_dir / f'{spec["name"]}.chn'
        write_graph(g, path)
        written.append((path, spec))
    lines = [f'{p.name}\t{s["load_dir"]}\t{s["glob"]}\t{s["save_dir"]}\t{s["fmt"]}' for p, s in written]
    (out_dir / 'graphs.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return [p for p, _ in written]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('config', type=pathlib.Path, help='JSON folder list')
    ap.add_argument('--template', type=pathlib.Path, help='your saved template.chn (overrides the config)')
    ap.add_argument('--out-dir', type=pathlib.Path, default=DEFAULT_OUT,
                    help='where to write the graphs (default: graphs/local)')
    a = ap.parse_args(argv)
    try:
        try:
            cfg = json.loads(a.config.read_text(encoding='utf-8-sig'))   # tolerate a BOM (PowerShell 5.1, Notepad)
        except (OSError, ValueError) as e:
            raise ConfigError(f'cannot read config {a.config}: {e}') from e
        tpath = a.template or cfg.get('template')
        if not tpath:
            raise ConfigError('no template: pass --template or set "template" in the config')
        tpath = pathlib.Path(tpath)
        if not a.template and not tpath.is_absolute():
            tpath = a.config.parent / tpath
        paths = build(cfg, load_template(tpath), a.out_dir)
    except (ConfigError, TemplateError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    for p in paths:
        print('wrote', p)
    print(f'{len(paths)} graph(s); run order in {a.out_dir / "graphs.txt"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
