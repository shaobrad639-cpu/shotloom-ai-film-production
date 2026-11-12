#!/usr/bin/env python3
"""Validate the identity, isolation, and technical format of a generation deliverable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DELIVERABLE_RULES = {
    "CLEAN_PLATE": ("INDEPENDENT_ASSET", "BACKGROUND", "SCENE", False, True),
    "CHARACTER_LAYER": ("INDEPENDENT_ASSET", "CHARACTER", "TRANSPARENT", True, True),
    "PROP_LAYER": ("INDEPENDENT_ASSET", "PROP", "TRANSPARENT", True, True),
    "EFFECT_LAYER": ("INDEPENDENT_ASSET", "EFFECT", "TRANSPARENT", True, True),
    "FOREGROUND_LAYER": ("INDEPENDENT_ASSET", "FOREGROUND_OCCLUSION", "TRANSPARENT", True, True),
    "COMPOSITE_KEYFRAME": ("COMPOSITE_FRAME", "COMPOSITE", "COMPOSITED", False, False),
    "STORYBOARD_PANEL": ("PLANNING_ARTIFACT", "COMPOSITE", "COMPOSITED", False, False),
    "VIDEO_SHOT": ("VIDEO_SHOT", "COMPOSITE", "COMPOSITED", False, False),
}
TEXT_POLICIES = {"FORBIDDEN", "REQUIRED", "ALLOWED"}


def is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def require_text(data: dict[str, Any], field: str, errors: list[str]) -> None:
    if not is_text(data.get(field)):
        errors.append(f"{field}: required non-empty text")


def require_list(data: dict[str, Any], field: str, errors: list[str], *, nonempty: bool = False) -> list[Any]:
    value = data.get(field)
    if not isinstance(value, list):
        errors.append(f"{field}: must be a list")
        return []
    if nonempty and not value:
        errors.append(f"{field}: must not be empty")
    for index, item in enumerate(value):
        if not is_text(item):
            errors.append(f"{field}[{index}]: required non-empty text")
    return value


def normalized(items: list[Any]) -> set[str]:
    return {str(item).strip().casefold() for item in items if is_text(item)}


def validate(data: dict[str, Any], *, require_approval: bool = True) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version: expected 1")
    for field in (
        "contract_id", "project_id", "scene_id", "aspect_ratio", "resolution",
        "color_space", "file_format", "evidence",
    ):
        require_text(data, field, errors)

    deliverable_type = data.get("deliverable_type")
    rule = DELIVERABLE_RULES.get(deliverable_type)
    if rule is None:
        errors.append(f"deliverable_type: expected one of {sorted(DELIVERABLE_RULES)}")
    else:
        expected_scope, expected_role, expected_background, expected_alpha, expected_isolation = rule
        for field, expected in (
            ("asset_scope", expected_scope),
            ("layer_role", expected_role),
            ("background_mode", expected_background),
            ("alpha_required", expected_alpha),
            ("isolation_required", expected_isolation),
        ):
            if data.get(field) != expected:
                errors.append(f"{field}: {deliverable_type} requires {expected!r}")

    required = require_list(data, "required_elements", errors, nonempty=True)
    forbidden = require_list(data, "forbidden_elements", errors, nonempty=True)
    require_list(data, "baked_elements_allowed", errors, nonempty=False)
    require_list(data, "reference_priority", errors, nonempty=True)
    overlap = normalized(required) & normalized(forbidden)
    if overlap:
        errors.append(f"required_elements/forbidden_elements: conflict {sorted(overlap)}")
    if data.get("text_policy") not in TEXT_POLICIES:
        errors.append(f"text_policy: expected one of {sorted(TEXT_POLICIES)}")
    if not isinstance(data.get("alpha_required"), bool):
        errors.append("alpha_required: must be boolean")
    if not isinstance(data.get("isolation_required"), bool):
        errors.append("isolation_required: must be boolean")

    if require_approval:
        if data.get("status") != "APPROVED":
            errors.append("status: formal generation requires APPROVED")
        approval = data.get("approval")
        if not isinstance(approval, dict):
            errors.append("approval: required object")
        else:
            if approval.get("status") != "PASS":
                errors.append("approval.status: formal generation requires PASS")
            for field in ("reviewer", "reviewed_at", "evidence"):
                if not is_text(approval.get(field)):
                    errors.append(f"approval.{field}: required non-empty text")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--draft", action="store_true", help="Check structure without requiring approval.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        data = json.loads(args.contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: cannot read valid JSON: {exc}")
        return 2
    if not isinstance(data, dict):
        print("BLOCKED: contract root must be an object")
        return 2
    errors = validate(data, require_approval=not args.draft)
    payload = {"status": "BLOCKED" if errors else "PASS", "errors": errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        print(f"BLOCKED: output contract has {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"PASS: {data.get('contract_id')} is approved for {data.get('deliverable_type')}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
