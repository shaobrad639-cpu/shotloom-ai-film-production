#!/usr/bin/env python3
"""Validate cross-shot continuity across a folder of shot production passes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def get(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def collect_passes(paths: list[Path]) -> tuple[dict[Path, dict[str, Any]], int]:
    """Load JSON files that look like shot passes; return (passes, ignored)."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.json")))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(path)

    passes: dict[Path, dict[str, Any]] = {}
    ignored = 0
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ignored += 1
            continue
        if not isinstance(data, dict) or not isinstance(data.get("shot"), dict):
            ignored += 1
            continue
        passes[file] = data
    return passes, ignored


def validate(
    passes: dict[Path, dict[str, Any]], manifest_digest: str | None
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    shot_ids: set[str] = set()
    takes: dict[tuple[str, str], list[tuple[Path, dict[str, Any]]]] = {}
    versions: dict[tuple[str, str, str], Path] = {}

    for file, data in passes.items():
        shot_id = get(data, "shot.shot_id")
        take_id = get(data, "shot.take_id")
        pass_version = get(data, "shot.pass_version")
        if not isinstance(shot_id, str) or not shot_id:
            errors.append(f"{file}: shot.shot_id is required")
            continue
        shot_ids.add(shot_id)
        key = (shot_id, str(take_id), str(pass_version))
        if key in versions:
            errors.append(f"{file}: duplicate pass {shot_id} {take_id} {pass_version} (also {versions[key]})")
        versions[key] = file
        takes.setdefault((shot_id, str(take_id)), []).append((file, data))

    for file, data in passes.items():
        shot_id = get(data, "shot.shot_id")
        relation = get(data, "shot.relation_from_previous")
        previous = get(data, "continuity.previous_shot_id")
        index = get(data, "shot.segment_sequence_index")
        mode = get(data, "shot.continuity_mode")

        if isinstance(previous, str) and previous and previous not in shot_ids:
            errors.append(f"{file}: continuity.previous_shot_id {previous!r} has no pass in this set")
        if relation == "EDITORIAL_CUT" and previous == shot_id:
            errors.append(f"{file}: editorial cut must reference a different shot")
        if relation == "CONTINUOUS_SEGMENT":
            if previous != shot_id:
                errors.append(f"{file}: CONTINUOUS_SEGMENT must continue the same shot_id")
            if isinstance(index, int) and index > 1:
                siblings = takes.get((str(shot_id), str(get(data, "shot.take_id"))), [])
                indexes = {get(item, "shot.segment_sequence_index") for _, item in siblings}
                if index - 1 not in indexes:
                    warnings.append(
                        f"{file}: segment {index} has no preceding segment {index - 1} in this set (chain unverifiable)"
                    )
            tail = get(data, "continuity.previous_tail_asset_version")
            if not isinstance(tail, str) or not tail.strip():
                errors.append(f"{file}: CONTINUOUS_SEGMENT requires continuity.previous_tail_asset_version")
        if mode == "CONTINUOUS_TAKE" and isinstance(index, int):
            if index < 1:
                errors.append(f"{file}: segment_sequence_index must be positive")
        if manifest_digest:
            status = get(data, "shot.status")
            if status in {"GREENLIT", "ACCEPTED"}:
                digest = get(data, "asset_identity_lock.manifest_digest_sha256")
                if digest != manifest_digest:
                    errors.append(
                        f"{file}: manifest digest does not match the sequence manifest "
                        f"(expected {manifest_digest})"
                    )

    for (shot_id, take_id), items in takes.items():
        continuous = [(file, data) for file, data in items if get(data, "shot.continuity_mode") == "CONTINUOUS_TAKE"]
        if not continuous:
            continue
        indexes = sorted(
            get(data, "shot.segment_sequence_index")
            for _, data in continuous
            if isinstance(get(data, "shot.segment_sequence_index"), int)
        )
        expected = list(range(1, len(indexes) + 1))
        if indexes != expected:
            warnings.append(
                f"{shot_id} {take_id}: continuous segment indexes {indexes} are not contiguous from 1 ({expected})"
            )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+", help="Directories or pass JSON files to validate.")
    parser.add_argument("--manifest-digest", help="Asset manifest digest every GREENLIT/ACCEPTED pass must carry.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable result.")
    args = parser.parse_args()

    try:
        passes, ignored = collect_passes(args.paths)
    except FileNotFoundError as exc:
        print(f"FAIL: path not found: {exc}", file=sys.stderr)
        return 2

    if not passes:
        print("FAIL: no shot passes found", file=sys.stderr)
        return 2

    errors, warnings = validate(passes, args.manifest_digest)
    payload = {
        "status": "BLOCKED" if errors else "PASS",
        "passes": len(passes),
        "ignored_files": ignored,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        print(f"BLOCKED: sequence continuity is broken ({len(errors)} issue(s))")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"PASS: {len(passes)} shot pass(es) form a consistent continuity chain")
        for warning in warnings:
            print(f"WARN: {warning}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
