import hashlib
import json
import pathlib

import make_chn
import make_graphs
import pytest

TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / 'graphs' / 'template.chn'


def node_inputs(g, schema):
    return next(n['data']['inputData'] for n in g['content']['nodes'] if n['data']['schemaId'] == schema)


def md5_compact(content):
    return hashlib.md5(json.dumps(content, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


@pytest.fixture
def template():
    return json.loads(TEMPLATE.read_text(encoding='utf-8'))


def test_shipped_template_checksum_is_valid(template):
    assert template['checksum'] == md5_compact(template['content'])


def test_checksum_is_md5_of_compact_content():
    content = {'nodes': [{'a': 'é', 'b': [1, 2]}], 'edges': [], 'viewport': {'x': 0.5}}
    assert make_chn.checksum(content) == md5_compact(content)
    assert make_chn.checksum(content) == hashlib.md5('{"nodes":[{"a":"é","b":[1,2]}],"edges":[],"viewport":{"x":0.5}}'
                                                     .encode('utf-8')).hexdigest()


def test_only_requested_inputs_change(template):
    g = make_chn.make_graph(template, load_dir='C:\\w\\in', glob='**/*.bmp', save_dir='C:\\w\\out', fmt='bmp',
                            model='C:\\m\\x.pth')
    assert node_inputs(g, make_chn.LOAD)['0'] == 'C:\\w\\in'
    assert node_inputs(g, make_chn.LOAD)['3'] == '**/*.bmp'
    assert node_inputs(g, make_chn.SAVE)['1'] == 'C:\\w\\out'
    assert node_inputs(g, make_chn.SAVE)['4'] == 'bmp'
    assert node_inputs(g, make_chn.MODEL)['0'] == 'C:\\m\\x.pth'
    assert g['checksum'] == md5_compact(g['content'])
    # everything else is identical
    up = 'chainner:pytorch:upscale_image'
    assert node_inputs(g, up) == node_inputs(template, up)
    assert g['content']['edges'] == template['content']['edges']
    assert template['checksum'] == md5_compact(template['content'])             # template not mutated


def test_no_options_keeps_content(template):
    g = make_chn.make_graph(template)
    assert g['content'] == template['content'] and g['checksum'] == template['checksum']


def test_template_without_save_node_rejected(template):
    template['content']['nodes'] = [n for n in template['content']['nodes']
                                    if n['data']['schemaId'] != make_chn.SAVE]
    with pytest.raises(make_chn.TemplateError):
        make_chn.make_graph(template)


def test_cli_writes_graph(tmp_path):
    out = tmp_path / 'g.chn'
    assert make_chn.main([str(TEMPLATE), str(out), '--load-dir', 'C:\\w\\a', '--no-limit']) == 0
    g = json.loads(out.read_text(encoding='utf-8'))
    assert node_inputs(g, make_chn.LOAD)['0'] == 'C:\\w\\a'
    assert g['checksum'] == md5_compact(g['content'])


def test_cli_bad_template_exit_1(tmp_path):
    (tmp_path / 't.chn').write_text('not json', encoding='utf-8')
    assert make_chn.main([str(tmp_path / 't.chn'), str(tmp_path / 'o.chn')]) == 1


def write_config(tmp_path, jobs, **extra):
    cfg = {'template': str(TEMPLATE), 'work_dir': 'C:\\work', 'jobs': jobs, **extra}
    p = tmp_path / 'folders.json'
    p.write_text(json.dumps(cfg), encoding='utf-8')
    return p


def test_make_graphs_lanes(tmp_path, capsys):
    cfg = write_config(tmp_path, [
        {'lane': 'alpha', 'folder': 'entity\\-human'},
        {'lane': 'opaque', 'folder': 'fx/_bmp'},
        {'lane': 'custom', 'name': 'dirnamed', 'load_dir': 'C:\\work\\tga_hold\\dirnamed', 'glob': '**/*.tga',
         'save_dir': 'C:\\work\\hd_out', 'format': 'tga'},
    ], model='C:\\models\\4x-UltraSharp.pth')
    out = tmp_path / 'local'
    assert make_graphs.main([str(cfg), '--out-dir', str(out)]) == 0
    names = sorted(p.name for p in out.glob('*.chn'))
    assert names == ['01_alpha_entity_-human.chn', '02_opaque_fx__bmp.chn', '03_custom_dirnamed.chn']

    g = json.loads((out / '01_alpha_entity_-human.chn').read_text(encoding='utf-8'))
    load, save = node_inputs(g, make_chn.LOAD), node_inputs(g, make_chn.SAVE)
    assert load['0'] == 'C:\\work\\stage_alpha\\entity\\-human' and load['3'] == '**/*.tga' and load['4'] == 0
    assert save['1'] == 'C:\\work\\hd_out\\entity\\-human' and save['4'] == 'tga'
    assert node_inputs(g, make_chn.MODEL)['0'] == 'C:\\models\\4x-UltraSharp.pth'
    assert g['checksum'] == md5_compact(g['content'])

    g = json.loads((out / '02_opaque_fx__bmp.chn').read_text(encoding='utf-8'))
    assert node_inputs(g, make_chn.LOAD)['0'] == 'C:\\work\\stage_opaque\\fx\\_bmp'
    assert node_inputs(g, make_chn.SAVE)['4'] == 'bmp'

    order = (out / 'graphs.txt').read_text(encoding='utf-8').splitlines()
    assert [line.split('\t')[0] for line in order] == names


def test_make_graphs_template_relative_to_config(tmp_path):
    (tmp_path / 'local').mkdir()
    (tmp_path / 'local' / 'template.chn').write_bytes(TEMPLATE.read_bytes())
    cfg = write_config(tmp_path, [{'lane': 'alpha', 'folder': 'texture'}], template='local/template.chn')
    assert make_graphs.main([str(cfg), '--out-dir', str(tmp_path / 'g')]) == 0


def test_shipped_example_config_is_valid():
    cfg = json.loads((TEMPLATE.parent / 'folders.example.json').read_text(encoding='utf-8'))
    jobs = make_graphs.plan_jobs(cfg)
    assert jobs[0]['load_dir'] == 'C:\\work\\stage_alpha\\entity\\-human'


@pytest.mark.parametrize('jobs', [
    [],
    [{'lane': 'sideways', 'folder': 'x'}],
    [{'lane': 'alpha'}],
    [{'lane': 'custom', 'name': 'x', 'glob': '*'}],
])
def test_make_graphs_bad_config_exit_1(tmp_path, jobs):
    assert make_graphs.main([str(write_config(tmp_path, jobs)), '--out-dir', str(tmp_path / 'g')]) == 1
