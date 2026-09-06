#!/usr/bin/env python3
"""Build the original two-layer page-worker prompt from local resources."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from runtime_paths import CLI_ENTRY, SKILL_ROOT, resolve_inside


BASE_TEMPLATE = SKILL_ROOT / "prompts" / "page-worker-base.md"
PROFILE_ADDENDUM = SKILL_ROOT / "prompts" / "page-worker.md"


def shell_command(argv: list[str], *, windows: bool | None = None) -> str:
    """Render display commands for POSIX shells or Windows PowerShell."""
    is_windows = sys.platform == "win32" if windows is None else windows
    if is_windows:
        return "& " + " ".join("'" + str(item).replace("'", "''") + "'" for item in argv)
    return shlex.join([str(item) for item in argv])


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def run_dir_from_target(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if path.is_dir():
        return path
    if path.name == "deck_manifest.json" and path.is_file():
        return path.parent
    raise ValueError(f"expected Image2PPT run directory or deck_manifest.json: {value}")


def find_page(run_dir: Path, page_ref: str) -> tuple[dict, Path]:
    jobs = read_json(run_dir / "page_jobs.json")
    candidates = {str(page_ref)}
    if str(page_ref).isdigit():
        candidates.add(f"page_{int(page_ref):03d}")
    for page in jobs.get("pages") or []:
        if str(page.get("page_id")) in candidates:
            page_dir = resolve_inside(run_dir, str(page.get("page_dir") or ""))
            return page, page_dir
    raise ValueError(f"page not found in page_jobs.json: {page_ref}")


def fenced_template(path: Path) -> str:
    """Return the original base prompt body without its documentation fence."""
    text = path.read_text(encoding="utf-8")
    marker = "```text"
    start = text.find(marker)
    if start == -1:
        return text.strip()
    start += len(marker)
    end = text.rfind("```")
    return text[start:end].strip() if end > start else text[start:].strip()


def render_prompt(run_dir: Path, page: dict, page_dir: Path) -> str:
    base = fenced_template(BASE_TEMPLATE)
    addendum = PROFILE_ADDENDUM.read_text(encoding="utf-8").strip()
    template = base + "\n\n" + addendum
    request = read_json(page_dir / "page_request.json")
    prefix = [sys.executable, str(CLI_ENTRY)]
    cli = shell_command(prefix)
    replacements = {
        "{{RUN_DIR}}": str(run_dir),
        "{{PAGE_ID}}": str(page.get("page_id")),
        "{{PAGE_DIR}}": str(page_dir),
        "{{SOURCE_IMAGE}}": str(request.get("source_image") or page_dir / "source.png"),
        "{{SKILL_ROOT}}": str(SKILL_ROOT),
        "{{CLI}}": cli,
        "{{PAGE_BUILD_COMMAND}}": shell_command([*prefix, "page", "build", str(page_dir)]),
        "{{PAGE_VALIDATE_COMMAND}}": shell_command([*prefix, "page", "validate", str(page_dir)]),
        "{{PAGE_QA_COMMAND}}": shell_command([sys.executable, str(SKILL_ROOT / "scripts/run_image2ppt_qa.py"), str(page_dir)]),
        "{{PAGE_CONTACT_COMMAND}}": shell_command([*prefix, "page", "contact-sheet", str(page_dir)]),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    unresolved = sorted({part for part in replacements if part in template})
    if unresolved:
        raise ValueError(f"unfilled prompt placeholders: {unresolved}")
    return template.rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a self-contained Image2PPT page-worker prompt")
    parser.add_argument("run")
    parser.add_argument("--page", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    run_dir = run_dir_from_target(args.run)
    page, page_dir = find_page(run_dir, args.page)
    try:
        out = resolve_inside(page_dir, args.out)
    except ValueError as exc:
        raise SystemExit(f"worker prompt must live inside the page directory: {args.out}") from exc
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_prompt(run_dir, page, page_dir), encoding="utf-8")
    dispatch_argv = [sys.executable, str(CLI_ENTRY), "run", "dispatch", str(run_dir),
                     "--page", str(page.get("page_id")), "--agent-id", "<worker-id>", "--prompt-file", str(out)]
    payload = {
        "prompt_file": str(out),
        "prompt_template": str(BASE_TEMPLATE),
        "prompt_addendum": str(PROFILE_ADDENDUM),
        "page_id": page.get("page_id"),
        "page_dir": str(page_dir),
        "run_dir": str(run_dir),
        "state_owner": "page_jobs.json",
        "dispatch_command_template": shell_command(dispatch_argv),
        "dispatch_argv_template": dispatch_argv,
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
