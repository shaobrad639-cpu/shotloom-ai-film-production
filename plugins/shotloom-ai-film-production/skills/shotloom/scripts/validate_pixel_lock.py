#!/usr/bin/env python3
"""Compare two frames while allowing changes only inside a declared mask."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover - environment-dependent message
    print("FAIL: Pillow is required. Install it with: python3 -m pip install Pillow", file=sys.stderr)
    raise SystemExit(2)


def count_pixels(image: Any, *, predicate) -> int:
    """Count pixels matching predicate, using numpy when available (fast on 4K frames)."""
    try:
        import numpy as np
    except ImportError:  # pragma: no cover - numpy is optional
        return sum(1 for value in image.getdata() if predicate(value))
    array = np.asarray(image)
    return int(np.count_nonzero(predicate(array)))


def write_report(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frame_a", type=Path)
    parser.add_argument("frame_b", type=Path)
    parser.add_argument("--allowed-mask", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--threshold", type=int, default=0, choices=range(0, 256), metavar="0..255")
    parser.add_argument("--min-protected-ratio", type=float, default=0.5)
    parser.add_argument("--max-protected-change-ratio", type=float, default=0.0)
    args = parser.parse_args()

    if not 0 <= args.min_protected_ratio <= 1:
        parser.error("--min-protected-ratio must be between 0 and 1")
    if not 0 <= args.max_protected_change_ratio <= 1:
        parser.error("--max-protected-change-ratio must be between 0 and 1")

    try:
        frame_a = Image.open(args.frame_a).convert("RGBA")
        frame_b = Image.open(args.frame_b).convert("RGBA")
        allowed_mask = Image.open(args.allowed_mask).convert("L")
    except (FileNotFoundError, OSError) as exc:
        print(f"FAIL: cannot open input image: {exc}", file=sys.stderr)
        return 2

    if frame_a.size != frame_b.size or frame_a.size != allowed_mask.size:
        print("FAIL: frames and mask must have identical dimensions", file=sys.stderr)
        return 2

    # White (>=128) is allowed to change; black (<128) is protected.
    allowed = allowed_mask.point(lambda value: 255 if value >= 128 else 0)
    protected = ImageChops.invert(allowed)
    difference = ImageChops.difference(frame_a, frame_b).convert("RGB")
    changed_any_channel = difference.point(lambda value: 255 if value > args.threshold else 0).convert("L")
    changed_protected = ImageChops.multiply(changed_any_channel, protected)

    total_pixels = frame_a.width * frame_a.height
    protected_pixels = count_pixels(protected, predicate=lambda values: values != 0)
    changed_protected_pixels = count_pixels(changed_protected, predicate=lambda values: values != 0)
    protected_ratio = protected_pixels / total_pixels if total_pixels else 0.0
    change_ratio = changed_protected_pixels / protected_pixels if protected_pixels else 1.0
    match_ratio = 1.0 - change_ratio
    passed = (
        protected_ratio >= args.min_protected_ratio
        and change_ratio <= args.max_protected_change_ratio
    )

    payload = {
        "status": "PASS" if passed else "BLOCKED",
        "frame_a": str(args.frame_a),
        "frame_b": str(args.frame_b),
        "allowed_mask": str(args.allowed_mask),
        "dimensions": [frame_a.width, frame_a.height],
        "threshold": args.threshold,
        "protected_pixels": protected_pixels,
        "protected_ratio": protected_ratio,
        "changed_protected_pixels": changed_protected_pixels,
        "protected_change_ratio": change_ratio,
        "protected_match_ratio": match_ratio,
        "required_min_protected_ratio": args.min_protected_ratio,
        "allowed_max_protected_change_ratio": args.max_protected_change_ratio,
    }
    write_report(args.report, payload)

    if passed:
        print(
            f"PASS: protected_match_ratio={match_ratio:.12f}, "
            f"changed_protected_pixels={changed_protected_pixels}"
        )
        return 0
    print(
        "BLOCKED: "
        f"protected_ratio={protected_ratio:.6f}, "
        f"protected_match_ratio={match_ratio:.12f}, "
        f"changed_protected_pixels={changed_protected_pixels}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
