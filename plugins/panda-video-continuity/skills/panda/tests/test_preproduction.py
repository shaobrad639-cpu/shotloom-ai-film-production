"""Behavioural tests for the story-to-animatic production gate."""

from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from support import ROOT, load_json, run_script, save_json

import validate_preproduction as vpp


TEMPLATES = ROOT / "assets" / "templates"


def approved_fixture() -> tuple[dict, list[dict], list[dict], dict, dict, dict]:
    breakdown = deepcopy(load_json(TEMPLATES / "script-breakdown.json"))
    breakdown.update({"project_id": "P1", "screenplay_version": "v001", "status": "APPROVED"})
    breakdown["beats"][0].update(
        {"cause": "cause", "visible_action": "action", "result": "result", "target_duration_seconds": 4}
    )
    scene = deepcopy(load_json(TEMPLATES / "scene-plan.json"))
    scene.update(
        {
            "project_id": "P1", "screenplay_version": "v001", "status": "APPROVED",
            "purpose": "purpose", "entry_state": "entry", "exit_state": "exit",
            "target_duration_seconds": 4,
        }
    )
    scene["approval"].update(
        {"status": "PASS", "reviewer": "reviewer", "reviewed_at": "2026-11-10", "evidence": "review"}
    )
    scene_asset = deepcopy(load_json(TEMPLATES / "scene-asset-package.json"))
    scene_asset.update(
        {"project_id": "P1", "stage": "FINAL", "status": "ACCEPTED"}
    )
    shots = deepcopy(load_json(TEMPLATES / "shot-list.json"))
    shots.update({"project_id": "P1", "status": "APPROVED"})
    shots["shots"][0].update(
        {
            "purpose": "purpose", "target_duration_frames": 96, "shot_size": "MS",
            "camera_angle_and_height": "eye level", "lens_or_fov": "50mm",
            "camera_motion": "static", "blocking_and_action": "action",
            "dialogue_and_sound": "room tone", "storyboard_reference": "SB_v001_P001",
        }
    )
    animatic = deepcopy(load_json(TEMPLATES / "animatic-timeline.json"))
    animatic.update(
        {"project_id": "P1", "status": "LOCKED_FOR_PRODUCTION", "target_duration_frames": 96}
    )
    animatic["clips"][0].update(
        {
            "source_reference": "SB_v001_P001", "timeline_out_frame_exclusive": 96,
            "source_out_frame_exclusive": 96,
        }
    )
    animatic["review"].update(
        {
            "story_readability": "PASS", "timing_and_pacing": "PASS",
            "performance_space": "PASS", "audio_continuity": "PASS",
            "coverage_complete": "PASS", "evidence": "animatic review",
        }
    )
    model = deepcopy(load_json(TEMPLATES / "model-capability-profile.json"))
    model.update(
        {
            "provider": "provider", "product_name": "product", "model_id": "model-v1",
            "verified_at": "2026-11-10", "verification_status": "VERIFIED",
            "verification_evidence": ["manual capability test"],
        }
    )
    model["outputs"]["frame_rates"] = ["24/1"]
    return breakdown, [scene], [scene_asset], shots, animatic, model


class PreproductionTests(unittest.TestCase):
    def test_approved_package_passes(self) -> None:
        errors, warnings = vpp.validate(*approved_fixture(), target="production")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_unlocked_animatic_blocks_production(self) -> None:
        package = list(approved_fixture())
        package[4]["status"] = "DRAFT"
        errors, _ = vpp.validate(*package, target="production")
        self.assertTrue(any("LOCKED_FOR_PRODUCTION" in error for error in errors), errors)

    def test_model_name_without_verified_capability_blocks(self) -> None:
        package = list(approved_fixture())
        package[5]["verification_status"] = "UNVERIFIED"
        errors, _ = vpp.validate(*package, target="production")
        self.assertTrue(any("must be VERIFIED" in error for error in errors), errors)

    def test_cli_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = approved_fixture()
            serializable = (
                package[0], package[1][0], package[2][0], package[3], package[4], package[5]
            )
            names = ("breakdown", "scene", "scene-asset", "shots", "animatic", "model")
            paths = []
            for name, data in zip(names, serializable):
                path = root / f"{name}.json"
                save_json(path, data)
                paths.append(path)
            result = run_script(
                "validate_preproduction.py",
                "--script-breakdown", paths[0], "--scene-plan", paths[1],
                "--scene-asset-package", paths[2],
                "--shot-list", paths[3], "--animatic", paths[4],
                "--model-profile", paths[5], "--target", "production", "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"status": "PASS"', result.stdout)


if __name__ == "__main__":
    unittest.main()
