"""Outline normalization: strip inconsistent outlines and rebuild a uniform,
grid-aligned, per-pixel tinted outline at the sprite's native art resolution."""
from dataclasses import dataclass, field
import numpy as np
from scipy import ndimage

from core import (lum, detect_scale, downscale, upscale, crop_tight,
                  border_ring, conn_structure)

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
    connectivity: int = 4         # 4 = no diagonal fill, 8 = filled corners
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


def _strip_outline(a, outline_colors, target_lum):
    """Remove any existing outline -> clean fill. Strips, as boundary-connected
    bands: (1) known palette outline colors, (2) the dominant dark boundary color,
    (3) any very-dark band (<= target_lum+8) so the tool's OWN output is stripped on
    re-run, making the operation idempotent."""
    op = a[:, :, 3] > 0
    ring = border_ring(op)
    if not ring.any():
        return a
    rpix = a[ring][:, :3]
    cols, counts = np.unique(rpix, axis=0, return_counts=True)
    dom = tuple(int(x) for x in cols[int(np.argmax(counts))])
    frac = counts.max() / len(rpix)

    targets = {tuple(c) for c in outline_colors}
    if frac >= 0.5 and lum(dom) <= 90:
        targets.add(dom)
    for c in targets:
        _strip_band(a, np.all(a[:, :, :3] == c, axis=2) & (a[:, :, 3] > 0))

    rgb = a[:, :, :3]
    L = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    _strip_band(a, (L <= target_lum + 8) & (a[:, :, 3] > 0))
    return a


def _darken_to_lum(c, target):
    """Scale colors (...,3) down so luminance == target (only darkens)."""
    L = 0.299 * c[..., 0] + 0.587 * c[..., 1] + 0.114 * c[..., 2]
    scale = np.minimum(1.0, target / np.maximum(L, 1.0))
    return np.clip((c * scale[..., None]).round(), 0, 255).astype(np.uint8)


def _add_tinted_outline(a, iters, connectivity, target_lum):
    """Add an `iters`-px ring. Each ring pixel is a darkened shade of the strongest
    (highest-chroma) fill color among its neighbors."""
    a = np.pad(a, ((iters, iters), (iters, iters), (0, 0)))
    sil = a[:, :, 3] > 0
    grown = ndimage.binary_dilation(sil, conn_structure(connectivity), iterations=iters)
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


def process_array(arr, params=None):
    """Full pipeline for one sprite -> new RGBA array (idempotent for thickness >= 1).

    thickness < 1 (e.g. 0.5, 0.25) draws a sub-art-pixel outline by subdividing each
    art pixel, which ENLARGES the output by `image_growth(thickness)`x."""
    p = params or OutlineParams()
    a = arr.copy()
    s = p.scale or detect_scale(a)
    art = downscale(a, s) if s > 1 else a
    art = _strip_outline(art, p.outline_colors, p.target_lum)

    sub = image_growth(p.thickness)               # 2 for 0.5, 4 for 0.25, else 1
    work = upscale(art, sub) if sub > 1 else art   # subdivide each art pixel
    iters = max(1, round(p.thickness * sub))       # outline thickness in work pixels
    work = _add_tinted_outline(work, iters, p.connectivity, p.target_lum)

    big = upscale(work, s) if s > 1 else work      # back to (enlarged) output resolution
    return crop_tight(big)
