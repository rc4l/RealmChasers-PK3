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

# Debug: dump every outline pipeline stage (+ detected scale/iters/etc.) for a sprite
python tools/spritekit debug sprites/rock/rock_10_w.png --target-lum 16 --thickness 1

```

### outline options
| flag | default | meaning |
|---|---|---|
| `--target-lum` | 16 | outline darkness (0 = black, higher = more visible tint) |
| `--conn` | 4 | 4 = outline protrudes only up/down/left/right — square, blocky pixel-art edges (default); 8 = also fills diagonal corners (rounded) |
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

1. **Detect the pixel scale** (each art pixel is an N×N block) and downscale to
   native art resolution so the outline is grid-aligned. The outline width matches
   the *apparent* block size, so chunky-but-imperfect art (e.g. detailed rocks whose
   blocks aren't perfectly uniform) gets a proportional outline rather than a
   too-thin 1px line.
2. **Strip** any existing outline so a fresh one rebuilds from the base art:
   - known **palette** outline colors (boundary-connected bands), and
   - a **dark-border peel** — flood-remove the connected boundary band that is much
     darker than the sprite body (an outline of any thickness). A fresh sprite's edge
     is about as bright as its body, so nothing is peeled; an already-outlined sprite
     (incl. the tool's own output) is rebuilt — so re-applying and **thickening
     outline the base, never the previous outline**, and changing Darkness only ever
     affects the outline.
3. **Rebuild** the outline as ONE dilation straight from the base (4-conn = a
   cardinal cross, so it protrudes only up/down/left/right — square pixel-art edges,
   never layering onto outline already placed), and color each pixel as the
   strongest (highest-chroma) neighboring fill color, **darkened to a fixed
   luminance** so light source colors get a properly dark outline while keeping
   their hue.

## Debugging

When an outline looks wrong, dump the pipeline instead of guessing. Either click
**Dump debug** in the GUI (writes `_debug/<name>_debug.png` for the loaded sprite +
current settings) or run `spritekit debug <sprite>`. The sheet shows every stage —
input → downscaled art → after palette-strip → after dark-border peel → after
outline → final — plus the detected `scale`, `visual_block`, outline `iters`,
connectivity, and sizes. That makes it obvious e.g. when `scale=1, visual_block=3`
(detailed art) or where a strip/peel removed too much.

## MCP server (drive it from an assistant)

`mcp_server.py` exposes the engine over MCP so an assistant (e.g. Claude Code) can
call it directly and **see** the rendered result, instead of writing throwaway
scripts. Tools: `outline_debug` (returns the labelled pipeline-stage sheet),
`outline_info` (the derived values as text), `outline_apply` (process + save), and
`split_preview` (contact sheet of a split).

```
python -m pip install -r tools/spritekit/requirements-mcp.txt
```

**Claude Code launches it automatically** (stdio) — no GUI, no port, nothing to start.
The repo `.mcp.json` registers it with relative paths so it works on any machine, and
runs it **under jurigged for hot reload** (see below) so engine edits go live with no
`/mcp` reconnect:

```json
{ "mcpServers": { "spritekit": { "command": "python",
    "args": ["-m", "jurigged", "-w", "tools/spritekit", "tools/spritekit/mcp_server.py"] } } }
```

So: open Claude Code in this repo → approve / `/mcp` the `spritekit` server → ask it to
"debug the rock outline" and one `outline_debug` call returns the stages as an image.

Driving spritekit from a session rooted in a **sibling** repo (e.g. the game project
next to this one)? Point that project's `.mcp.json` at the sibling path (and watch it):
`"args": ["-m", "jurigged", "-w", "../RealmChasers-PK3/tools/spritekit", "../RealmChasers-PK3/tools/spritekit/mcp_server.py"]`.

## Hot reload (on by default)

The launchers and the MCP server run under **jurigged**, which live-patches the
running process on save — so edits to `core` / `outline` / `split` take effect in place
with **no restart** (and no `/mcp` reconnect for the server). It's in `requirements.txt`;
zero code changes, stdout-clean (safe for the stdio MCP).

- **GUI** (`start_*` launchers): the window stays open; after editing, nudge a slider to
  re-render with the new code.
- **MCP server**: an assistant's edits to the engine are live on the next tool call.

(`gui.py`'s *structure* — new widgets — still needs a restart; jurigged patches
function bodies, which is where the engine logic lives. For full auto-restart-on-save
instead, `watchfiles`/`tkreload` work but drop window state.)

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
