"""MCP server exposing spritekit's outline/split engine as tools that return rendered
images. Lets an assistant drive the tool directly -- call outline_debug(...) and SEE
every pipeline stage in the result, tune params, apply -- instead of round-tripping
through ad-hoc scripts and screenshots.

Run (Claude Code launches this via .mcp.json):  python tools/spritekit/mcp_server.py
"""
import os
import socket
import sys
import threading
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MCP_HOST = "127.0.0.1"
MCP_PORT = int(os.environ.get("SPRITEKIT_MCP_PORT", "8765"))

import core                       # noqa: E402
import outline as outline_mod     # noqa: E402
import split as split_mod         # noqa: E402
from mcp.server.fastmcp import FastMCP, Image   # noqa: E402

mcp = FastMCP("spritekit")


def _png(pil_image) -> bytes:
    buf = BytesIO()
    pil_image.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _params(target_lum, connectivity, thickness, scale):
    return outline_mod.OutlineParams(
        target_lum=target_lum, connectivity=connectivity, thickness=thickness, scale=scale)


@mcp.tool()
def outline_debug(sprite_path: str, target_lum: int = 16, connectivity: int = 4,
                  thickness: float = 1.0, scale: int = 0) -> Image:
    """Render every stage of the outline pipeline for a sprite PNG (input ->
    downscaled art -> palette strip -> dark-border peel -> outline -> final) with the
    detected scale/visual_block/iters/etc. labelled. The single best way to see what
    the outline did and why. connectivity 4 = sharp corners (sealed diagonals),
    8 = rounded. scale 0 = auto-detect."""
    _, stages, info = outline_mod.run_pipeline(
        core.load_rgba(sprite_path), _params(target_lum, connectivity, thickness, scale))
    return Image(data=_png(core.debug_sheet(stages, info, cell=150)), format="png")


@mcp.tool()
def outline_info(sprite_path: str, target_lum: int = 16, connectivity: int = 4,
                 thickness: float = 1.0, scale: int = 0) -> str:
    """Return the outline pipeline's derived values for a sprite as text (detected
    scale, visual_block, outline iters, sizes, etc.) -- no image."""
    _, _, info = outline_mod.run_pipeline(
        core.load_rgba(sprite_path), _params(target_lum, connectivity, thickness, scale))
    return "\n".join(f"{k} = {v}" for k, v in info.items())


@mcp.tool()
def outline_apply(sprite_path: str, target_lum: int = 16, connectivity: int = 4,
                  thickness: float = 1.0, scale: int = 0, out_path: str = "") -> str:
    """Process a sprite and SAVE the outlined result (overwrites in place unless
    out_path is given). Returns the output path and size."""
    out = outline_mod.process_array(
        core.load_rgba(sprite_path), _params(target_lum, connectivity, thickness, scale))
    dest = out_path or sprite_path
    core.save_rgba(out, dest)
    return f"wrote {dest}  size={out.shape[1]}x{out.shape[0]}"


@mcp.tool()
def split_preview(sheet_path: str, hgap: int = 6, vgap: int = 8,
                  attach_h: int = 0, attach_v: int = 16, fragment_max_dim: int = 22) -> Image:
    """Split a sprite sheet (no files written) and return a contact sheet of the
    extracted sprites for review. attach_h > 0 merges small detached fragments into
    the nearest larger sprite."""
    params = split_mod.SplitParams(hgap=hgap, vgap=vgap, attach_h=attach_h,
                                   attach_v=attach_v, fragment_max_dim=fragment_max_dim)
    count, results = split_mod.split_sheet(sheet_path, ".", params, dry_run=True)
    pairs = [(None, crop) for crop, _ in results]
    names = [str(i + 1) for i in range(len(results))]
    sheet = core.contact_sheet(pairs, names, cols=12, cell=46, pad=52)
    return Image(data=_png(sheet), format="png")


_thread = None


def _port_free(host, port):
    s = socket.socket()
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def serve_in_thread(host=MCP_HOST, port=MCP_PORT):
    """Start the HTTP MCP server in a daemon thread, once. No-op if it's already
    running here or the port is taken by another spritekit instance. Best-effort:
    used to auto-start the server when the GUI launches."""
    global _thread
    if _thread is not None or not _port_free(host, port):
        return _thread
    mcp.settings.host = host
    mcp.settings.port = port
    _thread = threading.Thread(
        target=lambda: mcp.run(transport="streamable-http"), daemon=True, name="spritekit-mcp")
    _thread.start()
    return _thread


if __name__ == "__main__":
    # stdio when launched directly (e.g. via .mcp.json command), else serve HTTP.
    mcp.run()
