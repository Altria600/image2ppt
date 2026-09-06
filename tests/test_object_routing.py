from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "cli/image2ppt/runtime"
sys.path.insert(0, str(RUNTIME_DIR))

from object_routing import (  # noqa: E402
    ObjectRoutingError,
    manifest_routing_violations,
    route_object,
)
from validate_pptx import page_contract_violations  # noqa: E402


class ObjectRoutingTests(unittest.TestCase):
    def write_svg(self, path: Path, body: str) -> None:
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">{body}</svg>',
            encoding="utf-8",
        )

    def flat_icon_record(self, path: str = "assets/icon.svg") -> dict:
        return {
            "object_kind": "flat-icon",
            "source_type": "svg-reconstructed",
            "editability": "svg-image",
            "path": path,
            "source_box_px": [10, 10, 40, 40],
            "identity_evidence": "Contour and negative space checked against the source icon.",
            "processing_method": "faithful-svg-reconstruction",
            "reason": "Flat icon is kept as a movable SVG image.",
        }

    def source_asset_record(self, path: str = "assets/photo.png") -> dict:
        return {
            "object_kind": "complex-visual",
            "source_type": "source-extracted",
            "editability": "raster-image",
            "path": path,
            "source": "source.png",
            "source_box_px": [20, 20, 30, 24],
            "identity_evidence": "Local photo bounds and source identity were checked.",
            "contamination_check": {
                "passed": True,
                "observation": "No neighboring text or card border is inside the extracted box.",
            },
            "processing_method": "bounded-source-extraction",
            "reason": "Only the bounded complex visual is retained as a raster image.",
        }

    def test_flat_svg_is_svg_image_not_native_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            self.write_svg(page / "assets/icon.svg", '<path d="M1 1 L19 1 L10 19 Z" fill="#2563EB"/>')
            route = route_object(self.flat_icon_record(), source_size_px=[100, 100], manifest_base=page)
            self.assertEqual("svg-reconstructed", route["source_type"])
            self.assertEqual("svg-image", route["editability"])

    def test_native_text_and_ordinary_arrow_are_protected(self) -> None:
        route = route_object({"object_kind": "ordinary-arrow"})
        self.assertEqual({"source_type": "native-object", "editability": "native-object"}, route)
        with self.assertRaises(ObjectRoutingError):
            route_object({"object_kind": "icon"})
        with self.assertRaises(ObjectRoutingError):
            route_object(
                {
                    "object_kind": "ordinary-arrow",
                    "source_type": "source-extracted",
                    "editability": "raster-image",
                    "path": "assets/arrow.png",
                    "source_box_px": [1, 1, 10, 10],
                    "identity_evidence": "not applicable",
                    "contamination_check": {"passed": True, "observation": "clean"},
                }
            )

    def test_bounded_complex_source_asset_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            Image.new("RGB", (30, 24), "#4B8BFF").save(page / "assets/photo.png")
            Image.new("RGB", (100, 100), "white").save(page / "source.png")
            route = route_object(self.source_asset_record(), source_size_px=[100, 100], manifest_base=page)
            self.assertEqual("source-extracted", route["source_type"])
            self.assertEqual("raster-image", route["editability"])

    def test_full_page_source_extraction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            Image.new("RGB", (100, 100), "white").save(page / "assets/photo.png")
            record = self.source_asset_record()
            record["source_box_px"] = [0, 0, 100, 100]
            with self.assertRaises(ObjectRoutingError):
                route_object(record, source_size_px=[100, 100], manifest_base=page)

    def test_renamed_page_screenshot_is_rejected_even_with_small_declared_box(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            source = Image.new("RGB", (100, 100), "white")
            source.save(page / "source.png")
            (page / "assets/renamed.png").write_bytes((page / "source.png").read_bytes())
            record = self.source_asset_record("assets/renamed.png")
            record["source_box_px"] = [20, 20, 30, 24]
            with self.assertRaises(ObjectRoutingError):
                route_object(
                    record,
                    source_size_px=[100, 100],
                    manifest_base=page,
                    page_source_path="source.png",
                )

    def test_source_extracted_clone_uses_default_page_source_when_path_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            source = Image.new("RGB", (100, 100), "white")
            source.save(page / "source.png")
            (page / "assets/renamed.png").write_bytes((page / "source.png").read_bytes())
            asset = self.source_asset_record("assets/renamed.png")
            manifest = {
                "source": {"width_px": 100, "height_px": 100},
                "visual_inventory": [{"id": "asset", "kind": "foreground-asset", **asset}],
                "images": [{"id": "asset", "path": "assets/renamed.png", "box_px": [20, 20, 30, 24]}],
                "asset_provenance": [{"path": "assets/renamed.png", **asset}],
            }
            violations = manifest_routing_violations(manifest, manifest_base=page)
            self.assertTrue(any("unchanged copy" in item["reason"] for item in violations))

    def test_new_source_extracted_route_fails_without_locatable_page_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            Image.new("RGB", (30, 24), "#4B8BFF").save(page / "assets/photo.png")
            asset = self.source_asset_record()
            manifest = {
                "source": {"width_px": 100, "height_px": 100},
                "visual_inventory": [{"id": "photo", "kind": "foreground-asset", **asset}],
                "images": [{"id": "photo", "path": "assets/photo.png", "box_px": [20, 20, 30, 24]}],
                "asset_provenance": [{"path": "assets/photo.png", **asset}],
            }
            violations = manifest_routing_violations(manifest, manifest_base=page)
            self.assertTrue(any("page source" in item["reason"] for item in violations))

    def test_invalid_editability_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            self.write_svg(page / "assets/icon.svg", '<circle cx="10" cy="10" r="8"/>')
            record = self.flat_icon_record()
            record["editability"] = "native-object"
            with self.assertRaises(ObjectRoutingError):
                route_object(record, source_size_px=[100, 100], manifest_base=page)

    def test_contaminated_svg_is_rejected_by_local_svg_validator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            self.write_svg(page / "assets/bad.svg", '<script>alert(1)</script><path d="M1 1 L19 19"/>')
            with self.assertRaises(ObjectRoutingError):
                route_object(self.flat_icon_record("assets/bad.svg"), source_size_px=[100, 100], manifest_base=page)

    def test_manifest_validator_is_the_page_route_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            Image.new("RGB", (30, 24), "#4B8BFF").save(page / "assets/photo.png")
            Image.new("RGB", (100, 100), "white").save(page / "source.png")
            asset = self.source_asset_record()
            manifest = {
                "source": {"path": "source.png", "width_px": 100, "height_px": 100},
                "visual_inventory": [{"id": "photo", "kind": "foreground-asset", **asset}],
                "images": [{"id": "photo", "path": "assets/photo.png", "box_px": [20, 20, 30, 24]}],
                "asset_provenance": [{"path": "assets/photo.png", **asset}],
            }
            self.assertEqual([], manifest_routing_violations(manifest, manifest_base=page))

    def clean_base_manifest(self, *, kind: str = "background") -> dict:
        return {
            "slide": {"width": 10, "height": 6},
            "images": [{"path": "assets/clean-base.png", "left": 0, "top": 0, "width": 10, "height": 6}],
            "text_boxes": [{"text": "Native title"}],
            "asset_provenance": [{
                "path": "assets/clean-base.png",
                "source_type": "image-edited",
                "editability": "raster-image",
                "source": "source.png",
                "provenance_note": "Explicit local clean base with source identity retained.",
            }],
            "visual_inventory": [{
                "id": "background",
                "kind": kind,
                "representation": "image-edited",
                "path": "assets/clean-base.png",
            }],
            "background_strategy": {
                "mode": "image-edited-clean-base",
                "source_consistency_contract": "Foreground text is removed while source composition and background identity remain.",
                "removed_foreground": ["Native title"],
                "comparison_note": "Clean base was compared against source.png after foreground removal.",
            },
        }

    def test_evidenced_background_clean_base_is_allowed_full_slide(self) -> None:
        self.assertEqual([], page_contract_violations(self.clean_base_manifest()))

    def test_full_slide_foreground_asset_is_rejected(self) -> None:
        violations = page_contract_violations(self.clean_base_manifest(kind="foreground-asset"))
        self.assertTrue(any("full-slide image" in item["reason"] for item in violations))

    def test_clean_base_that_copies_page_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            (page / "assets").mkdir()
            source = Image.new("RGB", (100, 60), "white")
            source.save(page / "source.png")
            (page / "assets/clean-base.png").write_bytes((page / "source.png").read_bytes())
            manifest = self.clean_base_manifest()
            manifest["source"] = {"width_px": 100, "height_px": 60}
            violations = page_contract_violations(manifest, manifest_base=page)
            self.assertTrue(any("unchanged copy" in item["reason"] for item in violations))


if __name__ == "__main__":
    unittest.main()
