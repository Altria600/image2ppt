from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from support import SCRIPTS


class RenderGuardTests(unittest.TestCase):
    def test_source_image_cannot_be_reused_as_render_proof(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "source.png"
            Image.new("RGB", (320, 180), "white").save(source)
            pptx = root / "page.pptx"
            pptx.write_bytes(b"not-needed-before-source-reuse-guard")
            report = root / "render_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "render_image2ppt_qa.py"),
                    str(pptx),
                    "--out-dir",
                    str(root / "render"),
                    "--report",
                    str(report),
                    "--source",
                    str(source),
                    "--existing-rendered",
                    str(source),
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source reuse", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
