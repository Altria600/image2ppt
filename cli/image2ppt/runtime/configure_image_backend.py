#!/usr/bin/env python3
"""Record the explicit image backend contract for a prepared run.

The contract is deliberately declarative.  In particular, a host image tool
is described for the parent Agent but is never executed by this subprocess;
``local-only`` and ``external-import`` keep runs useful without credentials or
an image-generation tool.
"""

from __future__ import annotations

import argparse
import json
import os

try:
    from deck_run_state import load_deck, load_jobs, read_json, run_dir_from_target, save_deck, write_json
    from runtime_env import (
        ALLOWED_IMAGE_BACKENDS,
        BACKEND_AUTO,
        BACKEND_BUILTIN_IMAGEGEN,
        BACKEND_CODEX_OAUTH,
        BACKEND_EXTERNAL_IMPORT,
        BACKEND_HOST_IMAGE_TOOL,
        BACKEND_IMAGE_CLI_LEGACY,
        BACKEND_LOCAL_ONLY,
        BACKEND_OPENAI_COMPATIBLE,
        config_path,
        read_config_file,
    )
except ImportError:  # package import from image2ppt.runtime
    from .deck_run_state import load_deck, load_jobs, read_json, run_dir_from_target, save_deck, write_json
    from .runtime_env import (
        ALLOWED_IMAGE_BACKENDS,
        BACKEND_AUTO,
        BACKEND_BUILTIN_IMAGEGEN,
        BACKEND_CODEX_OAUTH,
        BACKEND_EXTERNAL_IMPORT,
        BACKEND_HOST_IMAGE_TOOL,
        BACKEND_IMAGE_CLI_LEGACY,
        BACKEND_LOCAL_ONLY,
        BACKEND_OPENAI_COMPATIBLE,
        config_path,
        read_config_file,
    )


def configured_model() -> str:
    """Resolve the exact user-configured model, without quality ranking."""

    values = read_config_file(config_path())
    return str(os.getenv("IMAGE2PPT_IMAGE_MODEL") or values.get("IMAGE2PPT_IMAGE_MODEL") or "").strip()


def _clean_declared(value: str | None, flag: str) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        raise SystemExit(f"{flag} must be non-empty when provided")
    if len(value) > 512 or any(ord(char) < 32 for char in value):
        raise SystemExit(f"{flag} must be at most 512 characters with no control characters")
    return value


def _arg(args: argparse.Namespace, name: str, default=None):
    return getattr(args, name, default)


