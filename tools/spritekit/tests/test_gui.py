"""GUI tests. A single Tk root is shared across the module (creating/destroying
many Tk roots in one process is flaky). Skipped entirely with no display."""
import numpy as np
import pytest

import core
from conftest import block_sprite

gui = pytest.importorskip("gui")
import tkinter as tk
from tkinter import ttk


@pytest.fixture(scope="module")
def app():
    try:
        a = gui.App()
    except tk.TclError:  # pragma: no cover - headless without a display
        pytest.skip("no display for tkinter")
    a.withdraw()
    yield a
    a.destroy()


@pytest.fixture(autouse=True)
def reset(app):
    app.files = []; app.cur = None; app.cur_path = None; app.sheet_path = None
    app.target_lum.set(16); app.conn.set(4); app.thick_idx.set(2)
    app._folder_mode = False
    app._clear_gallery()
    yield


@pytest.fixture
def folder(tmp_path):
    for i in range(20):
        core.save_rgba(block_sprite(2), tmp_path / f"s{i:02d}.png")
    return tmp_path


def drain(app):
    while app._pending:
        app._render_next()


@pytest.fixture
def png(tmp_path):
    p = tmp_path / "m.png"
    core.save_rgba(block_sprite(5), p)
    return p


@pytest.fixture
def sheet_png(tmp_path):
    a = np.zeros((20, 40, 4), np.uint8)
    a[2:8, 2:8, :3] = (200, 0, 0); a[2:8, 2:8, 3] = 255
    a[2:8, 30:36, :3] = (0, 200, 0); a[2:8, 30:36, 3] = 255
    p = tmp_path / "s.png"; core.save_rgba(a, p)
    return p


def find(widget, cls):
    out = []
    for c in widget.winfo_children():
        if isinstance(c, cls):
            out.append(c)
        out += find(c, cls)
    return out


def test_load_sample(app):
    app._load_sample()
    assert app.cur is not None and app.sheet_path is not None


def test_tooltip_lifecycle(app):
    tip = gui.ToolTip(ttk.Label(app, text="x"), "hello")
    tip._show(); tip._show()        # second call: already shown -> early return
    assert tip.tip is not None
    tip._hide()
    assert tip.tip is None
    tip._hide()                     # hide when nothing shown -> no-op
    empty = gui.ToolTip(ttk.Label(app), "")
    empty._show()                   # no text -> early return
    tip._schedule(); tip._cancel()  # schedule then cancel


def test_open_file_and_cancel(app, png, monkeypatch):
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(png))
    app._open_file()
    assert app.cur is not None
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: "")
    app._open_file()                # cancel branch: no change


def test_open_folder_empty_populated_cancel(app, tmp_path, png, monkeypatch):
    seen = {}
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: seen.setdefault("info", a))
    empty = tmp_path / "empty"; empty.mkdir()
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: str(empty))
    app._open_folder()
    assert "info" in seen            # "no PNGs" branch
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: str(png.parent))
    app._open_folder()
    assert app.files                 # populated branch
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: "")
    app._open_folder()               # cancel branch


def test_refresh_without_image(app):
    assert app.cur is None
    app._refresh()                   # early-return branch (no image loaded)


def test_sliders_and_radios_fire(app, png, sheet_png, monkeypatch):
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(png))
    app._open_file()
    app.sheet_path = sheet_png
    app._split_preview()
    for s in find(app, ttk.Scale):
        lo, hi = float(s.cget("from")), float(s.cget("to"))
        s.set(hi if float(s.get()) != hi else lo)   # change value -> fires slider command
    for r in find(app, ttk.Radiobutton):
        r.invoke()


def test_thickness_slider_reaches_4(app):
    assert gui.THICKNESS_STOPS[-1] == 4.0                         # slider goes up to 4 px
    app.thick_idx.set(len(gui.THICKNESS_STOPS) - 1); app._on_thickness()
    assert app._params().thickness == 4.0


