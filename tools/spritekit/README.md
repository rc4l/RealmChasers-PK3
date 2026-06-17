# spritekit

Pixel-art sprite tooling for Realm Chasers. Two capabilities:

- **outline** — strip inconsistent outlines and rebuild a uniform, grid-aligned,
  per-pixel **tinted** outline at the sprite's native art resolution.
- **split** — extract individual sprites from a sheet using transparency + gap
  rules, with optional attachment of small detached fragments to nearby sprites.

Cross-platform: Windows, macOS, Linux (pure Python).

## Install

```
python -m pip install -r tools/spritekit/requirements.txt
```

`numpy`, `Pillow`, `scipy`. The GUI also needs `tkinter`, which ships with most
Python builds — on some Linux distros install it separately
(Debian/Ubuntu: `sudo apt install python3-tk`).

## Launch (double-click)

| OS | File |
|---|---|
| Windows | `start_windows.bat` |
| macOS | `start_macos.command` |
| Linux | `start_linux.sh` |

Double-click it — it finds Python, installs missing dependencies the first time,
and opens the GUI. (macOS/Linux: if it won't run, `chmod +x start_*.command` once,
or right-click → Open the first time to clear Gatekeeper.)

## Usage

Run the folder directly (works from the repo root on any OS):

```
# GUI with live preview + sliders
python tools/spritekit gui

# Normalize outlines on a folder, in place
python tools/spritekit outline sprites/mushroom

# Preview first (writes a before/after contact sheet, changes nothing)
python tools/spritekit outline sprites/mushroom --dry-run --preview review.png

# Darker / thicker / filled corners; write copies instead of in place
python tools/spritekit outline sprites/flower --target-lum 10 --thickness 2 --conn 8 --out out/

# Split a sheet (fragment attachment off by default; --attach-h 24 to enable)
python tools/spritekit split path/to/sheet.png out_dir/ --hgap 6 --vgap 8
```

### outline options
| flag | default | meaning |
|---|---|---|
| `--target-lum` | 16 | outline darkness (0 = black, higher = more visible tint) |
| `--conn` | 4 | 4 = no diagonal corner fill, 8 = filled corners |
| `--thickness` | 1 | outline thickness in **art** pixels. `0.5` / `0.25` draw a thinner sub-pixel outline by enlarging the output image **2× / 4×** (a warning is printed) |
| `--scale` | 0 | upscale factor; 0 = auto-detect per sprite |
| `--recursive` | off | recurse into subfolders |
| `--out DIR` | — | write copies to DIR instead of editing in place |
| `--dry-run` / `--preview P` | — | don't write / also emit a before-after sheet |

### split options
| flag | default | meaning |
|---|---|---|
| `--hgap` / `--vgap` | 6 / 8 | bridge non-transparent pixels within this many px |
| `--attach-h` / `--attach-v` | 0 / 16 | attach small fragments to the nearest larger sprite within this reach (`--attach-h 0` = off) |
| `--fragment-max-dim` | 22 | a piece this small (longer side, px) counts as an attachable fragment |
| `--min-area` | 4 | drop fragments smaller than this (noise) |

Fragment attachment is a general "loose bits belong to the nearby sprite" rule
(off by default). Turn it on (`--attach-h 24`) for sheets where small detached
pieces — a leaf, a spark, a dropped pixel cluster — should merge into the main
sprite they sit beside, regardless of color.

## How outline works

1. **Detect upscale factor** (each art pixel is an N×N block) and downscale to
   native art resolution so the outline is exactly 1 art-pixel and grid-aligned.
2. **Strip** the source art's existing outline — a boundary-connected band that is a
   known palette outline color, or the dominant dark boundary color *only when it is
   largely absent from the interior* (so an authored fill/shading color is never
   mistaken for an outline). Changing **Darkness** therefore only ever affects the
   outline, never authored colors. (Re-applying the tool stacks an outline; the GUI
   preview always works from the original, so it is unaffected.)
3. **Rebuild** a `connectivity`-respecting ring and color each pixel as the
   strongest (highest-chroma) neighboring fill color, **darkened to a fixed
   luminance** so light source colors get a properly dark outline while keeping
   their hue.

## Tests

Full suite with 100% line + branch coverage (pytest + coverage.py):

```
python -m pip install pytest coverage
cd tools/spritekit
python -m coverage run --rcfile=.coveragerc -m pytest tests
python -m coverage report --rcfile=.coveragerc      # fails if coverage < 100%
```

GUI tests use a single shared Tk root and skip automatically where no display is
available (headless CI); every other module is display-independent.

## Layout

```
tools/spritekit/
  __main__.py   entry point (python tools/spritekit ...)
  cli.py        argparse CLI
  gui.py        tkinter GUI
  core.py       shared helpers (scale detect, io, contact sheet)
  outline.py    outline engine (OutlineParams)
  split.py      split engine (SplitParams)
```
