from __future__ import annotations

import re
import unittest
from pathlib import Path

from support import SKILL_ROOT


class ProjectMetadataTests(unittest.TestCase):
    def test_readmes_are_mirrored_and_preview_assets_exist(self) -> None:
        readme_cn = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (SKILL_ROOT / "README_EN.md").read_text(encoding="utf-8")
        # The compact badge header must keep both language navigation and the
        # two supported agent installation targets discoverable.
        self.assertIn('href="README_EN.md"', readme_cn)
        self.assertIn('href="README.md"', readme_en)
        for readme in (readme_cn, readme_en):
            self.assertIn('alt="Install"', readme)
            self.assertIn("Claude%20Code%20%7C%20Codex", readme)
            self.assertIn("https://github.com/Paul-Jeo/Image2PPT", readme)
            self.assertNotIn("<IMAGE2PPT_REPOSITORY>", readme)
            self.assertNotIn("https://github.com/Paul-Jeo/fed_llm", readme)
        self.assertEqual(
            len(re.findall(r"^## ", readme_cn, flags=re.MULTILINE)),
            len(re.findall(r"^## ", readme_en, flags=re.MULTILINE)),
        )
        for relative in (
            "assets/readme/banner.png",
            "assets/readme/business-source.png",
            "assets/readme/business-converted.png",
            "assets/readme/scientific-source.png",
            "assets/readme/scientific-converted.png",
            "assets/readme/clarity-comparison.png",
            "assets/readme/detail-comparison.png",
        ):
            self.assertTrue((SKILL_ROOT / relative).is_file(), relative)

    def test_public_config_template_contains_no_secret(self) -> None:
        yaml_template = (SKILL_ROOT / "config.example.yaml").read_text(encoding="utf-8")
        self.assertRegex(yaml_template, r'(?m)^PADDLE_OCR_TOKEN:\s*""\s*$')
        self.assertNotIn("sk-", yaml_template)
        self.assertFalse((SKILL_ROOT / ".env.example").exists())

    def test_secret_files_and_generated_runs_are_ignored(self) -> None:
        ignore = (SKILL_ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", "config.yaml", "output/", "runs/", "__pycache__/"):
            self.assertIn(pattern, ignore)

    def test_openai_metadata_has_required_user_facing_fields(self) -> None:
        metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Image2PPT"', metadata)
        self.assertIn("$image2ppt", metadata)
        match = re.search(r'^\s*short_description:\s*"([^"]+)"', metadata, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(len(match.group(1)), 25)
        self.assertLessEqual(len(match.group(1)), 64)


if __name__ == "__main__":
    unittest.main()
