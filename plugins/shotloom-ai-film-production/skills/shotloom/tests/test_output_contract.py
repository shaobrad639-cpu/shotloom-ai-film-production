"""Behavioural tests for generation output identity and isolation contracts."""

from __future__ import annotations

from copy import deepcopy
import unittest

from support import ROOT, load_json

import validate_output_contract as voc


TEMPLATE = ROOT / "assets" / "templates" / "generation-output-contract.json"


def approved_contract() -> dict:
    data = deepcopy(load_json(TEMPLATE))
    data.update(
        {
            "contract_id": "P1_SC01_PLATE_v001",
            "project_id": "P1",
            "scene_id": "SC01",
            "status": "APPROVED",
            "required_elements": ["approved environment"],
            "forbidden_elements": ["characters", "text", "poster layout"],
            "aspect_ratio": "16:9",
            "resolution": "1920x1080",
            "color_space": "Rec.709",
            "file_format": "PNG",
            "reference_priority": ["SC01 spatial master"],
            "evidence": "clean plate review",
        }
    )
    data["approval"].update(
        {
            "status": "PASS", "reviewer": "art director",
            "reviewed_at": "2026-11-12", "evidence": "preflight review",
        }
    )
    return data


class OutputContractTests(unittest.TestCase):
    def test_clean_plate_contract_passes(self) -> None:
        self.assertEqual(voc.validate(approved_contract()), [])

    def test_required_and_forbidden_conflict_is_blocked(self) -> None:
        data = approved_contract()
        data["forbidden_elements"].append("approved environment")
        errors = voc.validate(data)
        self.assertTrue(any("conflict" in error for error in errors), errors)

    def test_character_layer_requires_transparency_and_alpha(self) -> None:
        data = approved_contract()
        data.update(
            {
                "deliverable_type": "CHARACTER_LAYER",
                "layer_role": "CHARACTER",
                "background_mode": "SCENE",
                "alpha_required": False,
            }
        )
        errors = voc.validate(data)
        self.assertTrue(any("background_mode" in error for error in errors), errors)
        self.assertTrue(any("alpha_required" in error for error in errors), errors)

    def test_clean_plate_rejects_composite_scope(self) -> None:
        data = approved_contract()
        data["asset_scope"] = "COMPOSITE_FRAME"
        errors = voc.validate(data)
        self.assertTrue(any("asset_scope" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
