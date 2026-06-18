"""Functional test for the optional MCP server. Skipped when `mcp` isn't installed
(the server is excluded from the coverage gate as an optional integration)."""
import pytest

pytest.importorskip("mcp")
import mcp_server as m   # noqa: E402
import core              # noqa: E402


def test_outline_tools(tmp_path):
    from conftest import block_sprite
    f = tmp_path / "s.png"
    core.save_rgba(block_sprite(5), f)

    img = m.outline_debug(str(f))
    assert img.data[:8] == b"\x89PNG\r\n\x1a\n"            # a valid PNG

    info = m.outline_info(str(f))
    assert "scale = 5" in info and "iters" in info

    out = tmp_path / "o.png"
    msg = m.outline_apply(str(f), out_path=str(out))
    assert out.exists() and "wrote" in msg


def test_split_preview_tool(tmp_path):
    import numpy as np
    a = np.zeros((20, 40, 4), np.uint8)
    a[2:8, 2:8, :3] = (200, 0, 0); a[2:8, 2:8, 3] = 255
    a[2:8, 30:36, :3] = (0, 200, 0); a[2:8, 30:36, 3] = 255
    sheet = tmp_path / "sheet.png"; core.save_rgba(a, sheet)
    img = m.split_preview(str(sheet))
    assert img.data[:8] == b"\x89PNG\r\n\x1a\n"
