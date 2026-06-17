"""Command-line interface for spritekit. Cross-platform (uses pathlib)."""
import argparse
import sys
from pathlib import Path

from core import load_rgba, save_rgba, contact_sheet
import outline as outline_mod
import split as split_mod


def _iter_pngs(path, recursive):
    path = Path(path)
    if path.is_file():
        return [path]
    pattern = "**/*.png" if recursive else "*.png"
    return sorted(path.glob(pattern))


def cmd_outline(args):
    params = outline_mod.OutlineParams(
        target_lum=args.target_lum, connectivity=args.conn,
        thickness=args.thickness, scale=args.scale)
    files = _iter_pngs(args.path, args.recursive)
    if not files:
        print(f"no .png files found at {args.path}")
        return 1
    growth = outline_mod.image_growth(args.thickness)
    if growth > 1:
        print(f"NOTE: thickness {args.thickness} is sub-art-pixel; output images "
              f"will be {growth}x larger.")
    pairs, names = [], []
    for f in files:
        before = load_rgba(f)
        after = outline_mod.process_array(before, params)
        names.append(f.name)
        pairs.append((before, after))
        if not args.dry_run:
            dest = f if args.out is None else Path(args.out) / f.name
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            save_rgba(after, dest)
    if args.dry_run or args.preview:
        sheet_path = Path(args.preview or "spritekit_preview.png")
        contact_sheet(pairs, names).save(sheet_path)
        print(f"preview written to {sheet_path}")
    action = "previewed" if args.dry_run else "processed"
    print(f"{action} {len(files)} sprite(s)")
    return 0


def cmd_split(args):
    params = split_mod.SplitParams(
        hgap=args.hgap, vgap=args.vgap, attach_h=args.attach_h, attach_v=args.attach_v,
        fragment_max_dim=args.fragment_max_dim, min_area=args.min_area)
    count, results = split_mod.split_sheet(
        args.sheet, args.out_dir, params, prefix=args.prefix, dry_run=args.dry_run)
    if args.dry_run or args.preview:
        pairs = [(None, crop) for crop, _ in results]
        names = [f"{args.prefix}_{i+1:03d}" for i in range(len(results))]
        sheet_path = Path(args.preview or "spritekit_split_preview.png")
        contact_sheet(pairs, names).save(sheet_path)
        print(f"preview written to {sheet_path}")
    action = "would extract" if args.dry_run else "extracted"
    print(f"{action} {count} sprite(s) from {args.sheet}")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="spritekit", description="Pixel-art sprite tooling")
    sub = ap.add_subparsers(dest="command", required=True)

    o = sub.add_parser("outline", help="normalize/tint outlines on sprite PNGs")
    o.add_argument("path", help="a PNG file or a folder of PNGs")
    o.add_argument("--target-lum", type=int, default=16, help="outline darkness (0=black)")
    o.add_argument("--conn", type=int, choices=(4, 8), default=4, help="4=no diagonal fill")
    o.add_argument("--thickness", type=float, default=1.0,
                   help="outline thickness in art pixels (0.25/0.5 enlarge the image)")
    o.add_argument("--scale", type=int, default=0, help="upscale factor (0=auto-detect)")
    o.add_argument("--recursive", action="store_true", help="recurse into subfolders")
    o.add_argument("--out", default=None, help="write copies here instead of in place")
    o.add_argument("--dry-run", action="store_true", help="don't write; make a preview")
    o.add_argument("--preview", default=None, help="also write a before/after sheet here")
    o.set_defaults(func=cmd_outline)

    s = sub.add_parser("split", help="split a sprite sheet into individual PNGs")
    s.add_argument("sheet", help="path to the sprite sheet PNG")
    s.add_argument("out_dir", help="output folder for the sprites")
    s.add_argument("--prefix", default="sprite", help="output filename prefix")
    s.add_argument("--hgap", type=int, default=6, help="bridge pixels within this many px horizontally")
    s.add_argument("--vgap", type=int, default=8, help="bridge pixels within this many px vertically")
    s.add_argument("--attach-h", type=int, default=0,
                   help="attach small fragments to nearest larger sprite within this px (0=off)")
    s.add_argument("--attach-v", type=int, default=16, help="vertical reach for fragment attachment")
    s.add_argument("--fragment-max-dim", type=int, default=22,
                   help="a piece this small (longer side, px) counts as an attachable fragment")
    s.add_argument("--min-area", type=int, default=4, help="drop fragments smaller than this (noise)")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--preview", default=None, help="write a contact sheet here")
    s.set_defaults(func=cmd_split)

    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
