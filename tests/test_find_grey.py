import find_grey
import pytest
from conftest import bmp24, bmp32, colour, grey, tga, write


def test_sample_grey_bmp_and_tga(tmp_path):
    assert find_grey.sample_grey(write(tmp_path / 'g.bmp', bmp24(40, 30, grey))) == 1.0
    assert find_grey.sample_grey(write(tmp_path / 'c.bmp', bmp24(40, 30, colour))) == 0.0
    assert find_grey.sample_grey(write(tmp_path / 'g.tga', tga(40, 30, grey))) == 1.0
    assert find_grey.sample_grey(write(tmp_path / 'c.tga', tga(40, 30, colour))) == 0.0


def test_unchecked_formats_return_none(tmp_path):
    assert find_grey.sample_grey(write(tmp_path / 'a.bmp', bmp32(16, 16, grey))) is None
    assert find_grey.sample_grey(write(tmp_path / 'b.tga', tga(16, 16, grey, bpp=24))) is None
    assert find_grey.sample_grey(write(tmp_path / 'c.tga', tga(16, 16, grey, rle=True))) is None


def test_transparent_pixels_ignored(tmp_path):
    # colour pixels are fully transparent, the visible ones are grey
    def px(x, y):
        return (255, 0, 0, 0) if x < 20 else (*grey(x, y)[:3], 255)
    assert find_grey.sample_grey(write(tmp_path / 'm.tga', tga(32, 32, px))) == 1.0

    def all_clear(x, y):
        return (255, 0, 0, 0)
    assert find_grey.sample_grey(write(tmp_path / 'n.tga', tga(16, 16, all_clear))) is None


def test_threshold_is_98_percent(tmp_path):
    def mostly(x, y):                                   # 1 colour column of 40 -> 97.5% grey
        return colour(x, y) if x == 0 else grey(x, y)
    assert find_grey.sample_grey(write(tmp_path / 'a.bmp', bmp24(40, 40, mostly))) == pytest.approx(0.975)
    write(tmp_path / 'stage/t/a.bmp', bmp24(40, 40, mostly))
    _, flagged = find_grey.scan([tmp_path / 'stage'])
    assert flagged == []


def test_main_reports_and_moves(tmp_path, capsys):
    sa, so, hold = tmp_path / 'stage_alpha', tmp_path / 'stage_opaque', tmp_path / 'grey_hold'
    write(sa / 'texture/common/mask.tga', tga(32, 32, grey))
    write(sa / 'texture/common/skin.tga', tga(32, 32, colour))
    write(so / 'entity/-human/light.bmp', bmp24(32, 32, grey))
    rep = tmp_path / 'g.txt'
    rc = find_grey.main([str(sa), str(so), '--move', str(hold), '--report', str(rep)])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'flagged 2 greyscale files' in out
    assert '    1 of     2 greyscale   stage_alpha\\texture\\common' in out
    assert (hold / 'stage_alpha/texture/common/mask.tga').is_file()
    assert (hold / 'stage_opaque/entity/-human/light.bmp').is_file()
    assert not (sa / 'texture/common/mask.tga').exists()
    assert (sa / 'texture/common/skin.tga').is_file()
    assert sorted(line.split('\t')[0] for line in rep.read_text().splitlines()) == ['stage_alpha', 'stage_opaque']


def test_without_move_nothing_moves(tmp_path):
    write(tmp_path / 's/a.bmp', bmp24(16, 16, grey))
    assert find_grey.main([str(tmp_path / 's'), '--report', str(tmp_path / 'r.txt')]) == 0
    assert (tmp_path / 's/a.bmp').is_file()


def test_missing_root_exit_1(tmp_path):
    assert find_grey.main([str(tmp_path / 'nope')]) == 1
