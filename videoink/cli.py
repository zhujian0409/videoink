"""videoink CLI entry point (v0.1 stub)."""

from __future__ import annotations

import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    print(f"videoink {__version__} — CLI stub. Full pipeline coming in v0.1.")
    print("Track progress: https://github.com/zhujian0409/videoink")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
