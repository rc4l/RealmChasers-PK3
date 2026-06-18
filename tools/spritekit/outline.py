"""Outline normalization: strip inconsistent outlines and rebuild a uniform,
grid-aligned, per-pixel tinted outline at the sprite's native art resolution."""
from dataclasses import dataclass, field
import numpy as np
from scipy import ndimage

from core import (lum, detect_scale, detect_visual_block, downscale, upscale,
                  crop_tight, border_ring)

# Dark "outline-role" colors observed across the vegetation art. Any of these
# forming a band that touches the silhouette boundary is treated as an existing
# outline and stripped. Interior shading of the same color is never touched.
DEFAULT_OUTLINE_COLORS = [
    (0, 0, 0), (16, 18, 28), (0, 101, 84),
    (30, 64, 68), (30, 71, 68), (62, 39, 49),
]


@dataclass
class OutlineParams:
    target_lum: int = 16          # outline pixels darkened to this luminance
    connectivity: int = 4         # 4 = sharp corners + sealed diagonals (default); 8 = rounded corners
    thickness: float = 1.0        # outline thickness in ART pixels (0.25/0.5 enlarge the image)
    scale: int = 0                # upscale factor; 0 = auto-detect per sprite
    outline_colors: list = field(default_factory=lambda: list(DEFAULT_OUTLINE_COLORS))


def image_growth(thickness):
    """Factor by which a given thickness enlarges the output (1 for thickness >= 1)."""
    return round(1.0 / thickness) if thickness < 1 else 1


def _strip_band(a, mask):
    """Make transparent the connected components of `mask` that touch the boundary."""
    if not mask.any():
        return
    lbl, _ = ndimage.label(mask, structure=np.ones((3, 3), int))
    touch = set(np.unique(lbl[border_ring(a[:, :, 3] > 0) & mask]))
    touch.discard(0)
    if touch:
        a[np.isin(lbl, list(touch)), 3] = 0


def _strip_outline(a, outline_colors):
    """Strip the source art's known palette outline colors (as boundary-connected
    bands). Unknown dark outlines -- including the tool's own output -- are handled
    geometrically by _strip_dark_border."""
    for c in outline_colors:
        _strip_band(a, np.all(a[:, :, :3] == c, axis=2) & (a[:, :, 3] > 0))
    return a


def _strip_dark_border(a):
    """Remove an EXISTING outline (of any thickness) so a fresh one can be (re)built
    from the base art. An outline is a connected band, touching the silhouette
    boundary, that is much DARKER than the sprite body; flood it out in one pass --
    so thickening/re-processing rebuilds from the base instead of outlining the
    previous outline. A fresh sprite, whose edge is about as bright as its body, has a
    boundary that isn't 'much darker', so nothing is removed (no erosion)."""
    op = a[:, :, 3] > 0
    L = 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]
    ring = border_ring(op)
    if not ring.any():
        return a
    interior = op & ~ring
    if not interior.any():
        return a
    ring_lum = float(L[ring].mean())
    body_lum = float(np.median(L[interior]))   # the fill under the boundary
    if ring_lum >= 0.6 * body_lum:          # boundary not clearly an outline -> keep all
        return a
    band = op & (L <= ring_lum + 24)        # the uniform dark outline band
    lbl, _ = ndimage.label(band, structure=np.ones((3, 3), int))
    touch = set(np.unique(lbl[ring & band]))
    touch.discard(0)
    a[np.isin(lbl, list(touch)), 3] = 0
    return a


def _darken_to_lum(c, target):
    """Scale colors (...,3) down so luminance == target (only darkens)."""
    L = 0.299 * c[..., 0] + 0.587 * c[..., 1] + 0.114 * c[..., 2]
    scale = np.minimum(1.0, target / np.maximum(L, 1.0))
    return np.clip((c * scale[..., None]).round(), 0, 255).astype(np.uint8)


def _shift(s, dr, dc):
    """Shift a boolean array by (dr, dc), vacated cells become False (no wrap-around)."""
    out = np.zeros_like(s)
    H, W = s.shape
    out[max(0, -dr):H + min(0, -dr), max(0, -dc):W + min(0, -dc)] = \
        s[max(0, dr):H + min(0, dr), max(0, dc):W + min(0, dc)]
    return out


def _convex_corner_fill(sil, n):
    """Square off TRUE convex 90-degree corners so a thick cardinal outline isn't chipped
    into a diagonal notch there -- WITHOUT sealing sloped/staircase edges. A corner only
    qualifies when BOTH its edges run straight (the diagonally-opposite cell is empty, so
    the edge doesn't immediately step); a staircase step fails that test and stays a
    cardinal step. Each qualifying corner fills its outer n x n block."""
    s = sil
    U, D, L, R = _shift(s, -1, 0), _shift(s, 1, 0), _shift(s, 0, -1), _shift(s, 0, 1)
    UL, UR, DL, DR = _shift(s, -1, -1), _shift(s, -1, 1), _shift(s, 1, -1), _shift(s, 1, 1)
    TL = s & ~U & ~L & R & D & ~UR & ~DL          # top-left corner  -> fill up-left
    TR = s & ~U & ~R & L & D & ~UL & ~DR          # top-right corner -> fill up-right
    BL = s & ~D & ~L & R & U & ~DR & ~UL          # bottom-left      -> fill down-left
    BR = s & ~D & ~R & L & U & ~DL & ~UR          # bottom-right     -> fill down-right
    fill = np.zeros_like(s)
    for dr in range(1, n + 1):
        for dc in range(1, n + 1):
            fill |= (_shift(TL, dr, dc) | _shift(TR, dr, -dc)
                     | _shift(BL, -dr, dc) | _shift(BR, -dr, -dc))
    return fill & ~sil


