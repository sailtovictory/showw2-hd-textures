import struct

import bmp_stage
import pytest
from conftest import bmp24, bmp32, colour, tree_snapshot, write


def alpha_px(x, y):
    r, g, b, _ = colour(x, y)
    return (r, g, b, (x * 16) % 256)


def tga_pixels(data):
    """-> (w, h, descriptor, BGRA bytes) of an uncompressed 32 bpp TGA."""
    w, h = struct.unpack_from('<HH', data, 12)
    assert data[2] == 2 and data[16] == 32
    return w, h, data[17], data[18:]


def expected_bgra(w, h, px):
    """Bottom-up BGRA rows, as the TGA stores them."""
    return b''.join(bytes((px(x, y)[2], px(x, y)[1], px(x, y)[0], px(x, y)[3]))
                    for y in range(h - 1, -1, -1) for x in range(w))


def run(tmp_path, *extra):
    src, a, o = tmp_path / 'res', tmp_path / 'stage_alpha', tmp_path / 'stage_opaque'
    rc = bmp_stage.main([str(src), str(a), str(o), '--report', str(tmp_path / 'r.txt'), *extra])
    return rc, a, o


def test_24bpp_copied_to_opaque(tmp_path):
    data = write(tmp_path / 'res/texture/wall.bmp', bmp24(20, 18)).read_bytes()
    rc, a, o = run(tmp_path)
    assert rc == 0
    assert (o / 'texture/wall.bmp').read_bytes() == data
    assert not a.exists()


@pytest.mark.parametrize('top_down', [False, True])
def test_32bpp_bi_rgb_alpha_becomes_tga(tmp_path, top_down):
    write(tmp_path / 'res/entity/-human/skin.bmp', bmp32(20, 17, alpha_px, top_down=top_down))
    rc, a, o = run(tmp_path)
    assert rc == 0
    w, h, desc, px = tga_pixels((a / 'entity/-human/skin.tga').read_bytes())
    assert (w, h, desc) == (20, 17, 0x08)
    assert px == expected_bgra(20, 17, alpha_px)
    assert not o.exists()


@pytest.mark.parametrize('masks', [
    (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000),   # standard order, stored as BITFIELDS
    (0xFF000000, 0x00FF0000, 0x0000FF00, 0x000000FF),   # RGBA
    (0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000),   # ABGR
])
def test_32bpp_bitfields_alpha_becomes_tga(tmp_path, masks):
    write(tmp_path / 'res/fx/a.bmp', bmp32(16, 16, alpha_px, masks=masks))
    run(tmp_path)
    _, _, _, px = tga_pixels((tmp_path / 'stage_alpha/fx/a.tga').read_bytes())
    assert px == expected_bgra(16, 16, alpha_px)


def test_bitfields_without_alpha_mask_is_opaque(tmp_path):
    write(tmp_path / 'res/fx/a.bmp', bmp32(16, 16, masks=(0xFF0000, 0xFF00, 0xFF, 0), alpha_mask=False))
    run(tmp_path)
    assert (tmp_path / 'stage_opaque/fx/a.bmp').exists()
    assert 'no varying alpha' in (tmp_path / 'r.txt').read_text()


def test_unsupported_masks_skipped(tmp_path):
    write(tmp_path / 'res/fx/a.bmp', bmp32(16, 16, masks=(0xF800, 0x7E0, 0x1F, 0)))
    run(tmp_path)
    assert not (tmp_path / 'stage_alpha').exists() and not (tmp_path / 'stage_opaque').exists()
    assert 'other (masks' in (tmp_path / 'r.txt').read_text()


def test_32bpp_full_alpha_copied_to_opaque(tmp_path):
    data = write(tmp_path / 'res/t/solid.bmp', bmp32(16, 16)).read_bytes()
    run(tmp_path)
    assert (tmp_path / 'stage_opaque/t/solid.bmp').read_bytes() == data


def test_tiny_and_junk_skipped(tmp_path, capsys):
    write(tmp_path / 'res/t/tiny.bmp', bmp24(15, 64))
    write(tmp_path / 'res/t/junk.bmp', b'not a bitmap at all' * 4)
    rc, a, o = run(tmp_path)
    assert rc == 0
    assert not a.exists() and not o.exists()
    out = capsys.readouterr().out
    assert "{'alpha_tga': 0, 'opaque_copy': 0, 'small_skipped': 1, 'other_skipped': 1}" in out
    rep = (tmp_path / 'r.txt').read_text()
    assert 'small 15x64 24bpp' in rep and 'other (not BMP)' in rep


def test_counts_line_format(tmp_path, capsys):
    write(tmp_path / 'res/a/one.bmp', bmp24(16, 16))
    write(tmp_path / 'res/a/two.bmp', bmp32(16, 16, alpha_px))
    run(tmp_path)
    assert "{'alpha_tga': 1, 'opaque_copy': 1, 'small_skipped': 0, 'other_skipped': 0}" in capsys.readouterr().out


def test_image_named_folders_are_marked(tmp_path, capsys):
    write(tmp_path / 'res/fx/_bmp/explosion/faerog.bmp/Faer01.bmp', bmp24(16, 16))
    write(tmp_path / 'res/fx/_bmp/explosion/faerog.bmp/Faer02.bmp', bmp32(16, 16, alpha_px))
    run(tmp_path)
    assert (tmp_path / 'stage_opaque/fx/_bmp/explosion/faerog.bmp__dir/Faer01.bmp').is_file()
    assert (tmp_path / 'stage_alpha/fx/_bmp/explosion/faerog.bmp__dir/Faer02.tga').is_file()
    assert not (tmp_path / 'stage_opaque/fx/_bmp/explosion/faerog.bmp').exists()
    assert '1 image-named folder(s)' in capsys.readouterr().out


def test_no_mark_dirs_keeps_names(tmp_path):
    write(tmp_path / 'res/fx/faerog.bmp/Faer01.bmp', bmp24(16, 16))
    run(tmp_path, '--no-mark-dirs')
    assert (tmp_path / 'stage_opaque/fx/faerog.bmp/Faer01.bmp').is_file()


def test_source_tree_unchanged(tmp_path):
    write(tmp_path / 'res/a/one.bmp', bmp24(16, 16))
    write(tmp_path / 'res/a/x.tga/two.bmp', bmp32(16, 16, alpha_px))
    before = tree_snapshot(tmp_path / 'res')
    run(tmp_path)
    assert tree_snapshot(tmp_path / 'res') == before


def test_default_report_in_cwd(chdir_tmp):
    write(chdir_tmp / 'res/a/one.bmp', bmp24(16, 16))
    assert bmp_stage.main(['res', 'sa', 'so']) == 0
    assert (chdir_tmp / 'bmp_report.txt').exists()


def test_missing_source_exit_1(tmp_path):
    assert bmp_stage.main([str(tmp_path / 'nope'), str(tmp_path / 'a'), str(tmp_path / 'o')]) == 1


def test_bad_usage_exit_2():
    with pytest.raises(SystemExit) as e:
        bmp_stage.main([])
    assert e.value.code == 2
