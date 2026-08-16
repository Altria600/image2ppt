#!/usr/bin/env python3
"""Postprocess and validate the final deck produced by ``image2ppt run finalize``."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from render_image2ppt_qa import image_diff
from runtime_paths import SCRIPT_DIR, image2ppt_runtime_script
from postprocess_manifest_arrows import load_run_manifests, read_json, write_json


def run(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-8000:],
    }


def safe_json(path: Path) -> dict[str, Any]:
    try:
        return read_json(path) if path.is_file() else {}
    except (OSError, ValueError, TypeError):
        return {}


def page_sources(run_dir: Path) -> list[Path]:
    deck = read_json(run_dir / "deck_manifest.json")
    root = Path(deck.get("job_dir") or run_dir)
    root = root.resolve() if root.is_absolute() else (run_dir / root).resolve()
    sources: list[Path] = []
    for page in deck.get("pages") or []:
        raw = str(page.get("source_image") or "").strip()
        if not raw:
            continue
        value = Path(raw)
        sources.append(value.resolve() if value.is_absolute() else (root / value).resolve())
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Image2PPT arrows and supplemental QA to a finalized image2ppt deck")
    parser.add_argument("run", type=Path)
    parser.add_argument("--pptx", type=Path)
    parser.add_argument("--visual-review-status", choices=["needs_review", "reviewed", "failed"], default="needs_review")
    parser.add_argument("--visual-review-notes", default="")
    parser.add_argument("--render-timeout", type=int, default=180)
    args = parser.parse_args()

    run_dir = args.run.expanduser().resolve()
    manifests, default_pptx = load_run_manifests(run_dir)
    pptx = args.pptx.expanduser().resolve() if args.pptx else default_pptx
    final_dir = pptx.parent
    paths = {
        "postprocess": final_dir / "image2ppt_arrow_postprocess.json",
        "regions": final_dir / "image2ppt_region_decomposition.json",
        "structural": final_dir / "image2ppt_structural_validation.json",
        "inspection": final_dir / "image2ppt_arrow_inspection.json",
        "render": final_dir / "image2ppt_render_report.json",
        "report": final_dir / "image2ppt_qa.json",
    }
    errors: list[str] = []
    checks: dict[str, Any] = {}
    if not pptx.is_file():
        errors.append(f"image2ppt final output is missing: {pptx}")

    if not errors:
        command = [
            sys.executable,
            str(SCRIPT_DIR / "inspect_region_decomposition.py"),
            "--run",
            str(run_dir),
            "--out",
            str(paths["regions"]),
        ]
        checks["region_decomposition_command"] = run(command)
        checks["region_decomposition"] = safe_json(paths["regions"])
        if (
            checks["region_decomposition_command"]["returncode"] != 0
            or checks["region_decomposition"].get("passed") is not True
        ):
            errors.append("final semantic-region or compound-diagram inspection failed")

    if not errors:
        command = [
            sys.executable,
            str(SCRIPT_DIR / "postprocess_manifest_arrows.py"),
            str(pptx),
            "--run",
            str(run_dir),
            "--report",
            str(paths["postprocess"]),
        ]
        checks["postprocess_command"] = run(command)
        checks["postprocess"] = safe_json(paths["postprocess"])
        if checks["postprocess_command"]["returncode"] != 0 or checks["postprocess"].get("passed") is not True:
            errors.append("final arrow postprocessing failed")

    if not errors:
        command = [
            sys.executable,
            str(image2ppt_runtime_script("validate_pptx.py")),
            str(pptx),
            "--deck-manifest",
            str(run_dir / "deck_manifest.json"),
            "--report",
            str(paths["structural"]),
        ]
        checks["image2ppt_validation_command"] = run(command)
        checks["image2ppt_validation"] = safe_json(paths["structural"])
        if checks["image2ppt_validation_command"]["returncode"] != 0 or checks["image2ppt_validation"].get("passed") is not True:
            errors.append("local image2ppt deck validation failed after arrow postprocessing")

    if not errors:
        command = [
            sys.executable,
            str(SCRIPT_DIR / "inspect_arrow_atomicity.py"),
            str(pptx),
            "--run",
            str(run_dir),
            "--out",
            str(paths["inspection"]),
        ]
        checks["arrow_inspection_command"] = run(command)
        checks["arrow_inspection"] = safe_json(paths["inspection"])
        if checks["arrow_inspection_command"]["returncode"] != 0 or checks["arrow_inspection"].get("passed") is not True:
            errors.append("final one-arrow-one-object inspection failed")

    if not errors:
        render_dir = final_dir / "image2ppt_render"
        command = [
            sys.executable,
            str(SCRIPT_DIR / "render_image2ppt_qa.py"),
            str(pptx),
            "--out-dir",
            str(render_dir),
            "--report",
            str(paths["render"]),
            "--timeout",
            str(args.render_timeout),
        ]
        checks["render_command"] = run(command)
        checks["render"] = safe_json(paths["render"])
        if checks["render_command"]["returncode"] != 0 or checks["render"].get("status") != "rendered":
            errors.append("final PowerPoint/LibreOffice render failed")
        else:
            rendered = [Path(value) for value in checks["render"].get("rendered_slides") or []]
            sources = page_sources(run_dir)
            if len(rendered) != len(sources):
                errors.append(f"render/source page count mismatch: rendered={len(rendered)} source={len(sources)}")
            else:
                checks["page_diff_metrics"] = [
                    {"page_index": index, **image_diff(source, image)}
                    for index, (source, image) in enumerate(zip(sources, rendered), start=1)
                ]

    if args.visual_review_status == "reviewed" and not args.visual_review_notes.strip():
        errors.append("reviewed final QA requires concrete --visual-review-notes covering every slide")
    if args.visual_review_status == "failed":
        errors.append("final source-versus-render comparison was marked failed")
    passed = not errors and args.visual_review_status == "reviewed"
    report = {
        "schema_version": "image2ppt-supplemental-final-qa-v1",
        "passed": passed,
        "state_owner": "image2ppt/page_jobs.json",
        "pptx": str(pptx),
        "manifests": [str(path) for path in manifests],
        "visual_review": {"status": args.visual_review_status, "notes": args.visual_review_notes},
        "checks": checks,
        "errors": errors,
    }
    write_json(paths["report"], report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
