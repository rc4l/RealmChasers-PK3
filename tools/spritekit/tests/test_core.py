import numpy as np
import pytest

import core
from conftest import solid, block_sprite


def test_lum_known_values():
    assert core.lum((0, 0, 0)) == 0
    assert core.lum((255, 255, 255)) == pytest.approx(255)


def test_load_save_roundtrip(tmp_path):
    a = solid(3, 2)
    p = tmp_path / "x.png"
    core.save_rgba(a, p)
    b = core.load_rgba(p)
    assert np.array_equal(a, b)


def test_detect_scale_block():
    assert core.detect_scale(block_sprite(5)) == 5
    assert core.detect_scale(block_sprite(1)) == 1


def test_detect_scale_empty_returns_one():
    assert core.detect_scale(np.zeros((0, 0, 4), np.uint8)) == 1


def test_detect_visual_block():
    assert core.detect_visual_block(block_sprite(5)) == 5      # clean upscale -> exact
    a = block_sprite(2).copy()
    a[0, 0] = (1, 2, 3, 255)                                   # one odd pixel breaks the GCD
    assert core.detect_scale(a) == 1                           # exact detector gives up
    assert core.detect_visual_block(a) == 2                    # apparent block still ~2
    assert core.detect_visual_block(np.full((3, 3, 4), 200, np.uint8)) >= 1   # size-break path


def test_downscale_upscale_roundtrip():
    art = np.arange(2 * 2 * 4, dtype=np.uint8).reshape(2, 2, 4)
    big = core.upscale(art, 5)
    assert big.shape == (10, 10, 4)
    assert np.array_equal(core.downscale(big, 5), art)


def test_crop_tight_and_empty():
    a = np.zeros((6, 6, 4), np.uint8)
    a[2:4, 1:5] = (1, 2, 3, 255)
    assert core.crop_tight(a).shape == (2, 4, 4)
    empty = np.zeros((4, 4, 4), np.uint8)
    assert core.crop_tight(empty).shape == (4, 4, 4)   # unchanged when nothing opaque


def test_border_ring():
    op = np.zeros((4, 4), bool)
    op[1:3, 1:3] = True              # a 2x2 block; all 4 touch the transparent edge
    ring = core.border_ring(op)
    assert ring[1:3, 1:3].all()
    assert not ring[0, 0]


def test_conn_structure():
    assert core.conn_structure(4)[0, 0] == 0 and core.conn_structure(4)[1, 1] == 1
    assert core.conn_structure(8).sum() == 9


def test_debug_sheet():
    import outline as outline_mod
    _, stages, info = outline_mod.run_pipeline(block_sprite(5))
    sheet = core.debug_sheet(stages, info)
    assert sheet.mode == "RGB" and sheet.size[0] > 0 and sheet.size[1] > 0


def test_demo_assets():
    sprite = core.demo_sprite()
    assert sprite.shape[2] == 4 and (sprite[:, :, 3] > 0).any()
    sheet = core.demo_sheet()
    assert (sheet[:, :, 3] > 0).any()


def test_contact_sheet_with_and_without_before():
    a = solid(5, 5, (10, 200, 10, 255))
    sheet = core.contact_sheet([(None, a), (a, a)], ["short", "a_very_long_name_exceeding"])
    assert sheet.mode == "RGB" and sheet.size[0] > 0
