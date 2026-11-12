"""Behavioural tests for the two-stage scene-asset gate."""

from __future__ import annotations

import unittest
from copy import deepcopy

from support import ROOT, load_json

import validate_asset_manifest as vam
import validate_scene_asset_package as vsap


TEMPLATE = ROOT / "assets" / "templates" / "scene-asset-package.json"


def layout_fixture() -> dict:
    data = deepcopy(load_json(TEMPLATE))
    data.update(
        {
            "project_id": "P1", "source_scene_plan_version": "v001",
            "stage": "LAYOUT", "status": "LAYOUT_APPROVED",
        }
    )
    data["spatial_master"].update(
        {
            "layout_reference": "SC01_LAYOUT_v001", "layout_version": "v001",
            "coordinate_origin": "floor center", "axis_convention": "+X right +Y forward +Z up",
            "unit": "meter", "key_dimensions": ["room 6m x 8m"],
            "fixed_equipment_status": "N/A",
            "reachability_and_blocking_evidence": "layout previs",
        }
    )
    data["camera_setups"][0].update(
        {
            "position_and_orientation": "(0,-4,1.5), toward origin", "lens_or_fov": "50mm",
            "visible_area": "main action area", "status": "PLANNED",
        }
    )
    data["environment"]["static_regions"] = ["architecture"]
    data["approval"].update(
        {"status": "PASS", "reviewer": "reviewer", "reviewed_at": "2026-11-10", "evidence": "layout review"}
    )
    return data


def final_fixture() -> tuple[dict, dict]:
    data = layout_fixture()
    data.update({"stage": "FINAL", "status": "ACCEPTED"})
    data["technical_baseline"].update(
        {"aspect_ratio": "16:9", "resolution": "1920x1080", "color_space": "sRGB"}
    )
    data["camera_setups"][0]["status"] = "APPROVED"
    data["picture_assets"]["scene_master_reference"] = "SC01_MASTER_v002"
    data["picture_assets"]["scene_master_output_contract_reference"] = "SC01_MASTER_CONTRACT_v001"
    data["picture_assets"]["scene_master_output_contract_validation_reference"] = "SC01_MASTER_CONTRACT_CHECK_PASS"
    data["environment"].update(
        {"light_state_reference": "LIGHT_SC01_v001", "look_reference": "LOOK_v001"}
    )
    manifest = {
        "schema_version": 1,
        "manifest_id": "P1_ASSETS",
        "manifest_version": "v001",
        "status": "ACCEPTED",
        "assets": [
            {
                "asset_id": "SC01_MASTER", "asset_type": "SCENE", "version": "v002",
                "reference": "SC01_MASTER_v002", "file": "scene.png", "sha256": "a" * 64,
                "status": "ACCEPTED",
            }
        ],
    }
    data["asset_manifest"].update(
        {"manifest_id": "P1_ASSETS", "manifest_digest_sha256": vam.canonical_digest(manifest)}
    )
    data["asset_refs"] = [
        {"asset_id": "SC01_MASTER", "version": "v002", "reference": "SC01_MASTER_v002"}
    ]
    return data, manifest


class SceneAssetTests(unittest.TestCase):
    def test_layout_package_passes_layout_gate(self) -> None:
        errors, warnings = vsap.validate(layout_fixture(), "layout")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_layout_package_cannot_pass_final_gate(self) -> None:
        errors, _ = vsap.validate(layout_fixture(), "final")
        self.assertTrue(any("stage: must be FINAL" in error for error in errors), errors)

    def test_final_package_closes_to_manifest(self) -> None:
        package, manifest = final_fixture()
        errors, warnings = vsap.validate(package, "final", manifest)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_unlisted_asset_reference_is_blocked(self) -> None:
        package, manifest = final_fixture()
        package["asset_refs"][0]["version"] = "v999"
        errors, _ = vsap.validate(package, "final", manifest)
        self.assertTrue(any("absent from supplied" in error for error in errors), errors)

    def test_dynamic_final_requires_environment_only_previs(self) -> None:
        package, manifest = final_fixture()
        package["environment"]["dynamic_regions"] = [
            {
                "region_id": "ENV-WATER",
                "motion_type": "surface flow",
                "motion_direction": "left to right",
                "speed_range": "0.2-0.4 m/s",
                "layer_reference": "ENV-WATER_LAYER_v001",
                "mask_reference": "ENV-WATER_MASK_v001",
                "intensity_range": "low to medium",
                "phase_baseline": "crest at x=0",
            }
        ]
        package["environment"]["dynamic_control"].update({"status": "PASS"})
        errors, _ = vsap.validate(package, "final", manifest)
        self.assertTrue(any("environment_only_previs" in error for error in errors), errors)

    def test_dynamic_final_passes_with_layered_previs(self) -> None:
        package, manifest = final_fixture()
        package["environment"]["dynamic_regions"] = [
            {
                "region_id": "ENV-WATER",
                "motion_type": "surface flow",
                "motion_direction": "left to right",
                "speed_range": "0.2-0.4 m/s",
                "layer_reference": "ENV-WATER_LAYER_v001",
                "mask_reference": "ENV-WATER_MASK_v001",
                "intensity_range": "low to medium",
                "phase_baseline": "crest at x=0",
            }
        ]
        package["environment"]["dynamic_control"].update(
            {
                "status": "PASS",
                "reason": "",
                "layer_manifest_reference": "SC01_ENV_LAYERS_v001",
                "environment_only_previs_reference": "SC01_ENV_PREVIS_v001",
                "environment_only_previs_status": "PASS",
                "reaction_coupling_plan_reference": "SC01_ENV_REACTION_v001",
                "phase_baseline_reference": "SC01_ENV_PHASE_v001",
                "evidence": "environment-only playback approved",
            }
        )
        errors, warnings = vsap.validate(package, "final", manifest)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
