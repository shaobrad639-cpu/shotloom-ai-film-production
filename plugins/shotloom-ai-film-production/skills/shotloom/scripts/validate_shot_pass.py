#!/usr/bin/env python3
"""Validate a film-structured AI-video shot pass and optionally stamp its state."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_asset_manifest  # noqa: E402  (co-located helper script)


SCHEMA_VERSION = 16
VALIDATOR_VERSION = "2.8.0"
GATE_STATUSES = {"NOT_RUN", "IN_PROGRESS", "PASS", "BLOCKED", "N/A"}
PASS_OR_NA = {"PASS", "N/A"}
SHOT_STATUSES = {
    "DRAFT", "BLOCKED", "READY_FOR_PREVIS", "PREVIS", "READY_FOR_RELEASE",
    "GREENLIT", "EDIT_READY", "ACCEPTED", "REJECTED", "SUPERSEDED",
}
STATUS_RANK = {
    "SUPERSEDED": -1, "REJECTED": -1, "DRAFT": 0, "BLOCKED": 0,
    "READY_FOR_PREVIS": 1, "PREVIS": 1, "READY_FOR_RELEASE": 2,
    "GREENLIT": 3, "EDIT_READY": 4, "ACCEPTED": 5,
}
TARGET_RANK = {"previs": 1, "release": 3, "edit-ready": 4, "acceptance": 5}
REOPENABLE = {"REJECTED", "SUPERSEDED"}
REQUIRED_GATES = {
    "previs": (
        "gate_1_script_edit_action", "gate_2_assets_scene_space_props",
        "gate_2b_environment_dynamics",
        "gate_3_blocking_camera_sound",
    ),
    "release": (
        "gate_1_script_edit_action", "gate_2_assets_scene_space_props",
        "gate_2b_environment_dynamics",
        "gate_3_blocking_camera_sound", "gate_4_key_states_previs", "gate_5a_release",
    ),
    "edit-ready": (
        "gate_1_script_edit_action", "gate_2_assets_scene_space_props",
        "gate_2b_environment_dynamics",
        "gate_3_blocking_camera_sound", "gate_4_key_states_previs", "gate_5a_release",
    ),
    "acceptance": (
        "gate_1_script_edit_action", "gate_2_assets_scene_space_props",
        "gate_2b_environment_dynamics",
        "gate_3_blocking_camera_sound", "gate_4_key_states_previs",
        "gate_5a_release", "gate_5b_acceptance",
    ),
}
CONTINUITY_MODES = {"EDITORIAL_SHOT", "CONTINUOUS_TAKE"}
RELATIONS = {"SCENE_START", "EDITORIAL_CUT", "CONTINUOUS_SEGMENT", "INDEPENDENT"}
PICTURE_MODES = {
    "EXACT_PLATE_COMPOSITE", "STRUCTURAL_ANCHOR_CHECK",
    "GEOMETRY_REPROJECTED", "N/A",
}
TRANSLATIONS = {"none", "dolly", "truck", "pedestal", "crane", "orbit", "tracking", "handheld_path"}
ROTATIONS = {"none", "pan", "tilt", "roll", "combined"}
LENS_CHANGES = {"none", "zoom_in", "zoom_out", "focus_pull", "iris_change", "combined"}
PRODUCTION_MODES = {"STANDARD", "EFFICIENT_SHORT"}
RISK_TIERS = {"L1", "L2", "L3", "L4"}
PRODUCTION_ROUTES = {
    "DIRECT_REFERENCE_VIDEO", "PLATE_PLUS_VIDEO_COMPOSITE",
    "KEYFRAME_GUIDED_VIDEO", "RIG_OR_3D_CONTROLLED",
}
REFERENCE_STRATEGIES = {
    "FIRST_FRAME_ONLY", "FIRST_AND_LAST", "MULTI_KEYFRAME",
    "VIDEO_REFERENCE", "COMPOSITE_INPUT",
}
SECONDARY_SUBJECT_TREATMENTS = {
    "FIXED_COMPOSITE", "MASKED_LOCAL_MOTION", "SEPARATE_PASS", "JOINT_GENERATION",
}
DURATION_CONTROL_MODES = {"MODEL_NATIVE_THEN_SELECT", "TARGET_DURATION_IF_SUPPORTED"}
ASSET_PARTICIPATION_MODES = {
    "DIRECT_MODEL_INPUT", "ASSEMBLED_IN_INPUT", "VIDEO_REFERENCE",
    "FIXED_COMPOSITE", "MASKED_LOCAL_EDIT", "SEPARATE_PASS", "POST_COMPOSITE",
}
MODEL_INPUT_STRATEGIES = {
    "DIRECT_MULTI_REFERENCE", "ASSEMBLED_KEYFRAME", "VIDEO_REFERENCE",
    "SEGMENTED_COMPOSITE", "FIXED_PLATE_COMPOSITE", "HYBRID",
}
MODEL_INPUT_TYPES = {"TEXT", "IMAGE", "VIDEO", "AUDIO", "CONTROL_DATA"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def get(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def require_text(data: dict[str, Any], dotted: str, errors: list[str]) -> None:
    value = get(data, dotted)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{dotted}: must be non-empty text")


def require_list(data: dict[str, Any], dotted: str, errors: list[str], *, nonempty: bool = False) -> list[Any]:
    value = get(data, dotted)
    if not isinstance(value, list):
        errors.append(f"{dotted}: must be a list")
        return []
    if nonempty and not value:
        errors.append(f"{dotted}: must not be empty")
    return value


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_base(data: dict[str, Any], errors: list[str]) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version: expected {SCHEMA_VERSION}")
    for dotted in (
        "shot.project_id", "shot.sequence_id", "shot.scene_id", "shot.shot_id",
        "shot.setup_id", "shot.take_id", "shot.pass_version",
        "shot.shot_purpose", "asset_baselines.scene", "state_transition.entry_state",
        "state_transition.exit_state",
    ):
        require_text(data, dotted, errors)
    if get(data, "shot.status") not in SHOT_STATUSES:
        errors.append(f"shot.status: unsupported value {get(data, 'shot.status')!r}")
    if get(data, "shot.continuity_mode") not in CONTINUITY_MODES:
        errors.append("shot.continuity_mode: must be EDITORIAL_SHOT or CONTINUOUS_TAKE")
    if get(data, "shot.continuity_mode") == "CONTINUOUS_TAKE":
        require_text(data, "shot.segment_id", errors)
    if get(data, "shot.relation_from_previous") not in RELATIONS:
        errors.append("shot.relation_from_previous: unsupported value")
    duration = get(data, "shot.duration_seconds")
    if not finite_number(duration) or duration <= 0:
        errors.append("shot.duration_seconds: must be greater than zero")
    sequence_index = get(data, "shot.segment_sequence_index")
    if not isinstance(sequence_index, int) or isinstance(sequence_index, bool) or sequence_index < 1:
        errors.append("shot.segment_sequence_index: must be a positive integer")
    require_list(data, "asset_baselines.characters", errors)
    require_list(data, "asset_baselines.props", errors)
    require_list(data, "state_transition.action_beats", errors, nonempty=True)
    require_list(data, "constraints.allowed_changes", errors)
    require_list(data, "constraints.prohibited_changes", errors, nonempty=True)
    require_list(data, "constraints.critical_open_questions", errors)
    require_list(data, "constraints.approved_assumptions", errors)
    require_list(data, "constraints.new_assets", errors)
    require_list(data, "prop_transitions", errors)

    gates = data.get("gates")
    if not isinstance(gates, dict):
        errors.append("gates: must be an object")
        return
    for gate_name in REQUIRED_GATES["acceptance"]:
        gate = gates.get(gate_name)
        if not isinstance(gate, dict):
            errors.append(f"gates.{gate_name}: missing")
            continue
        status = gate.get("status")
        if status not in GATE_STATUSES:
            errors.append(f"gates.{gate_name}.status: unsupported value {status!r}")
        if status in {"PASS", "N/A"} and not str(gate.get("evidence", "")).strip():
            errors.append(f"gates.{gate_name}.evidence: required for {status}")
        if status in {"BLOCKED", "N/A"} and not str(gate.get("reason", "")).strip():
            errors.append(f"gates.{gate_name}.reason: required for {status}")


def validate_production_plan(data: dict[str, Any], errors: list[str]) -> None:
    if get(data, "production_plan.status") != "PASS":
        errors.append("production_plan.status: must be PASS")
    for dotted in (
        "production_plan.project_brief_reference", "production_plan.editorial_intent",
        "production_plan.model_risk_review_reference", "production_plan.visual_direction_reference",
        "production_plan.audio_intent",
    ):
        require_text(data, dotted, errors)
    require_list(data, "production_plan.action_beats", errors, nonempty=True)


def validate_production_strategy(data: dict[str, Any], errors: list[str]) -> None:
    strategy = data.get("production_strategy")
    if not isinstance(strategy, dict) or strategy.get("status") != "PASS":
        errors.append("production_strategy.status: must be PASS")
        return
    if strategy.get("mode") not in PRODUCTION_MODES:
        errors.append(f"production_strategy.mode: expected one of {sorted(PRODUCTION_MODES)}")
    risk_tier = strategy.get("risk_tier")
    if risk_tier not in RISK_TIERS:
        errors.append(f"production_strategy.risk_tier: expected one of {sorted(RISK_TIERS)}")
    route = strategy.get("production_route")
    if route not in PRODUCTION_ROUTES:
        errors.append(f"production_strategy.production_route: expected one of {sorted(PRODUCTION_ROUTES)}")
    for field in ("route_version", "route_rationale"):
        require_text(data, f"production_strategy.{field}", errors)
    if strategy.get("change_review_status") != "PASS":
        errors.append("production_strategy.change_review_status: must be PASS")
    inherited = require_list(data, "production_strategy.inherited_locked_items", errors)
    require_list(data, "production_strategy.changed_items", errors)
    impacted = require_list(data, "production_strategy.impacted_checks", errors)
    if not isinstance(strategy.get("full_rereview_required"), bool):
        errors.append("production_strategy.full_rereview_required: must be boolean")
    elif strategy.get("full_rereview_required") is False:
        if not inherited:
            errors.append("production_strategy.inherited_locked_items: change-only review requires locked baselines")
        if not impacted:
            errors.append("production_strategy.impacted_checks: change-only review requires impact scope")

    core_required = strategy.get("core_test_required")
    if not isinstance(core_required, bool):
        errors.append("production_strategy.core_test_required: must be boolean")
    efficient_higher_risk = strategy.get("mode") == "EFFICIENT_SHORT" and risk_tier in {"L2", "L3", "L4"}
    if efficient_higher_risk and core_required is not True:
        errors.append("production_strategy.core_test_required: efficient L2-L4 shots require a core-risk test")
    if core_required is True:
        if strategy.get("core_test_status") != "PASS":
            errors.append("production_strategy.core_test_status: required core-risk test must PASS")
        duration = strategy.get("core_test_duration_seconds")
        if not finite_number(duration) or duration <= 0:
            errors.append("production_strategy.core_test_duration_seconds: must be greater than zero")
        for field in ("core_test_reference", "core_test_evidence"):
            require_text(data, f"production_strategy.{field}", errors)
        require_list(data, "production_strategy.core_test_acceptance_criteria", errors, nonempty=True)
    elif core_required is False:
        if strategy.get("core_test_status") != "N/A":
            errors.append("production_strategy.core_test_status: non-required test must be N/A")
        require_text(data, "production_strategy.core_test_reason", errors)
    if route == "RIG_OR_3D_CONTROLLED":
        require_text(data, "production_strategy.rig_or_3d_justification", errors)

    reference_strategy = strategy.get("reference_strategy")
    if reference_strategy not in REFERENCE_STRATEGIES:
        errors.append(
            f"production_strategy.reference_strategy: expected one of {sorted(REFERENCE_STRATEGIES)}"
        )
    require_text(data, "production_strategy.minimum_reference_reason", errors)
    if not isinstance(strategy.get("precise_exit_control_required"), bool):
        errors.append("production_strategy.precise_exit_control_required: must be boolean")
    require_list(data, "production_strategy.primary_motion_subjects", errors, nonempty=True)
    secondary = require_list(data, "production_strategy.secondary_subject_treatments", errors)
    joint_generation = False
    for index, item in enumerate(secondary):
        prefix = f"production_strategy.secondary_subject_treatments[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        for field in ("subject_id", "reason"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field}: required")
        treatment = item.get("treatment")
        if treatment not in SECONDARY_SUBJECT_TREATMENTS:
            errors.append(f"{prefix}.treatment: unsupported value")
        joint_generation = joint_generation or treatment == "JOINT_GENERATION"
    if not isinstance(strategy.get("model_multi_subject_identity_verified"), bool):
        errors.append("production_strategy.model_multi_subject_identity_verified: must be boolean")
    if secondary:
        require_text(data, "production_strategy.multi_subject_plan_evidence", errors)
    if joint_generation and strategy.get("model_multi_subject_identity_verified") is not True:
        errors.append(
            "production_strategy.model_multi_subject_identity_verified: JOINT_GENERATION requires verified identity reliability"
        )


def validate_asset_identity(data: dict[str, Any], target: str, errors: list[str]) -> None:
    lock = data.get("asset_identity_lock")
    if not isinstance(lock, dict):
        errors.append("asset_identity_lock: required")
        return
    if target == "previs" and lock.get("status") != "PASS":
        return
    if lock.get("status") != "PASS":
        errors.append("asset_identity_lock.status: formal release requires PASS")
    for dotted in (
        "asset_identity_lock.manifest_reference", "asset_identity_lock.manifest_validation_reference",
    ):
        require_text(data, dotted, errors)
    digest = lock.get("manifest_digest_sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        errors.append("asset_identity_lock.manifest_digest_sha256: must be lowercase SHA-256")
    assets = require_list(data, "asset_identity_lock.assets", errors, nonempty=True)
    for index, asset in enumerate(assets):
        prefix = f"asset_identity_lock.assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        for field in ("asset_id", "asset_type", "version", "reference", "file", "sha256"):
            if not isinstance(asset.get(field), str) or not asset[field].strip():
                errors.append(f"{prefix}.{field}: required")
        if asset.get("status") != "ACCEPTED":
            errors.append(f"{prefix}.status: must be ACCEPTED")
        sha = asset.get("sha256")
        if isinstance(sha, str) and not SHA256_RE.fullmatch(sha):
            errors.append(f"{prefix}.sha256: invalid")


def validate_asset_usage(data: dict[str, Any], target: str, errors: list[str]) -> None:
    """Prove approved assets actually participate in generation or controlled compositing."""
    if target == "previs":
        return
    audit = data.get("asset_usage_audit")
    if not isinstance(audit, dict) or audit.get("status") != "PASS":
        errors.append("asset_usage_audit.status: formal generation requires PASS")
        return
    for dotted in (
        "asset_usage_audit.shot_asset_map_reference",
        "asset_usage_audit.assembly_record_reference",
        "asset_usage_audit.model_capability_profile_reference",
        "asset_usage_audit.model_input_manifest_reference",
        "asset_usage_audit.capability_fit_evidence",
    ):
        require_text(data, dotted, errors)
    if audit.get("unique_baselines_status") != "PASS":
        errors.append("asset_usage_audit.unique_baselines_status: must be PASS")
    if audit.get("all_visible_entities_mapped") is not True:
        errors.append("asset_usage_audit.all_visible_entities_mapped: must be true")
    if audit.get("capability_fit_status") != "PASS":
        errors.append("asset_usage_audit.capability_fit_status: must be PASS")
    if audit.get("model_input_strategy") not in MODEL_INPUT_STRATEGIES:
        errors.append("asset_usage_audit.model_input_strategy: unsupported value")

    locked_assets = {
        item.get("reference")
        for item in get(data, "asset_identity_lock.assets") or []
        if isinstance(item, dict) and item.get("status") == "ACCEPTED"
    }
    model_inputs = require_list(data, "asset_usage_audit.model_received_inputs", errors, nonempty=True)
    received_references: set[str] = set()
    for index, item in enumerate(model_inputs):
        prefix = f"asset_usage_audit.model_received_inputs[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        for field in ("input_id", "reference", "purpose", "evidence"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field}: required")
        if item.get("input_type") not in MODEL_INPUT_TYPES:
            errors.append(f"{prefix}.input_type: unsupported value")
        if item.get("verified_received") is not True:
            errors.append(f"{prefix}.verified_received: must be true")
        reference = item.get("reference")
        if isinstance(reference, str) and reference.strip():
            received_references.add(reference)

    source_assets = require_list(data, "asset_usage_audit.source_assets", errors, nonempty=True)
    covered: set[str] = set()
    transmitted_modes = {"DIRECT_MODEL_INPUT", "ASSEMBLED_IN_INPUT", "VIDEO_REFERENCE"}
    for index, item in enumerate(source_assets):
        prefix = f"asset_usage_audit.source_assets[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        for field in (
            "asset_reference", "asset_type", "role_in_shot", "actual_input_reference", "evidence",
        ):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field}: required")
        reference = item.get("asset_reference")
        if isinstance(reference, str) and reference.strip():
            covered.add(reference)
            if reference not in locked_assets:
                errors.append(f"{prefix}.asset_reference: {reference!r} is not an ACCEPTED locked asset")
        if item.get("approved_status") != "PASS":
            errors.append(f"{prefix}.approved_status: must be PASS")
        mode = item.get("participation_mode")
        if mode not in ASSET_PARTICIPATION_MODES:
            errors.append(f"{prefix}.participation_mode: unsupported value")
        actual_input = item.get("actual_input_reference")
        if mode in transmitted_modes and actual_input not in received_references:
            errors.append(
                f"{prefix}.actual_input_reference: transmitted asset is absent from model_received_inputs"
            )

    baselines: set[str] = set()
    scene = get(data, "asset_baselines.scene")
    if isinstance(scene, str) and scene.strip():
        baselines.add(scene)
    for dotted in ("asset_baselines.characters", "asset_baselines.props"):
        baselines.update(value for value in (get(data, dotted) or []) if isinstance(value, str) and value)
    missing = sorted(baselines - covered)
    if missing:
        errors.append(f"asset_usage_audit.source_assets: missing baseline participation for {missing}")

    transformed = require_list(data, "asset_usage_audit.new_or_transformed_entities", errors)
    for index, item in enumerate(transformed):
        prefix = f"asset_usage_audit.new_or_transformed_entities[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        for field in (
            "entity_id", "approved_visual_reference", "introduction_state",
            "actual_input_reference", "evidence",
        ):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field}: required")
        visual_reference = item.get("approved_visual_reference")
        if isinstance(visual_reference, str) and visual_reference not in locked_assets:
            errors.append(f"{prefix}.approved_visual_reference: must be an ACCEPTED locked visual asset")
        mode = item.get("participation_mode")
        if mode not in ASSET_PARTICIPATION_MODES:
            errors.append(f"{prefix}.participation_mode: unsupported value")
        actual_input = item.get("actual_input_reference")
        if mode in transmitted_modes and actual_input not in received_references:
            errors.append(f"{prefix}.actual_input_reference: absent from model_received_inputs")

    constraints = require_list(data, "asset_usage_audit.untransmitted_constraints", errors)
    for index, item in enumerate(constraints):
        prefix = f"asset_usage_audit.untransmitted_constraints[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        for field in ("constraint", "reason_not_directly_transmitted", "verification_method", "risk_treatment"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field}: required")

    if target in {"edit-ready", "acceptance"}:
        if audit.get("post_generation_asset_comparison_status") != "PASS":
            errors.append(
                "asset_usage_audit.post_generation_asset_comparison_status: edit-ready/acceptance requires PASS"
            )
        require_text(data, "asset_usage_audit.post_generation_asset_comparison_reference", errors)


def validate_scene_and_space(data: dict[str, Any], target: str, errors: list[str]) -> None:
    lock = data.get("scene_asset_lock")
    if not isinstance(lock, dict) or lock.get("status") != "PASS":
        errors.append("scene_asset_lock.status: must be PASS")
    else:
        for dotted in (
            "scene_asset_lock.scene_asset_bundle_reference",
            "scene_asset_lock.spatial_master_reference",
            "scene_asset_lock.background_geometry_or_render_reference",
        ):
            require_text(data, dotted, errors)
        if lock.get("production_method") not in PICTURE_MODES - {"N/A"}:
            errors.append("scene_asset_lock.production_method: unsupported value")
        if lock.get("uncontrolled_scene_regeneration") is not False:
            errors.append("scene_asset_lock.uncontrolled_scene_regeneration: must be false")

    spatial = data.get("spatial_lock")
    if not isinstance(spatial, dict):
        errors.append("spatial_lock: required")
        return
    if spatial.get("status") == "N/A":
        if not str(spatial.get("reason", "")).strip():
            errors.append("spatial_lock.reason: required for N/A")
        return
    if spatial.get("status") != "PASS":
        errors.append("spatial_lock.status: must be PASS or N/A")
        return
    for dotted in (
        "spatial_lock.coordinate_system.layout_version",
        "spatial_lock.coordinate_system.origin", "spatial_lock.coordinate_system.axes",
    ):
        require_text(data, dotted, errors)
    if get(data, "spatial_lock.coordinate_system.unit") not in {"m", "cm", "mm"}:
        errors.append("spatial_lock.coordinate_system.unit: must be m, cm, or mm")
    for field in ("fixed_equipment", "relative_scale_checks", "reachability_checks"):
        require_list(data, f"spatial_lock.{field}", errors)
    for index, check in enumerate(spatial.get("reachability_checks", [])):
        if not isinstance(check, dict):
            errors.append(f"spatial_lock.reachability_checks[{index}]: must be an object")
            continue
        if check.get("status") not in PASS_OR_NA:
            errors.append(f"spatial_lock.reachability_checks[{index}].status: must be PASS or N/A")


def validate_camera(data: dict[str, Any], errors: list[str]) -> None:
    camera = data.get("camera_plan")
    if not isinstance(camera, dict) or camera.get("status") != "PASS":
        errors.append("camera_plan.status: must be PASS")
        return
    for field in (
        "shot_size", "camera_height_and_angle", "focal_length_or_fov",
        "capture_rate_and_shutter", "exposure_and_white_balance", "focus_plan",
        "depth_of_field", "start_framing", "end_framing", "path", "direction",
        "speed_curve", "subject_lock", "parallax_expected", "motivation", "post_process",
    ):
        if not isinstance(camera.get(field), str) or not camera[field].strip():
            errors.append(f"camera_plan.{field}: required")
    if not isinstance(camera.get("position_moves"), bool):
        errors.append("camera_plan.position_moves: must be boolean")
    translation = camera.get("translation")
    if translation not in TRANSLATIONS:
        errors.append("camera_plan.translation: unsupported value")
    elif camera.get("position_moves") is False and translation != "none":
        errors.append("camera_plan.translation: must be none when position_moves is false")
    elif camera.get("position_moves") is True and translation == "none":
        errors.append("camera_plan.translation: must describe position movement")
    if camera.get("rotation") not in ROTATIONS:
        errors.append("camera_plan.rotation: unsupported value")
    if camera.get("lens_change") not in LENS_CHANGES:
        errors.append("camera_plan.lens_change: unsupported value")


def validate_continuity(data: dict[str, Any], errors: list[str]) -> None:
    continuity = data.get("continuity")
    if not isinstance(continuity, dict) or continuity.get("status") != "PASS":
        errors.append("continuity.status: must be PASS")
        return
    require_text(data, "continuity.editorial_intent", errors)
    require_text(data, "continuity.evidence", errors)
    for field in (
        "axis_status", "eyeline_status", "screen_direction_status", "match_on_action_status",
        "lighting_color_status", "audio_bridge_status",
    ):
        if continuity.get(field) not in PASS_OR_NA:
            errors.append(f"continuity.{field}: must be PASS or N/A")

    mode = get(data, "shot.continuity_mode")
    relation = get(data, "shot.relation_from_previous")
    index = get(data, "shot.segment_sequence_index")
    if mode == "EDITORIAL_SHOT":
        if relation == "CONTINUOUS_SEGMENT":
            errors.append("shot.relation_from_previous: editorial shot cannot be CONTINUOUS_SEGMENT")
        if str(get(data, "shot.segment_id") or "").strip():
            errors.append("shot.segment_id: must be empty for EDITORIAL_SHOT")
        if index != 1:
            errors.append("shot.segment_sequence_index: must be 1 for EDITORIAL_SHOT")
        if continuity.get("merge_with_previous_segment") is not False:
            errors.append("continuity.merge_with_previous_segment: must be false for EDITORIAL_SHOT")
        if continuity.get("actual_tail_required") is not False:
            errors.append("continuity.actual_tail_required: must be false for EDITORIAL_SHOT")
        if relation == "EDITORIAL_CUT":
            previous = continuity.get("previous_shot_id")
            if not isinstance(previous, str) or not previous.strip():
                errors.append("continuity.previous_shot_id: required for EDITORIAL_CUT")
            elif previous == get(data, "shot.shot_id"):
                errors.append("continuity.previous_shot_id: must differ from shot_id for EDITORIAL_CUT")
            for dotted in (
                "continuity.previous_actual_video_reference",
                "continuity.previous_actual_tail_reference",
                "continuity.previous_tail_motion_summary",
            ):
                require_text(data, dotted, errors)
            for field in (
                "entry_design_from_actual_tail_status", "entry_position_status",
                "motion_direction_status", "motion_speed_status",
                "impact_or_interaction_region_status",
            ):
                if continuity.get(field) not in PASS_OR_NA:
                    errors.append(f"continuity.{field}: EDITORIAL_CUT requires PASS or N/A")
        return

    if not isinstance(continuity.get("is_take_start"), bool):
        errors.append("continuity.is_take_start: must be boolean")
    previous = continuity.get("previous_shot_id")
    if relation == "CONTINUOUS_SEGMENT":
        if previous != get(data, "shot.shot_id"):
            errors.append("continuity.previous_shot_id: CONTINUOUS_SEGMENT must continue the same shot_id")
    elif relation == "EDITORIAL_CUT":
        if not isinstance(previous, str) or not previous.strip():
            errors.append("continuity.previous_shot_id: required for EDITORIAL_CUT")
        elif previous == get(data, "shot.shot_id"):
            errors.append("continuity.previous_shot_id: must differ from shot_id for EDITORIAL_CUT")
    if index == 1:
        if continuity.get("is_take_start") is not True:
            errors.append("continuity.is_take_start: first continuous segment must be true")
        if relation not in {"SCENE_START", "INDEPENDENT", "EDITORIAL_CUT"}:
            errors.append("shot.relation_from_previous: invalid for continuous take start")
        if continuity.get("merge_with_previous_segment") is not False:
            errors.append("continuity.merge_with_previous_segment: first segment must be false")
        if continuity.get("actual_tail_required") is not False:
            errors.append("continuity.actual_tail_required: take start must be false")
    elif isinstance(index, int):
        if relation != "CONTINUOUS_SEGMENT":
            errors.append("shot.relation_from_previous: later continuous segments require CONTINUOUS_SEGMENT")
        if continuity.get("is_take_start") is not False:
            errors.append("continuity.is_take_start: later continuous segment must be false")
        if continuity.get("merge_with_previous_segment") is not True:
            errors.append("continuity.merge_with_previous_segment: later segment must be true")
        if continuity.get("actual_tail_required") is not True:
            errors.append("continuity.actual_tail_required: later segment must be true")
        for dotted in (
            "continuity.previous_tail_asset_version", "continuity.previous_tail_validation_reference",
            "continuity.previous_tail_window_reference", "continuity.previous_actual_video_reference",
            "continuity.previous_actual_tail_reference", "continuity.previous_tail_motion_summary",
        ):
            require_text(data, dotted, errors)
        if continuity.get("previous_tail_acceptance_status") != "PASS":
            errors.append("continuity.previous_tail_acceptance_status: must be PASS")
        if continuity.get("planned_keyframe_used_as_substitute") is not False:
            errors.append("continuity.planned_keyframe_used_as_substitute: must be false")
        for field in (
            "camera_end_to_start_status", "action_phase_status",
            "audio_phase_status", "environment_phase_status",
            "entry_design_from_actual_tail_status", "entry_position_status",
            "motion_direction_status", "motion_speed_status",
            "impact_or_interaction_region_status",
        ):
            if continuity.get(field) not in PASS_OR_NA:
                errors.append(f"continuity.{field}: must be PASS or N/A")
    if continuity.get("editorial_cuts") != 0:
        errors.append("continuity.editorial_cuts: CONTINUOUS_TAKE must have zero cuts")
    gap = continuity.get("temporal_gap_seconds")
    if not finite_number(gap) or abs(gap) > 1e-9:
        errors.append("continuity.temporal_gap_seconds: CONTINUOUS_TAKE must have zero gap")


def validate_picture_lock(data: dict[str, Any], target: str, errors: list[str]) -> None:
    lock = data.get("picture_lock")
    if not isinstance(lock, dict):
        errors.append("picture_lock: required")
        return
    mode = lock.get("mode")
    if mode not in PICTURE_MODES:
        errors.append("picture_lock.mode: unsupported value")
        return
    if target == "previs" and lock.get("status") in {"PASS", "N/A", "IN_PROGRESS", "NOT_RUN"}:
        return
    if lock.get("status") != "PASS":
        errors.append("picture_lock.status: formal release requires PASS")
    if lock.get("uncontrolled_full_frame_regeneration") is not False:
        errors.append("picture_lock.uncontrolled_full_frame_regeneration: must be false")
    if mode == "EXACT_PLATE_COMPOSITE":
        require_text(data, "picture_lock.background_plate_reference", errors)
        require_list(data, "picture_lock.allowed_change_masks", errors, nonempty=True)
        if lock.get("protected_match_target") != 1.0:
            errors.append("picture_lock.protected_match_target: exact plate composite requires 1.0")
        require_list(data, "picture_lock.comparison_pairs", errors, nonempty=True)
    elif mode in {"STRUCTURAL_ANCHOR_CHECK", "GEOMETRY_REPROJECTED"}:
        require_text(data, "picture_lock.anchor_or_geometry_report_reference", errors)


def validate_environment(data: dict[str, Any], target: str, errors: list[str]) -> None:
    env = data.get("environment_animation")
    if not isinstance(env, dict):
        errors.append("environment_animation: required")
        return
    status = env.get("status")
    if status == "N/A":
        if not str(env.get("reason", "")).strip():
            errors.append("environment_animation.reason: required for N/A")
        if env.get("environment_only_previs_status") != "N/A":
            errors.append("environment_animation.environment_only_previs_status: N/A environment requires N/A")
        if env.get("reaction_coupling_status") != "N/A":
            errors.append("environment_animation.reaction_coupling_status: N/A environment requires N/A")
        return
    if status != "PASS":
        errors.append("environment_animation.status: must be PASS or N/A")
        return
    require_text(data, "environment_animation.scene_dynamic_control_reference", errors)
    require_text(data, "environment_animation.environment_only_previs_reference", errors)
    if env.get("environment_only_previs_status") != "PASS":
        errors.append("environment_animation.environment_only_previs_status: dynamic environment requires PASS")
    require_list(data, "environment_animation.registered_regions", errors, nonempty=True)
    for field in ("motion_direction", "motion_intensity", "entry_phase", "exit_phase"):
        require_text(data, f"environment_animation.{field}", errors)
    if env.get("loop_reset_forbidden") is not True:
        errors.append("environment_animation.loop_reset_forbidden: must be true")
    coupling_status = env.get("reaction_coupling_status")
    if coupling_status == "PASS":
        couplings = require_list(data, "environment_animation.reaction_couplings", errors, nonempty=True)
        for index, coupling in enumerate(couplings):
            prefix = f"environment_animation.reaction_couplings[{index}]"
            if not isinstance(coupling, dict):
                errors.append(f"{prefix}: must be an object")
                continue
            for field in ("trigger", "target_region_id", "expected_response", "delay_or_phase", "falloff_or_extent"):
                if not isinstance(coupling.get(field), str) or not coupling[field].strip():
                    errors.append(f"{prefix}.{field}: required")
    elif coupling_status == "N/A":
        require_text(data, "environment_animation.reaction_coupling_reason", errors)
    else:
        errors.append("environment_animation.reaction_coupling_status: must be PASS or N/A")
    if target == "acceptance":
        if env.get("environment_motion_check") != "PASS":
            errors.append("environment_animation.environment_motion_check: acceptance requires PASS")
        if env.get("freeze_check") != "PASS" or env.get("static_drift_check") != "PASS":
            errors.append("environment_animation: acceptance requires freeze and static-drift PASS")
        expected_reaction = "PASS" if coupling_status == "PASS" else "N/A"
        if env.get("reaction_check") != expected_reaction:
            errors.append(
                "environment_animation.reaction_check: must match reaction_coupling_status "
                f"({expected_reaction})"
            )
        require_text(data, "environment_animation.evidence", errors)
        require_text(data, "environment_animation.full_shot_evidence", errors)


def validate_release_inputs(data: dict[str, Any], errors: list[str]) -> None:
    review = data.get("preflight_review")
    if not isinstance(review, dict) or review.get("status") != "PASS":
        errors.append("preflight_review.status: release requires PASS")
    else:
        if review.get("context_mode") not in {"STANDARD_REVIEW", "COLD_REVIEW"}:
            errors.append("preflight_review.context_mode: unsupported value")
        require_text(data, "preflight_review.report_reference", errors)
        for field in (
            "script_visual_alignment", "asset_direction_check", "output_contract_check", "environment_motion_check",
            "subject_environment_causality_check", "camera_editing_check",
            "physical_action_check", "sound_check",
        ):
            if review.get(field) not in PASS_OR_NA:
                errors.append(f"preflight_review.{field}: must be PASS or N/A")

    cost = data.get("cost_control")
    if not isinstance(cost, dict) or cost.get("status") != "PASS":
        errors.append("cost_control.status: release requires PASS")
    elif cost.get("external_paid_generation") is True:
        require_text(data, "cost_control.estimate_reference", errors)
        if cost.get("user_spend_approval") != "PASS":
            errors.append("cost_control.user_spend_approval: paid generation requires PASS")
    elif cost.get("user_spend_approval") not in {"PASS", "NOT_REQUIRED"}:
        errors.append("cost_control.user_spend_approval: must be PASS or NOT_REQUIRED")

    handoff = data.get("generation_handoff")
    if not isinstance(handoff, dict):
        errors.append("generation_handoff: required")
    else:
        for field in (
            "model_capability", "output_contract_reference", "output_contract_validation_reference",
            "audio_plan", "output_specification",
        ):
            if not isinstance(handoff.get(field), str) or not handoff[field].strip():
                errors.append(f"generation_handoff.{field}: required")
        if handoff.get("deliverable_type") != "VIDEO_SHOT":
            errors.append("generation_handoff.deliverable_type: formal shot generation requires VIDEO_SHOT")
        for field in (
            "reference_priority", "motion_beats", "positive_invariants",
            "negative_constraints", "acceptance_criteria",
        ):
            require_list(data, f"generation_handoff.{field}", errors, nonempty=True)

        duration_mode = handoff.get("duration_control_mode")
        if duration_mode not in DURATION_CONTROL_MODES:
            errors.append(
                f"generation_handoff.duration_control_mode: expected one of {sorted(DURATION_CONTROL_MODES)}"
            )
        native_duration = handoff.get("model_native_duration_seconds")
        target_duration = handoff.get("editorial_target_duration_seconds")
        if not finite_number(native_duration) or native_duration <= 0:
            errors.append("generation_handoff.model_native_duration_seconds: must be greater than zero")
        if not finite_number(target_duration) or target_duration <= 0:
            errors.append("generation_handoff.editorial_target_duration_seconds: must be greater than zero")
        elif finite_number(get(data, "shot.duration_seconds")) and abs(
            target_duration - get(data, "shot.duration_seconds")
        ) > 0.1:
            errors.append("generation_handoff.editorial_target_duration_seconds: must match shot.duration_seconds")
        if (
            duration_mode == "MODEL_NATIVE_THEN_SELECT"
            and finite_number(native_duration)
            and finite_number(target_duration)
            and native_duration < target_duration
        ):
            errors.append(
                "generation_handoff.model_native_duration_seconds: native duration must cover editorial target"
            )
        require_text(data, "generation_handoff.duration_behavior_evidence", errors)

    keyframes = require_list(data, "keyframes", errors, nonempty=True)
    roles = {frame.get("role") for frame in keyframes if isinstance(frame, dict)}
    if "first" not in roles:
        errors.append("keyframes: missing 'first' state")
    strategy = get(data, "production_strategy.reference_strategy")
    precise_exit = get(data, "production_strategy.precise_exit_control_required") is True
    if strategy in {"FIRST_AND_LAST", "MULTI_KEYFRAME"} or precise_exit:
        if "last" not in roles:
            errors.append("keyframes: last state required by the selected reference strategy")
    if strategy == "MULTI_KEYFRAME" and len(keyframes) < 3:
        errors.append("keyframes: MULTI_KEYFRAME requires at least three states")
    for index, frame in enumerate(keyframes):
        if not isinstance(frame, dict):
            errors.append(f"keyframes[{index}]: must be an object")
            continue
        for field in ("role", "timecode", "state", "reference"):
            if not isinstance(frame.get(field), str) or not frame[field].strip():
                errors.append(f"keyframes[{index}].{field}: required")

    if get(data, "release.references_locked") is not True:
        errors.append("release.references_locked: must be true")
    for dotted in ("release.released_by", "release.released_at"):
        require_text(data, dotted, errors)


def validate_edit_ready(data: dict[str, Any], errors: list[str]) -> None:
    review = data.get("edit_ready_review")
    if not isinstance(review, dict) or review.get("status") != "PASS":
        errors.append("edit_ready_review.status: edit-ready requires PASS")
        return
    for dotted in (
        "edit_ready_review.source_video_reference",
        "edit_ready_review.selected_in_timecode",
        "edit_ready_review.selected_out_timecode",
        "edit_ready_review.actual_tail_frame_reference",
        "edit_ready_review.actual_tail_window_reference",
        "edit_ready_review.actual_tail_motion_summary",
        "edit_ready_review.timeline_reference",
        "edit_ready_review.evidence",
    ):
        require_text(data, dotted, errors)
    duration = review.get("selected_duration_seconds")
    target_duration = get(data, "generation_handoff.editorial_target_duration_seconds")
    if not finite_number(duration) or duration <= 0:
        errors.append("edit_ready_review.selected_duration_seconds: must be greater than zero")
    elif finite_number(target_duration) and abs(duration - target_duration) > 0.1:
        errors.append("edit_ready_review.selected_duration_seconds: must match editorial target duration")
    for field in (
        "story_action_readability_status", "identity_status",
        "scene_camera_continuity_status", "environment_status",
        "timeline_replacement_status",
    ):
        if review.get(field) not in PASS_OR_NA:
            errors.append(f"edit_ready_review.{field}: must be PASS or N/A")
    blockers = require_list(data, "edit_ready_review.blocking_defects", errors)
    require_list(data, "edit_ready_review.deferred_polish_items", errors)
    if blockers:
        errors.append("edit_ready_review.blocking_defects: must be empty")
    if review.get("timeline_replacement_status") != "PASS":
        errors.append("edit_ready_review.timeline_replacement_status: must be PASS")


def validate_retry(data: dict[str, Any], errors: list[str]) -> None:
    retry = data.get("retry_control")
    if not isinstance(retry, dict):
        errors.append("retry_control: required")
        return
    values = [retry.get(k) for k in (
        "current_round", "max_rounds", "same_defect_count", "same_defect_limit",
        "method_attempt_count", "method_attempt_limit",
    )]
    if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in values):
        errors.append("retry_control: counters and limits must be non-negative integers")
        return
    current, maximum, same_count, same_limit, method_count, method_limit = values
    if maximum < 1 or current >= maximum:
        errors.append("retry_control: generation round limit reached or invalid")
    if same_limit < 1 or same_count >= same_limit:
        errors.append("retry_control: same-defect fuse is open")
    require_text(data, "retry_control.method_id", errors)
    if method_limit < 1 or method_count >= method_limit:
        errors.append("retry_control: same-method attempt limit reached; change production method")
    if not isinstance(retry.get("method_switch_required"), bool):
        errors.append("retry_control.method_switch_required: must be boolean")
    elif retry.get("method_switch_required") is True:
        errors.append("retry_control.method_switch_required: switch method before release")
    previous_method = retry.get("previous_method_id")
    if isinstance(previous_method, str) and previous_method.strip() and previous_method != retry.get("method_id"):
        require_text(data, "retry_control.method_switch_reason", errors)
    if current > 0:
        require_text(data, "retry_control.repair_ladder_step", errors)
        require_text(data, "retry_control.changed_production_condition", errors)


def validate_acceptance(data: dict[str, Any], errors: list[str]) -> None:
    if get(data, "edit_ready_review.status") != "PASS":
        errors.append("edit_ready_review.status: acceptance requires prior EDIT_READY PASS")
    sampling = data.get("acceptance_sampling")
    if not isinstance(sampling, dict) or sampling.get("status") != "PASS":
        errors.append("acceptance_sampling.status: acceptance requires PASS")
        return
    interval = sampling.get("interval_seconds")
    if not finite_number(interval) or interval <= 0:
        errors.append("acceptance_sampling.interval_seconds: must be greater than zero")
    require_text(data, "acceptance_sampling.contact_sheet_reference", errors)
    mode = get(data, "shot.continuity_mode")
    minimum_radius = 3 if mode == "CONTINUOUS_TAKE" else 1
    radius = sampling.get("boundary_frame_radius")
    if not isinstance(radius, int) or isinstance(radius, bool) or radius < minimum_radius:
        errors.append(
            f"acceptance_sampling.boundary_frame_radius: must be at least {minimum_radius} for {mode}"
        )
    require_list(data, "acceptance_sampling.full_resolution_frame_checks", errors, nonempty=True)
    if sampling.get("motion_review_status") != "PASS":
        errors.append("acceptance_sampling.motion_review_status: must be PASS")
    require_text(data, "acceptance_sampling.motion_review_evidence", errors)
    if sampling.get("deliverable_identity_status") != "PASS":
        errors.append("acceptance_sampling.deliverable_identity_status: must be PASS")
    require_text(data, "acceptance_sampling.deliverable_identity_evidence", errors)
    for field in (
        "subject_motion_status", "environment_motion_status", "camera_motion_status",
        "subject_environment_causality_status",
    ):
        if sampling.get(field) not in PASS_OR_NA:
            errors.append(f"acceptance_sampling.{field}: must be PASS or N/A")
    if sampling.get("audio_review_status") not in PASS_OR_NA:
        errors.append("acceptance_sampling.audio_review_status: must be PASS or N/A")
    require_text(data, "acceptance_sampling.audio_review_evidence", errors)

    triage = sampling.get("defect_triage")
    if not isinstance(triage, dict) or triage.get("status") != "PASS":
        errors.append("acceptance_sampling.defect_triage.status: must be PASS")
    else:
        c0 = require_list(data, "acceptance_sampling.defect_triage.c0_blocking", errors)
        c1 = require_list(data, "acceptance_sampling.defect_triage.c1_must_fix", errors)
        c2 = require_list(data, "acceptance_sampling.defect_triage.c2_conditional", errors)
        require_list(data, "acceptance_sampling.defect_triage.c3_deferred_polish", errors)
        require_list(data, "acceptance_sampling.defect_triage.c4_accepted", errors)
        if c0 or c1:
            errors.append("acceptance_sampling.defect_triage: C0/C1 defects must be empty before acceptance")
        if c2:
            require_text(data, "acceptance_sampling.defect_triage.c2_disposition", errors)
        if triage.get("delivery_resolution_review_status") != "PASS":
            errors.append("acceptance_sampling.defect_triage.delivery_resolution_review_status: must be PASS")
        require_text(data, "acceptance_sampling.defect_triage.evidence", errors)

    timeline = sampling.get("timeline_integration")
    efficient = get(data, "production_strategy.mode") == "EFFICIENT_SHORT"
    if not isinstance(timeline, dict):
        errors.append("acceptance_sampling.timeline_integration: required")
    elif efficient:
        if timeline.get("status") != "PASS":
            errors.append("acceptance_sampling.timeline_integration.status: efficient mode requires PASS")
        for field in ("sequence_playback_status", "full_film_priority_status"):
            if timeline.get(field) != "PASS":
                errors.append(f"acceptance_sampling.timeline_integration.{field}: efficient mode requires PASS")
        for field in ("timeline_reference", "evidence"):
            require_text(data, f"acceptance_sampling.timeline_integration.{field}", errors)
    else:
        if timeline.get("status") not in PASS_OR_NA:
            errors.append("acceptance_sampling.timeline_integration.status: must be PASS or N/A")
        if timeline.get("status") == "N/A":
            require_text(data, "acceptance_sampling.timeline_integration.reason", errors)
    if get(data, "acceptance.result") != "PASS":
        errors.append("acceptance.result: must be PASS")
    require_text(data, "acceptance.accepted_asset_version", errors)
    require_text(data, "acceptance.ledger_writeback", errors)


SINGLE_REFERENCE_FIELDS = (
    "asset_baselines.scene",
    "scene_asset_lock.scene_asset_bundle_reference",
    "scene_asset_lock.spatial_master_reference",
    "scene_asset_lock.background_geometry_or_render_reference",
    "picture_lock.background_plate_reference",
)
LIST_REFERENCE_FIELDS = (
    "asset_baselines.characters",
    "asset_baselines.props",
    "picture_lock.allowed_change_masks",
)
PAIR_REFERENCE_FIELDS = (
    ("picture_lock.comparison_pairs", "baseline"),
    ("picture_lock.comparison_pairs", "candidate"),
)
def collect_references(data: dict[str, Any]) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    for dotted in SINGLE_REFERENCE_FIELDS:
        value = get(data, dotted)
        if isinstance(value, str) and value.strip():
            references.append((dotted, value.strip()))
    for dotted in LIST_REFERENCE_FIELDS:
        for index, value in enumerate(get(data, dotted) or []):
            if isinstance(value, str) and value.strip():
                references.append((f"{dotted}[{index}]", value.strip()))
    for dotted, field in PAIR_REFERENCE_FIELDS:
        for index, pair in enumerate(get(data, dotted) or []):
            if isinstance(pair, dict):
                value = pair.get(field)
                if isinstance(value, str) and value.strip():
                    references.append((f"{dotted}[{index}].{field}", value.strip()))
    for index, frame in enumerate(get(data, "keyframes") or []):
        if isinstance(frame, dict):
            value = frame.get("reference")
            if isinstance(value, str) and value.strip():
                references.append((f"keyframes[{index}].reference", value.strip()))
    return references


def normalized_file(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("./")


def validate_evidence(
    data: dict[str, Any], manifest_path: Path, root: Path, errors: list[str]
) -> None:
    if not manifest_path.is_file():
        errors.append(f"--manifest: file not found: {manifest_path}")
        return
    manifest_errors, manifest = validate_asset_manifest.validate_manifest(manifest_path, root)
    for error in manifest_errors:
        errors.append(f"manifest: {error}")
    if manifest is None:
        return

    expected = get(data, "asset_identity_lock.manifest_digest_sha256")
    actual = validate_asset_manifest.canonical_digest(manifest)
    if expected != actual:
        errors.append(
            "asset_identity_lock.manifest_digest_sha256: does not match --manifest "
            f"(expected {actual})"
        )

    entries: dict[str, dict[str, Any]] = {}
    for item in manifest.get("assets") or []:
        if isinstance(item, dict) and isinstance(item.get("reference"), str):
            entries[item["reference"]] = item

    for index, asset in enumerate(get(data, "asset_identity_lock.assets") or []):
        if not isinstance(asset, dict):
            continue
        reference = asset.get("reference")
        entry = entries.get(reference) if isinstance(reference, str) else None
        if entry is None:
            errors.append(
                f"asset_identity_lock.assets[{index}].reference: {reference!r} is not in the asset manifest"
            )
            continue
        for field in ("asset_id", "asset_type", "version", "sha256"):
            if asset.get(field) != entry.get(field):
                errors.append(
                    f"asset_identity_lock.assets[{index}].{field}: does not match the asset manifest"
                )
        if normalized_file(str(asset.get("file", ""))) != normalized_file(str(entry.get("file", ""))):
            errors.append(
                f"asset_identity_lock.assets[{index}].file: does not match the asset manifest"
            )

    for dotted, reference in collect_references(data):
        if reference not in entries:
            errors.append(f"{dotted}: {reference!r} is not in the asset manifest")


def validate_target(
    data: dict[str, Any], target: str, errors: list[str], restamp: bool = False
) -> None:
    validate_production_plan(data, errors)
    validate_production_strategy(data, errors)
    validate_scene_and_space(data, target, errors)
    validate_camera(data, errors)
    validate_continuity(data, errors)
    validate_picture_lock(data, target, errors)
    validate_asset_identity(data, target, errors)
    validate_asset_usage(data, target, errors)
    validate_environment(data, target, errors)
    validate_retry(data, errors)

    status = get(data, "shot.status")
    rank = STATUS_RANK.get(status)
    if rank is None:
        errors.append(f"shot.status: unsupported value {status!r}")
    elif rank < 0:
        errors.append(f"shot.status: {status} is closed; reopen it with --reopen --reason first")
    elif rank > TARGET_RANK[target]:
        errors.append(f"shot.status: {status} is beyond the {target} target")
    if target == "edit-ready" and status not in {"GREENLIT", "EDIT_READY"}:
        errors.append("shot.status: edit-ready requires a prior GREENLIT release")
    if target == "acceptance" and status not in {"EDIT_READY", "ACCEPTED"}:
        errors.append("shot.status: acceptance requires a prior EDIT_READY stamp")
    for gate_name in REQUIRED_GATES[target]:
        gate_status = get(data, f"gates.{gate_name}.status")
        if gate_name == "gate_2b_environment_dynamics":
            if gate_status not in PASS_OR_NA:
                errors.append(f"gates.{gate_name}.status: {target} requires PASS or justified N/A")
        elif gate_status != "PASS":
            errors.append(f"gates.{gate_name}.status: {target} requires PASS")
    if target in {"release", "edit-ready", "acceptance"}:
        questions = get(data, "constraints.critical_open_questions")
        if isinstance(questions, list) and questions:
            errors.append("constraints.critical_open_questions: must be empty before release")
        validate_release_inputs(data, errors)
        if status in {"GREENLIT", "EDIT_READY", "ACCEPTED"}:
            if get(data, "release.validator_result") != "PASS":
                errors.append("release.validator_result: GREENLIT/EDIT_READY/ACCEPTED requires PASS")
            if not restamp and get(data, "release.validator_version") != VALIDATOR_VERSION:
                errors.append(f"release.validator_version: expected {VALIDATOR_VERSION}")
    if target in {"edit-ready", "acceptance"}:
        validate_edit_ready(data, errors)
        if (
            status in {"EDIT_READY", "ACCEPTED"}
            and not restamp
            and get(data, "edit_ready_review.validator_version") != VALIDATOR_VERSION
        ):
            errors.append(f"edit_ready_review.validator_version: expected {VALIDATOR_VERSION}")
    if target == "acceptance":
        validate_acceptance(data, errors)
        if (
            status == "ACCEPTED"
            and not restamp
            and get(data, "acceptance.validator_version") != VALIDATOR_VERSION
        ):
            errors.append(f"acceptance.validator_version: expected {VALIDATOR_VERSION}")


def write_pass(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def report(args: argparse.Namespace, payload: dict[str, Any], lines: list[str]) -> None:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in lines:
            print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pass_file", type=Path)
    parser.add_argument("--target", choices=("previs", "release", "edit-ready", "acceptance"))
    parser.add_argument("--stamp", action="store_true")
    parser.add_argument(
        "--restamp",
        action="store_true",
        help="Migrate a pass stamped by an older validator: re-validate, then overwrite validator_version/validated_at.",
    )
    parser.add_argument("--manifest", type=Path, help="Asset manifest used to verify digests, files and references.")
    parser.add_argument("--root", type=Path, help="Resolve relative asset paths from here; defaults to the pass directory.")
    parser.add_argument("--require-evidence", action="store_true", help="Fail when --manifest is absent.")
    parser.add_argument("--allow-unverified", action="store_true", help="Release without a manifest (discouraged).")
    parser.add_argument("--reopen", action="store_true", help="Reopen a REJECTED/SUPERSEDED pass as DRAFT.")
    parser.add_argument("--reason", default="", help="Reason recorded when reopening.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable result.")
    args = parser.parse_args()

    if args.reopen and (args.target or args.stamp or args.restamp):
        parser.error("--reopen cannot be combined with --target, --stamp or --restamp")
    if not args.reopen and not args.target:
        parser.error("--target is required unless --reopen is used")
    if args.restamp and args.target not in {"release", "edit-ready", "acceptance"}:
        parser.error("--restamp is only meaningful for --target release, edit-ready or acceptance")

    try:
        data = json.loads(args.pass_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"FAIL: file not found: {args.pass_file}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("FAIL: pass root must be a JSON object", file=sys.stderr)
        return 2

    if args.reopen:
        if not args.reason.strip():
            parser.error("--reopen requires --reason")
        status = get(data, "shot.status")
        if status not in REOPENABLE:
            print(f"BLOCKED: only REJECTED or SUPERSEDED passes can be reopened, not {status!r}")
            return 1
        data["shot"]["status"] = "DRAFT"
        retry = data.setdefault("retry_control", {})
        retry["reopen_reason"] = args.reason.strip()
        retry["reopened_at"] = datetime.now(timezone.utc).isoformat()
        write_pass(args.pass_file, data)
        print(f"REOPENED: {get(data, 'shot.shot_id')} {get(data, 'shot.pass_version')} -> DRAFT")
        return 0

    target = args.target
    errors: list[str] = []
    validate_base(data, errors)
    validate_target(data, target, errors, restamp=args.restamp)

    root = (args.root or args.pass_file.parent).resolve()
    if args.manifest:
        validate_evidence(data, args.manifest, root, errors)
    elif target in {"release", "edit-ready", "acceptance"} and not args.allow_unverified:
        errors.append(
            f"{target} validation requires --manifest (asset manifest) or an explicit --allow-unverified"
        )
    elif args.require_evidence:
        errors.append("--require-evidence: --manifest is required")

    shot_id = get(data, "shot.shot_id")
    pass_version = get(data, "shot.pass_version")
    if errors:
        payload = {
            "status": "BLOCKED",
            "target": target,
            "shot_id": shot_id,
            "pass_version": pass_version,
            "errors": errors,
        }
        report(
            args,
            payload,
            [f"BLOCKED: {args.pass_file} is not ready for {target}", *(f"- {error}" for error in errors)],
        )
        return 1

    previous_version = None
    if args.stamp or args.restamp:
        desired = {
            "previs": "PREVIS", "release": "GREENLIT",
            "edit-ready": "EDIT_READY", "acceptance": "ACCEPTED",
        }[target]
        current = data["shot"]["status"]
        stamp_section = {
            "previs": "release", "release": "release",
            "edit-ready": "edit_ready_review", "acceptance": "acceptance",
        }[target]
        previous_version = get(data, f"{stamp_section}.validator_version")
        next_status = current if STATUS_RANK.get(current, -1) >= STATUS_RANK[desired] else desired
        data["shot"]["status"] = next_status
        now = datetime.now(timezone.utc).isoformat()
        if target == "release":
            data["release"].update(
                {"validator_result": "PASS", "validator_version": VALIDATOR_VERSION, "validated_at": now}
            )
        if target == "edit-ready":
            data["edit_ready_review"].update(
                {"validator_version": VALIDATOR_VERSION, "validated_at": now}
            )
        if target == "acceptance":
            data["acceptance"].update({"validator_version": VALIDATOR_VERSION, "validated_at": now})
        write_pass(args.pass_file, data)

    status_after = get(data, "shot.status")
    payload = {
        "status": "PASS",
        "target": target,
        "shot_id": shot_id,
        "pass_version": pass_version,
        "shot_status": status_after,
        "stamped": bool(args.stamp or args.restamp),
        "validator_version": VALIDATOR_VERSION,
    }
    lines = [f"PASS: {shot_id} {pass_version} is ready for {target}"]
    if args.restamp:
        lines.insert(
            0,
            f"RESTAMPED: validator_version {previous_version!r} -> {VALIDATOR_VERSION} "
            f"(shot.status {status_after})",
        )
    elif args.stamp:
        lines.insert(0, f"STAMPED: shot.status -> {status_after}")
    report(args, payload, lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
