"""Minimal cross-platform GUI for spritekit (tkinter + Pillow).

Outline mode: load a PNG or folder, tweak darkness / connectivity / thickness with
a live before/after preview, then apply in place or to a copy folder.
Split mode: load a sheet, tweak gaps, preview the contact sheet, then export.

Every slider shows its current value and every control has a hover tooltip."""
import tempfile
from pathlib import Path
import numpy as np

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from PIL import Image, ImageTk
except Exception as e:  # pragma: no cover - only when tkinter/Pillow unavailable
    raise SystemExit(
        "GUI needs tkinter and Pillow. On Debian/Ubuntu: 'sudo apt install python3-tk'.\n"
        f"Import error: {e}")

from core import load_rgba, save_rgba, contact_sheet, debug_sheet, demo_sprite, demo_sheet
import outline as outline_mod
import split as split_mod

CHECK = (90, 90, 90, 255)
ACCENT = "#1a66cc"
THICKNESS_STOPS = [0.25, 0.5, 1.0, 2.0, 3.0]   # discrete outline-thickness slider stops
GALLERY_CELL = 70        # thumbnail cell size (px)
GALLERY_CHUNK = 12       # thumbnails rendered per UI tick (keeps the UI responsive)
GALLERY_DEBOUNCE = 200   # ms to wait after a settings change before rebuilding
GALLERY_MAX = 600        # cap on thumbnails rendered (avoids pathological folders)


