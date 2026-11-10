#!/usr/bin/env python3
"""Validate the story-to-animatic package before formal shot production."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: cannot read JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be an object")
    return data


def text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def require_text(data: dict[str, Any], field: str, prefix: str, errors: list[str]) -> str:
    value = data.get(field)
    if not text(value):
        errors.append(f"{prefix}.{field}: required non-empty text")
        return ""
    return str(value)


def require_schema(data: dict[str, Any], prefix: str, errors: list[str], expected: int = 1) -> None:
    if data.get("schema_version") != expected:
        errors.append(f"{prefix}.schema_version: expected {expected}")


def unique_ids(items: Any, field: str, prefix: str, errors: list[str]) -> set[str]:
    if not isinstance(items, list) or not items:
        errors.append(f"{prefix}: required non-empty list")
        return set()
    found: set[str] = set()
    for index, item in enumerate(items):
        item_prefix = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_prefix}: must be an object")
            continue
        value = require_text(item, field, item_prefix, errors)
        if value in found:
            errors.append(f"{item_prefix}.{field}: duplicate {value!r}")
        if value:
            found.add(value)
    return found


def list_of_text(value: Any, prefix: str, errors: list[str], nonempty: bool = True) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        errors.append(f"{prefix}: required {'non-empty ' if nonempty else ''}list")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not text(item):
            errors.append(f"{prefix}[{index}]: required non-empty text")
        else:
            result.append(str(item))
    return result


def validate(
    breakdown: dict[str, Any],
    scene_plans: list[dict[str, Any]],
    scene_asset_packages: list[dict[str, Any]],
    shot_list: dict[str, Any],
    animatic: dict[str, Any],
    model_profile: dict[str, Any],
    target: str,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    documents = [
        ("script_breakdown", breakdown, 1),
        *( (f"scene_plan[{index}]", item, 1) for index, item in enumerate(scene_plans) ),
        *( (f"scene_asset_package[{index}]", item, 2) for index, item in enumerate(scene_asset_packages) ),
        ("shot_list", shot_list, 1),
        ("animatic", animatic, 1),
        ("model_profile", model_profile, 1),
    ]
    for prefix, data, expected in documents:
        require_schema(data, prefix, errors, expected)

    project_id = require_text(breakdown, "project_id", "script_breakdown", errors)
    require_text(breakdown, "screenplay_version", "script_breakdown", errors)
    sequence_ids = unique_ids(breakdown.get("sequences"), "sequence_id", "script_breakdown.sequences", errors)
    scene_ids = unique_ids(breakdown.get("scenes"), "scene_id", "script_breakdown.scenes", errors)
    beat_ids = unique_ids(breakdown.get("beats"), "beat_id", "script_breakdown.beats", errors)

    for index, scene in enumerate(breakdown.get("scenes", [])):
        if not isinstance(scene, dict):
            continue
        prefix = f"script_breakdown.scenes[{index}]"
        if scene.get("sequence_id") not in sequence_ids:
            errors.append(f"{prefix}.sequence_id: not present in sequences")
        for beat_id in list_of_text(scene.get("beat_ids"), f"{prefix}.beat_ids", errors):
            if beat_id not in beat_ids:
                errors.append(f"{prefix}.beat_ids: unknown {beat_id!r}")

    for index, beat in enumerate(breakdown.get("beats", [])):
        if not isinstance(beat, dict):
            continue
        prefix = f"script_breakdown.beats[{index}]"
        if beat.get("scene_id") not in scene_ids:
            errors.append(f"{prefix}.scene_id: not present in scenes")
        duration = beat.get("target_duration_seconds")
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append(f"{prefix}.target_duration_seconds: must be positive")

    planned_by_scene: dict[str, set[str]] = {}
    plan_scene_ids: set[str] = set()
    for index, plan in enumerate(scene_plans):
        prefix = f"scene_plan[{index}]"
        if plan.get("project_id") != project_id:
            errors.append(f"{prefix}.project_id: must match {project_id!r}")
        scene_id = require_text(plan, "scene_id", prefix, errors)
        if scene_id in plan_scene_ids:
            errors.append(f"{prefix}.scene_id: duplicate plan for {scene_id!r}")
        plan_scene_ids.add(scene_id)
        if scene_id not in scene_ids:
            errors.append(f"{prefix}.scene_id: not present in script breakdown")
        for beat_id in list_of_text(plan.get("beat_ids"), f"{prefix}.beat_ids", errors):
            if beat_id not in beat_ids:
                errors.append(f"{prefix}.beat_ids: unknown {beat_id!r}")
        planned_by_scene[scene_id] = set(
            list_of_text(plan.get("planned_shot_ids"), f"{prefix}.planned_shot_ids", errors)
        )
        duration = plan.get("target_duration_seconds")
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append(f"{prefix}.target_duration_seconds: must be positive")

    if target == "production" and plan_scene_ids != scene_ids:
        missing = sorted(scene_ids - plan_scene_ids)
        extra = sorted(plan_scene_ids - scene_ids)
        if missing:
            errors.append(f"scene_plans: missing plans for {missing}")
        if extra:
            errors.append(f"scene_plans: unknown plans for {extra}")

    package_scene_ids: set[str] = set()
    for index, package in enumerate(scene_asset_packages):
        prefix = f"scene_asset_package[{index}]"
        if package.get("project_id") != project_id:
            errors.append(f"{prefix}.project_id: must match {project_id!r}")
        scene_id = require_text(package, "scene_id", prefix, errors)
        if scene_id in package_scene_ids:
            errors.append(f"{prefix}.scene_id: duplicate package for {scene_id!r}")
        package_scene_ids.add(scene_id)
        if scene_id not in scene_ids:
            errors.append(f"{prefix}.scene_id: not present in script breakdown")
        require_text(package, "package_id", prefix, errors)
        require_text(package, "package_version", prefix, errors)
        if target == "production":
            if package.get("stage") != "FINAL":
                errors.append(f"{prefix}.stage: must be FINAL for production")
            if package.get("status") != "ACCEPTED":
                errors.append(f"{prefix}.status: must be ACCEPTED for production")
        else:
            if package.get("stage") not in {"LAYOUT", "FINAL"}:
                errors.append(f"{prefix}.stage: must be LAYOUT or FINAL for previs")
            if package.get("status") not in {"LAYOUT_APPROVED", "ACCEPTED"}:
                errors.append(f"{prefix}.status: must be LAYOUT_APPROVED or ACCEPTED for previs")
    missing_packages = scene_ids - package_scene_ids
    if missing_packages:
        errors.append(f"scene_asset_packages: missing scenes {sorted(missing_packages)}")

    if shot_list.get("project_id") != project_id:
        errors.append(f"shot_list.project_id: must match {project_id!r}")
    timeline_rate = require_text(shot_list, "timeline_frame_rate", "shot_list", errors)
    shots = shot_list.get("shots")
    shot_ids = unique_ids(shots, "shot_id", "shot_list.shots", errors)
    for index, shot in enumerate(shots if isinstance(shots, list) else []):
        if not isinstance(shot, dict):
            continue
        prefix = f"shot_list.shots[{index}]"
        scene_id = shot.get("scene_id")
        shot_id = shot.get("shot_id")
        if scene_id not in scene_ids:
            errors.append(f"{prefix}.scene_id: not present in script breakdown")
        elif shot_id not in planned_by_scene.get(str(scene_id), set()):
            errors.append(f"{prefix}.shot_id: not planned by scene {scene_id!r}")
        for beat_id in list_of_text(shot.get("beat_ids"), f"{prefix}.beat_ids", errors):
            if beat_id not in beat_ids:
                errors.append(f"{prefix}.beat_ids: unknown {beat_id!r}")
        for field in ("setup_id", "purpose", "continuity_mode", "shot_size", "storyboard_reference"):
            require_text(shot, field, prefix, errors)
        duration = shot.get("target_duration_frames")
        if not isinstance(duration, int) or duration <= 0:
            errors.append(f"{prefix}.target_duration_frames: must be a positive integer")
        for field in ("head_handle_frames", "tail_handle_frames"):
            value = shot.get(field)
            if not isinstance(value, int) or value < 0:
                errors.append(f"{prefix}.{field}: must be a non-negative integer")

    for scene_id, planned in planned_by_scene.items():
        missing = planned - shot_ids
        if missing:
            errors.append(f"shot_list.shots: scene {scene_id!r} is missing planned shots {sorted(missing)}")

    if animatic.get("project_id") != project_id:
        errors.append(f"animatic.project_id: must match {project_id!r}")
    if animatic.get("timeline_frame_rate") != timeline_rate:
        errors.append("animatic.timeline_frame_rate: must match shot list")
    require_text(animatic, "timeline_start_timecode", "animatic", errors)
    clips = animatic.get("clips")
    clip_shot_ids = unique_ids(clips, "shot_id", "animatic.clips", errors)
    for index, clip in enumerate(clips if isinstance(clips, list) else []):
        if not isinstance(clip, dict):
            continue
        prefix = f"animatic.clips[{index}]"
        if clip.get("shot_id") not in shot_ids:
            errors.append(f"{prefix}.shot_id: not present in shot list")
        start = clip.get("timeline_in_frame")
        end = clip.get("timeline_out_frame_exclusive")
        if not isinstance(start, int) or start < 0 or not isinstance(end, int) or end <= start:
            errors.append(f"{prefix}: timeline frame range must be positive and exclusive-out")
    missing_clips = shot_ids - clip_shot_ids
    if missing_clips:
        errors.append(f"animatic.clips: missing shots {sorted(missing_clips)}")

    require_text(model_profile, "provider", "model_profile", errors)
    require_text(model_profile, "model_id", "model_profile", errors)
    require_text(model_profile, "profile_version", "model_profile", errors)
    require_text(model_profile, "verified_at", "model_profile", errors)
    evidence = model_profile.get("verification_evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("model_profile.verification_evidence: required non-empty list")
    frame_rates = model_profile.get("outputs", {}).get("frame_rates") if isinstance(model_profile.get("outputs"), dict) else None
    if isinstance(frame_rates, list) and timeline_rate and timeline_rate not in frame_rates:
        warnings.append(
            "model_profile.outputs.frame_rates: timeline rate is not declared; plan deterministic normalization before edit"
        )

    if target == "production":
        if breakdown.get("status") != "APPROVED":
            errors.append("script_breakdown.status: must be APPROVED for production")
        for index, plan in enumerate(scene_plans):
            if plan.get("status") != "APPROVED":
                errors.append(f"scene_plan[{index}].status: must be APPROVED for production")
            approval = plan.get("approval")
            if not isinstance(approval, dict) or approval.get("status") != "PASS":
                errors.append(f"scene_plan[{index}].approval.status: must be PASS for production")
        if shot_list.get("status") != "APPROVED":
            errors.append("shot_list.status: must be APPROVED for production")
        if animatic.get("status") != "LOCKED_FOR_PRODUCTION":
            errors.append("animatic.status: must be LOCKED_FOR_PRODUCTION")
        review = animatic.get("review")
        for field in (
            "story_readability", "timing_and_pacing", "performance_space",
            "audio_continuity", "coverage_complete",
        ):
            if not isinstance(review, dict) or review.get(field) != "PASS":
                errors.append(f"animatic.review.{field}: must be PASS for production")
        if not isinstance(review, dict) or not text(review.get("evidence")):
            errors.append("animatic.review.evidence: required for production")
        if model_profile.get("verification_status") != "VERIFIED":
            errors.append("model_profile.verification_status: must be VERIFIED for production")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script-breakdown", type=Path, required=True)
    parser.add_argument("--scene-plan", type=Path, action="append", required=True)
    parser.add_argument("--scene-asset-package", type=Path, action="append", required=True)
    parser.add_argument("--shot-list", type=Path, required=True)
    parser.add_argument("--animatic", type=Path, required=True)
    parser.add_argument("--model-profile", type=Path, required=True)
    parser.add_argument("--target", choices=("previs", "production"), default="production")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        breakdown = load(args.script_breakdown)
        scene_plans = [load(path) for path in args.scene_plan]
        scene_asset_packages = [load(path) for path in args.scene_asset_package]
        shot_list = load(args.shot_list)
        animatic = load(args.animatic)
        model_profile = load(args.model_profile)
    except ValueError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate(
        breakdown, scene_plans, scene_asset_packages, shot_list, animatic, model_profile, args.target
    )
    payload = {
        "status": "BLOCKED" if errors else "PASS",
        "target": args.target,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        print(f"BLOCKED: preproduction package has {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
        for warning in warnings:
            print(f"WARN: {warning}")
    else:
        print(f"PASS: preproduction package is ready for {args.target}")
        for warning in warnings:
            print(f"WARN: {warning}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
