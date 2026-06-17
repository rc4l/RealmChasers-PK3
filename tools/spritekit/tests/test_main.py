import importlib.util
from pathlib import Path

import core
from conftest import block_sprite

PKG = Path(__file__).resolve().parent.parent


def load_entry():
    spec = importlib.util.spec_from_file_location("sk_entry", PKG / "__main__.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_main_dispatches_gui(monkeypatch):
    import gui
    called = {}
    monkeypatch.setattr(gui, "launch", lambda: called.setdefault("ran", True))
    assert load_entry().main(["gui"]) == 0
    assert called.get("ran")


def test_main_dispatches_cli(tmp_path):
    f = tmp_path / "m.png"
    core.save_rgba(block_sprite(5), f)
    rc = load_entry().main(["outline", str(f), "--dry-run", "--preview", str(tmp_path / "p.png")])
    assert rc == 0