def _grow_outline(sil, iters, connectivity):
    """Place the outline with ONE dilation from the base (never layering outline onto
    outline). 8-conn: a full square (every corner filled = rounded). 4-conn: a cardinal
    cross of arm `iters` -- protrudes only up/down/left/right, no seal on sloped edges --
    PLUS squared-off true convex corners so a thick outline isn't chipped at 90-degree
    corners."""
    n = iters
    if connectivity == 8:
        return ndimage.binary_dilation(sil, np.ones((2 * n + 1, 2 * n + 1), bool))
    cross = np.zeros((2 * n + 1, 2 * n + 1), bool)
    cross[n, :] = True
    cross[:, n] = True
    return ndimage.binary_dilation(sil, cross) | _convex_corner_fill(sil, n)


def _add_tinted_outline(a, iters, connectivity, target_lum):
    """Add an `iters`-px ring. Each ring pixel is a darkened shade of the strongest
    (highest-chroma) fill color among its neighbors."""
    a = np.pad(a, ((iters, iters), (iters, iters), (0, 0)))
    sil = a[:, :, 3] > 0
    grown = _grow_outline(sil, iters, connectivity)
    ring = grown & ~sil

    rgb = a[:, :, :3].astype(np.int16)
    best_chroma = np.full(sil.shape, -1, np.int16)
    best_color = np.zeros_like(rgb)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            nc = np.roll(np.roll(rgb, dy, 0), dx, 1)
            nv = np.roll(np.roll(sil, dy, 0), dx, 1)
            ch = np.where(nv, nc.max(2) - nc.min(2), -1).astype(np.int16)
            take = ch > best_chroma
            best_chroma = np.where(take, ch, best_chroma)
            best_color = np.where(take[..., None], nc, best_color)

    if iters > 1:   # thick rings: pixels with no fill neighbor take the nearest fill color
        miss = ring & (best_chroma < 0)
        idx = ndimage.distance_transform_edt(
            ~sil, return_distances=False, return_indices=True)
        nearest = rgb[idx[0], idx[1]]
        best_color = np.where(miss[..., None], nearest, best_color)

    tint = _darken_to_lum(best_color, target_lum)
    a[ring, :3] = tint[ring]
    a[ring, 3] = 255
    return a


def run_pipeline(arr, params=None):
    """Full pipeline -> (final RGBA, stages, info). `stages` is a list of
    (label, array) snapshots for debugging; `info` is a dict of derived values.

    thickness < 1 (e.g. 0.5, 0.25) draws a sub-art-pixel outline by subdividing each
    art pixel, which ENLARGES the output by `image_growth(thickness)`x."""
    p = params or OutlineParams()
    a = arr.copy()
    stages = [("input", a.copy())]
    s = p.scale or detect_scale(a)                 # exact block size (lossless downscale)
    art = downscale(a, s) if s > 1 else a
    stages.append(("downscaled art", art.copy()))
    art = _strip_outline(art, p.outline_colors)
    stages.append(("after palette strip", art.copy()))
    art = _strip_dark_border(art)                  # peel any existing outline -> base
    stages.append(("after dark-border peel", art.copy()))

    # On chunky-but-imperfect art (e.g. rocks) the apparent block is bigger than the
    # exact scale, so widen the outline to match instead of drawing a too-thin 1px.
    # Measured on the peeled BASE so re-processing an outlined sprite stays stable.
    factor = 1 if p.scale else detect_visual_block(art)
    sub = image_growth(p.thickness)               # 2 for 0.5, 4 for 0.25, else 1
    work = upscale(art, sub) if sub > 1 else art   # subdivide each art pixel
    iters = max(1, round(p.thickness * sub * factor))   # outline thickness in work pixels
    work = _add_tinted_outline(work, iters, p.connectivity, p.target_lum)
    stages.append(("after outline", work.copy()))

    big = upscale(work, s) if s > 1 else work      # back to (enlarged) output resolution
    final = crop_tight(big)
    stages.append(("final", final))
    info = {"scale": s, "visual_block": factor if not p.scale else s, "factor": factor,
            "sub": sub, "iters": iters, "connectivity": p.connectivity,
            "target_lum": p.target_lum, "thickness": p.thickness,
            "input_size": (arr.shape[1], arr.shape[0]),
            "output_size": (final.shape[1], final.shape[0])}
    return final, stages, info


def process_array(arr, params=None):
    """Full pipeline for one sprite -> new RGBA array."""
    return run_pipeline(arr, params)[0]
