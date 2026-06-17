"""Entry point: `python tools/spritekit gui` or `python tools/spritekit outline ...`.

Adds this directory to sys.path so the flat sibling modules import cleanly on
Windows, macOS and Linux regardless of how the folder is invoked."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "gui":
        import gui
        gui.launch()
        return 0
    import cli
    return cli.main(argv)


if __name__ == "__main__":
    sys.exit(main())
