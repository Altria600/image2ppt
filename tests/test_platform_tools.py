from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

from support import SKILL_ROOT

RUNTIME = SKILL_ROOT / "cli" / "image2ppt" / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from platform_tools import discover_image_magick, discover_libreoffice  # noqa: E402


class PlatformToolTests(unittest.TestCase):
    def test_path_discovery_precedes_platform_candidates(self) -> None:
        with patch("platform_tools.shutil.which", side_effect=lambda name: "/custom/bin/soffice" if name == "soffice" else None):
            self.assertEqual("/custom/bin/soffice", discover_libreoffice(system="Darwin", env={}))

    def test_macos_bundle_candidate_is_discovered_without_installed_program(self) -> None:
        bundle = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")

        def is_file(path: Path) -> bool:
            return path == bundle

        with patch("platform_tools.shutil.which", return_value=None), patch.object(Path, "is_file", is_file):
            self.assertEqual(str(bundle), discover_libreoffice(system="Darwin", env={}))

    def test_windows_program_files_candidate_is_discovered_from_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            executable = root / "LibreOffice 25.2" / "program" / "soffice.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"fixture")
            with patch("platform_tools.shutil.which", return_value=None):
                found = discover_libreoffice(system="Windows", env={"ProgramFiles": str(root)})
            self.assertEqual(str(executable), found)

    def test_no_renderer_is_reported_when_fixture_paths_are_absent(self) -> None:
        with patch("platform_tools.shutil.which", return_value=None), patch.object(Path, "is_file", return_value=False):
            self.assertIsNone(discover_libreoffice(system="Windows", env={}))
            self.assertIsNone(discover_libreoffice(system="Darwin", env={}))

    def test_windows_does_not_treat_system_convert_as_image_magick(self) -> None:
        with patch("platform_tools.shutil.which", side_effect=lambda name: "C:/Windows/System32/convert.exe" if name == "convert" else None):
            self.assertIsNone(discover_image_magick(system="Windows"))


if __name__ == "__main__":
    unittest.main()
