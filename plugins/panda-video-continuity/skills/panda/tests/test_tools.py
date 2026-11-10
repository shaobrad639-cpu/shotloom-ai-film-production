"""Tests for the companion tools: asset manifest, pixel lock and sequence validators."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from support import copy_example, load_json, run_script, save_json

import validate_asset_manifest as vam
import validate_sequence as vsq


class AssetManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.example = copy_example(self.tmp)
        self.manifest = self.example / "asset-manifest.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_manifest_passes_and_prints_digest(self) -> None:
        result = run_script("validate_asset_manifest.py", self.manifest, "--root", self.example)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("locks 11 ACCEPTED assets", result.stdout)
        digest = vam.canonical_digest(load_json(self.manifest))
        self.assertIn(f"manifest_digest_sha256: {digest}", result.stdout)

    def test_tampered_asset_is_blocked(self) -> None:
        target = self.example / "assets" / "char-001-v003.png"
        with target.open("ab") as stream:
            stream.write(b"tampered")
        result = run_script("validate_asset_manifest.py", self.manifest, "--root", self.example)
        self.assertEqual(result.returncode, 1)
        self.assertIn("content mismatch", result.stdout)

    def test_duplicate_reference_is_blocked(self) -> None:
        data = load_json(self.manifest)
        data["assets"].append(dict(data["assets"][0]))
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        errors, _ = vam.validate_manifest(self.manifest, self.example)
        self.assertTrue(any("duplicate asset identity" in error for error in errors), errors)


class RestampBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.example = copy_example(self.tmp)
        self.pass_file = self.example / "shot-pass-greenlit.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def make_legacy(self) -> None:
        data = load_json(self.pass_file)
        data["release"]["validator_version"] = "2.0.0"
        save_json(self.pass_file, data)

    def test_dry_run_reports_legacy_pass_without_writing(self) -> None:
        self.make_legacy()
        result = run_script("restamp_passes.py", self.example, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WOULD RESTAMP", result.stdout)
        self.assertEqual(load_json(self.pass_file)["release"]["validator_version"], "2.0.0")

    def test_batch_restamps_legacy_pass(self) -> None:
        self.make_legacy()
        result = run_script("restamp_passes.py", self.example)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESTAMPED", result.stdout)
        self.assertEqual(load_json(self.pass_file)["release"]["validator_version"], "2.3.0")


class PixelLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.a = self.tmp / "a.png"
        self.b = self.tmp / "b.png"
        self.mask = self.tmp / "mask.png"
        self.report = self.tmp / "report.json"
        Image.new("RGBA", (10, 10), (0, 0, 0, 255)).save(self.a)
        changed = Image.open(self.a).copy()
        changed.putpixel((0, 0), (255, 255, 255, 255))
        changed.save(self.b)
        Image.new("L", (10, 10), 0).save(self.mask)  # everything protected

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pass_reports_real_changed_pixel_count(self) -> None:
        result = run_script(
            "validate_pixel_lock.py", self.a, self.b,
            "--allowed-mask", self.mask, "--report", self.report,
            "--max-protected-change-ratio", "0.5",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("changed_protected_pixels=1", result.stdout)
        payload = load_json(self.report)
        self.assertEqual(payload["changed_protected_pixels"], 1)
        self.assertEqual(payload["protected_pixels"], 100)

    def test_block_reports_real_changed_pixel_count(self) -> None:
        result = run_script(
            "validate_pixel_lock.py", self.a, self.b,
            "--allowed-mask", self.mask, "--report", self.report,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed_protected_pixels=1", result.stdout)
        self.assertEqual(load_json(self.report)["status"], "BLOCKED")


class SequenceTests(unittest.TestCase):
    def pass_data(self, shot_id: str, previous: str = "", relation: str = "INDEPENDENT", **extra) -> dict:
        data = {
            "shot": {
                "shot_id": shot_id,
                "take_id": f"{shot_id}_TK01",
                "pass_version": "v001",
                "continuity_mode": "CONTINUOUS_TAKE",
                "relation_from_previous": relation,
                "segment_sequence_index": 1,
                "status": "GREENLIT",
            },
            "continuity": {"previous_shot_id": previous},
            "asset_identity_lock": {"manifest_digest_sha256": "a" * 64},
        }
        data["shot"].update(extra.pop("shot", {}))
        return data

    def test_duplicate_pass_is_an_error(self) -> None:
        passes = {Path("a.json"): self.pass_data("SH01"), Path("b.json"): self.pass_data("SH01")}
        errors, _ = vsq.validate(passes, None)
        self.assertTrue(any("duplicate pass" in error for error in errors), errors)

    def test_dangling_previous_shot_is_an_error(self) -> None:
        passes = {Path("a.json"): self.pass_data("SH02", previous="SH01", relation="EDITORIAL_CUT")}
        errors, _ = vsq.validate(passes, None)
        self.assertTrue(any("has no pass in this set" in error for error in errors), errors)

    def test_manifest_digest_mismatch_is_an_error(self) -> None:
        passes = {Path("a.json"): self.pass_data("SH01")}
        errors, _ = vsq.validate(passes, "b" * 64)
        self.assertTrue(any("manifest digest does not match" in error for error in errors), errors)

    def test_missing_predecessor_is_a_warning(self) -> None:
        passes = {
            Path("a.json"): self.pass_data(
                "SH01", relation="CONTINUOUS_SEGMENT", shot={"segment_sequence_index": 3, "relation_from_previous": "CONTINUOUS_SEGMENT"}
            )
        }
        passes[Path("a.json")]["continuity"].update(
            {"previous_shot_id": "SH01", "previous_tail_asset_version": "TAIL_v001"}
        )
        errors, warnings = vsq.validate(passes, None)
        self.assertEqual(errors, [])
        self.assertTrue(any("chain unverifiable" in warning for warning in warnings), warnings)


if __name__ == "__main__":
    unittest.main()