class ToolTip:
    """Lightweight hover tooltip for any tk widget."""
    def __init__(self, widget, text):
        self.widget, self.text, self.tip, self._after = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._after = self.widget.after(450, self._show)

    def _cancel(self):
        if self._after:
            self.widget.after_cancel(self._after)
            self._after = None

    def _show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, justify="left", background="#fffbe6",
                 relief="solid", borderwidth=1, wraplength=250, padx=7, pady=5,
                 font=("TkDefaultFont", 8)).pack()

    def _hide(self, _=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


def labeled_slider(parent, label, var, lo, hi, tip, on_change, unit="", fmt=None, hint=None):
    """A slider row with a live value readout on the right and a tooltip. `var` is an
    integer-snapping IntVar; `fmt(value)->str` customizes the readout (e.g. discrete
    thickness stops); `hint` overrides the small range caption underneath."""
    show = fmt or (lambda v: f"{v}{unit}")
    frame = ttk.Frame(parent)
    frame.pack(fill="x", pady=(10, 0))
    head = ttk.Frame(frame)
    head.pack(fill="x")
    name = ttk.Label(head, text=label)
    name.pack(side="left")
    value = ttk.Label(head, text=show(var.get()), foreground=ACCENT,
                      font=("TkDefaultFont", 9, "bold"))
    value.pack(side="right")

    def handle(*_):
        var.set(int(float(var.get())))
        value.config(text=show(var.get()))
        on_change()

    scale = ttk.Scale(frame, from_=lo, to=hi, variable=var, command=handle)
    scale.pack(fill="x")
    ttk.Label(frame, text=hint if hint is not None else f"{lo}–{hi}", foreground="#888",
              font=("TkDefaultFont", 7)).pack(anchor="e")
    for w in (name, value, scale):
        ToolTip(w, tip)
    return scale


def _to_photo(arr, box, bg=CHECK):
    im = Image.fromarray(arr.astype(np.uint8))
    s = max(1, min(box[0] // max(im.size[0], 1), box[1] // max(im.size[1], 1)))
    im = im.resize((im.size[0] * s, im.size[1] * s), Image.NEAREST)
    canvas = Image.new("RGBA", im.size, bg)
    canvas.alpha_composite(im)
    return ImageTk.PhotoImage(canvas.convert("RGBA"))


def _to_photo_fit(arr, cell, bg=CHECK):
    """Thumbnail that fits within a `cell`x`cell` box (scales up or down)."""
    im = Image.fromarray(arr.astype(np.uint8))
    s = min(cell / max(im.size[0], 1), cell / max(im.size[1], 1))
    w, h = max(1, round(im.size[0] * s)), max(1, round(im.size[1] * s))
    im = im.resize((w, h), Image.NEAREST)
    canvas = Image.new("RGBA", im.size, bg)
    canvas.alpha_composite(im)
    return ImageTk.PhotoImage(canvas.convert("RGBA"))


TIPS = {
    "lum": "How dark the outline is. 0 = pure black; higher keeps more of the\n"
           "tint. Each outline pixel is a darkened shade of the fill color it borders.",
    "conn": "Both seal sloped edges into a solid outline. Sharp (4-conn) keeps 90-degree\n"
            "corners crisp (default). Rounded (8-conn) also fills the corner pixel for a\n"
            "softer, rounded look.",
    "thick": "Outline thickness in ART pixels (auto-scaled to the sprite's upscale\n"
             "factor). 1 = one art pixel. 0.5 / 0.25 draw a thinner sub-pixel outline\n"
             "by enlarging the image (2x / 4x) so the thin line can be drawn crisply.",
    "hgap": "Two non-transparent pixels within this many pixels HORIZONTALLY are\n"
            "treated as one sprite. Higher merges pieces sitting side by side.",
    "vgap": "Two non-transparent pixels within this many pixels VERTICALLY are\n"
            "treated as one sprite. Higher merges stacked pieces.",
    "ath": "Attach small detached fragments to the nearest LARGER sprite within\n"
           "this horizontal distance (e.g. a stray bit that belongs to a sprite).\n"
           "0 = off.",
    "atv": "Vertical reach for fragment attachment (see 'Attach fragments H').",
    "frag": "A piece whose longer side is at most this many pixels counts as an\n"
            "attachable 'fragment'. Larger pieces are always kept as their own sprite.",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("spritekit")
        self.geometry("1000x640")
        self.files = []
        self.cur = None
        self.cur_path = None
        self._photos = []

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.outline_tab = ttk.Frame(nb); nb.add(self.outline_tab, text="Outline")
        self.split_tab = ttk.Frame(nb); nb.add(self.split_tab, text="Split sheet")
        self._build_outline(self.outline_tab)
        self._build_split(self.split_tab)
        self._load_sample()

    def _load_sample(self):
        """Populate both tabs with a built-in sample so startup isn't blank."""
        self.files = []
        self._folder_mode = False
        self._clear_gallery()
        self.cur = demo_sprite()
        self.cur_path = None
        self.o_status.config(text="sample sprite — open a file or folder to replace")
        self._refresh()
        sample_sheet = Path(tempfile.gettempdir()) / "spritekit_sample_sheet.png"
        save_rgba(demo_sheet(), sample_sheet)
        self.sheet_path = sample_sheet
        self._split_preview()

    # ---------------- Outline tab ----------------
    def _build_outline(self, root):
        side = ttk.Frame(root, padding=12); side.pack(side="left", fill="y")
        self.o_preview = ttk.Frame(root, padding=10); self.o_preview.pack(side="right", fill="both", expand=True)

        b1 = ttk.Button(side, text="Open PNG…", command=self._open_file); b1.pack(fill="x")
        b2 = ttk.Button(side, text="Open folder…", command=self._open_folder); b2.pack(fill="x", pady=(4, 8))
        ToolTip(b1, "Load a single sprite PNG to preview and edit.")
        ToolTip(b2, "Load every PNG in a folder; preview one, apply to all.")
        self.o_status = ttk.Label(side, text="No file loaded.", wraplength=190, foreground="#555")
        self.o_status.pack(fill="x")

        self.target_lum = tk.IntVar(value=16)
        self.conn = tk.IntVar(value=4)
        labeled_slider(side, "Darkness", self.target_lum, 0, 80, TIPS["lum"], self._refresh)

        cf = ttk.Frame(side); cf.pack(fill="x", pady=(12, 0))
        clab = ttk.Label(cf, text="Corners"); clab.pack(anchor="w")
        row = ttk.Frame(cf); row.pack(anchor="w")
        r1 = ttk.Radiobutton(row, text="Sharp (4-conn)", variable=self.conn, value=4, command=self._refresh)
        r2 = ttk.Radiobutton(row, text="Rounded (8-conn)", variable=self.conn, value=8, command=self._refresh)
        r1.pack(side="left"); r2.pack(side="left")
        for w in (clab, r1, r2):
            ToolTip(w, TIPS["conn"])

        self.thick_idx = tk.IntVar(value=THICKNESS_STOPS.index(1.0))
        labeled_slider(side, "Thickness (art px)", self.thick_idx, 0, len(THICKNESS_STOPS) - 1,
                       TIPS["thick"], self._on_thickness,
                       fmt=lambda i: f"{THICKNESS_STOPS[i]:g} px",
                       hint=" · ".join(f"{t:g}" for t in THICKNESS_STOPS))
        self.thick_warn = ttk.Label(side, text="", foreground="#cc6600",
                                    wraplength=190, font=("TkDefaultFont", 8))
        self.thick_warn.pack(fill="x")

        ttk.Separator(side).pack(fill="x", pady=12)
        a1 = ttk.Button(side, text="Apply to this file", command=lambda: self._apply_outline(False))
        a2 = ttk.Button(side, text="Apply to whole folder", command=lambda: self._apply_outline(True))
        a1.pack(fill="x"); a2.pack(fill="x", pady=4)
        ToolTip(a1, "Overwrite the currently loaded PNG with the previewed result.")
        ToolTip(a2, "Apply the current settings to every loaded PNG (overwrites in place).")
        dbg = ttk.Button(side, text="Dump debug", command=self._dump_debug)
        dbg.pack(fill="x", pady=(8, 0))
        ToolTip(dbg, "Write a sheet of every pipeline stage (+ detected scale, iters, "
                     "etc.) to _debug/ for inspecting exactly what the outline did.")

        top = ttk.Frame(self.o_preview); top.pack(side="top", fill="x")
        self.o_before = ttk.Label(top, compound="top"); self.o_before.pack(side="left", expand=True)
        self.o_after = ttk.Label(top, compound="top"); self.o_after.pack(side="right", expand=True)

        # Scrollable thumbnail gallery (folders only). Built incrementally + debounced.
        self.gallery_label = ttk.Label(self.o_preview, text="", foreground="#555")
        self.gallery_label.pack(side="top", anchor="w", pady=(8, 2))
        wrap = ttk.Frame(self.o_preview); wrap.pack(side="top", fill="both", expand=True)
        self.gallery_canvas = tk.Canvas(wrap, highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.gallery_canvas.yview)
        self.gallery = ttk.Frame(self.gallery_canvas)
        self.gallery.bind("<Configure>", lambda e: self.gallery_canvas.configure(
            scrollregion=self.gallery_canvas.bbox("all")))
        self.gallery_canvas.create_window((0, 0), window=self.gallery, anchor="nw")
        self.gallery_canvas.configure(yscrollcommand=vsb.set)
        self.gallery_canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._folder_mode = False
        self._gallery_after = None
        self._pending = []
        self._gallery_photos = []

    def _dump_debug(self):
        if self.cur is None:
            messagebox.showinfo("spritekit", "Open a file or folder first."); return
        _, stages, info = outline_mod.run_pipeline(self.cur, self._params())
        out = Path("_debug") / ((self.cur_path.stem if self.cur_path else "sample") + "_debug.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        debug_sheet(stages, info).save(out)
        messagebox.showinfo("spritekit", f"Debug sheet written to:\n{out.resolve()}")

    def _on_thickness(self):
        g = outline_mod.image_growth(THICKNESS_STOPS[self.thick_idx.get()])
        self.thick_warn.config(
            text=(f"⚠ sub-pixel outline — output image will be {g}× larger" if g > 1 else ""))
        self._refresh()

    def _params(self):
        return outline_mod.OutlineParams(
            target_lum=self.target_lum.get(), connectivity=self.conn.get(),
            thickness=THICKNESS_STOPS[self.thick_idx.get()])

    def _open_file(self):
        f = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if f:
            self._folder_mode = False
            self.files = [Path(f)]
            self._clear_gallery()
            self._load(Path(f))

    def _open_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.files = sorted(Path(d).glob("*.png"))
            if self.files:
                self._folder_mode = True
                self._load(self.files[0])
                self._rebuild_gallery()
            else:
                messagebox.showinfo("spritekit", "No PNGs in that folder.")

    def _load(self, path):
        self.cur = load_rgba(path); self.cur_path = path
        self.o_status.config(text=f"{path.name}  —  {len(self.files)} file(s) loaded")
        self._refresh()

    def _refresh(self):
        if self.cur is not None:
            after = outline_mod.process_array(self.cur, self._params())
            box = (max(self.o_preview.winfo_width() // 2 - 20, 380),
                   max(self.gallery_label.winfo_rooty() - self.o_preview.winfo_rooty() - 20, 220))
            pb, pa = _to_photo(self.cur, box), _to_photo(after, box)
            self._photos = [pb, pa]
            self.o_before.config(image=pb, text="BEFORE")
            self.o_after.config(image=pa, text="AFTER")
        self._schedule_gallery()

    # ---- thumbnail gallery (folder mode) ----
    def _schedule_gallery(self):
        """Debounce: rebuild the gallery only once the settings stop changing."""
        if not self._folder_mode:
            return
        if self._gallery_after is not None:
            self.after_cancel(self._gallery_after)
        self._gallery_after = self.after(GALLERY_DEBOUNCE, self._rebuild_gallery)

    def _clear_gallery(self):
        if self._gallery_after is not None:
            self.after_cancel(self._gallery_after)
            self._gallery_after = None
        self._pending = []
        self._gallery_photos = []
        for w in self.gallery.winfo_children():
            w.destroy()
        self.gallery_label.config(text="")

    def _rebuild_gallery(self):
        self._clear_gallery()
        shown = list(self.files)[:GALLERY_MAX]
        extra = len(self.files) - len(shown)
        self.gallery_label.config(
            text=f"{len(self.files)} sprites — click a thumbnail to edit"
                 + (f"  (showing first {GALLERY_MAX})" if extra > 0 else ""))
        self._pending = list(enumerate(shown))
        self._render_next()

    def _render_next(self):
        """Render one chunk of thumbnails, then yield to the UI before the next."""
        params = self._params()
        cols = max(1, self.gallery_canvas.winfo_width() // (GALLERY_CELL + 8))
        for idx, path in self._pending[:GALLERY_CHUNK]:
            after = outline_mod.process_array(load_rgba(path), params)
            photo = _to_photo_fit(after, GALLERY_CELL)
            self._gallery_photos.append(photo)
            cell = ttk.Label(self.gallery, image=photo, cursor="hand2", padding=2)
            cell.grid(row=idx // cols, column=idx % cols, padx=2, pady=2)
            cell.sprite_path = path
            cell.bind("<Button-1>", self._on_thumb_click)
        self._pending = self._pending[GALLERY_CHUNK:]
        if self._pending:
            self._gallery_after = self.after(1, self._render_next)

    def _on_thumb_click(self, event):
        self._load(event.widget.sprite_path)

    def _apply_outline(self, whole_folder):
        if not self.files:
            messagebox.showinfo("spritekit", "Open a file or folder first."); return
        targets = self.files if whole_folder else [self.cur_path]
        for f in targets:
            save_rgba(outline_mod.process_array(load_rgba(f), self._params()), f)
        messagebox.showinfo("spritekit", f"Applied to {len(targets)} file(s).")
        self._load(self.cur_path)

    # ---------------- Split tab ----------------
    def _build_split(self, root):
        side = ttk.Frame(root, padding=12); side.pack(side="left", fill="y")
        self.s_canvas = ttk.Label(root, padding=10, anchor="center"); self.s_canvas.pack(side="right", fill="both", expand=True)

        b = ttk.Button(side, text="Open sheet…", command=self._open_sheet); b.pack(fill="x")
        ToolTip(b, "Load a sprite sheet PNG to split into individual sprites.")
        self.s_status = ttk.Label(side, text="No sheet loaded.", wraplength=190, foreground="#555")
        self.s_status.pack(fill="x", pady=(4, 4))

        self.hgap = tk.IntVar(value=6); self.vgap = tk.IntVar(value=8)
        self.attach_h = tk.IntVar(value=0); self.attach_v = tk.IntVar(value=16)
        self.fragment_max_dim = tk.IntVar(value=22)
        labeled_slider(side, "H gap", self.hgap, 0, 30, TIPS["hgap"], self._split_preview, unit=" px")
        labeled_slider(side, "V gap", self.vgap, 0, 30, TIPS["vgap"], self._split_preview, unit=" px")

        ttk.Separator(side).pack(fill="x", pady=12)
        hdr = ttk.Label(side, text="Attach loose fragments", font=("TkDefaultFont", 9, "bold"))
        hdr.pack(anchor="w")
        ToolTip(hdr, TIPS["ath"])
        labeled_slider(side, "Reach H (0 = off)", self.attach_h, 0, 60, TIPS["ath"], self._split_preview, unit=" px")
        labeled_slider(side, "Reach V", self.attach_v, 0, 40, TIPS["atv"], self._split_preview, unit=" px")
        labeled_slider(side, "Max fragment size", self.fragment_max_dim, 4, 60, TIPS["frag"], self._split_preview, unit=" px")

        ttk.Separator(side).pack(fill="x", pady=12)
        e = ttk.Button(side, text="Export to folder…", command=self._export_split); e.pack(fill="x")
        ToolTip(e, "Write the split sprites (as previewed) into a folder you choose.")
        self.sheet_path = None

    def _sparams(self):
        return split_mod.SplitParams(
            hgap=self.hgap.get(), vgap=self.vgap.get(),
            attach_h=self.attach_h.get(), attach_v=self.attach_v.get(),
            fragment_max_dim=self.fragment_max_dim.get())

    def _open_sheet(self):
        f = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if f:
            self.sheet_path = Path(f); self._split_preview()

    def _split_preview(self):
        if not self.sheet_path:
            return
        count, results = split_mod.split_sheet(self.sheet_path, ".", self._sparams(), dry_run=True)
        pairs = [(None, crop) for crop, _ in results]
        names = [str(i + 1) for i in range(len(results))]
        sheet = contact_sheet(pairs, names, cols=10, cell=46, pad=52)
        box = (max(self.s_canvas.winfo_width() - 20, 640), max(self.s_canvas.winfo_height() - 20, 560))
        s = min(box[0] / sheet.size[0], box[1] / sheet.size[1], 1.0)
        sheet = sheet.resize((max(1, int(sheet.size[0] * s)), max(1, int(sheet.size[1] * s))))
        self._sphoto = ImageTk.PhotoImage(sheet)
        self.s_canvas.config(image=self._sphoto)
        self.s_status.config(text=f"{self.sheet_path.name}  —  {count} sprite(s)")

    def _export_split(self):
        if not self.sheet_path:
            messagebox.showinfo("spritekit", "Open a sheet first."); return
        d = filedialog.askdirectory(title="Export sprites to…")
        if d:
            count, _ = split_mod.split_sheet(self.sheet_path, d, self._sparams())
            messagebox.showinfo("spritekit", f"Exported {count} sprite(s) to:\n{d}")


def launch():
    App().mainloop()


if __name__ == "__main__":
    launch()
