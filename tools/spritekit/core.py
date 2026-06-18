"""Shared helpers for spritekit: pixel-art sprite splitting and outline tooling."""
import numpy as np
from PIL import Image
from scipy import ndimage
from math import gcd
from functools import reduce


def load_rgba(path):
    return np.array(Image.open(path).convert("RGBA"))


def save_rgba(arr, path):
    Image.fromarray(arr.astype(np.uint8)).save(path)


def lum(c):
    """Rec.601 luminance of an (r,g,b) tuple/array."""
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def detect_scale(arr):
    """Detect the integer upscale factor (art-pixel block size) of a sprite by
    taking the GCD of all horizontal/vertical constant-color run lengths."""
    runs = []
    for line in list(arr) + list(arr.transpose(1, 0, 2)):
        d = np.any(line[1:] != line[:-1], axis=1)
        bounds = np.concatenate(([0], np.flatnonzero(d) + 1, [len(line)]))
        runs += list(np.diff(bounds))
    return max(1, reduce(gcd, runs)) if runs else 1


def detect_visual_block(arr, min_fidelity=0.9, max_scale=8):
    """Estimate the apparent pixel-block size, tolerant of fine detail that defeats
    the exact GCD `detect_scale`. Returns the largest S (>=1) for which the image is
    at least `min_fidelity` an S-block upscale -- used to size the outline so it
    matches chunky art whose blocks aren't perfectly uniform (e.g. detailed rocks).
    For clean upscaled art it equals detect_scale."""
    h, w = arr.shape[:2]
    best = 1
    for s in range(2, max_scale + 1):
        if h < s or w < s:
            break
        rep = arr[s // 2::s, s // 2::s]
        up = np.repeat(np.repeat(rep, s, axis=0), s, axis=1)
        hh, ww = min(up.shape[0], h), min(up.shape[1], w)
        if np.all(up[:hh, :ww] == arr[:hh, :ww], axis=2).mean() >= min_fidelity:
            best = s
    return best


def downscale(arr, s):
    """Sample one pixel per s x s block (block-aligned, uniform-block art)."""
    return arr[s // 2::s, s // 2::s]


def upscale(arr, s):
    return np.repeat(np.repeat(arr, s, axis=0), s, axis=1)


def crop_tight(arr):
    """Crop to the bounding box of non-transparent pixels."""
    ys, xs = np.where(arr[:, :, 3] > 0)
    if len(ys) == 0:
        return arr
    return arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def border_ring(opaque):
    """Boolean mask of opaque pixels that touch a transparent pixel or the edge."""
    pad = np.pad(opaque, 1, constant_values=False)
    t = (~pad[:-2, 1:-1]) | (~pad[2:, 1:-1]) | (~pad[1:-1, :-2]) | (~pad[1:-1, 2:])
    return opaque & t


def demo_sprite(scale=6):
    """A small procedurally-built sample sprite (upscaled) for the startup preview."""
    palette = {".": (0, 0, 0, 0), "r": (200, 30, 30, 255), "d": (150, 18, 18, 255),
               "w": (240, 235, 230, 255), "s": (225, 215, 180, 255)}
    rows = ["..rrrr..",
            ".rwrrwr.",
            "rrrrrrrr",
            "rdrrrrdr",
            "..ssss..",
            "..ssss..",
            "..ssss.."]
    art = np.zeros((len(rows), len(rows[0]), 4), np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            art[y, x] = palette[ch]
    return upscale(art, scale)


def demo_sheet():
    """A tiny sample sheet (three separated blobs) for the startup split preview."""
    a = np.zeros((28, 64, 4), np.uint8)
    for y0, y1, x0, x1, col in [(4, 12, 4, 12, (200, 30, 30)),
                                (4, 12, 26, 34, (40, 160, 60)),
                                (4, 14, 48, 60, (60, 90, 210))]:
        a[y0:y1, x0:x1, :3] = col
        a[y0:y1, x0:x1, 3] = 255
    return a


def debug_sheet(stages, info, cell=200):
    """Render pipeline `stages` [(label, rgba), ...] side by side, each scaled to fit a
    `cell`-px box on a checker background, with `info` printed underneath. For
    diagnosing exactly what each step did to a sprite."""
    from PIL import Image, ImageDraw
    n = len(stages)
    foot = 8 + 14 * (len(info) + 1)
    sheet = Image.new("RGB", (n * (cell + 10) + 10, cell + 40 + foot), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    for i, (label, arr) in enumerate(stages):
        im = Image.fromarray(arr.astype(np.uint8))
        s = min(cell / max(im.size[0], 1), cell / max(im.size[1], 1))
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.NEAREST)
        bg = Image.new("RGBA", (cell, cell), (90, 90, 90, 255))
        bg.alpha_composite(im, ((cell - im.size[0]) // 2, (cell - im.size[1]) // 2))
        x = i * (cell + 10) + 10
        sheet.paste(bg.convert("RGB"), (x, 24))
        draw.text((x, 8), f"{label}  {arr.shape[1]}x{arr.shape[0]}", fill=(235, 235, 235))
    y = cell + 36
    draw.text((10, y), "info:", fill=(255, 220, 120))
    for k, v in info.items():
        y += 14
        draw.text((10, y), f"  {k} = {v}", fill=(210, 210, 210))
    return sheet


def contact_sheet(pairs, names, cols=6, cell=58, pad=120, scale_cap=4):
    """Build a before/after review image. `pairs` = list of (before_arr, after_arr)."""
    from PIL import ImageDraw
    rows = (len(pairs) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * pad, rows * (cell + 14) + 14), (60, 60, 60, 255))
    draw = ImageDraw.Draw(sheet)

    def place(arr, cx, cy):
        im = Image.fromarray(arr.astype(np.uint8))
        s = min(cell / im.size[0], cell / im.size[1], scale_cap)
        w, h = max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))
        im = im.resize((w, h), Image.NEAREST)
        sheet.alpha_composite(im, (cx + (cell - w) // 2, cy + (cell - h) // 2))

    for i, (before, after) in enumerate(pairs):
        r, c = divmod(i, cols)
        x, y = c * pad, r * (cell + 14) + 14
        if before is not None:
            place(before, x + 2, y)
        place(after, x + cell + 4, y)
        draw.text((x + 2, y + cell + 1), names[i][:18], fill=(230, 230, 230, 255))
    return sheet.convert("RGB")
