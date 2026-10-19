import compare_alpha
import pytest
from conftest import tga, write


def half_clear(x, y):
    return (200, 100, 50, 255 if x < 8 else 0)


def half_clear_2x(x, y):
    return half_clear(x // 2, y // 2)


def test_stats(tmp_path):
    w, h, px, raw = compare_alpha.read_tga(write(tmp_path / 'a.tga', tga(16, 16, half_clear)))
    alpha, coverage, brightness = compare_alpha.stats(raw, px)
    assert (w, h, px) == (16, 16, 4)
    assert alpha == pytest.approx(127.5) and coverage == 0.5
    assert brightness == pytest.approx((200 + 100 + 50) / 3)
    _, _, px3, raw3 = compare_alpha.read_tga(write(tmp_path / 'b.tga', tga(16, 16, half_clear, bpp=24)))
    assert compare_alpha.stats(raw3, px3)[:2] == (255, 1.0)                 # 24 bpp: no alpha, all visible


def test_clean_upscale_keeps_coverage(tmp_path, capsys):
    write(tmp_path / 'orig/entity/s/a.tga', tga(16, 16, half_clear))
    write(tmp_path / 'hd/entity/s/a.tga', tga(32, 32, half_clear_2x))
    write(tmp_path / 'hd/entity/s/rle.tga', tga(32, 32, half_clear_2x, rle=True))
    write(tmp_path / 'orig/entity/s/rle.tga', tga(16, 16, half_clear, rle=True))
    write(tmp_path / 'hd/entity/s/new_only.tga', tga(32, 32))
    assert compare_alpha.main([str(tmp_path / 'orig'), str(tmp_path / 'hd'), 'entity']) == 0
    out = capsys.readouterr().out
    assert '16x16 ->     32x32' in out
    assert '50.0%-> 50.0%' in out
    assert '2 files. Median change: alpha mean x1.00, coverage x1.00, brightness x1.00' in out


def test_spread_alpha_detected(tmp_path):
    write(tmp_path / 'o/x/a.tga', tga(16, 16, half_clear))
    write(tmp_path / 'n/x/a.tga', tga(32, 32))                      # fully opaque: coverage doubled
    rows = compare_alpha.compare(tmp_path / 'o', tmp_path / 'n', 'x')
    assert compare_alpha.median_change(rows, 1) == pytest.approx(2.0)


def test_unsupported_and_empty(tmp_path, capsys):
    write(tmp_path / 'o/x/g.tga', tga(16, 16, bpp=8, typ=3))
    write(tmp_path / 'n/x/g.tga', tga(32, 32, bpp=8, typ=3))
    assert compare_alpha.main([str(tmp_path / 'o'), str(tmp_path / 'n'), 'x']) == 0
    assert 'no matching files found' in capsys.readouterr().out


def test_missing_root_exit_1(tmp_path):
    assert compare_alpha.main([str(tmp_path / 'a'), str(tmp_path / 'b'), 'x']) == 1