def backend_contract(args: argparse.Namespace) -> dict:
    """Build one provider-neutral, provenance-preserving backend contract."""

    backend_id = str(_arg(args, "backend_id", BACKEND_LOCAL_ONLY) or BACKEND_LOCAL_ONLY).strip().lower()
    if backend_id not in ALLOWED_IMAGE_BACKENDS:
        raise SystemExit(f"unsupported image backend: {backend_id}")
    requested_backend = backend_id
    if backend_id == BACKEND_AUTO:
        # ``auto`` is a runtime selection alias only; the persisted contract
        # must make its local-only behavior explicit.
        backend_id = BACKEND_LOCAL_ONLY

    tool_name = _clean_declared(_arg(args, "tool_name"), "--tool-name")
    tool_call = _clean_declared(_arg(args, "tool_call"), "--tool-call")
    fallback_command = _clean_declared(_arg(args, "fallback_command"), "--fallback-command")
    input_context_policy = _clean_declared(_arg(args, "input_context_policy"), "--input-context-policy")
    model = _clean_declared(_arg(args, "model"), "--model")
    runtime_home = _arg(args, "runtime_home")

    # Legacy builtin-imagegen is retained as a fixed alias for the host tool.
    # Its old automatic remote fallback is intentionally removed.
    if backend_id == BACKEND_BUILTIN_IMAGEGEN:
        supplied = [
            flag
            for flag, value in (
                ("--tool-name", tool_name),
                ("--tool-call", tool_call),
                ("--fallback-command", fallback_command),
                ("--input-context-policy", input_context_policy),
            )
            if value is not None
        ]
        if supplied:
            raise SystemExit(
                f"{', '.join(supplied)} cannot override the fixed builtin-imagegen contract (compatibility alias)"
            )
        tool_name = "image_gen.imagegen"
        tool_call = "image_gen.imagegen"
        input_context_policy = (
            "generation needs prompt; for editing inspect every local input with view_image first, then pass "
            "prompt plus absolute local paths in referenced_image_paths"
        )
        fallback_command = None
        # The compatibility alias has no provider model of its own; do not
        # copy an unrelated API model into its provenance contract.
        model = None

    if backend_id == BACKEND_HOST_IMAGE_TOOL:
        if not tool_name or not tool_call:
            raise SystemExit("host-image-tool requires both --tool-name and --tool-call")
        if fallback_command is not None:
            raise SystemExit("host-image-tool does not accept a fallback command")
        if input_context_policy is None:
            input_context_policy = "the Agent inspects every edit input, then invokes the declared host tool"
    elif backend_id in {BACKEND_LOCAL_ONLY, BACKEND_EXTERNAL_IMPORT}:
        if tool_name or tool_call or fallback_command:
            raise SystemExit(f"{backend_id} does not accept host tool or fallback declarations")
        if input_context_policy is None:
            input_context_policy = "reconstruct with local/native/SVG/source-extracted objects only"
    else:
        if tool_name is None:
            tool_name = "image2ppt image"
        if tool_call is None:
            tool_call = "image2ppt image generate/edit"
        if input_context_policy is None:
            input_context_policy = "pass edit targets and strict visual references via image2ppt image edit --image"

    if backend_id in {BACKEND_OPENAI_COMPATIBLE, BACKEND_CODEX_OAUTH} and not model:
        raise SystemExit("--model or IMAGE2PPT_IMAGE_MODEL must be a non-empty configured provider model id")
    if backend_id in {BACKEND_LOCAL_ONLY, BACKEND_EXTERNAL_IMPORT}:
        model = None
    if backend_id in {BACKEND_OPENAI_COMPATIBLE, BACKEND_CODEX_OAUTH}:
        # Remote backends are explicit transports, never a fallback target.
        fallback_command = None

    remote = backend_id in {BACKEND_OPENAI_COMPATIBLE, BACKEND_CODEX_OAUTH}
    contract = {
        "backend_id": backend_id,
        "requested_backend": requested_backend if requested_backend != backend_id else None,
        "tool_name": tool_name,
        "tool_call": tool_call,
        "fallback_command": fallback_command,
        "runtime_home": runtime_home,
        "model": model,
        "requires_openai_api_key": backend_id == BACKEND_OPENAI_COMPATIBLE,
        "requires_remote_authorization": remote,
        "remote_authorization_control": "--allow-remote" if remote else None,
        "mode_policy": (
            "generate-or-edit-per-asset"
            if backend_id not in {BACKEND_LOCAL_ONLY, BACKEND_EXTERNAL_IMPORT}
            else "local-reconstruction-or-import"
        ),
        "chroma_key_helper": "image2ppt image process-sheet" if backend_id != BACKEND_LOCAL_ONLY else None,
        "input_context_policy": input_context_policy,
        "save_path_policy": (
            "agent must use only an explicit valid local result/output_hint path, then image2ppt image import; "
            "never scan for the newest file"
            if backend_id in {BACKEND_BUILTIN_IMAGEGEN, BACKEND_HOST_IMAGE_TOOL}
            else "write outputs directly to the page directory or import an explicitly selected local image"
        ),
        "handoff_rule": (
            "the parent Agent invokes the declared host tool and records its explicit local output; "
            "this subprocess cannot call a host-native tool"
            if backend_id in {BACKEND_BUILTIN_IMAGEGEN, BACKEND_HOST_IMAGE_TOOL}
            else "reconstruct locally and do not invoke an image transport or upload source material"
            if backend_id == BACKEND_LOCAL_ONLY
            else "use image2ppt image import for an explicitly selected local output"
            if backend_id in {BACKEND_EXTERNAL_IMPORT, BACKEND_IMAGE_CLI_LEGACY}
            else "call the explicitly selected image transport only with --allow-remote"
        ),
        "agent_only": backend_id in {BACKEND_BUILTIN_IMAGEGEN, BACKEND_HOST_IMAGE_TOOL},
        "subprocess_invocation": backend_id not in {BACKEND_BUILTIN_IMAGEGEN, BACKEND_HOST_IMAGE_TOOL},
        "automatic_fallback": False,
        "no_silent_fallback": True,
    }

    if backend_id == BACKEND_BUILTIN_IMAGEGEN:
        contract.update(
            {
                "compatibility_alias_for": BACKEND_HOST_IMAGE_TOOL,
                "alias_for": BACKEND_HOST_IMAGE_TOOL,
                "required_parameters": {
                    "generate": ["prompt"],
                    "edit": ["prompt", "referenced_image_paths"],
                },
                "fallback_order": [],
                "fallback_selection_policy": "none; builtin-imagegen never silently falls back",
                "fallback_policy": {"on": [], "missing_optional_parameters": False},
            }
        )
    elif backend_id == BACKEND_HOST_IMAGE_TOOL:
        contract.update(
            {
                "parameter_policy": "Use the declared host tool's actual schema for argument names; edits must include the source image as a reference.",
                "fallback_order": [],
                "fallback_policy": {"on": [], "missing_optional_parameters": False},
            }
        )
    elif backend_id == BACKEND_EXTERNAL_IMPORT:
        contract.update(
            {
                "import_required": True,
                "required_parameters": {"import": ["source_image", "dest"]},
                "fallback_order": [],
                "fallback_policy": {"on": [], "missing_optional_parameters": False},
            }
        )
    elif backend_id == BACKEND_LOCAL_ONLY:
        contract.update(
            {
                "capabilities": ["native", "svg", "source-extracted"],
                "remote_credentials_required": False,
                "required_parameters": {"reconstruction": []},
                "fallback_order": [],
                "fallback_policy": {"on": [], "missing_optional_parameters": False},
            }
        )
    elif backend_id == BACKEND_IMAGE_CLI_LEGACY:
        contract.update(
            {
                "compatibility_alias_for": BACKEND_EXTERNAL_IMPORT,
                "legacy": True,
                "fallback_order": [],
                "fallback_policy": {"on": [], "missing_optional_parameters": False},
            }
        )
    else:
        contract.update(
            {
                "fallback_order": [],
                "fallback_policy": {"on": [], "missing_optional_parameters": False},
            }
        )
    return contract


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the explicit run-level image backend contract.")
    parser.add_argument("run")
    parser.add_argument(
        "--backend-id",
        default=BACKEND_LOCAL_ONLY,
        choices=sorted(ALLOWED_IMAGE_BACKENDS),
        help="Contract mode; default local-only never requires an image API.",
    )
    parser.add_argument("--tool-name", help="Explicit host tool name; required for host-image-tool.")
    parser.add_argument("--tool-call", help="Explicit host tool call declaration; required for host-image-tool.")
    parser.add_argument(
        "--model",
        default=None,
        help="Exact configured provider model id; required for explicit remote backends.",
    )
    parser.add_argument("--fallback-command", help="Legacy option; remote fallback is never automatic.")
    parser.add_argument("--runtime-home", default=None, help="Shared config home. Defaults to the active config home.")
    parser.add_argument("--input-context-policy", help="Optional host/agent input inspection policy.")
    args = parser.parse_args()

    if args.model is None:
        args.model = configured_model() or None
    if args.runtime_home is None:
        args.runtime_home = str(config_path().parent)

    run_dir = run_dir_from_target(args.run)
    deck = load_deck(run_dir)
    contract = backend_contract(args)
    deck["image_backend"] = contract
    save_deck(run_dir, deck)

    jobs = load_jobs(run_dir)
    for page in jobs.get("pages", []):
        request_path = run_dir / page["page_request"]
        request = read_json(request_path)
        request["image_backend"] = contract
        write_json(request_path, request)
    print(json.dumps({"image_backend": contract}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
