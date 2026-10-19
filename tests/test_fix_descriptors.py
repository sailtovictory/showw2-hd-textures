import fix_descriptors
import pytest
from conftest import bmp24, bmp32, tga, tree_snapshot, write

EBM_FX = ('; old: {Frame "a.bmp"} {Axis 1 1}\r\n'
          '{bitmap {Axis 10 13}{Filtering}{Mipmap}{AlphaChannel}{Blend}{Frame "a.bmp"}} ; Flamme \xe9t\xe9\r\n')
TEX_FX = '{Bitmap {Filtering}{Mipmap}{Blend}{AlphaChannel}{Frame "a.bmp"}}\r\n'
EBM_HUMAN = '{bitmap\r\n  {Axis 16 30}\r\n  {Frame "sold.bmp"}\r\n}\r\n'
EBM_MISSING = '{bitmap {Axis 5 5}{Frame "ghost"}}\r\n'


@pytest.fixture
def trees(tmp_path):
    res, out = tmp_path / 'res', tmp_path / 'hd_out'
    write(res / 'fx/a.bmp', bmp32(20, 10))                   # converted to TGA by bmp_stage
    write(out / 'fx/a.tga', tga(40, 20))
    write(res / 'fx/a.ebm', EBM_FX.encode('latin-1'))
    write(res / 'fx/a.tex', TEX_FX.encode('latin-1'))
    write(res / 'entity/-human/sold.bmp', bmp24(16, 16))     # kept as BMP
    write(out / 'entity/-human/sold.bmp', bmp24(32, 32))
    write(res / 'entity/-human/sold.ebm', EBM_HUMAN.encode('latin-1'))
    write(res / 'fx/ghost.bmp', bmp24(16, 16))               # original data: Frame "ghost" has no extension
    write(res / 'fx/missing.ebm', EBM_MISSING.encode('latin-1'))
    write(res / 'misc/list.txt', b'sprite fx\\a.bmp\r\n')
    write(res / 'entity/-human/unused.bmp', bmp24(16, 16))
    write(out / 'entity/-human/unused.bmp', bmp24(32, 32))
    return res, out


def run(trees, tmp_path, *extra):
    res, out = trees
    return fix_descriptors.main([str(res), str(out), '--report', str(tmp_path / 'd.txt'), *extra])


def test_summary_line(trees, tmp_path, capsys):
    assert run(trees, tmp_path) == 0
    out = capsys.readouterr().out
    assert "{'written': 3, 'frames_renamed': 2, 'axis_scaled': 2, 'mixed_ratio': 0, 'frame_unresolved': 1}" in out
    assert 'upscaled images matched to originals: 3  (BMP->TGA conversions: 1)' in out
    assert 'orphan images: 1   other files naming converted BMPs: 1' in out


def test_ebm_frame_renamed_axis_scaled_bytes_preserved(trees, tmp_path):
    run(trees, tmp_path)
    got = (trees[1] / 'fx/a.ebm').read_bytes()
    want = EBM_FX.replace('{Axis 10 13}', '{Axis 20 26}').replace('{Frame "a.bmp"}}', '{Frame "a.tga"}}')
    assert got == want.encode('latin-1')
    assert b'; old: {Frame "a.bmp"} {Axis 1 1}\r\n' in got          # comment line untouched
    assert b'\r\n' in got and b'\xe9t\xe9' in got                    # CRLF and latin-1 kept


def test_tex_frame_renamed_without_axis(trees, tmp_path):
    run(trees, tmp_path)
    assert (trees[1] / 'fx/a.tex').read_bytes() == TEX_FX.replace('a.bmp', 'a.tga').encode('latin-1')


def test_axis_scaled_when_frame_keeps_extension(trees, tmp_path):
    run(trees, tmp_path)
    assert (trees[1] / 'entity/-human/sold.ebm').read_bytes() == EBM_HUMAN.replace('16 30', '32 60').encode('latin-1')


def test_unresolved_frame_reported_not_written(trees, tmp_path):
    run(trees, tmp_path)
    assert not (trees[1] / 'fx/missing.ebm').exists()
    rep = (tmp_path / 'd.txt').read_text()
    assert 'Frame "ghost"\tfile with appended ext exists: [\'.bmp\']' in rep
    assert 'entity/-human/unused.bmp' in rep.replace('\\', '/')     # orphan
    assert 'list.txt' in rep                                         # other file naming a converted BMP


def test_no_axis(trees, tmp_path, capsys):
    run(trees, tmp_path, '--no-axis')
    assert "'axis_scaled': 0" in capsys.readouterr().out
    assert b'{Axis 10 13}' in (trees[1] / 'fx/a.ebm').read_bytes()
    assert not (trees[1] / 'entity/-human/sold.ebm').exists()        # nothing else to change there


def test_dry_run_writes_nothing(trees, tmp_path, capsys):
    before = tree_snapshot(trees[1])
    run(trees, tmp_path, '--dry-run')
    assert tree_snapshot(trees[1]) == before
    out = capsys.readouterr().out
    assert "'written': 3" in out and '(dry run: nothing written)' in out


def test_resource_tree_unchanged(trees, tmp_path):
    before = tree_snapshot(trees[0])
    run(trees, tmp_path)
    assert tree_snapshot(trees[0]) == before


def test_mixed_ratio_warned(tmp_path):
    res, out = tmp_path / 'res', tmp_path / 'hd_out'
    write(res / 'x/a.bmp', bmp24(16, 16))
    write(out / 'x/a.bmp', bmp24(32, 32))
    write(res / 'x/b.bmp', bmp24(16, 16))
    write(out / 'x/b.bmp', bmp24(64, 64))
    write(res / 'x/m.ebm', b'{bitmap {Axis 4 4}{Frame "a.bmp"}}\r\n{bitmap {Frame "b.bmp"}}\r\n')
    r = fix_descriptors.fix(res, out, dry=True)
    assert r['stats']['mixed_ratio'] == 1
    assert r['stats']['axis_scaled'] == 1                            # first frame's ratio wins


def test_missing_root_exit_1(tmp_path):
    assert fix_descriptors.main([str(tmp_path / 'a'), str(tmp_path / 'b')]) == 1
