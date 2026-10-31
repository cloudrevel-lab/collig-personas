#!/usr/bin/env python3
"""Generate or check index.json for the collig-personas market."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from validate_personas import build_index, render_index, validate_repository


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the collig-personas index")
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--write", action="store_true", help="write index.json (default)")
    parser.add_argument("--check", action="store_true", help="fail if index.json is stale")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    report = validate_repository(root, check_index=False)
    if report.errors:
        for error in report.errors:
            print("ERROR: " + error)
        return 1

    index_path = root / "index.json"
    if args.check:
        if not index_path.is_file():
            print("ERROR: index.json is missing")
            return 1
        if index_path.read_text(encoding="utf-8") != render_index(root):
            print("ERROR: index.json is stale; run make index")
            return 1
        print("OK: index.json is up to date")
        return 0

    index_path.write_text(render_index(root), encoding="utf-8")
    print("Wrote " + str(index_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
