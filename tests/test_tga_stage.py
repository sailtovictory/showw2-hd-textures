import tga_stage
from conftest import colour, grey, tga, tree_snapshot, write


def build_resource(res, hd_out):
    """One file for every group tga_stage knows about."""
    write(res / 'entity/-human/staged.tga', tga(32, 32))
    write(res / 'interface/menu/button.tga', tga(32, 32))                    # excluded
    write(res / 'fx/_tga/vihlop.tga/vihlop01.tga', tga(32, 32))              # dirnamed (folder named like an image)
    write(res / 'fx/_bmp/explosion/faerog.bmp/Faer01.tga', tga(32, 32))      # dirnamed (.bmp folder)
    write(res / 'entity/fauna/small.tga', tga(15, 40))                       # small
    write(res / 'texture/common/big.tga', tga(1025, 16, bpp=24))             # big
    write(res / 'texture/common/mask.tga', tga(32, 32, grey))                # grey
    write(res / 'texture/common/mono.tga', tga(32, 32, bpp=8, typ=3))        # grey (greyscale type)
    write(res / 'entity/landscape/done.tga', tga(32, 32))                    # conflict
    write(hd_out / 'entity/landscape/done.tga', b'already upscaled')
    write(res / 'entity/landscape/broken.tga', b'\x00' * 10)                 # unreadable
    write(res / 'entity/landscape/rle.tga', tga(32, 32, rle=True))           # staged, RLE


def run(tmp_path, *extra):
    res, hd = tmp_path / 'res', tmp_path / 'hd_out'
    build_resource(res, hd)
    args = [str(res), str(tmp_path / 'stage'), str(tmp_path / 'hold'), '--hd-out', str(hd),
            '--report', str(tmp_path / 'r.txt'), *extra]
    return tga_stage.main(args)


def groups(report):
    return {line.split('\t')[1].replace('\\', '/'): line.split('\t')[0] for line in report.read_text().splitlines()}


def test_every_group(tmp_path, capsys):
    assert run(tmp_path) == 0
    g = groups(tmp_path / 'r.txt')
    assert g == {
        'interface/menu/button.tga': 'excluded',
        'fx/_tga/vihlop.tga/vihlop01.tga': 'dirnamed',
        'fx/_bmp/explosion/faerog.bmp/Faer01.tga': 'dirnamed',
        'entity/fauna/small.tga': 'small',
        'texture/common/big.tga': 'big',
        'texture/common/mask.tga': 'grey',
        'texture/common/mono.tga': 'grey',
        'entity/landscape/done.tga': 'conflict',
        'entity/landscape/broken.tga': 'unreadable',
    }
    out = capsys.readouterr().out
    assert "'staged': 2" in out
    assert "'dirnamed': 2" in out


def test_files_land_in_the_right_place(tmp_path):
    run(tmp_path)
    stage, hold = tmp_path / 'stage', tmp_path / 'hold'
    staged = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    assert staged == {'entity/-human/staged.tga', 'entity/landscape/rle.tga'}
    held = {p.relative_to(hold).as_posix() for p in hold.rglob('*') if p.is_file()}
    assert held == {
        'dirnamed/fx/_tga/vihlop.tga__dir/vihlop01.tga',
        'dirnamed/fx/_bmp/explosion/faerog.bmp__dir/Faer01.tga',
        'big/texture/common/big.tga',
        'grey/texture/common/mask.tga',
        'grey/texture/common/mono.tga',
    }


def test_exclude_and_max_side_options(tmp_path):
    run(tmp_path, '--exclude', 'interface, entity', '--max-side', '2048')
    g = groups(tmp_path / 'r.txt')
    assert g['entity/-human/staged.tga'] == 'excluded'
    assert 'texture/common/big.tga' not in g                                  # now staged


def test_dry_run_copies_nothing(tmp_path, capsys):
    run(tmp_path, '--dry-run')
    assert not (tmp_path / 'stage').exists() and not (tmp_path / 'hold').exists()
    assert '(dry run: nothing copied)' in capsys.readouterr().out


def test_resource_tree_unchanged(tmp_path):
    res = tmp_path / 'res'
    build_resource(res, tmp_path / 'hd_out')
    before = tree_snapshot(res)
    tga_stage.main([str(res), str(tmp_path / 'stage'), str(tmp_path / 'hold'), '--report', str(tmp_path / 'r.txt')])
    assert tree_snapshot(res) == before


def test_rle_decodes_like_uncompressed(tmp_path):
    a = tga_stage.read_tga(write(tmp_path / 'a.tga', tga(20, 10, colour)))
    b = tga_stage.read_tga(write(tmp_path / 'b.tga', tga(20, 10, colour, rle=True)))
    assert a['raw'] == b['raw'] and a['raw'] is not None
    assert b['type'] == 10


def test_truncated_pixels_not_decodable(tmp_path):
    d = tga_stage.read_tga(write(tmp_path / 'a.tga', tga(20, 10)[:-5]))
    assert d is not None and d['raw'] is None


def test_mark_dirs():
    from pathlib import Path as P
    assert tga_stage.mark_dirs(P('a/X.TGA/b.bmp/f.tga')) == P('a/X.TGA__dir/b.bmp__dir/f.tga')
    assert tga_stage.mark_dirs(P('a/b/f.tga')) == P('a/b/f.tga')


def test_missing_root_exit_1(tmp_path):
    assert tga_stage.main([str(tmp_path / 'nope'), str(tmp_path / 's'), str(tmp_path / 'h')]) == 1