def test_preview_box_independent_of_content():
    # the viewport is a pure function of the preview pane size -- no image input at all,
    # so it can't shift with thickness or feed image height back into itself (no growth)
    assert gui._preview_box(1000, 720) == (480, 500)
    assert gui._preview_box(1, 1) == (380, 240)            # floors hold pre-layout
    big = gui._preview_box(1000, 5000)
    assert gui._preview_box(1000, 5000) == big             # deterministic, content-free


def test_preview_scales_match_sprite():
    box = (400, 400)
    sb, sa = gui._preview_scales((60, 60), box, 2)    # sub-pixel: after upscaled 2x...
    assert sa >= 1 and sb == sa * 2                    # ...so render before 2x to match sprite
    sb1, sa1 = gui._preview_scales((60, 60), box, 1)   # normal thickness -> identical scale
    assert sb1 == sa1


def test_fit_scale_never_crops():
    assert gui._fit_scale(50, 50, (400, 300)) >= 1.0        # room to enlarge -> integer
    assert gui._fit_scale(600, 200, (400, 300)) < 1.0       # too big -> shrink to fit
    for w, h in [(600, 200), (100, 500), (50, 50), (380, 240)]:
        s = gui._fit_scale(w, h, (400, 300))
        nw = w * int(s) if s >= 1 else int(w * s)
        nh = h * int(s) if s >= 1 else int(h * s)
        assert 1 <= nw <= 400 and 1 <= nh <= 300            # always within the box


def test_preview_large_sprite_not_cropped(app, tmp_path, monkeypatch):
    # a sprite larger than the box must downscale to FIT (not get cropped at 1x)
    big = np.zeros((300, 560, 4), np.uint8)
    big[10:290, 10:550, :3] = (180, 60, 60); big[10:290, 10:550, 3] = 255
    p = tmp_path / "big.png"; core.save_rgba(big, p)
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(p))
    app._open_file()
    pa = app._photos[1]
    box = gui._preview_box(app.o_preview.winfo_width(), app.o_preview.winfo_height())
    assert (pa.width(), pa.height()) == tuple(box)          # fills the fixed viewport, fit not cropped


def test_hot_reload_rebuild_preserves_state(app, folder, sheet_png, monkeypatch):
    # a reload rebuilds the widget tree in place (so __init__/structure edits go live)
    # while keeping the loaded sprite, the open sheet, the gallery and slider values.
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: str(folder))
    app._open_folder(); drain(app)                                 # folder mode + gallery
    app.sheet_path = sheet_png                                     # and a split sheet open
    app.target_lum.set(9); app.conn.set(8); app.thick_idx.set(4)
    path = app.cur_path; nb_old = app.nb
    app._reload_pending = "refresh"; app._apply_pending_reload()   # engine edit -> just re-render
    assert app._reload_pending is None
    app._apply_pending_reload()                                    # nothing pending -> no-op
    app._reload_pending = "rebuild"; app._apply_pending_reload()   # gui edit -> full rebuild
    drain(app)
    assert app.nb is not nb_old                                    # widget tree actually rebuilt
    assert app.cur_path == path                                    # sprite preserved
    assert app._folder_mode and app.gallery.winfo_children()      # gallery rebuilt
    assert app.sheet_path == sheet_png                            # open sheet preserved
    assert (app.target_lum.get(), app.conn.get(), app.thick_idx.get()) == (9, 8, 4)
    # rebuild as a single file with no sheet open -> the no-sheet / no-gallery branches
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(folder / "s00.png"))
    app._open_file(); app.sheet_path = None
    app._rebuild()
    assert not app._folder_mode


def test_preview_refits_on_resize(app, png, monkeypatch):
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(png))
    app._open_file()
    app._last_box = None; app._resize_after = None
    app._on_preview_resize()                     # first event -> schedules a re-fit
    assert app._resize_after is not None and app._last_box is not None
    app._on_preview_resize()                     # same box -> ignored (no thrash)
    app._last_box = (1, 1)
    app._on_preview_resize()                     # box changed -> cancels pending, reschedules
    assert app._resize_after is not None
    app.after_cancel(app._resize_after); app._resize_after = None


