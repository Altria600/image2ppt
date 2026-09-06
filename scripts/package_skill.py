#!/usr/bin/env python3
"""Create a portable, local Image2PPT Skill archive.

The command packages the checked-out Skill itself.  It never installs to a
global location or guesses a host application's directory.  An explicit
``--stage`` target can be used when an installer needs an unpacked copy; the
target must not already exist.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]

# The package surface is intentionally explicit.  New project-local folders
# (runs, scratch files, reports, or user exports) must not become distributable
# merely because they were added to a checkout.
INCLUDED_TOP_LEVEL = {
    ".gitignore",
    "SKILL.md",
    "LICENSE",
    "README.md",
    "README_EN.md",
    "requirements.txt",
    "config.example.yaml",
    "manifest.yaml",
    "assets",
    "agents",
    "cli",
    "prompts",
    "references",
    "schemas",
    "scripts",
}

# Project-local state, generated data, caches, and credentials must never leak
# into a distributable Skill.  Keep this list name-based so it also protects a
# package built from a dirty worktree or a temporary fixture.
EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".coverage",
    "build",
    "dist",
    "node_modules",
    "output",
    "outputs",
    "artifacts",
    "test-output",
    "tests",
}
EXCLUDED_FILES = {
    "AGENTS.md",
    "PROJECT_STATE.md",
    "config.yaml",
    ".DS_Store",
}
SECRET_SUFFIXES = {".env", ".key", ".pem", ".p12", ".pfx", ".secret", ".token"}
SECRET_NAMES = {
    ".env",
    ".env.local",
    "auth.json",
    "credentials.json",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
}


class PackageError(ValueError):
    """Raised for an invalid source, output, or staging target."""


def _resolved(path: Path) -> Path:
    return Path(path).expanduser().resolve()


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError as exc:
        raise PackageError(f"path is outside the Skill root: {path}") from exc


def _looks_like_secret(path: Path) -> bool:
    name = path.name.lower()
    if name.startswith(".env") or name.endswith((".local.yaml", ".local.yml")):
        return True
    if name in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES:
        return True
    return any(marker in name for marker in ("secret", "credential", "password", "api-key", "apikey", "token"))


def _excluded(relative: Path) -> bool:
    if not relative.parts or relative.parts[0] not in INCLUDED_TOP_LEVEL:
        return True
    if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
        return True
    if (
        relative.name in EXCLUDED_FILES
        or relative.suffix.lower() in {".pyc", ".pyo"}
        or _looks_like_secret(relative)
    ):
        return True
    return False


def _excluded_directory(relative: Path) -> bool:
    return (
        not relative.parts
        or relative.parts[0] not in INCLUDED_TOP_LEVEL
        or any(part in EXCLUDED_DIRECTORIES for part in relative.parts)
    )


def collect_package_files(
    source_root: Path = SKILL_ROOT,
    *,
    output: Path | None = None,
    stage: Path | None = None,
) -> list[Path]:
    """Return source files that belong in a portable Skill package.

    Symlinks are skipped entirely.  This avoids following a link to a secret
    outside the checkout and keeps archives portable across Windows/macOS.
    """

    root = _resolved(source_root)
    if not root.is_dir():
        raise PackageError(f"Skill source directory does not exist: {root}")
    for required in (root / "SKILL.md", root / "requirements.txt"):
        if not required.is_file():
            raise PackageError(f"required Skill file is missing: {required}")

    output_path = _resolved(output) if output is not None else None
    stage_path = _resolved(stage) if stage is not None else None
    relative_stage: Path | None = None
    if stage_path is not None:
        try:
            relative_stage = stage_path.relative_to(root)
        except ValueError:
            relative_stage = None

    files: list[Path] = []

    def visit(directory: Path) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.lower())
        except OSError as exc:
            raise PackageError(f"cannot read Skill source directory: {directory}") from exc
        for path in children:
            if path.is_symlink():
                continue
            relative = _relative(path, root)
            if path.is_dir():
                # Prune excluded directories before entering them.  In
                # particular, packaging must not walk a large local .venv.
                if _excluded_directory(relative):
                    continue
                if relative_stage is not None and (
                    relative == relative_stage or relative_stage in relative.parents
                ):
                    continue
                visit(path)
                continue
            if not path.is_file() or _excluded(relative):
                continue
            resolved = _resolved(path)
            if output_path is not None and resolved == output_path:
                continue
            files.append(path)

    visit(root)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def _zip_info(arcname: str, source: Path) -> zipfile.ZipInfo:
    """Build deterministic archive metadata while retaining executable bits."""

    info = zipfile.ZipInfo(arcname)
    # ZIP timestamps cannot represent dates before 1980.  A fixed timestamp
    # makes package hashes stable across checkouts and avoids leaking local
    # modification times.
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    try:
        if source.stat().st_mode & 0o111:
            info.external_attr = (0o100755 << 16) | 0x80000000
        else:
            info.external_attr = (0o100644 << 16) | 0x80000000
    except OSError:
        info.external_attr = (0o100644 << 16) | 0x80000000
    return info


def _write_zip(output: Path, root: Path, files: list[Path]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = output.open("xb")
    except FileExistsError as exc:
        raise PackageError(f"refusing to overwrite existing package: {output}") from exc
    try:
        with handle:
            with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for source in files:
                    relative = source.relative_to(root).as_posix()
                    archive.writestr(_zip_info(relative, source), source.read_bytes())
    except Exception:
        output.unlink(missing_ok=True)
        raise


def _stage_files(stage: Path, root: Path, files: list[Path]) -> None:
    if stage.exists():
        raise PackageError(f"refusing to overwrite existing staging target: {stage}")
    stage.parent.mkdir(parents=True, exist_ok=True)
    try:
        stage.mkdir()
        for source in files:
            relative = source.relative_to(root)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def create_package(
    output: Path,
    *,
    source_root: Path = SKILL_ROOT,
    stage: Path | None = None,
) -> list[str]:
    """Create ``output`` and optionally an unpacked copy at ``stage``."""

    root = _resolved(source_root)
    target = _resolved(output)
    stage_target = _resolved(stage) if stage is not None else None
    if target.exists():
        raise PackageError(f"refusing to overwrite existing package: {target}")
    if stage_target is not None and stage_target.exists():
        raise PackageError(f"refusing to overwrite existing staging target: {stage_target}")
    files = collect_package_files(root, output=target, stage=stage_target)
    if not files:
        raise PackageError("Skill source contains no packageable files")
    _write_zip(target, root, files)
    if stage_target is not None:
        _stage_files(stage_target, root, files)
    return [path.relative_to(root).as_posix() for path in files]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a portable Image2PPT Skill ZIP.")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Destination ZIP path. It must not already exist.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=SKILL_ROOT,
        help="Skill root to package (default: this repository).",
    )
    parser.add_argument(
        "--stage",
        "--staging-dir",
        "--stage-dir",
        "--install-to",
        "--install-target",
        dest="stage",
        type=Path,
        help="Optional explicit unpacked staging directory; it must not already exist.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        members = create_package(args.output, source_root=args.source, stage=args.stage)
    except (OSError, PackageError) as exc:
        print(f"package failed: {exc}", file=sys.stderr)
        return 2
    print(f"package={_resolved(args.output)}")
    print(f"files={len(members)}")
    if args.stage is not None:
        print(f"stage={_resolved(args.stage)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
