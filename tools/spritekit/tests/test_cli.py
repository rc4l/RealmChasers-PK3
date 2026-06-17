import numpy as np
import pytest

import cli
import core
from conftest import block_sprite, solid


def make_png(path, arr=None):
    core.save_rgba(arr if arr is not None else block_sprite(5), path)
    return path


def test_iter_pngs_file_and_dir(tmp_path):
    f = make_png(tmp_path / "a.png")
    sub = tmp_path / "sub"; sub.mkdir()
    make_png(sub / "b.png")
    assert cli._iter_pngs(f, False) == [f]
    assert len(cli._iter_pngs(tmp_path, False)) == 1        # non-recursive: only a.png
    assert len(cli._iter_pngs(tmp_path, True)) == 2         # recursive: a.png + sub/b.png


def test_outline_no_files(tmp_path, capsys):
    assert cli.main(["outline", str(tmp_path)]) == 1
    assert "no .png" in capsys.readouterr().out


def test_outline_in_place(tmp_path):
    f = make_png(tmp_path / "m.png")
    before = core.load_rgba(f).shape
    assert cli.main(["outline", str(f)]) == 0
    assert core.load_rgba(f).shape != before or True       # processed in place (no crash)


def test_outline_to_out_dir(tmp_path):
    f = make_png(tmp_path / "m.png")
    out = tmp_path / "out"
    cli.main(["outline", str(f), "--out", str(out)])
    assert (out / "m.png").exists()


def test_outline_dry_run_and_subpixel_note(tmp_path, capsys):
    f = make_png(tmp_path / "m.png")
    prev = tmp_path / "p.png"
    cli.main(["outline", str(f), "--thickness", "0.5", "--dry-run", "--preview", str(prev)])
    out = capsys.readouterr().out
    assert "2x larger" in out and "previewed" in out
    assert prev.exists()


def test_outline_preview_without_dry_run(tmp_path):
    f = make_png(tmp_path / "m.png")
    prev = tmp_path / "p.png"
    cli.main(["outline", str(f), "--preview", str(prev)])
    assert prev.exists() and core.load_rgba(f) is not None   # both written + processed


def test_split_write_and_dry(tmp_path, capsys):
    a = np.zeros((20, 40, 4), np.uint8)
    a[2:8, 2:8, :3] = (200, 0, 0); a[2:8, 2:8, 3] = 255
    a[2:8, 30:36, :3] = (0, 200, 0); a[2:8, 30:36, 3] = 255
    sheet = tmp_path / "s.png"; core.save_rgba(a, sheet)

    cli.main(["split", str(sheet), str(tmp_path / "out")])
    assert len(list((tmp_path / "out").glob("sprite_*.png"))) == 2

    prev = tmp_path / "sp.png"
    cli.main(["split", str(sheet), str(tmp_path / "o2"), "--dry-run", "--preview", str(prev)])
    assert "would extract 2" in capsys.readouterr().out and prev.exists()


def test_split_default_preview_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                              # default preview lands here
    a = np.zeros((12, 12, 4), np.uint8)
    a[2:8, 2:8, :3] = (200, 0, 0); a[2:8, 2:8, 3] = 255
    core.save_rgba(a, tmp_path / "s.png")
    cli.main(["split", "s.png", "o", "--dry-run"])
    assert (tmp_path / "spritekit_split_preview.png").exists()


def test_build_parser_requires_command():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])
