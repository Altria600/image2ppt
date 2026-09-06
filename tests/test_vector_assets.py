from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "cli/image2ppt/runtime"
sys.path.insert(0, str(RUNTIME_DIR))

from vector_assets import (  # noqa: E402
    SvgValidationError,
    VectorTraceError,
    trace_raster_to_svg,
    validate_svg,
)


class VectorAssetTests(unittest.TestCase):
    def write_svg(self, directory: Path, name: str, body: str, *, view_box: str = "0 0 20 20") -> Path:
        path = directory / name
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}">{body}</svg>',
            encoding="utf-8",
        )
        return path

    def test_validate_supported_primitives_groups_transforms_and_fills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg = self.write_svg(
                Path(tmp),
                "supported.svg",
                '<g transform="translate(1,2)"><rect x="1" y="2" width="4" height="5" fill="#fff"/>'
                '<circle cx="10" cy="10" r="3" fill="red"/></g>',
            )
            result = validate_svg(svg)
            self.assertTrue(result["valid"])
            self.assertEqual(2, result["geometry_count"])
            self.assertEqual("svg-image", result["editability"])

    def test_validate_rejects_untrusted_or_non_vector_content(self) -> None:
        cases = {
            "raster.svg": '<image href="data:image/png;base64,AAAA" x="0" y="0" width="10" height="10"/>',
            "remote.svg": '<path d="M0 0 L10 10" fill="url(https://example.test/a.svg)"/>',
            "script.svg": '<script>window.alert(1)</script><path d="M0 0 L10 10"/>',
            "event.svg": '<path d="M0 0 L10 10" onload="alert(1)"/>',
            "text.svg": '<text x="0" y="10">not native</text>',
            "foreign.svg": '<foreignObject width="10" height="10"/>',
            "empty.svg": '<g/>',
        }
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name, body in cases.items():
                with self.subTest(name=name):
                    path = self.write_svg(directory, name, body)
                    with self.assertRaises(ValueError):
                        validate_svg(path)

    def test_validate_requires_finite_positive_view_box(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            missing = directory / "missing.svg"
            missing.write_text('<svg><path d="M0 0 L1 1"/></svg>', encoding="utf-8")
            invalid = self.write_svg(directory, "invalid.svg", '<path d="M0 0 L1 1"/>', view_box="0 0 NaN 20")
            for path in (missing, invalid):
                with self.subTest(path=path.name):
                    with self.assertRaises(SvgValidationError):
                        validate_svg(path)

    def test_trace_uses_real_vtracer_and_writes_fragment_for_chinese_space_paths(self) -> None:
        try:
            import vtracer  # noqa: F401
        except ImportError:
            self.skipTest("optional vtracer package is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "中文 页面"
            page.mkdir()
            source = page / "输入 图.png"
            image = Image.new("RGBA", (32, 24), (255, 255, 255, 0))
            ImageDraw.Draw(image).rectangle((3, 4, 20, 18), fill=(255, 0, 0, 255))
            image.save(source)
            result = trace_raster_to_svg(
                "输入 图.png",
                "assets/diagram.svg",
                page_dir=page,
                source_path="输入 图.png",
                box_px="3,4,18,15",
                fragment_path="diagram-fragment.json",
            )
            output = page / "assets/diagram.svg"
            fragment_path = page / "diagram-fragment.json"
            self.assertEqual(output.resolve(), Path(result["out"]).resolve())
            self.assertIn("<path", output.read_text(encoding="utf-8"))
            self.assertIn("viewBox=", output.read_text(encoding="utf-8"))
            fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
            self.assertEqual("assets/diagram.svg", fragment["images"][0]["path"])
            self.assertEqual("vector-traced", fragment["asset_provenance"][0]["source_type"])
            self.assertEqual("svg-image", fragment["asset_provenance"][0]["editability"])
            self.assertEqual([3.0, 4.0, 18.0, 15.0], fragment["images"][0]["box_px"])

    def test_trace_refuses_overwrite_and_output_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page"
            page.mkdir()
            source = page / "source.png"
            Image.new("RGB", (8, 8), "red").save(source)
            output = page / "asset.svg"
            output.write_text("keep", encoding="utf-8")
            with self.assertRaises(VectorTraceError):
                trace_raster_to_svg(source, output)
            with self.assertRaises(VectorTraceError):
                trace_raster_to_svg(source, "../escaped.svg", page_dir=page)

    def test_fragment_requires_page_local_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / "page"
            page.mkdir()
            source = root / "outside.png"
            Image.new("RGB", (8, 8), "red").save(source)
            with self.assertRaises(VectorTraceError):
                trace_raster_to_svg(source, page / "asset.svg", fragment_path=page / "fragment.json")
            with self.assertRaises(VectorTraceError):
                trace_raster_to_svg(
                    source,
                    page / "asset.svg",
                    page_dir=page,
                    fragment_path="fragment.json",
                )

    def test_cli_exposes_vector_commands(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNTIME_DIR / "main.py"), "vector", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("trace", result.stdout)
        self.assertIn("validate", result.stdout)


if __name__ == "__main__":
    unittest.main()
