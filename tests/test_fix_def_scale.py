import fix_def_scale
import pytest
from conftest import bmp24, bmp32, tga, tree_snapshot, write

DEF_SCALED = '{Sprite "road.ebm"\r\n\t{Scale 1.0}\r\n\t{PreScaleX 3}\r\n\t{PreScaleY 0.5 }\r\n}\r\n'
DEF_MULTI = '{Sprite "crater.ebm"\r\n  {Layer 1}\r\n}\r\n'
DEF_ONELINE = '{Sprite "track.ebm" {Layer 2}} ; Spur \xfc\r\n'
DEF_SHARED = '{Sprite "/properties/shadow/round.ebm" {Layer 0}}\r\n{Sprite "same.ebm" {Layer 0}}\r\n'


@pytest.fixture
def trees(tmp_path):
    res, out = tmp_path / 'res', tmp_path / 'hd_out'
    st = res / 'entity/landscape/stamp'
    # road: original TGA, upscaled 2x
    write(st / 'Roads/road.tga', tga(32, 16))
    write(out / 'entity/landscape/stamp/Roads/road.tga', tga(64, 32))
    write(st / 'Roads/road.ebm', b'{bitmap {Axis 16 8}{Frame "road.tga"}}\r\n')
    write(st / 'Roads/road.def', DEF_SCALED.encode('latin-1'))
    # crater: BMP with alpha, converted to TGA by bmp_stage
    write(st / 'Craters/crater.bmp', bmp32(20, 20))
    write(out / 'entity/landscape/stamp/Craters/crater.tga', tga(40, 40))
    write(st / 'Craters/crater.ebm', b'{bitmap {Axis 10 10}{Frame "crater.bmp"}}\r\n')
    write(st / 'Craters/crater.def', DEF_MULTI.encode('latin-1'))
    # track: opaque BMP, upscaled 2x as BMP
    write(st / 'Tracks/track.bmp', bmp24(16, 16))
    write(out / 'entity/landscape/stamp/Tracks/track.bmp', bmp24(32, 32))
    write(st / 'Tracks/track.ebm', b'{bitmap {Frame "track.bmp"}}\r\n')
    write(st / 'Tracks/track.def', DEF_ONELINE.encode('latin-1'))
    # shared shadow sprite (absolute path) and a sprite whose image was not upscaled
    write(st / 'Misc/same.bmp', bmp24(16, 16))
    write(st / 'Misc/same.ebm', b'{bitmap {Frame "same.bmp"}}\r\n')
    write(st / 'Misc/misc.def', DEF_SHARED.encode('latin-1'))
    return res, out


def run(trees, tmp_path, *extra):
    res, out = trees
    return fix_def_scale.main([str(res), str(out), 'entity', '--report', str(tmp_path / 'r.txt'), *extra])


def read(out, rel):
    return (out / 'entity/landscape/stamp' / rel).read_bytes().decode('latin-1')


def test_summary(trees, tmp_path, capsys):
    assert run(trees, tmp_path) == 0
    assert "{'files_changed': 3, 'blocks_scaled': 1, 'blocks_added': 2, 'skipped': 2}" in capsys.readouterr().out


def test_existing_scales_divided(trees, tmp_path):
    run(trees, tmp_path)
    assert read(trees[1], 'Roads/road.def') == ('{Sprite "road.ebm"\r\n\t{Scale 0.5}\r\n\t{PreScaleX 1.5}\r\n'
                                               '\t{PreScaleY 0.25 }\r\n}\r\n')


def test_scale_inserted_multiline_keeps_indent_and_crlf(trees, tmp_path):
    run(trees, tmp_path)
    assert read(trees[1], 'Craters/crater.def') == '{Sprite "crater.ebm"\r\n  {Scale 0.5 }\r\n  {Layer 1}\r\n}\r\n'


def test_scale_inserted_oneline_keeps_latin1(trees, tmp_path):
    run(trees, tmp_path)
    assert read(trees[1], 'Tracks/track.def') == '{Sprite "track.ebm" {Scale 0.5 } {Layer 2}} ; Spur \xfc\r\n'


def test_not_upscaled_and_shared_sprites_skipped(trees, tmp_path):
    run(trees, tmp_path)
    assert not (trees[1] / 'entity/landscape/stamp/Misc/misc.def').exists()
    rep = (tmp_path / 'r.txt').read_text()
    assert 'sprite file not found: /properties/shadow/round.ebm' in rep
    assert 'no upscaled image for' in rep and 'same.bmp' in rep


def test_only_from(trees, tmp_path, capsys):
    only = tmp_path / 'tga_batch'
    write(only / 'entity/landscape/stamp/Roads/road.tga', b'')
    run(trees, tmp_path, '--only-from', str(only))
    assert "'files_changed': 1" in capsys.readouterr().out
    assert (trees[1] / 'entity/landscape/stamp/Roads/road.def').exists()
    assert not (trees[1] / 'entity/landscape/stamp/Tracks/track.def').exists()


def test_dry_run_and_rerun(trees, tmp_path, capsys):
    before = tree_snapshot(trees[1])
    run(trees, tmp_path, '--dry-run')
    assert tree_snapshot(trees[1]) == before
    assert '(dry run: nothing written)' in capsys.readouterr().out
    run(trees, tmp_path)
    first = tree_snapshot(trees[1])
    run(trees, tmp_path)                                          # reads the originals again: same result
    assert tree_snapshot(trees[1]) == first


def test_resource_tree_unchanged(trees, tmp_path):
    before = tree_snapshot(trees[0])
    run(trees, tmp_path)
    assert tree_snapshot(trees[0]) == before


def test_rescale_block_formats():
    assert fix_def_scale.rescale_block('{Sprite "a" {Scale 1}}', 2) == ('{Sprite "a" {Scale 0.5}}', 'scaled')
    assert fix_def_scale.rescale_block('{Sprite "a" {Scale 1}}', 3)[0] == '{Sprite "a" {Scale 0.333333}}'


def test_missing_subfolder_exit_1(trees, tmp_path):
    res, out = trees
    assert fix_def_scale.main([str(res), str(out), 'nope']) == 1
