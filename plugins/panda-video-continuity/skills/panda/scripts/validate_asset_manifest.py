#!/usr/bin/env python3
"""Validate an approved video asset manifest and verify every file SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ASSET_TYPES = {
    "CHARACTER",
    "SCENE",
    "SCENE_BUNDLE",
    "BACKGROUND_PLATE",
    "DEPTH_OR_GEOMETRY",
    "FOREGROUND_OCCLUSION",
    "FIXED_EQUIPMENT",
    "OCCLUSION_COMPLETION",
    "ENVIRONMENT_ANIMATION",
    "SPATIAL_LAYOUT",
    "CAMERA",
    "PROP",
    "KEYFRAME",
    "ALLOWED_CHANGE_MASK",
    "ACTUAL_RENDERED_TAIL",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_digest(data: Any) -> str:
    """Stable SHA-256 of the manifest content, independent of formatting."""
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_text(item: dict[str, Any], field: str, prefix: str, errors: list[str]) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{prefix}.{field}: required")
        return ""
    return value.strip()


def validate_manifest(manifest: Path, root: Path | None = None) -> tuple[list[str], dict[str, Any] | None]:
    """Validate a manifest and every referenced file. Returns (errors, data)."""
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"manifest not found: {manifest}"], None
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read valid manifest JSON: {exc}"], None
    if not isinstance(data, dict):
        return ["manifest root must be a JSON object"], None

    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version: expected 1")
    for field in ("manifest_id", "manifest_version"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f"{field}: required")
    if data.get("status") != "ACCEPTED":
        errors.append("status: manifest must be ACCEPTED")

    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("assets: must be a non-empty list")
        assets = []

    base = (root or manifest.parent).resolve()
    identities: set[tuple[str, str]] = set()
    references: set[str] = set()

    for index, item in enumerate(assets):
        prefix = f"assets[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        asset_id = required_text(item, "asset_id", prefix, errors)
        version = required_text(item, "version", prefix, errors)
        reference = required_text(item, "reference", prefix, errors)
        file_value = required_text(item, "file", prefix, errors)
        digest = required_text(item, "sha256", prefix, errors).lower()
        asset_type = required_text(item, "asset_type", prefix, errors)

        if asset_type and asset_type not in ASSET_TYPES:
            errors.append(f"{prefix}.asset_type: unsupported value {asset_type!r}")
        if item.get("status") != "ACCEPTED":
            errors.append(f"{prefix}.status: must be ACCEPTED")
        if digest and not SHA256_RE.fullmatch(digest):
            errors.append(f"{prefix}.sha256: must be 64 lowercase hexadecimal characters")

        identity = (asset_id, version)
        if all(identity):
            if identity in identities:
                errors.append(f"{prefix}: duplicate asset identity {asset_id!r} {version!r}")
            identities.add(identity)
        if reference:
            if reference in references:
                errors.append(f"{prefix}.reference: duplicate reference {reference!r}")
            references.add(reference)

        if file_value:
            path = Path(file_value)
            resolved = path if path.is_absolute() else base / path
            if not resolved.is_file():
                errors.append(f"{prefix}.file: not found or not a file: {resolved}")
            elif SHA256_RE.fullmatch(digest):
                actual = sha256_file(resolved)
                if actual != digest:
                    errors.append(
                        f"{prefix}.sha256: content mismatch for {resolved}; "
                        f"expected {digest}, got {actual}"
                    )

    return errors, data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        help="Resolve relative asset file paths from this directory; defaults to manifest parent.",
    )
    args = parser.parse_args()

    errors, data = validate_manifest(args.manifest, args.root)
    if data is None:
        print(f"FAIL: {errors[0]}", file=sys.stderr)
        return 2

    if errors:
        print(f"BLOCKED: asset manifest is not production-locked: {args.manifest}")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"PASS: {data['manifest_id']} {data['manifest_version']} locks "
        f"{len(data['assets'])} ACCEPTED assets"
    )
    print(f"manifest_digest_sha256: {canonical_digest(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
