from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import SKILL_ROOT, SCRIPTS, write_json


class SingleRuntimeTests(unittest.TestCase):
    def test_only_one_state_and_manifest_lifecycle_is_defined(self) -> None:
        forbidden_files = [
            "image2ppt_jobs.json",
            "image2ppt_plan.json",
            "source_reconstruction_plan.json",
            "image2ppt_page_result.json",
        ]
        runtime_text = "\n".join(
            path.read_text(encoding="utf-8")
            for root in (SKILL_ROOT / "cli", SKILL_ROOT / "scripts")
            for path in root.rglob("*.py")
        )
        for name in forbidden_files:
            self.assertNotIn(name, runtime_text)
        self.assertTrue((SKILL_ROOT / "cli/image2ppt/runtime/deck_run_state.py").is_file())
        self.assertTrue((SKILL_ROOT / "cli/image2ppt/runtime/paddle_text_hints.py").is_file())
        self.assertTrue((SKILL_ROOT / "cli/image2ppt/runtime/text_hints.py").is_file())

    def test_prompt_builder_is_complete_and_uses_absolute_local_cli(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            run = Path(name)
            page = run / "pages" / "page_001"
            page.mkdir(parents=True)
            source = page / "source.png"
            source.write_bytes(b"fixture-path-only")
            write_json(
                run / "page_jobs.json",
                {"schema_version": 1, "pages": [{"page_id": "page_001", "page_dir": "pages/page_001", "status": "pending"}]},
            )
            write_json(page / "page_request.json", {"source_image": str(source)})
            out = page / "worker-prompt.md"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "build_page_worker_prompt.py"), str(run), "--page", "page_001", "--out", str(out)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state_owner"], "page_jobs.json")
            prompt_template = Path(payload["prompt_template"])
            prompt_addendum = Path(payload["prompt_addendum"])
            self.assertEqual(prompt_template, SKILL_ROOT / "prompts" / "page-worker-base.md")
            self.assertEqual(prompt_addendum, SKILL_ROOT / "prompts" / "page-worker.md")
            self.assertTrue(prompt_template.is_file())
            self.assertTrue(prompt_addendum.is_file())
            prompt = out.read_text(encoding="utf-8")
            self.assertIn(str(SKILL_ROOT / "cli/image2ppt/cli.py"), prompt)
            self.assertIn("Image2PPT", prompt)
            for contract in (
                "page_jobs.json",
                "manifest.json",
                "asset_provenance",
                "image2ppt_region_decomposition",
                "text_style_id",
                "validation.json",
                "run_image2ppt_qa.py",
            ):
                self.assertIn(contract, prompt)
            self.assertNotIn("{{RUN_DIR}}", prompt)
            self.assertNotIn("{{PAGE_DIR}}", prompt)
            self.assertNotIn("{{CLI}}", prompt)

    def test_skill_declares_local_owners_and_final_gate(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for contract in (
            "page_jobs.json",
            "manifest.json",
            "Paddle token",
            "builtin-ink",
            "run_final_image2ppt_qa.py",
        ):
            self.assertIn(contract, skill)
        self.assertRegex(skill, r"(?i)(local|本地).*(remote|远程)")
        self.assertIn("visual_review_status", skill)


if __name__ == "__main__":
    unittest.main()
