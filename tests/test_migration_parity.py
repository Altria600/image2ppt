from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# These files are the behavior-bearing prompt/runtime surface of the migration.
# Keep the inventory explicit, but validate that the current resources exist and
# parse instead of freezing historical bytes while routing/provider contracts
# continue to evolve.
BEHAVIOR_BEARING_FILES = (
    "prompts/page-worker-base.md",
    "prompts/page-worker.md",
    "cli/image2ppt/runtime/_page_artifacts.py",
    "cli/image2ppt/runtime/split_alpha_components.py",
    "cli/image2ppt/runtime/build_pptx_from_manifest.py",
    "cli/image2ppt/runtime/deck_run_state.py",
    "cli/image2ppt/runtime/finalize_deck_run.py",
    "cli/image2ppt/runtime/paddle_text_hints.py",
    "cli/image2ppt/runtime/page_job_status.py",
    "cli/image2ppt/runtime/record_page_dispatch.py",
    "cli/image2ppt/runtime/reset_page_job.py",
    "cli/image2ppt/runtime/text_hints.py",
    "cli/image2ppt/runtime/validate_pptx.py",
)


class MigrationParityTests(unittest.TestCase):
    def test_behavior_bearing_sources_are_present_and_parseable(self) -> None:
        missing: list[str] = []
        invalid_python: list[str] = []
        empty_documents: list[str] = []
        for relative in BEHAVIOR_BEARING_FILES:
            path = ROOT / relative
            if not path.is_file():
                missing.append(relative)
                continue
            source = path.read_text(encoding="utf-8")
            if not source.strip():
                empty_documents.append(relative)
            if path.suffix == ".py":
                try:
                    compile(source, str(path), "exec")
                except SyntaxError:
                    invalid_python.append(relative)
        self.assertEqual([], missing)
        self.assertEqual([], empty_documents)
        self.assertEqual([], invalid_python)

    def test_prompt_keeps_base_then_profile_layering(self) -> None:
        base = (ROOT / "prompts/page-worker-base.md").read_text(encoding="utf-8")
        profile = (ROOT / "prompts/page-worker.md").read_text(encoding="utf-8")

        for placeholder in ("{{RUN_DIR}}", "{{PAGE_DIR}}", "{{PAGE_BUILD_COMMAND}}"):
            self.assertIn(placeholder, base)
        self.assertIn("{{SKILL_ROOT}}", profile)
        for contract in ("page_jobs.json", "manifest.json", "asset_provenance", "validation.json"):
            self.assertIn(contract, base)
        for contract in ("image2ppt_region_decomposition", "source_type", "editability", "Extended page gate"):
            self.assertIn(contract, profile)
        self.assertLess(base.index("Required page artifacts"), base.index("Return only:"))
        self.assertLess(profile.index("Profile rules:"), profile.index("## Extended page gate"))


if __name__ == "__main__":
    unittest.main()