def test_preview_viewport_fixed_across_thickness(app, png, monkeypatch):
    # the before/after preview must NOT resize when thickness changes (no layout shift)
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(png))
    app._open_file()
    app.thick_idx.set(2); app._on_thickness()                            # 1 px
    b1, a1 = app._photos
    sz = (a1.width(), a1.height())
    app.thick_idx.set(len(gui.THICKNESS_STOPS) - 1); app._on_thickness()  # 4 px -> larger output
    b2, a2 = app._photos
    assert (a2.width(), a2.height()) == sz                               # after viewport unchanged
    assert (b1.width(), b1.height()) == sz == (b2.width(), b2.height())  # and matches before


def test_thickness_warning_toggles(app, png, monkeypatch):
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(png))
    app._open_file()
    app.thick_idx.set(0); app._on_thickness()      # 0.25 -> warning shown
    assert app.thick_warn.cget("text")
    app.thick_idx.set(2); app._on_thickness()      # 1.0 -> no warning
    assert app.thick_warn.cget("text") == ""


def test_apply_outline_file_folder_and_none(app, png, monkeypatch):
    msgs = []
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: msgs.append(a))
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(png))
    app._open_file()
    app._apply_outline(False)
    app._apply_outline(True)
    app.files = []
    app._apply_outline(True)                       # no-files branch -> info
    assert msgs


def test_split_open_preview_export(app, sheet_png, tmp_path, monkeypatch):
    msgs = []
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: msgs.append(a))
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(sheet_png))
    app._open_sheet()
    assert app.sheet_path is not None
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: "")
    app._open_sheet()                              # cancel branch
    out = tmp_path / "out"
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: str(out))
    app._export_split()
    assert list(out.glob("sprite_*.png"))
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: "")
    app._export_split()                            # cancel branch
    app.sheet_path = None
    app._export_split()                            # no-sheet branch -> info
    app._split_preview()                           # no-sheet early return
    assert msgs


def test_gallery_builds_chunks_and_click(app, folder, monkeypatch):
    import types
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: str(folder))
    app._open_folder()
    assert app._folder_mode and len(app.files) == 20
    drain(app)                                   # finish chunked rendering (20 > GALLERY_CHUNK)
    cells = app.gallery.winfo_children()
    assert len(cells) == 20 and len(app._gallery_photos) == 20
    app._on_thumb_click(types.SimpleNamespace(widget=cells[3]))   # click loads that sprite
    assert app.cur_path == cells[3].sprite_path


def test_gallery_cap(app, folder, monkeypatch):
    monkeypatch.setattr(gui, "GALLERY_MAX", 5)
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: str(folder))
    app._open_folder()
    drain(app)
    assert len(app.gallery.winfo_children()) == 5
    assert "showing first 5" in app.gallery_label.cget("text")


def test_gallery_debounce_cancels_pending(app, folder, monkeypatch):
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: str(folder))
    app._open_folder(); drain(app)
    app._schedule_gallery()                      # schedules a rebuild
    assert app._gallery_after is not None
    app._schedule_gallery()                      # cancels the pending one, schedules anew
    assert app._gallery_after is not None
    app.after_cancel(app._gallery_after); app._gallery_after = None


def test_single_file_clears_gallery(app, folder, png, monkeypatch):
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **k: str(folder))
    app._open_folder(); drain(app)
    assert app.gallery.winfo_children()
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(png))
    app._open_file()                             # switching to a single file clears the gallery
    assert not app._folder_mode and not app.gallery.winfo_children()
    app._schedule_gallery()                      # no-op when not in folder mode


def test_dump_debug(app, png, tmp_path, monkeypatch):
    msgs = []
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a, **k: msgs.append(a))
    app._dump_debug()                                # no image loaded -> info message
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **k: str(png))
    app._open_file()
    monkeypatch.chdir(tmp_path)
    app._dump_debug()                                # writes _debug/<name>_debug.png
    assert (tmp_path / "_debug" / "m_debug.png").exists()
    assert msgs


def test_launch_runs_mainloop(monkeypatch):
    ran = {}

    class FakeApp:
        def mainloop(self):
            ran["mainloop"] = True

    monkeypatch.setattr(gui, "App", FakeApp)       # avoid a second real Tk root
    gui.launch()
    assert ran["mainloop"]
