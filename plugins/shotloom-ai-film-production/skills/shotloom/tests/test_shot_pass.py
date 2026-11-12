"""Behavioural tests for scripts/validate_shot_pass.py (validator 2.5.0)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import copy_example, greenlit, load_json, run_script, save_json

import validate_shot_pass as vsp


class ShotPassTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.example = copy_example(self.tmp)
        self.pass_file = self.example / "shot-pass-greenlit.json"
        self.manifest = self.example / "asset-manifest.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_pass(self, *args: object):
        return run_script("validate_shot_pass.py", *args)

    def release(self, *extra: object):
        return self.run_pass(
            self.pass_file, "--target", "release", "--manifest", self.manifest, "--root", self.example, *extra
        )

    def mutate(self, callback) -> None:
        data = load_json(self.pass_file)
        callback(data)
        save_json(self.pass_file, data)

    # -- happy path -----------------------------------------------------
    def test_example_passes_release_with_manifest(self) -> None:
        result = self.release()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: DEMO_EP01_SH03", result.stdout)

    def test_release_without_manifest_is_blocked(self) -> None:
        result = self.run_pass(self.pass_file, "--target", "release")
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires --manifest", result.stdout)

    def test_allow_unverified_is_the_explicit_escape_hatch(self) -> None:
        result = self.run_pass(self.pass_file, "--target", "release", "--allow-unverified")
        self.assertEqual(result.returncode, 0, result.stdout)

    # -- restamp migration ----------------------------------------------
    def test_legacy_stamp_is_blocked_until_restamped(self) -> None:
        self.mutate(lambda data: data["release"].update({"validator_version": "2.0.0"}))
        blocked = self.release()
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("expected 2.5.0", blocked.stdout)

        result = self.release("--restamp")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESTAMPED", result.stdout)
        data = load_json(self.pass_file)
        self.assertEqual(data["release"]["validator_version"], vsp.VALIDATOR_VERSION)
        self.assertEqual(data["shot"]["status"], "GREENLIT")

    def test_restamp_is_limited_to_sealed_targets(self) -> None:
        result = self.run_pass(self.pass_file, "--target", "previs", "--restamp")
        self.assertEqual(result.returncode, 2)

    def test_restamp_still_enforces_evidence_closure(self) -> None:
        def break_evidence(data):
            data["release"]["validator_version"] = "2.0.0"
            data["asset_baselines"]["characters"][0] = "CHAR-999_v001"

        self.mutate(break_evidence)
        result = self.release("--restamp")
        self.assertEqual(result.returncode, 1)
        self.assertIn("is not in the asset manifest", result.stdout)

    # -- evidence closure ----------------------------------------------
    def test_fake_manifest_digest_is_blocked(self) -> None:
        self.mutate(lambda data: data["asset_identity_lock"].update({"manifest_digest_sha256": "a" * 64}))
        result = self.release()
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match --manifest", result.stdout)

    def test_missing_asset_file_is_blocked(self) -> None:
        (self.example / "assets" / "char-001-v003.png").unlink()
        result = self.release()
        self.assertEqual(result.returncode, 1)
        self.assertIn("manifest:", result.stdout)
        self.assertIn("not found or not a file", result.stdout)

    def test_asset_sha_mismatch_is_blocked(self) -> None:
        self.mutate(lambda data: data["asset_identity_lock"]["assets"][0].update({"sha256": "b" * 64}))
        result = self.release()
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match the asset manifest", result.stdout)

    def test_asset_reference_missing_from_manifest_is_blocked(self) -> None:
        self.mutate(
            lambda data: data["asset_identity_lock"]["assets"].append(
                {
                    "asset_id": "GHOST-001",
                    "asset_type": "PROP",
                    "version": "v001",
                    "reference": "GHOST-001_v001",
                    "file": "assets/ghost.png",
                    "sha256": "c" * 64,
                    "status": "ACCEPTED",
                }
            )
        )
        result = self.release()
        self.assertEqual(result.returncode, 1)
        self.assertIn("is not in the asset manifest", result.stdout)

    def test_dangling_keyframe_reference_is_blocked(self) -> None:
        self.mutate(lambda data: data["keyframes"][0].update({"reference": "PLATE_MISSING_v001"}))
        result = self.release()
        self.assertEqual(result.returncode, 1)
        self.assertIn("keyframes[0].reference", result.stdout)
        self.assertIn("is not in the asset manifest", result.stdout)

    # -- state machine --------------------------------------------------
    def test_ready_for_previs_can_proceed_to_release(self) -> None:
        self.mutate(lambda data: data["shot"].update({"status": "READY_FOR_PREVIS"}))
        result = self.release()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_blocked_pass_can_be_validated_for_previs(self) -> None:
        self.mutate(lambda data: data["shot"].update({"status": "BLOCKED"}))
        result = self.run_pass(self.pass_file, "--target", "previs")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_accepted_pass_cannot_roll_back_to_previs(self) -> None:
        self.mutate(lambda data: data["shot"].update({"status": "ACCEPTED"}))
        result = self.run_pass(self.pass_file, "--target", "previs")
        self.assertEqual(result.returncode, 1)
        self.assertIn("is beyond the previs target", result.stdout)

    def test_rejected_pass_requires_reopen(self) -> None:
        self.mutate(lambda data: data["shot"].update({"status": "REJECTED"}))
        result = self.run_pass(self.pass_file, "--target", "previs")
        self.assertEqual(result.returncode, 1)
        self.assertIn("is closed; reopen it with --reopen", result.stdout)

        reopened = self.run_pass(self.pass_file, "--reopen", "--reason", "client asked for another pass")
        self.assertEqual(reopened.returncode, 0, reopened.stdout)
        data = load_json(self.pass_file)
        self.assertEqual(data["shot"]["status"], "DRAFT")
        self.assertEqual(data["retry_control"]["reopen_reason"], "client asked for another pass")
        self.assertTrue(data["retry_control"]["reopened_at"])

    def test_reopen_requires_reason(self) -> None:
        self.mutate(lambda data: data["shot"].update({"status": "SUPERSEDED"}))
        result = self.run_pass(self.pass_file, "--reopen")
        self.assertEqual(result.returncode, 2)

    def test_reopen_refuses_open_passes(self) -> None:
        result = self.run_pass(self.pass_file, "--reopen", "--reason", "nope")
        self.assertEqual(result.returncode, 1)
        self.assertIn("only REJECTED or SUPERSEDED", result.stdout)

    def test_json_output_is_machine_readable(self) -> None:
        result = self.release("--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["validator_version"], "2.5.0")

    def test_stamp_writes_validator_metadata(self) -> None:
        self.mutate(lambda data: data["shot"].update({"status": "READY_FOR_RELEASE"}))
        result = self.release("--stamp")
        self.assertEqual(result.returncode, 0, result.stdout)
        data = load_json(self.pass_file)
        self.assertEqual(data["shot"]["status"], "GREENLIT")
        self.assertEqual(data["release"]["validator_version"], "2.5.0")
        self.assertEqual(data["release"]["validator_result"], "PASS")


class RuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = greenlit()

    def errors_of(self, validator, *args: str) -> list[str]:
        errors: list[str] = []
        validator(self.data, *args, errors)
        return errors

    def test_editorial_shot_rejects_segment_semantics(self) -> None:
        self.data["shot"].update(
            {
                "continuity_mode": "EDITORIAL_SHOT",
                "relation_from_previous": "SCENE_START",
                "segment_id": "SG03",
                "segment_sequence_index": 3,
            }
        )
        self.data["continuity"].update({"merge_with_previous_segment": True})
        errors: list[str] = []
        vsp.validate_base(self.data, errors)
        vsp.validate_continuity(self.data, errors)
        self.assertIn("shot.segment_id: must be empty for EDITORIAL_SHOT", errors)
        self.assertIn("shot.segment_sequence_index: must be 1 for EDITORIAL_SHOT", errors)
        self.assertIn("continuity.merge_with_previous_segment: must be false for EDITORIAL_SHOT", errors)

    def test_production_method_na_is_rejected(self) -> None:
        self.data["scene_asset_lock"]["production_method"] = "N/A"
        errors: list[str] = []
        vsp.validate_scene_and_space(self.data, "previs", errors)
        self.assertIn("scene_asset_lock.production_method: unsupported value", errors)

    def test_continuity_requires_three_boundary_frames(self) -> None:
        sampling = {
            "status": "PASS",
            "interval_seconds": 0.4,
            "contact_sheet_reference": "sheet.png",
            "boundary_frame_radius": 1,
            "full_resolution_frame_checks": ["before", "after"],
            "motion_review_status": "PASS",
            "motion_review_evidence": "reviewed",
            "audio_review_status": "N/A",
            "audio_review_evidence": "no audio",
        }
        self.data["acceptance_sampling"] = sampling
        self.data["acceptance"] = {
            "result": "PASS",
            "accepted_asset_version": "v011",
            "ledger_writeback": "ledger row 12",
        }
        errors: list[str] = []
        vsp.validate_acceptance(self.data, errors)
        self.assertTrue(any("boundary_frame_radius" in error for error in errors), errors)

        sampling["boundary_frame_radius"] = 3
        errors = []
        vsp.validate_acceptance(self.data, errors)
        self.assertFalse(any("boundary_frame_radius" in error for error in errors), errors)

    def test_retry_fuse_closes_at_limit(self) -> None:
        self.data["retry_control"].update(
            {"current_round": 3, "max_rounds": 3, "repair_ladder_step": "relight", "changed_production_condition": "new rig"}
        )
        errors: list[str] = []
        vsp.validate_retry(self.data, errors)
        self.assertIn("retry_control: generation round limit reached or invalid", errors)

    def test_same_defect_fuse_uses_inclusive_limit(self) -> None:
        self.data["retry_control"].update({"same_defect_count": 2, "same_defect_limit": 2})
        errors: list[str] = []
        vsp.validate_retry(self.data, errors)
        self.assertIn("retry_control: same-defect fuse is open", errors)

    def test_formal_shot_requires_output_contract(self) -> None:
        self.data["generation_handoff"]["output_contract_reference"] = ""
        errors: list[str] = []
        vsp.validate_release_inputs(self.data, errors)
        self.assertIn("generation_handoff.output_contract_reference: required", errors)

    def test_formal_shot_rejects_wrong_deliverable_type(self) -> None:
        self.data["generation_handoff"]["deliverable_type"] = "COMPOSITE_KEYFRAME"
        errors: list[str] = []
        vsp.validate_release_inputs(self.data, errors)
        self.assertIn(
            "generation_handoff.deliverable_type: formal shot generation requires VIDEO_SHOT",
            errors,
        )

    def test_dynamic_environment_requires_environment_only_previs(self) -> None:
        self.data["environment_animation"].update(
            {
                "status": "PASS",
                "reason": "",
                "registered_regions": ["water"],
                "motion_direction": "left to right",
                "motion_intensity": "low",
                "entry_phase": "crest enters frame",
                "exit_phase": "crest reaches center",
                "reaction_coupling_status": "N/A",
                "reaction_coupling_reason": "no subject contact",
            }
        )
        errors: list[str] = []
        vsp.validate_environment(self.data, "release", errors)
        self.assertTrue(any("scene_dynamic_control_reference" in error for error in errors), errors)
        self.assertTrue(any("environment_only_previs" in error for error in errors), errors)

    def test_reaction_coupling_requires_observable_mapping(self) -> None:
        self.data["environment_animation"].update(
            {
                "status": "PASS",
                "scene_dynamic_control_reference": "SC01_ENV_v001",
                "environment_only_previs_reference": "SC01_ENV_PREVIS_v001",
                "environment_only_previs_status": "PASS",
                "registered_regions": ["mist"],
                "motion_direction": "away from subject",
                "motion_intensity": "medium",
                "entry_phase": "settled",
                "exit_phase": "dispersed",
                "reaction_coupling_status": "PASS",
                "reaction_couplings": [],
            }
        )
        errors: list[str] = []
        vsp.validate_environment(self.data, "release", errors)
        self.assertTrue(any("reaction_couplings" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
