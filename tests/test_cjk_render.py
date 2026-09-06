"""Catch Chinese glyph loss in the actual Office -> PDF -> PNG renderer."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli/image2ppt/runtime"))
from build_pptx_from_manifest import write_pptx
from platform_tools import discover_libreoffice


@unittest.skipUnless(discover_libreoffice(), "actual rendering requires LibreOffice")
class ChineseRenderTests(unittest.TestCase):
    def test_native_chinese_title_has_visible_ink(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)
            manifest = {
                "slide": {"width": 5, "height": 2, "background": "#FFFFFF"},
                "typography_policy": "governed",
                "text_boxes": [{"text": "中文渲染验收", "font": "Noto Sans CJK SC", "font_size": 24,
                                "left": 0.5, "top": 0.5, "width": 4, "height": 1, "color": "#000000"}],
            }
            write_pptx(manifest, page / "page.pptx", page / "manifest.json")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/render_image2ppt_qa.py"), str(page / "page.pptx"),
                 "--out-dir", "render", "--report", "render.json"],
                text=True, capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            report = json.loads((page / "render.json").read_text())
            with Image.open(report["rendered_slides"][0]).convert("L") as image:
                ink = int(np.count_nonzero(np.asarray(image) < 128))
            self.assertGreater(ink, 100, "Chinese text is present in PPTX but absent in its rendered image")
