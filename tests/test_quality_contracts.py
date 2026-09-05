import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "cli/image2ppt/runtime"
sys.path.insert(0, str(RUNTIME_DIR))

from validate_pptx import ALLOWED_SOURCE_TYPES, quality_contract_violations, required_texts_from_manifest  # noqa: E402
from build_pptx_from_manifest import normalize_manifest, shape_xml  # noqa: E402


def base_manifest():
    return {
        "visual_inventory": [],
        "background_strategy": {
            "mode": "native-or-script",
            "comparison_note": "background checked against source",
        },
        "quality_checks": {
            "font_size_calibrated": True,
            "visual_inventory_matched": True,
            "background_strategy_checked": True,
            "shape_corner_geometry_checked": True,
        },
        "shapes": [],
    }


class QualityContractTest(unittest.TestCase):
    def test_quality_checks_are_required(self):
        violations = quality_contract_violations({})
        fields = {item["field"] for item in violations}
        self.assertIn("visual_inventory", fields)
        self.assertIn("background_strategy", fields)
        self.assertIn("quality_checks", fields)

    def test_round_rect_requires_source_evidence(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "roundRect", "box_px": [0, 0, 100, 40]}]
        violations = quality_contract_violations(manifest)
        self.assertEqual(["shapes[0]"], [item["field"] for item in violations])

    def test_rect_does_not_need_corner_evidence(self):
        manifest = base_manifest()
        manifest["shapes"] = [{"type": "rect", "box_px": [0, 0, 100, 40]}]
        self.assertEqual([], quality_contract_violations(manifest))

    def test_source_derived_assets_are_not_allowed(self):
        self.assertNotIn("source-derived-rasterization", ALLOWED_SOURCE_TYPES)

    def test_latex_rendered_formula_assets_are_allowed(self):
        self.assertIn("latex-rendered-formula", ALLOWED_SOURCE_TYPES)

    def test_asset_sheet_separated_assets_are_allowed(self):
        self.assertIn("asset-sheet-separated", ALLOWED_SOURCE_TYPES)

    def test_foreground_native_approximation_is_contract_violation(self):
        manifest = base_manifest()
        manifest["visual_inventory"] = [
            {
                "id": "bottom_icon",
                "description": "semantic icon in the bottom flow",
                "decision": "native approximation with text symbol",
            }
        ]
        violations = quality_contract_violations(manifest)
        reasons = " ".join(item["reason"] for item in violations)
        self.assertIn("foreground visual decisions", reasons)

    def test_foreground_direct_crop_provenance_is_contract_violation(self):
        manifest = base_manifest()
        manifest["visual_inventory"] = [
            {
                "id": "photo_panel",
                "description": "foreground photo panel",
                "decision": "source-faithful asset-sheet separation",
                "path": "assets/source_crops/photo.png",
            }
        ]
        manifest["asset_provenance"] = [
            {
                "path": "assets/source_crops/photo.png",
                "source_type": "user-provided",
                "source": "source.png",
                "provenance_note": "cropped from source foreground photo",
            }
        ]
        violations = quality_contract_violations(manifest)
        fields = [item["field"] for item in violations]
        self.assertIn("visual_inventory[0]", fields)
        self.assertIn("asset_provenance[0]", fields)

    def test_foreground_asset_sheet_decision_passes_contract(self):
        manifest = base_manifest()
        manifest["visual_inventory"] = [
            {
                "id": "photo_panel",
                "description": "foreground photo panel",
                "decision": "source-faithful asset-sheet separation through image2ppt image edit",
                "path": "assets/photo_panel.png",
            }
        ]
        manifest["asset_provenance"] = [
            {
                "path": "assets/photo_panel.png",
                "source_type": "asset-sheet-separated",
                "source": "assets/photo_sheet.png",
                "provenance_note": "split from source-faithful asset sheet generated with image2ppt image edit",
            }
        ]
        self.assertEqual([], quality_contract_violations(manifest))

    def test_round_rect_writes_ooxml_adjustment(self):
        xml = shape_xml(
            2,
            {
                "type": "roundRect",
                "box_px": [0, 0, 400, 200],
                "left": 0,
                "top": 0,
                "width": 4,
                "height": 2,
                "source_corner_radius_px": 10,
                "fill": "none",
                "stroke": "#000000",
            },
        )
        self.assertIn('prst="roundRect"', xml)
        self.assertIn('name="adj"', xml)
        self.assertIn('fmla="val 5000"', xml)

    def test_structured_text_inventory_flattens_to_required_strings(self):
        required = required_texts_from_manifest(
            {
                "required_text": ["市场概览"],
                "text_inventory": [
                    {"id": "metric", "text": "4280 万", "decision": "native-text"},
                    {"id": "insights", "required_text": ["扩张", "续约"]},
                    {"id": "note", "description": "not an exact text requirement"},
                ],
            }
        )
        self.assertEqual(["市场概览", "4280 万", "扩张", "续约"], required)

    def test_invalid_text_alignment_is_a_contract_violation(self):
        manifest = base_manifest()
        manifest["text_boxes"] = [
            {
                "text": "1",
                "box_px": [0, 0, 40, 40],
                "align": "sideways",
                "valign": "floating",
            }
        ]

        violations = quality_contract_violations(manifest)
        fields = {item["field"] for item in violations}

        self.assertIn("text_boxes[0].align", fields)
        self.assertIn("text_boxes[0].valign", fields)

    def test_same_text_style_id_rejects_font_or_size_drift(self):
        manifest = base_manifest()
        manifest["text_boxes"] = [
            {
                "text": "标题一",
                "box_px": [20, 20, 120, 30],
                "text_style_id": "card-title",
                "font": "Microsoft YaHei",
                "font_size": 18,
            },
            {
                "text": "标题二",
                "box_px": [20, 80, 120, 30],
                "text_style_id": "card-title",
                "font": "Microsoft YaHei",
                "font_size": 16,
            },
        ]

        violations = quality_contract_violations(manifest)

        self.assertTrue(any(item["field"] == "text_boxes[1].text_style_id" for item in violations))

    def test_alignment_group_rejects_x_and_typography_drift(self):
        manifest = base_manifest()
        manifest["text_boxes"] = [
            {
                "text": "编号",
                "box_px": [20, 20, 120, 30],
                "alignment_group": "benefit-cards",
                "role": "title",
                "font": "Microsoft YaHei",
                "font_size": 18,
            },
            {
                "text": "编号",
                "box_px": [24, 80, 120, 30],
                "alignment_group": "benefit-cards",
                "role": "title",
                "font": "PingFang SC",
                "font_size": 16,
            },
        ]

        violations = quality_contract_violations(manifest)
        reasons = " ".join(item["reason"] for item in violations)

        self.assertIn("x anchor drifts", reasons)
        self.assertIn("changes font, font size, or line height", reasons)

    def test_alignment_group_number_frames_require_matching_geometry(self):
        manifest = base_manifest()
        manifest["shapes"] = [
            {
                "type": "roundRect",
                "box_px": [20, 20, 40, 40],
                "source_corner_radius_px": 4,
                "alignment_group": "benefit-cards",
                "role": "number",
            },
            {
                "type": "roundRect",
                "box_px": [80, 20, 40, 40],
                "source_corner_radius_px": 8,
                "alignment_group": "benefit-cards",
                "role": "number",
            },
        ]

        violations = quality_contract_violations(manifest)

        self.assertTrue(any(item["field"] == "shapes[1].alignment_group" for item in violations))

    def test_alignment_group_number_frames_reject_x_drift(self):
        manifest = base_manifest()
        manifest["shapes"] = [
            {
                "type": "roundRect",
                "box_px": [20, 20, 40, 40],
                "source_corner_radius_px": 4,
                "alignment_group": "benefit-cards",
                "role": "number-frame",
            },
            {
                "type": "roundRect",
                "box_px": [80, 20, 40, 40],
                "source_corner_radius_px": 4,
                "alignment_group": "benefit-cards",
                "role": "number-frame",
            },
        ]

        violations = quality_contract_violations(manifest)

        self.assertTrue(any(item["field"] == "shapes[1].box_px[0]" for item in violations))

    def test_number_frame_does_not_enter_text_typography_rail(self):
        manifest = base_manifest()
        manifest["text_boxes"] = [
            {
                "text": "01",
                "box_px": [20, 20, 40, 40],
                "alignment_group": "benefit-cards",
                "role": "number-label",
                "text_style_id": "number-label",
                "font": "Microsoft YaHei",
                "font_size": 18,
            }
        ]
        manifest["shapes"] = [
            {
                # A pure frame must stay out of the text style rail even if a
                # malformed producer copied text metadata onto it.
                "type": "roundRect",
                "box_px": [20, 20, 40, 40],
                "source_corner_radius_px": 4,
                "alignment_group": "benefit-cards",
                "role": "number-label",
                "font": "PingFang SC",
                "font_size": 10,
                "text_style_id": "number-label",
            }
        ]

        violations = quality_contract_violations(manifest)

        self.assertFalse(any("changes font" in item["reason"] for item in violations))

    def test_legacy_manifest_without_typography_fields_remains_valid(self):
        manifest = base_manifest()
        manifest["text_boxes"] = [{"text": "旧页面", "box_px": [0, 0, 160, 40], "font_size": 18}]

        self.assertEqual([], quality_contract_violations(manifest))

    def test_governance_fields_require_governed_policy(self):
        manifest = base_manifest()
        manifest["text_boxes"] = [
            {
                "text": "标题",
                "box_px": [20, 20, 120, 30],
                "text_style_id": "card-title",
                "font_size": 18,
            }
        ]

        violations = quality_contract_violations(manifest)

        self.assertTrue(any(item["field"] == "typography_policy" for item in violations))

    def test_unknown_typography_policy_is_rejected(self):
        manifest = base_manifest()
        manifest["typography_policy"] = "goverened"

        violations = quality_contract_violations(manifest)

        self.assertTrue(any(item["field"] == "typography_policy" for item in violations))

    def test_overflow_is_reported_without_mutating_authored_size(self):
        manifest = base_manifest()
        manifest.update(
            {
                "source": {"width_px": 1600, "height_px": 900},
                "slide": {"width": 13.333, "height": 7.5},
                "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
                "typography_policy": "governed",
                "text_boxes": [
                    {
                        "text": "一段会溢出的长文本",
                        "box_px": [20, 20, 80, 10],
                        "font_size": 30,
                    }
                ],
            }
        )

        normalized = normalize_manifest(manifest)
        violations = quality_contract_violations(manifest)

        self.assertEqual(30, normalized["text_boxes"][0]["font_size"])
        self.assertTrue(any("exceeds the estimated" in item["reason"] for item in violations))

    def test_governed_shape_text_overflow_is_reported(self):
        manifest = base_manifest()
        manifest.update(
            {
                "source": {"width_px": 1600, "height_px": 900},
                "slide": {"width": 13.333, "height": 7.5},
                "content_box": {"left": 0, "top": 0, "width": 13.333, "height": 7.5},
                "typography_policy": "governed",
                "shapes": [
                    {
                        "type": "shape",
                        "preset": "rightArrow",
                        "box_px": [20, 20, 80, 10],
                        "text": "箭头内文字",
                        "font_size": 30,
                    }
                ],
            }
        )

        normalized = normalize_manifest(manifest)
        violations = quality_contract_violations(manifest)

        self.assertEqual(30, normalized["shapes"][0]["font_size"])
        self.assertTrue(any(item["field"] == "shapes[0].font_size" for item in violations))


if __name__ == "__main__":
    unittest.main()
