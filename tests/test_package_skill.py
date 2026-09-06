from __future__ import annotations

import tempfile
import unittest
import zipfile
import sys
from pathlib import Path

from support import SKILL_ROOT

SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from package_skill import PackageError, collect_package_files, create_package  # noqa: E402


class PackageSkillTests(unittest.TestCase):
    def test_real_package_contains_runtime_resources_and_excludes_caches(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            output = Path(name) / "image2ppt.zip"
            members = create_package(output)
            self.assertIn("SKILL.md", members)
            self.assertIn("requirements.txt", members)
            self.assertIn(".gitignore", members)
            self.assertIn("cli/image2ppt/cli.py", members)
            self.assertIn("scripts/render_image2ppt_qa.py", members)
            self.assertIn("references/workflow.md", members)
            self.assertIn("prompts/page-worker.md", members)
            self.assertIn("schemas/page-manifest-v2.schema.json", members)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                requirements = archive.read("requirements.txt").decode("utf-8")
            self.assertEqual(names, set(members))
            self.assertIn("resvg_py", requirements)
            self.assertFalse(any("__pycache__" in name or name.startswith("tests/") for name in names))
            self.assertFalse(any(name.startswith(".venv/") or name.startswith(".git/") for name in names))

    def test_fixture_secrets_outputs_and_symlink_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "skill"
            root.mkdir()
            (root / "SKILL.md").write_text("# fixture\n", encoding="utf-8")
            (root / "requirements.txt").write_text("Pillow\n", encoding="utf-8")
            (root / "references").mkdir()
            (root / "references" / "contract.md").write_text("contract\n", encoding="utf-8")
            (root / "config.yaml").write_text("OPENAI_API_KEY: leaked\n", encoding="utf-8")
            (root / "config.local.yaml").write_text("PADDLE_OCR_TOKEN: leaked\n", encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "scripts" / ".env.production").write_text("PRIVATE_VALUE=leaked\n", encoding="utf-8")
            (root / "scripts" / "config.local.yaml").write_text("PRIVATE_VALUE: leaked\n", encoding="utf-8")
            (root / "runs").mkdir()
            (root / "runs" / "run.json").write_text("generated\n", encoding="utf-8")
            (root / "secret.pem").write_text("private\n", encoding="utf-8")
            (root / "output").mkdir()
            (root / "output" / "generated.pptx").write_bytes(b"output")
            (root / ".venv").mkdir()
            (root / ".venv" / "python").write_bytes(b"cache")
            (root / "tests").mkdir()
            (root / "tests" / "test_fixture.py").write_text("test\n", encoding="utf-8")
            outside = Path(name) / "outside-secret.txt"
            outside.write_text("secret\n", encoding="utf-8")
            try:
                (root / "linked-secret.txt").symlink_to(outside)
            except (OSError, NotImplementedError):
                pass

            files = collect_package_files(root)
            members = {path.relative_to(root.resolve()).as_posix() for path in files}
            self.assertEqual(members, {"SKILL.md", "requirements.txt", "references/contract.md"})

    def test_existing_output_and_stage_are_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "skill"
            root.mkdir()
            (root / "SKILL.md").write_text("# fixture\n", encoding="utf-8")
            (root / "requirements.txt").write_text("Pillow\n", encoding="utf-8")
            output = Path(name) / "package.zip"
            output.write_bytes(b"sentinel")
            with self.assertRaises(PackageError):
                create_package(output, source_root=root)
            self.assertEqual(b"sentinel", output.read_bytes())

            stage = Path(name) / "stage"
            stage.mkdir()
            (stage / "sentinel").write_text("keep", encoding="utf-8")
            with self.assertRaises(PackageError):
                create_package(Path(name) / "other.zip", source_root=root, stage=stage)
            self.assertEqual("keep", (stage / "sentinel").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
