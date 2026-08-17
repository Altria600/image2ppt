from __future__ import annotations

import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# These behavior-bearing files are pinned to the migrated baseline. Updating a
# hash is an explicit behavior change and must be accompanied by real conversion
# regression evidence, not only structural unit tests.
BASELINE_SHA256 = {
    "prompts/page-worker-base.md": "62530e2b3bdb1a2103decf68be6b8ebd49294bca55399da2e200687759d14d54",
    "prompts/page-worker.md": "4348386bcda8352e9d387eef99147a70ca885d3a7db16cb666de7fe738a1a27d",
    "cli/image2ppt/runtime/_page_artifacts.py": "f3c46c78cfd1661897d655bfdedd872bc27383325588c7bc7dc26186647e744b",
    "cli/image2ppt/runtime/build_pptx_from_manifest.py": "d547fe8b1d04cf49375654c2e22a9d4a8b11fcd978a6cd3ceae65954f16c2cc0",
    "cli/image2ppt/runtime/deck_run_state.py": "f23da1f111e711f36e1f4ac3244bd64e38a50d9591f4a23b2380bb31891f04e9",
    "cli/image2ppt/runtime/finalize_deck_run.py": "fbf2f819c2c4d62144b5c6007fbaf17024eda3f56e436e7bff36aad08378b29d",
    "cli/image2ppt/runtime/paddle_text_hints.py": "c21c9912aaafdd22dd8399d5b07d8bc9a05732c015001079a7c1ff7ec0de0289",
    "cli/image2ppt/runtime/page_job_status.py": "01e8effade4c3ab6719341c60490cb874f6c9d780e1fdbe00088696362d8703b",
    "cli/image2ppt/runtime/record_page_dispatch.py": "d91b45281c0eafa10801b1344f3c423712b5aeae0aea0231d2243003176f0522",
    "cli/image2ppt/runtime/reset_page_job.py": "81181eb9e5bb42cb973608795592d1a7c1dd04e5bd4ddd339bdc0864f080f42e",
    "cli/image2ppt/runtime/text_hints.py": "07daccc89a847bf9c481fa8f2f2044cc7924e59389e12e0a36eff0a43b45001d",
    "cli/image2ppt/runtime/validate_pptx.py": "2f888f2c3276a5917f29b1bad861955f502b2118dac71e0d326c8513637162c0",
}


class MigrationParityTests(unittest.TestCase):
    def test_behavior_bearing_sources_match_the_migrated_baseline(self) -> None:
        mismatches = []
        for relative, expected in BASELINE_SHA256.items():
            path = ROOT / relative
            content = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else None
            actual = hashlib.sha256(content).hexdigest() if content is not None else "missing"
            if actual != expected:
                mismatches.append(f"{relative}: expected {expected}, got {actual}")
        self.assertEqual([], mismatches)

    def test_prompt_keeps_base_then_profile_layering(self) -> None:
        base = (ROOT / "prompts/page-worker-base.md").read_text(encoding="utf-8")
        profile = (ROOT / "prompts/page-worker.md").read_text(encoding="utf-8")
        self.assertIn("Every non-text foreground visual object must be separated", base)
        self.assertIn("Do not invent an object-source strategy", base)
        self.assertIn("This addendum extends the complete local page-reconstructor prompt above", profile)
        self.assertIn("Replace only the base prompt's final page build/validate sequence", profile)


if __name__ == "__main__":
    unittest.main()
