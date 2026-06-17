import numpy as np
import pytest

import outline as o
import core
from conftest import solid, block_sprite, with_outline


def test_image_growth():
    assert o.image_growth(0.25) == 4
    assert o.image_growth(0.5) == 2
    assert o.image_growth(1) == 1
    assert o.image_growth(3) == 1


def test_params_default_colors_independent():
    a, b = o.OutlineParams(), o.OutlineParams()
    a.outline_colors.append((1, 1, 1))
    assert (1, 1, 1) not in b.outline_colors


def test_darken_to_lum_caps_luminance():
    out = o._darken_to_lum(np.array([[[255, 255, 255]]], np.int16), 16)
    assert core.lum(out[0, 0]) == pytest.approx(16, abs=1)
    # already-dark colors are not brightened
    dark = o._darken_to_lum(np.array([[[5, 5, 5]]], np.int16), 16)
    assert tuple(dark[0, 0]) == (5, 5, 5)


def test_adds_outline_when_none():
    out = o.process_array(block_sprite(5), o.OutlineParams())
    # there are now near-black border pixels that were not in the source
    assert (core_lum_min(out) <= 24)


def core_lum_min(arr):
    op = arr[:, :, 3] > 0
    px = arr[op][:, :3].astype(int)
    return (0.299 * px[:, 0] + 0.587 * px[:, 1] + 0.114 * px[:, 2]).min()


def test_strips_known_palette_outline():
    art = np.zeros((4, 4, 4), np.uint8)
    art[1:3, 1:3] = (200, 30, 30, 255)
    sprite = with_outline(art, (0, 0, 0))          # palette outline color
    out = o.process_array(sprite, o.OutlineParams(scale=1))
    assert (out[:, :, :3] == [0, 0, 0]).all(axis=2).sum() >= 1   # rebuilt, still dark


def test_strips_dominant_dark_non_palette():
    art = np.zeros((4, 4, 4), np.uint8)
    art[1:3, 1:3] = (200, 30, 30, 255)
    sprite = with_outline(art, (50, 50, 50))       # dark, not in palette, dominant
    out = o.process_array(sprite, o.OutlineParams(scale=1))
    visible = (out[:, :, :3] == [50, 50, 50]).all(axis=2) & (out[:, :, 3] > 0)
    assert not visible.any()                       # the (50,50,50) outline is gone


def test_strip_outline_all_transparent_returns_input():
    a = np.zeros((4, 4, 4), np.uint8)
    assert o._strip_outline(a.copy(), o.DEFAULT_OUTLINE_COLORS, 16).shape == a.shape


def test_scale_one_path():
    out = o.process_array(block_sprite(1), o.OutlineParams(scale=1))
    assert out.shape[2] == 4


def test_thickness_enlarges_image():
    base = o.process_array(block_sprite(5), o.OutlineParams(thickness=1))
    half = o.process_array(block_sprite(5), o.OutlineParams(thickness=0.5))
    quarter = o.process_array(block_sprite(5), o.OutlineParams(thickness=0.25))
    assert half.shape[0] > base.shape[0]
    assert quarter.shape[0] > half.shape[0]


def test_thick_ring_uses_nearest_fill():
    out = o.process_array(block_sprite(5), o.OutlineParams(thickness=2))
    assert out.shape[0] > 0   # exercises iters>1 + distance-transform branch


def test_connectivity_8_fills_corners():
    out4 = o.process_array(block_sprite(5), o.OutlineParams(connectivity=4))
    out8 = o.process_array(block_sprite(5), o.OutlineParams(connectivity=8))
    n4 = (out4[:, :, 3] > 0).sum()
    n8 = (out8[:, :, 3] > 0).sum()
    assert n8 >= n4   # filled corners add at least as many pixels


def test_bright_dominant_and_interior_dark_band():
    # dominant boundary color is bright (lum > 90) -> dom NOT added to strip targets;
    # the lone interior dark pixel forms a band that doesn't touch the boundary ->
    # not stripped. Covers both those branches.
    art = np.zeros((5, 5, 4), np.uint8)
    art[:, :] = (200, 200, 200, 255)
    art[2, 2, :3] = (5, 5, 5)
    out = o.process_array(art, o.OutlineParams(scale=1))
    keep = (out[:, :, :3] == [5, 5, 5]).all(axis=2) & (out[:, :, 3] > 0)
    assert keep.any()        # interior dark pixel survived (its band never touched the edge)


def test_solid_fill_not_stripped_as_outline():
    # Regression: a sprite with NO outline whose dominant edge color is a dark-ish
    # fill (the sample mushroom's red cap) must keep its fill -- the dominant-dark
    # strip must not mistake fill for an outline and erase it.
    out = o.process_array(__import__("core").demo_sprite())
    cap = (out[:, :, :3] == [200, 30, 30]).all(axis=2) & (out[:, :, 3] > 0)
    assert cap.sum() >= 10                 # the red cap survives processing


def test_high_darkness_keeps_fill():
    # Regression: at a high target_lum the very-dark strip threshold rises into fill
    # luminance; the red cap (lum ~81) must NOT be eroded when target_lum=80.
    out = o.process_array(__import__("core").demo_sprite(), o.OutlineParams(target_lum=80))
    cap = (out[:, :, :3] == [200, 30, 30]).all(axis=2) & (out[:, :, 3] > 0)
    assert cap.sum() >= 10


def test_palette_color_interior_only_is_kept():
    # a palette outline color sitting only INSIDE the sprite (not on the boundary)
    # forms a band that doesn't touch the edge -> must not be stripped.
    art = np.zeros((5, 5, 4), np.uint8)
    art[:, :] = (200, 30, 30, 255)
    art[2, 2, :3] = (16, 18, 28)          # navy (a palette outline color) in the center
    out = o.process_array(art, o.OutlineParams(scale=1))
    keep = (out[:, :, :3] == [16, 18, 28]).all(axis=2) & (out[:, :, 3] > 0)
    assert keep.any()


def test_strip_outline_no_interior():
    a = np.zeros((2, 2, 4), np.uint8); a[:, :] = (50, 50, 50, 255)   # all-boundary, no interior
    o._strip_outline(a.copy(), o.DEFAULT_OUTLINE_COLORS, 16)         # interior.any() == False path


def test_idempotent_default():
    s = block_sprite(5)
    r1 = o.process_array(s)
    r2 = o.process_array(r1)
    assert r1.shape == r2.shape and np.array_equal(r1, r2)
