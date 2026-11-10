#!/usr/bin/env python3
"""Check or update the installed runtime copy from the maintained skill source."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path


SOURCE = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = Path.home() / ".codex" / "skills" / SOURCE.name
IGNORED_PARTS = {"__pycache__", ".DS_Store"}


def files_under(root: Path) -> dict[Path, Path]:
    result: dict[Path, Path] = {}
    if not root.exists():
        return result
    for path in root.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        result[path.relative_to(root)] = path
    return result


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def differences(target: Path) -> tuple[list[Path], list[Path], list[Path]]:
    source_files = files_under(SOURCE)
    target_files = files_under(target)
    missing = sorted(set(source_files) - set(target_files))
    stale = sorted(set(target_files) - set(source_files))
    changed = sorted(
        relative
        for relative in set(source_files) & set(target_files)
        if digest(source_files[relative]) != digest(target_files[relative])
    )
    return missing, stale, changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--install", action="store_true")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    if target == SOURCE or SOURCE in target.parents:
        print("FAIL: target must not be the maintained source directory", file=sys.stderr)
        return 2

    missing, stale, changed = differences(target)
    if args.check:
        if not (missing or stale or changed):
            print(f"PASS: installed copy matches source: {target}")
            return 0
        print(f"DIFF: installed copy does not match source: {target}")
        for label, paths in (("missing", missing), ("stale", stale), ("changed", changed)):
            for path in paths:
                print(f"- {label}: {path}")
        return 1

    if stale:
        print("BLOCKED: target contains files absent from source; review before removal:", file=sys.stderr)
        for path in stale:
            print(f"- {path}", file=sys.stderr)
        return 1

    target.mkdir(parents=True, exist_ok=True)
    for relative, source_file in files_under(SOURCE).items():
        target_file = target / relative
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)

    missing, stale, changed = differences(target)
    if missing or stale or changed:
        print("FAIL: copy completed but verification still differs", file=sys.stderr)
        return 1
    print(f"PASS: installed and verified: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
