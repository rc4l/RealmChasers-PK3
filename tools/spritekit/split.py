"""Transparency-aware sprite-sheet splitting.

Groups non-transparent pixels into sprites using horizontal/vertical gap
tolerances (bridging small gaps), optionally attaches small detached fragments to
the nearest larger sprite, then writes each sprite masked to its own pixels."""
from dataclasses import dataclass
from collections import defaultdict
import numpy as np
from scipy import ndimage

from core import load_rgba, save_rgba


@dataclass
class SplitParams:
    hgap: int = 6              # bridge non-transparent pixels within this many px horizontally
    vgap: int = 8             # ... and vertically (covers diagonal offsets too)
    min_area: int = 4         # drop fragments smaller than this (noise)
    row_tol: int = 24         # vertical banding tolerance for output ordering
    # Fragment attachment: a small detached piece (bounding box <= fragment_max_dim
    # on its longer side) is merged into the nearest LARGER sprite within reach,
    # chaining through other fragments. Set attach_h = 0 to disable.
    attach_h: int = 0
    attach_v: int = 16
    fragment_max_dim: int = 22


def _gap(a, b):
    gx = max(0, max(a['x0'], b['x0']) - min(a['x1'], b['x1']))
    gy = max(0, max(a['y0'], b['y0']) - min(a['y1'], b['y1']))
    return gx, gy


def _components(arr, p):
    mask = arr[:, :, 3] > 0
    hx, vy = (p.hgap + 1) // 2, (p.vgap + 1) // 2
    struct = np.ones((2 * vy + 1, 2 * hx + 1), bool)
    dilated = ndimage.binary_dilation(mask, structure=struct)
    labels, _ = ndimage.label(dilated, structure=np.ones((3, 3), int))

    info = {}
    for i, sl in enumerate(ndimage.find_objects(labels), start=1):
        if sl is None:   # pragma: no cover - defensive; labels are contiguous
            continue
        ys, xs = sl
        sub = (labels[ys, xs] == i) & mask[ys, xs]
        a = int(sub.sum())
        if a < p.min_area:
            continue
        rows, colsm = np.any(sub, 1), np.any(sub, 0)
        y0 = ys.start + int(np.argmax(rows)); y1 = ys.start + len(rows) - int(np.argmax(rows[::-1]))
        x0 = xs.start + int(np.argmax(colsm)); x1 = xs.start + len(colsm) - int(np.argmax(colsm[::-1]))
        info[i] = dict(y0=y0, y1=y1, x0=x0, x1=x1, area=a)
    return labels, info


def _group(info, p):
    """Return owner[label] = group-anchor label, attaching small fragments to the
    nearest larger sprite within reach (chaining through other fragments)."""
    if p.attach_h <= 0:
        return {i: i for i in info}
    fragments = {i for i in info
                 if max(info[i]['x1'] - info[i]['x0'],
                        info[i]['y1'] - info[i]['y0']) <= p.fragment_max_dim}
    owner = {i: i for i in info if i not in fragments}   # larger sprites are anchors
    remaining = set(fragments)
    while True:
        progressed = False
        for gid in list(remaining):
            best, best_d = None, None
            for oid, aid in owner.items():
                gx, gy = _gap(info[gid], info[oid])
                if gx <= p.attach_h and gy <= p.attach_v:
                    d = gx + gy
                    if best_d is None or d < best_d:
                        best_d, best = d, aid
            if best is not None:
                owner[gid] = best
                remaining.discard(gid)
                progressed = True
        if not progressed:
            break
    for gid in remaining:
        owner[gid] = gid
    return owner


def split_sheet(sheet_path, out_dir, params=None, prefix="sprite", dry_run=False):
    """Split a sheet into individual PNGs. Returns (count, list of (box, members))."""
    from pathlib import Path
    p = params or SplitParams()
    arr = load_rgba(sheet_path)
    labels, info = _components(arr, p)
    owner = _group(info, p)

    groups = defaultdict(list)
    for cid, aid in owner.items():
        groups[aid].append(cid)

    comps = []
    for aid, members in groups.items():
        y0 = min(info[m]['y0'] for m in members); y1 = max(info[m]['y1'] for m in members)
        x0 = min(info[m]['x0'] for m in members); x1 = max(info[m]['x1'] for m in members)
        comps.append((y0, y1, x0, x1, members))

    # order top-to-bottom in bands, then left-to-right
    comps.sort(key=lambda c: c[0])
    ordered, band, band_y = [], [], None
    for c in comps:
        if band_y is None or c[0] - band_y <= p.row_tol:
            band.append(c); band_y = c[0] if band_y is None else band_y
        else:
            band.sort(key=lambda c: c[2]); ordered += band; band = [c]; band_y = c[0]
    band.sort(key=lambda c: c[2]); ordered += band

    out_dir = Path(out_dir)
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for idx, (y0, y1, x0, x1, members) in enumerate(ordered, start=1):
        crop = arr[y0:y1, x0:x1].copy()
        keep = np.isin(labels[y0:y1, x0:x1], list(members))   # mask out neighbor pixels
        crop[~keep, 3] = 0
        results.append((crop, (x0, y0, x1, y1)))
        if not dry_run:
            save_rgba(crop, out_dir / f"{prefix}_{idx:03d}.png")
    return len(ordered), results
