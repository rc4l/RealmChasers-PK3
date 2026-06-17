import numpy as np
import pytest

import split as sp
import core


def sheet(rects, size=(40, 40)):
    """rects: list of (y0, y1, x0, x1, (r,g,b)). Returns an RGBA sheet."""
    a = np.zeros((size[1], size[0], 4), np.uint8)
    for y0, y1, x0, x1, col in rects:
        a[y0:y1, x0:x1, :3] = col
        a[y0:y1, x0:x1, 3] = 255
    return a


def save(tmp, a, name="sheet.png"):
    p = tmp / name
    core.save_rgba(a, p)
    return p


def test_gap_helper():
    assert sp._gap(dict(x0=0, x1=2, y0=0, y1=2), dict(x0=5, x1=7, y0=0, y1=2)) == (3, 0)


def test_basic_two_sprites(tmp_path):
    p = save(tmp_path, sheet([(2, 8, 2, 8, (200, 0, 0)), (2, 8, 30, 36, (0, 200, 0))]))
    count, results = sp.split_sheet(p, tmp_path / "out", sp.SplitParams())
    assert count == 2
    assert len(list((tmp_path / "out").glob("sprite_*.png"))) == 2


def test_min_area_drops_noise(tmp_path):
    a = sheet([(2, 12, 2, 12, (200, 0, 0))])
    a[30, 30, :3] = (9, 9, 9); a[30, 30, 3] = 255   # 1px speck
    p = save(tmp_path, a)
    count, _ = sp.split_sheet(p, tmp_path / "o", sp.SplitParams(min_area=4))
    assert count == 1


def test_attach_off_keeps_fragment_separate(tmp_path):
    a = sheet([(2, 14, 2, 14, (200, 0, 0)), (4, 7, 22, 25, (0, 200, 0))])  # big + small, 8px apart
    p = save(tmp_path, a)
    count, _ = sp.split_sheet(p, tmp_path / "o", sp.SplitParams(attach_h=0))
    assert count == 2


def test_attach_on_merges_fragment(tmp_path):
    a = sheet([(2, 14, 2, 14, (200, 0, 0)), (4, 7, 22, 25, (0, 200, 0))])
    p = save(tmp_path, a)
    count, _ = sp.split_sheet(p, tmp_path / "o",
                              sp.SplitParams(attach_h=20, fragment_max_dim=6))
    assert count == 1


def test_attach_no_anchors_all_standalone(tmp_path):
    # every blob is a small fragment -> no anchors -> each stays separate
    a = sheet([(2, 6, 2, 6, (10, 10, 200)), (2, 6, 20, 24, (10, 200, 10))])
    p = save(tmp_path, a)
    count, _ = sp.split_sheet(p, tmp_path / "o",
                              sp.SplitParams(attach_h=30, fragment_max_dim=8))
    assert count == 2


def test_attach_chaining(tmp_path):
    # anchor, then a fragment near it, then a fragment near THAT fragment
    a = sheet([(2, 16, 2, 16, (200, 0, 0)),     # anchor (big)
               (8, 12, 20, 24, (0, 200, 0)),    # frag1 ~4px from anchor
               (8, 12, 28, 32, (0, 0, 200))],   # frag2 ~4px from frag1
              size=(48, 24))
    p = save(tmp_path, a)
    count, _ = sp.split_sheet(p, tmp_path / "o",
                              sp.SplitParams(attach_h=8, attach_v=8, fragment_max_dim=6))
    assert count == 1


def test_masked_crop_excludes_neighbor(tmp_path):
    # A is a "U" whose bbox encloses an unrelated blob B; B must not bleed into A's crop.
    a = np.zeros((24, 24, 4), np.uint8)
    for (y0, y1, x0, x1) in [(0, 24, 0, 2), (0, 24, 22, 24), (0, 2, 0, 24)]:  # ⊓ shape, A
        a[y0:y1, x0:x1, :3] = (200, 0, 0); a[y0:y1, x0:x1, 3] = 255
    a[11:13, 11:13, :3] = (0, 0, 200); a[11:13, 11:13, 3] = 255               # B, centered
    p = save(tmp_path, a)
    count, results = sp.split_sheet(p, tmp_path / "o", sp.SplitParams(hgap=2, vgap=2, attach_h=0))
    assert count == 2
    big = max(results, key=lambda r: (r[1][2] - r[1][0]) * (r[1][3] - r[1][1]))[0]
    visible_blue = (big[:, :, :3] == [0, 0, 200]).all(axis=2) & (big[:, :, 3] > 0)
    assert not visible_blue.any()   # B's blue is masked out of A (alpha 0)


def test_ordering_top_then_left(tmp_path):
    a = sheet([(0, 5, 20, 25, (1, 0, 0)),    # top-right
               (0, 5, 0, 5, (2, 0, 0)),      # top-left
               (30, 35, 5, 10, (3, 0, 0))],  # bottom
              size=(40, 40))
    p = save(tmp_path, a)
    _, results = sp.split_sheet(p, tmp_path / "o", sp.SplitParams(), dry_run=True)
    xs_first_band = [results[0][1][0], results[1][1][0]]
    assert xs_first_band[0] < xs_first_band[1]           # left before right in top band
    assert results[2][1][1] > results[0][1][1]           # third is the lower band


def test_group_reach_and_distance_branches():
    # F is near anchor A and far from anchor B.
    info = {
        1: dict(x0=0, x1=10, y0=0, y1=10, area=100),    # anchor A (close)
        2: dict(x0=40, x1=50, y0=0, y1=10, area=100),   # anchor B (far)
        3: dict(x0=12, x1=14, y0=2, y1=4, area=4),      # fragment F
    }
    # both anchors in reach: A sets best, B is farther -> "d < best_d" is False (75->71)
    owner = sp._group(info, sp.SplitParams(attach_h=40, attach_v=40, fragment_max_dim=5))
    assert owner[3] == 1
    # B now out of reach: its gx > attach_h -> condition False (73->71)
    owner2 = sp._group(info, sp.SplitParams(attach_h=20, attach_v=40, fragment_max_dim=5))
    assert owner2[3] == 1


def test_dry_run_writes_nothing(tmp_path):
    p = save(tmp_path, sheet([(2, 8, 2, 8, (200, 0, 0))]))
    out = tmp_path / "nope"
    sp.split_sheet(p, out, sp.SplitParams(), dry_run=True)
    assert not out.exists()
