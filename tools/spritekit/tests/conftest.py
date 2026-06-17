"""Test fixtures for spritekit. Adds the package dir to sys.path so the flat
modules import the same way they do at runtime."""
import sys
from pathlib import Path

import numpy as np

PKG_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG_DIR))


def solid(w, h, color=(200, 30, 30, 255)):
    """A fully opaque w x h sprite of one color."""
    a = np.zeros((h, w, 4), np.uint8)
    a[:, :] = color
    return a


def block_sprite(scale=5):
    """A small art sprite upscaled by `scale` (so detect_scale returns `scale`).
    Cap region of one color over a stem of another, on transparency."""
    art = np.zeros((4, 4, 4), np.uint8)
    art[0:2, 0:4] = (200, 30, 30, 255)     # red cap
    art[2:4, 1:3] = (230, 230, 210, 255)   # pale stem
    return np.repeat(np.repeat(art, scale, 0), scale, 1)


def with_outline(arr, color):
    """Add a 1px hard border of `color` around the opaque silhouette (art res)."""
    from scipy import ndimage
    a = np.pad(arr, ((1, 1), (1, 1), (0, 0)))
    sil = a[:, :, 3] > 0
    ring = ndimage.binary_dilation(sil, np.ones((3, 3), int)) & ~sil
    a[ring, :3] = color
    a[ring, 3] = 255
    return a
