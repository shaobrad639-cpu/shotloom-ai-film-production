#!/usr/bin/env python3
"""Re-stamp shot passes that were sealed by an older validator version.

Scans a project (or the shipped examples) for shot production passes, works out
the validation target from shot.status, locates the asset manifest, and runs
validate_shot_pass.py with --restamp. Nothing is written unless the pass passes
every current check; passes whose evidence is missing are reported, not forced.

Examples
    python3 scripts/restamp_passes.py examples
    python3 scripts/restamp_passes.py /path/to/project --dry-run
    python3 scripts/restamp_passes.py /path/to/project --manifest assets/asset-manifest.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
VALIDATOR = SCRIPTS / "validate_shot_pass.py"
IGNORED_PARTS = {"__pycache__", ".git", "node_modules", ".venv"}
TARGET_BY_STATUS = {
    "READY_FOR_RELEASE": "release",
    "GREENLIT": "release",
    "ACCEPTED": "acceptance",
}

sys.path.insert(0, str(SCRIPTS))
from validate_shot_pass import VALIDATOR_VERSION, get  # noqa: E402


def is_pass(data: object) -> bool:
    return (
        isinstance(data, dict)
        and isinstance(data.get("shot"), dict)
        and isinstance(data["shot"].get("pass_version"), str)
    )


def find_passes(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in sorted(root.rglob("*.json")):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if is_pass(data):
            found.append(path)
    return found


def locate_manifest(data: dict, pass_file: Path, root: Path, override: Path | None) -> Path | None:
    if override is not None:
        return override if override.is_file() else None
    reference = get(data, "asset_identity_lock.manifest_reference")
    candidates = []
    if isinstance(reference, str) and reference.strip():
        candidates.append(pass_file.parent / reference.strip())
        candidates.append(root / reference.strip())
    candidates.extend([pass_file.parent / "asset-manifest.json", root / "asset-manifest.json"])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path, help="Directory to scan for shot production passes.")
    parser.add_argument("--manifest", type=Path, help="Use this asset manifest for every pass.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be restamped, write nothing.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"FAIL: not a directory: {root}", file=sys.stderr)
        return 2
    override = args.manifest.expanduser().resolve() if args.manifest else None

    results: list[dict[str, str]] = []
    failures = 0
    for pass_file in find_passes(root):
        data = json.loads(pass_file.read_text(encoding="utf-8"))
        shot_id = get(data, "shot.shot_id")
        version = get(data, "shot.pass_version")
        status = get(data, "shot.status")
        target = TARGET_BY_STATUS.get(status)
        if target is None:
            results.append({"file": str(pass_file), "result": "SKIP", "detail": f"status {status} has no sealed stamp"})
            continue
        section = "release" if target == "release" else "acceptance"
        stamped = get(data, f"{section}.validator_version")
        manifest = locate_manifest(data, pass_file, root, override)
        if manifest is None:
            results.append({"file": str(pass_file), "result": "SKIP", "detail": "asset manifest not found"})
            continue
        if stamped == VALIDATOR_VERSION:
            results.append(
                {"file": str(pass_file), "result": "CURRENT", "detail": f"{shot_id} {version} already stamped by {VALIDATOR_VERSION}"}
            )
            continue
        if args.dry_run:
            results.append(
                {"file": str(pass_file), "result": "WOULD RESTAMP", "detail": f"{shot_id} {version} {stamped!r} -> {VALIDATOR_VERSION}"}
            )
            continue
        command = [
            sys.executable,
            str(VALIDATOR),
            str(pass_file),
            "--target",
            target,
            "--manifest",
            str(manifest),
            "--root",
            str(pass_file.parent),
            "--restamp",
            "--json",
        ]
        proc = subprocess.run(command, capture_output=True, text=True)
        if proc.returncode == 0:
            results.append({"file": str(pass_file), "result": "RESTAMPED", "detail": f"{shot_id} {version} {stamped!r} -> {VALIDATOR_VERSION}"})
            continue
        failures += 1
        detail = ""
        try:
            payload = json.loads(proc.stdout)
            errors = payload.get("errors") or []
            detail = errors[0] if errors else payload.get("status", "BLOCKED")
        except json.JSONDecodeError:
            detail = (proc.stdout or proc.stderr).strip().splitlines()[:1] or ["BLOCKED"]
            detail = detail[0] if isinstance(detail, list) else detail
        results.append({"file": str(pass_file), "result": "BLOCKED", "detail": f"{shot_id} {version}: {detail}"})

    if args.json:
        print(json.dumps({"root": str(root), "validator_version": VALIDATOR_VERSION, "results": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print(f"{item['result']:<14} {item['file']}")
            if item["detail"]:
                print(f"{'':<14} {item['detail']}")
        counts: dict[str, int] = {}
        for item in results:
            counts[item["result"]] = counts.get(item["result"], 0) + 1
        summary = ", ".join(f"{name}={count}" for name, count in sorted(counts.items())) or "nothing found"
        print(f"\n{summary} (validator {VALIDATOR_VERSION})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
