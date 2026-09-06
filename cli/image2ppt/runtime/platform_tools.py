#!/usr/bin/env python3
"""Small platform capability helpers shared by the Image2PPT runtime.

The runtime deliberately discovers local programs instead of guessing from a
provider or host application.  Keeping the candidate paths here lets the CLI,
input normalisation, and QA renderer report the same result on each platform.
"""

from __future__ import annotations

import os
import platform
import shutil
from collections.abc import Mapping
from pathlib import Path
from xml.etree import ElementTree as ET


def _windows_candidates(environ: Mapping[str, str]) -> list[Path]:
    """Return conventional LibreOffice install paths on Windows.

    LibreOffice normally installs below ``Program Files``.  The three
    variables cover native 64-bit installs and 32-bit installs on a 64-bit
    system without relying on a particular drive letter.  A versioned
    directory (for example ``LibreOffice 25.2``) is also accepted.
    """

    candidates: list[Path] = []
    roots: list[Path] = []
    normalized_env = {str(key).lower(): value for key, value in environ.items()}
    for name in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        value = str(normalized_env.get(name.lower(), "")).strip()
        if value:
            root = Path(value)
            if root not in roots:
                roots.append(root)

    for root in roots:
        install_dirs = [root / "LibreOffice"]
        try:
            install_dirs.extend(sorted(root.glob("LibreOffice*")))
        except OSError:
            # A missing/inaccessible Program Files directory is simply an
            # unavailable optional renderer, not a discovery failure.
            pass
        for install_dir in install_dirs:
            for executable in ("soffice.exe", "soffice.com", "soffice"):
                candidate = install_dir / "program" / executable
                if candidate not in candidates:
                    candidates.append(candidate)
    return candidates


def _platform_candidates(system: str, environ: Mapping[str, str]) -> list[Path]:
    normalized = system.strip().lower()
    if normalized in {"darwin", "mac", "macos", "osx"}:
        # The system-wide app path is the supported default.  A per-user app
        # install is common on macOS, so include it without requiring it.
        return [
            Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
            Path.home() / "Applications" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
        ]
    if normalized in {"windows", "win32", "win"}:
        return _windows_candidates(environ)
    return []


def discover_libreoffice(
    system: str | None = None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Return an existing local LibreOffice executable, or ``None``.

    PATH is checked first, followed by platform-native installation paths.
    ``system`` and ``env`` are optional seams for offline discovery tests; the
    normal runtime uses :func:`platform.system` and :data:`os.environ`.
    """

    current_system = system or platform.system()
    environ = os.environ if env is None else env

    for command in ("soffice", "libreoffice"):
        found = shutil.which(command)
        if found:
            return found

    for candidate in _platform_candidates(current_system, environ):
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return None


def discover_image_magick(system: str | None = None) -> str | None:
    """Return an ImageMagick executable available on PATH, if any.

    ``magick`` is preferred on current ImageMagick releases; ``convert`` is
    retained as a portable fallback for older Unix installations.
    """

    commands = ["magick"]
    # Windows ships a different ``convert.exe`` (the filesystem conversion
    # utility), so never mistake it for ImageMagick.  Unix installations may
    # still expose ImageMagick 6 as ``convert``.
    if (system or platform.system()).strip().lower() not in {"windows", "win32", "win"}:
        commands.append("convert")
    for command in commands:
        found = shutil.which(command)
        if found:
            return found
    return None


def libreoffice_environment(work_dir: Path) -> dict[str, str]:
    """Give macOS headless Fontconfig access to the installed system fonts.

    Some macOS LibreOffice builds use Fontconfig in headless mode but ship no
    macOS font directories. The resulting PDF silently omits CJK glyphs.
    Keep this configuration and cache scoped to the conversion, and respect an
    explicitly configured Fontconfig installation.
    """
    env = os.environ.copy()
    if platform.system().lower() != "darwin" or env.get("FONTCONFIG_FILE") or env.get("FONTCONFIG_PATH"):
        return env
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    root = ET.Element("fontconfig")
    for directory in (Path("/Library/Fonts"), Path("/System/Library/Fonts"), Path.home() / "Library/Fonts"):
        if directory.is_dir():
            ET.SubElement(root, "dir").text = str(directory)
    ET.SubElement(root, "cachedir").text = str(work_dir / "font-cache")
    config = work_dir / "fonts.conf"
    ET.ElementTree(root).write(config, encoding="utf-8", xml_declaration=True)
    env["FONTCONFIG_FILE"] = str(config)
    return env


__all__ = ["discover_image_magick", "discover_libreoffice", "libreoffice_environment"]
