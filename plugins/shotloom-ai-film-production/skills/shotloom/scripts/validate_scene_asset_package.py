#!/usr/bin/env python3
"""Validate a scene layout asset or final production scene-asset package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import validate_asset_manifest as vam


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
METHODS = {
    "EXACT_PLATE_COMPOSITE",
    "STRUCTURAL_ANCHOR_CHECK",
    "GEOMETRY_REPROJECTED",
    "HYBRID",
}


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("root must be an object")
    return data


def is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def require_text(data: dict[str, Any], field: str, prefix: str, errors: list[str]) -> str:
    value = data.get(field)
    if not is_text(value):
        errors.append(f"{prefix}.{field}: required")
        return ""
    return str(value).strip()


def require_list(data: dict[str, Any], field: str, prefix: str, errors: list[str], nonempty: bool) -> list[Any]:
    value = data.get(field)
    if not isinstance(value, list) or (nonempty and not value):
        errors.append(f"{prefix}.{field}: required {'non-empty ' if nonempty else ''}list")
        return []
    return value


def validate(
    package: dict[str, Any],
    target: str,
    manifest_data: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if package.get("schema_version") != 1:
        errors.append("schema_version: expected 1")
    for field in (
        "project_id", "scene_id", "package_id", "package_version",
        "source_scene_plan_version", "production_method",
    ):
        require_text(package, field, "package", errors)
    if package.get("production_method") not in METHODS:
        errors.append(f"production_method: expected one of {sorted(METHODS)}")

    technical = package.get("technical_baseline")
    if not isinstance(technical, dict):
        errors.append("technical_baseline: required object")
        technical = {}
    spatial = package.get("spatial_master")
    if not isinstance(spatial, dict):
        errors.append("spatial_master: required object")
        spatial = {}
    for field in (
        "layout_reference", "layout_version", "coordinate_origin", "axis_convention",
        "unit", "reachability_and_blocking_evidence",
    ):
        require_text(spatial, field, "spatial_master", errors)
    require_list(spatial, "key_dimensions", "spatial_master", errors, nonempty=True)
    require_list(spatial, "fixed_equipment", "spatial_master", errors, nonempty=False)
    if spatial.get("fixed_equipment_status") not in {"PASS", "N/A"}:
        errors.append("spatial_master.fixed_equipment_status: must be PASS or N/A")

    setups = require_list(package, "camera_setups", "package", errors, nonempty=True)
    setup_ids: set[str] = set()
    for index, setup in enumerate(setups):
        prefix = f"camera_setups[{index}]"
        if not isinstance(setup, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        setup_id = require_text(setup, "setup_id", prefix, errors)
        if setup_id in setup_ids:
            errors.append(f"{prefix}.setup_id: duplicate {setup_id!r}")
        setup_ids.add(setup_id)
        for field in ("position_and_orientation", "lens_or_fov", "visible_area"):
            require_text(setup, field, prefix, errors)
        if setup.get("status") not in {"PLANNED", "APPROVED"}:
            errors.append(f"{prefix}.status: must be PLANNED or APPROVED")

    environment = package.get("environment")
    if not isinstance(environment, dict):
        errors.append("environment: required object")
        environment = {}
    require_list(environment, "static_regions", "environment", errors, nonempty=True)
    require_list(environment, "dynamic_regions", "environment", errors, nonempty=False)

    approval = package.get("approval")
    if not isinstance(approval, dict):
        errors.append("approval: required object")
        approval = {}
    if approval.get("status") != "PASS":
        errors.append("approval.status: must be PASS")
    for field in ("reviewer", "reviewed_at", "evidence"):
        require_text(approval, field, "approval", errors)

    if target == "layout":
        if package.get("stage") not in {"LAYOUT", "FINAL"}:
            errors.append("stage: layout validation accepts LAYOUT or FINAL")
        if package.get("status") not in {"LAYOUT_APPROVED", "ACCEPTED"}:
            errors.append("status: must be LAYOUT_APPROVED or ACCEPTED for layout")
        return errors, warnings

    if package.get("stage") != "FINAL":
        errors.append("stage: must be FINAL")
    if package.get("status") != "ACCEPTED":
        errors.append("status: must be ACCEPTED")
    for field in ("aspect_ratio", "resolution", "color_space"):
        require_text(technical, field, "technical_baseline", errors)

    picture = package.get("picture_assets")
    if not isinstance(picture, dict):
        errors.append("picture_assets: required object")
        picture = {}
    require_text(picture, "scene_master_reference", "picture_assets", errors)
    if package.get("production_method") == "EXACT_PLATE_COMPOSITE":
        require_text(picture, "clean_plate_reference", "picture_assets", errors)
        require_text(picture, "allowed_change_mask_reference", "picture_assets", errors)
    if package.get("production_method") == "GEOMETRY_REPROJECTED":
        require_text(picture, "depth_or_geometry_reference", "picture_assets", errors)

    for setup_index, setup in enumerate(setups):
        if isinstance(setup, dict) and setup.get("status") != "APPROVED":
            errors.append(f"camera_setups[{setup_index}].status: must be APPROVED for final")
    require_text(environment, "light_state_reference", "environment", errors)
    require_text(environment, "look_reference", "environment", errors)

    manifest = package.get("asset_manifest")
    if not isinstance(manifest, dict):
        errors.append("asset_manifest: required object")
        manifest = {}
    manifest_id = require_text(manifest, "manifest_id", "asset_manifest", errors)
    manifest_digest = require_text(manifest, "manifest_digest_sha256", "asset_manifest", errors).lower()
    if manifest_digest and not SHA256_RE.fullmatch(manifest_digest):
        errors.append("asset_manifest.manifest_digest_sha256: must be 64 lowercase hexadecimal characters")

    refs = require_list(package, "asset_refs", "package", errors, nonempty=True)
    identities: set[tuple[str, str, str]] = set()
    for index, item in enumerate(refs):
        prefix = f"asset_refs[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        identity = tuple(require_text(item, field, prefix, errors) for field in ("asset_id", "version", "reference"))
        if identity in identities:
            errors.append(f"{prefix}: duplicate asset reference {identity!r}")
        identities.add(identity)

    if manifest_data is None:
        errors.append("manifest: required for final validation")
        return errors, warnings
    if manifest_data.get("manifest_id") != manifest_id:
        errors.append("asset_manifest.manifest_id: does not match supplied manifest")
    actual_digest = vam.canonical_digest(manifest_data)
    if manifest_digest != actual_digest:
        errors.append("asset_manifest.manifest_digest_sha256: does not match supplied manifest")
    manifest_refs = {
        (str(item.get("asset_id")), str(item.get("version")), str(item.get("reference")))
        for item in manifest_data.get("assets", [])
        if isinstance(item, dict) and item.get("status") == "ACCEPTED"
    }
    for identity in identities:
        if identity not in manifest_refs:
            errors.append(f"asset_refs: {identity!r} is absent from supplied ACCEPTED manifest")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--target", choices=("layout", "final"), required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        package = load(args.package)
    except ValueError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    manifest_data = None
    manifest_errors: list[str] = []
    if args.manifest:
        manifest_errors, manifest_data = vam.validate_manifest(args.manifest, args.root)
    elif args.target == "final":
        manifest_errors.append("--manifest is required for final validation")

    errors, warnings = validate(package, args.target, manifest_data)
    errors = manifest_errors + errors
    payload = {"status": "BLOCKED" if errors else "PASS", "target": args.target, "errors": errors, "warnings": warnings}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        print(f"BLOCKED: scene asset package has {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"PASS: scene asset package is ready for {args.target}")
        for warning in warnings:
            print(f"WARN: {warning}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
