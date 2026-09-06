#!/usr/bin/env python3
"""Configuration and independent runtime diagnostics for Image2PPT."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path


DEFAULT_CONFIG_HOME = "~/.image2ppt"
DEFAULT_CODEX_AUTH_FILE = "~/.codex/auth.json"
DEFAULT_IMAGE_MODEL = "gpt-image-2"
DEFAULT_IMAGE_BACKEND = "local-only"

# Backends describe a run/manifest contract.  ``local-only`` is deliberately
# the default: it covers native/SVG/source-extracted reconstruction and never
# needs an image provider.  The two legacy names remain accepted so existing
# manifests can be inspected or migrated without silently acquiring a remote
# fallback.
BACKEND_AUTO = "auto"
BACKEND_LOCAL_ONLY = "local-only"
BACKEND_HOST_IMAGE_TOOL = "host-image-tool"
BACKEND_EXTERNAL_IMPORT = "external-import"
BACKEND_BUILTIN_IMAGEGEN = "builtin-imagegen"
BACKEND_IMAGE_CLI_LEGACY = "image2ppt-image-cli"
BACKEND_OPENAI_COMPATIBLE = "openai-compatible-api"
BACKEND_CODEX_OAUTH = "codex-oauth"

ALLOWED_IMAGE_BACKENDS = {
    BACKEND_AUTO,
    BACKEND_LOCAL_ONLY,
    BACKEND_HOST_IMAGE_TOOL,
    BACKEND_EXTERNAL_IMPORT,
    BACKEND_BUILTIN_IMAGEGEN,
    BACKEND_IMAGE_CLI_LEGACY,
    BACKEND_OPENAI_COMPATIBLE,
    BACKEND_CODEX_OAUTH,
}
REMOTE_IMAGE_BACKENDS = {BACKEND_OPENAI_COMPATIBLE, BACKEND_CODEX_OAUTH}
ENV_FIELDS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "IMAGE2PPT_IMAGE_MODEL",
    "IMAGE2PPT_IMAGE_BACKEND",
    "IMAGE2PPT_IMAGE_USER_AGENT",
    "PADDLE_OCR_TOKEN",
)
PADDLE_TOKEN_APPLY_URL = "https://aistudio.baidu.com/account/accessToken"
PADDLE_ENDPOINT = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
PADDLE_MODEL = "PaddleOCR-VL-1.6"
SKILL_ROOT = Path(__file__).resolve().parents[3]
CLI_ENTRY = SKILL_ROOT / "cli" / "image2ppt" / "cli.py"


def cli_reinstall_hint() -> str:
    return "`python -m pip install -r <image2ppt-root>/requirements.txt`"


def project_config_path() -> Path:
    return SKILL_ROOT / "config.yaml"


def user_config_path() -> Path:
    return Path(DEFAULT_CONFIG_HOME).expanduser() / "config.yaml"


def config_path(home: Path | None = None) -> Path:
    if home is not None:
        return Path(home).expanduser() / "config.yaml"
    explicit_home = os.getenv("IMAGE2PPT_CONFIG_HOME", "").strip()
    if explicit_home:
        return Path(explicit_home).expanduser() / "config.yaml"
    project = project_config_path()
    if project.is_file():
        return project
    user = user_config_path()
    if user.is_file():
        return user
    # A fresh project-local Skill creates config.yaml beside config.example.yaml.
    return project


def runtime_home() -> Path:
    return config_path().parent


def config_scope(path: Path | None = None) -> str:
    resolved = (path or config_path()).resolve()
    if resolved == project_config_path().resolve():
        return "project"
    if resolved == user_config_path().resolve():
        return "user"
    return "override"


def read_config_file(path: Path) -> dict:
    path = Path(path).expanduser()
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(f"PyYAML is required to read Image2PPT config. Install with {cli_reinstall_hint()}.") from exc
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid config file: {path}")
    return data


def write_config_file(path: Path, values: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(f"PyYAML is required to write Image2PPT config. Install with {cli_reinstall_hint()}.") from exc
    data = {key: values[key] for key in ENV_FIELDS if values.get(key)}
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=True)


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def codex_auth_file() -> Path:
    return Path(os.getenv("CODEX_AUTH_FILE", DEFAULT_CODEX_AUTH_FILE)).expanduser()


def codex_oauth_ready() -> bool:
    path = codex_auth_file()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    tokens = data.get("tokens")
    return isinstance(tokens, dict) and bool(str(tokens.get("access_token") or "").strip())


def codex_model_compatible(model: str) -> bool:
    return "gpt-image-" in str(model).lower()


def configured_image_backend(values: dict) -> str:
    """Return the configured backend without probing any provider.

    In particular, ``auto`` is a local-only policy.  It is retained as a
    configuration value for compatibility, but must never inspect another
    host's OAuth file or switch to a remote provider based on credentials.
    """

    preference = str(values.get("IMAGE2PPT_IMAGE_BACKEND") or DEFAULT_IMAGE_BACKEND).strip().lower()
    return preference or DEFAULT_IMAGE_BACKEND


def is_remote_backend(backend: str) -> bool:
    return str(backend).strip().lower() in REMOTE_IMAGE_BACKENDS


def select_image_backend(
    values: dict,
    codex_ready: bool = False,
    api_ready: bool = False,
    *,
    host_tool_declared: bool = False,
) -> tuple[str, bool]:
    """Resolve a manifest backend without implicit provider switching.

    ``codex_ready`` and ``api_ready`` are supplied by an explicitly selected
    backend/doctor check.  They are not used to make ``auto`` remote.  The
    second tuple value is a readiness indication for the selected contract;
    it is not user authorization to perform a remote call.
    """

    preference = configured_image_backend(values)
    if preference not in ALLOWED_IMAGE_BACKENDS:
        return "invalid", False
    if preference == BACKEND_AUTO:
        return BACKEND_LOCAL_ONLY, True
    if preference in {BACKEND_LOCAL_ONLY, BACKEND_EXTERNAL_IMPORT}:
        return preference, True
    if preference == BACKEND_HOST_IMAGE_TOOL:
        # Host capability is a declaration in a manifest, never inferred from
        # a subprocess environment.  ``None`` is represented as not-ready here
        # while the contract itself remains valid for the agent to fulfill.
        return preference, bool(host_tool_declared)
    if preference == BACKEND_BUILTIN_IMAGEGEN:
        return preference, bool(host_tool_declared)
    if preference == BACKEND_IMAGE_CLI_LEGACY:
        return preference, True
    if preference == BACKEND_CODEX_OAUTH:
        model = str(values.get("IMAGE2PPT_IMAGE_MODEL") or DEFAULT_IMAGE_MODEL)
        return preference, bool(codex_ready and codex_model_compatible(model))
    if preference == BACKEND_OPENAI_COMPATIBLE:
        return preference, bool(api_ready)
    return "invalid", False


def config(args: argparse.Namespace) -> int:
    home = runtime_home()
    values = read_config_file(config_path(home))
    before = dict(values)
    if args.api_key:
        values["OPENAI_API_KEY"] = args.api_key
    if args.base_url is not None:
        values["OPENAI_BASE_URL"] = args.base_url.strip()
    if args.clear_base_url:
        values.pop("OPENAI_BASE_URL", None)
    if args.model is not None:
        values["IMAGE2PPT_IMAGE_MODEL"] = args.model.strip()
    if args.image_backend is not None:
        backend = args.image_backend.strip().lower()
        if backend not in ALLOWED_IMAGE_BACKENDS:
            raise SystemExit(
                "--image-backend must be local-only, host-image-tool, external-import, "
                "openai-compatible-api, or explicitly selected codex-oauth"
            )
        values["IMAGE2PPT_IMAGE_BACKEND"] = backend
    if args.image_user_agent is not None:
        values["IMAGE2PPT_IMAGE_USER_AGENT"] = args.image_user_agent.strip()
    if args.clear_image_user_agent:
        values.pop("IMAGE2PPT_IMAGE_USER_AGENT", None)
    if args.paddle_ocr_token:
        values["PADDLE_OCR_TOKEN"] = args.paddle_ocr_token.strip()
    changed = sorted(key for key in ENV_FIELDS if before.get(key) != values.get(key))
    if changed or not config_path(home).exists():
        write_config_file(config_path(home), values)
        state = "updated" if before else "created"
    else:
        state = "unchanged"
    print(f"config={state} path={config_path(home)}")
    print(f"changed={', '.join(changed) if changed else '<none>'}")
    for key in ENV_FIELDS:
        value = str(values.get(key, ""))
        if key in ("OPENAI_API_KEY", "PADDLE_OCR_TOKEN"):
            value = mask_secret(value)
        print(f"{key}={value or '<unset>'}")
    return 0


def module_status() -> dict[str, dict]:
    purposes = {
        "pypdfium2": "PDF input normalization and rendered-slide rasterization",
        "PIL": "image normalization, assets, previews, and offline OCR geometry",
        "openai": "optional image backend",
        "yaml": "local configuration",
        "numpy": "offline ink metrics",
        "requests": "PaddleOCR HTTP client",
        "resvg_py": "portable SVG preview and PowerPoint PNG compatibility image",
    }
    return {
        name: {"available": importlib.util.find_spec(name) is not None, "purpose": purpose}
        for name, purpose in purposes.items()
    }


def renderer_status() -> dict:
    try:
        from .platform_tools import discover_libreoffice
    except ImportError:
        from platform_tools import discover_libreoffice

    system = platform.system().lower()
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    libreoffice = discover_libreoffice()
    powerpoint_candidate = False
    if system == "windows" and powershell:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"PowerPoint.Application\CLSID"):
                powerpoint_candidate = True
        except (ImportError, OSError):
            pass
    selection = "powerpoint-com" if powerpoint_candidate else ("libreoffice" if libreoffice else "missing")
    return {
        "platform": system,
        "powerpoint_com_candidate": powerpoint_candidate,
        "powershell": powershell,
        "libreoffice": libreoffice,
        "selection": selection,
        "ready": bool(powerpoint_candidate or libreoffice),
    }


def font_status() -> dict:
    candidates = [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("C:/Windows/Fonts/msyh.ttc"),
    ]
    existing = [str(path) for path in candidates if path.is_file()]
    fc_match = shutil.which("fc-match")
    matched = ""
    if fc_match:
        try:
            result = subprocess.run(
                [fc_match, "-f", "%{family}|%{file}", "sans-serif"],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                matched = result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            matched = ""
    return {"ready": bool(existing or matched), "fontconfig": fc_match, "matched": matched, "known_files": existing}


def image_processing_status(modules: dict[str, dict]) -> dict:
    imagemagick = shutil.which("magick") or shutil.which("convert")
    return {
        "pillow": modules["PIL"]["available"],
        "imagemagick": imagemagick,
        "svg_renderer": "resvg_py" if modules.get("resvg_py", {}).get("available") else None,
        "local_vector_tracing": importlib.util.find_spec("vtracer") is not None,
        "ready": modules["PIL"]["available"],
        "note": "Pillow processes raster assets; resvg_py renders SVG; VTracer is optional for local tracing.",
    }


def internal_resource_status() -> dict:
    required = {
        "skill": SKILL_ROOT / "SKILL.md",
        "cli": CLI_ENTRY,
        "runtime_main": Path(__file__).resolve().parent / "main.py",
        "ocr_client": Path(__file__).resolve().parent / "paddle_text_hints.py",
        "offline_ocr": Path(__file__).resolve().parent / "text_hints.py",
        "builder": Path(__file__).resolve().parent / "build_pptx_from_manifest.py",
        "validator": Path(__file__).resolve().parent / "validate_pptx.py",
        "worker_prompt_base": SKILL_ROOT / "prompts" / "page-worker-base.md",
        "worker_prompt_addendum": SKILL_ROOT / "prompts" / "page-worker.md",
        "prompt_builder": SKILL_ROOT / "scripts" / "build_page_worker_prompt.py",
        "page_qa": SKILL_ROOT / "scripts" / "run_image2ppt_qa.py",
        "final_qa": SKILL_ROOT / "scripts" / "run_final_image2ppt_qa.py",
        "renderer": SKILL_ROOT / "scripts" / "render_image2ppt_qa.py",
        "visual_review_evidence": SKILL_ROOT / "scripts" / "visual_review_evidence.py",
        "workflow": SKILL_ROOT / "references" / "workflow.md",
        "manifest_schema": SKILL_ROOT / "references" / "manifest-schema.md",
        "manifest_json_schema": SKILL_ROOT / "schemas" / "page-manifest-v2.schema.json",
        "decision_tree": SKILL_ROOT / "references" / "page-decision-tree.md",
        "cli_contract": SKILL_ROOT / "references" / "cli-helper.md",
        "ocr_contract": SKILL_ROOT / "references" / "ocr-text-hints-contract.md",
        "region_contract": SKILL_ROOT / "references" / "region-decomposition.md",
        "object_routing": SKILL_ROOT / "references" / "object-routing.md",
        "arrow_contract": SKILL_ROOT / "references" / "manifest-arrow-extension.md",
        "qa_contract": SKILL_ROOT / "references" / "qa-contract.md",
        "dependency_contract": SKILL_ROOT / "references" / "runtime-dependencies.md",
        "asset_contract": SKILL_ROOT / "references" / "assets-provenance-contract.md",
        "typography_contract": SKILL_ROOT / "references" / "typography-alignment-contract.md",
        "source_fidelity_contract": SKILL_ROOT / "references" / "source-fidelity-style-contract.md",
    }
    files = {key: {"path": str(path), "exists": path.is_file()} for key, path in required.items()}
    return {"ready": all(item["exists"] for item in files.values()), "files": files}


def collect_status(
    check_api: bool = False,
    check_ocr: bool = False,
    *,
    image_backend: str | None = None,
    check_codex: bool = False,
    allow_remote_ocr: bool = False,
) -> dict:
    home = runtime_home()
    active_config = config_path(home)
    config_values = read_config_file(active_config)
    values = dict(config_values)
    for key in ENV_FIELDS:
        if os.getenv(key):
            values[key] = os.environ[key]

    modules = module_status()
    renderer = renderer_status()
    fonts = font_status()
    processing = image_processing_status(modules)
    resources = internal_resource_status()
    api_ready = bool(values.get("OPENAI_API_KEY"))
    if image_backend:
        values["IMAGE2PPT_IMAGE_BACKEND"] = image_backend
    configured_backend = configured_image_backend(values)
    # OAuth is deliberately opt-in.  The default/auto path must not even read
    # another host's ~/.codex/auth.json.
    codex_checked = configured_backend == BACKEND_CODEX_OAUTH or check_codex
    codex_ready = codex_oauth_ready() if codex_checked else False
    selected_backend, cli_fallback_ready = select_image_backend(values, codex_ready, api_ready)
    token = str(values.get("PADDLE_OCR_TOKEN") or "").strip()
    token_source = "environment" if os.getenv("PADDLE_OCR_TOKEN") else ("config" if token else "unset")
    offline_ready = modules["PIL"]["available"] and modules["numpy"]["available"]
    dependency_ready = all(item["available"] for item in modules.values())
    if check_api:
        if configured_backend == BACKEND_CODEX_OAUTH:
            remote_check_ready = codex_ready
        else:
            remote_check_ready = api_ready
    else:
        remote_check_ready = True
    ok = (
        dependency_ready
        and renderer["ready"]
        and fonts["ready"]
        and processing["ready"]
        and resources["ready"]
        and offline_ready
        and (remote_check_ready if check_api else True)
        and (bool(token) if check_ocr else True)
    )
    api_status = {
        "ready": api_ready,
        "configured": api_ready,
        "authorized": False,
        "OPENAI_API_KEY": "set" if api_ready else "unset",
        "OPENAI_BASE_URL": values.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "IMAGE2PPT_IMAGE_MODEL": values.get("IMAGE2PPT_IMAGE_MODEL", "<configured-by-user>"),
        "IMAGE2PPT_IMAGE_USER_AGENT": values.get("IMAGE2PPT_IMAGE_USER_AGENT", "<default>"),
        "requires_allow_remote": True,
    }
    host_status = {
        "checked": False,
        "ready": None,
        "tool_name": None,
        "tool_call": None,
        "declaration_required": True,
        "agent_only": True,
        "subprocess_invocation": False,
    }
    codex_status = {
        "checked": codex_checked,
        "ready": codex_ready if codex_checked else None,
        "auth_file": str(codex_auth_file()) if codex_checked else None,
        "authorized": False,
        "requires_allow_remote": True,
        "legacy": True,
    }
    legacy_agent_status = dict(host_status)
    legacy_agent_status["tool_name"] = "image_gen.imagegen"
    return {
        "schema_version": "image2ppt-doctor-v1",
        "ok": ok,
        "skill_root": str(SKILL_ROOT),
        "local_cli": {"path": str(CLI_ENTRY), "ready": CLI_ENTRY.is_file(), "python": sys.executable},
        "config_home": str(home),
        "config_file": str(active_config),
        "config_scope": config_scope(active_config),
        "config_exists": active_config.exists(),
        "dependencies": modules,
        "internal_resources": resources,
        "rendering": renderer,
        "fonts": fonts,
        "image_processing": processing,
        "ocr": {
            # A configured token is an optional capability, not permission to
            # upload.  Remote OCR only becomes selected after the explicit
            # allow flag is carried through the caller.
            "selection": "paddleocr-vl" if token and allow_remote_ocr else "builtin-ink",
            "configured": bool(token),
            "remote_authorized": bool(token and allow_remote_ocr),
            "token": "set" if token else "unset",
            "token_source": token_source,
            "endpoint": PADDLE_ENDPOINT,
            "model": PADDLE_MODEL,
            "network_client_ready": modules["requests"]["available"],
            "network_probe_performed": False,
            "fallback": {"backend": "builtin-ink", "ready": offline_ready, "priority": "local-first"},
            "apply_url": PADDLE_TOKEN_APPLY_URL,
            "configure_command": "image2ppt config --paddle-ocr-token <token>",
        },
        "image_backend": {
            "default": DEFAULT_IMAGE_BACKEND,
            "preference": configured_backend,
            "cli_fallback_ready": cli_fallback_ready,
            "selection": selected_backend,
            "local_only": {"ready": offline_ready, "remote_credentials_required": False},
            "host_image_tool": host_status,
            # Legacy doctor consumers can still inspect this key; it is an
            # unprobed capability, never an inferred host-tool availability.
            "agent_builtin": legacy_agent_status,
            "external_import": {"ready": True, "remote_credentials_required": False},
            "codex_oauth": codex_status,
            "api": api_status,
            # Compatibility key for consumers that still call this a fallback.
            "api_fallback": api_status,
            "remote_authorization": {"provided": False, "control": "--allow-remote"},
        },
        "checks_requested": {
            "require_image_api": check_api,
            "require_network_ocr_token": check_ocr,
            "check_codex_oauth": codex_checked,
            "allow_remote_ocr": allow_remote_ocr,
        },
        "next": "no action needed" if ok else "inspect failed doctor sections and install/configure only the missing local or system dependency",
    }


def doctor(args: argparse.Namespace) -> int:
    status = collect_status(
        check_api=args.check_api,
        check_ocr=args.check_ocr,
        image_backend=getattr(args, "image_backend", None),
        check_codex=getattr(args, "check_codex", False),
        allow_remote_ocr=getattr(args, "allow_remote_ocr", False),
    )
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["ok"] else 1

    print(f"skill root: {status['skill_root']}")
    print(f"local CLI: {'ready' if status['local_cli']['ready'] else 'missing'} ({status['local_cli']['path']})")
    print(f"config: {status['config_file']} ({'exists' if status['config_exists'] else 'missing'})")
    for module, item in status["dependencies"].items():
        print(f"python import {module}: {'ok' if item['available'] else 'missing'}")
    render = status["rendering"]
    print(f"PPTX renderer: {render['selection']} ({'ready' if render['ready'] else 'missing'})")
    print(f"fonts: {'ready' if status['fonts']['ready'] else 'missing'} ({status['fonts']['matched'] or 'known-file scan'})")
    processing = status["image_processing"]
    print(f"image processing: Pillow={'ready' if processing['pillow'] else 'missing'} ImageMagick={processing['imagemagick'] or 'optional/missing'}")
    ocr = status["ocr"]
    print(
        f"OCR: {ocr['selection']} token={ocr['token']} source={ocr['token_source']} "
        f"remote_authorized={'yes' if ocr['remote_authorized'] else 'no'}"
    )
    print(f"OCR endpoint: {ocr['endpoint']}")
    print(f"OCR model: {ocr['model']}")
    print(f"OCR fallback: {ocr['fallback']['backend']} ({'ready' if ocr['fallback']['ready'] else 'missing'})")
    backend = status["image_backend"]
    print(f"image backend: {backend['selection']} ({'ready' if backend['cli_fallback_ready'] else 'optional/not configured'})")
    print(f"remote authorization: {backend['remote_authorization']['control']} (not granted by environment keys)")
    if backend["codex_oauth"]["checked"]:
        print(f"Codex OAuth: {'ready' if backend['codex_oauth']['ready'] else 'missing'} (explicitly selected)")
    else:
        print("Codex OAuth: not checked (select codex-oauth explicitly to inspect it)")
    print(f"internal resources: {'ready' if status['internal_resources']['ready'] else 'missing'}")
    if ocr["token"] == "unset":
        print(
            "PaddleOCR token is optional and does not authorize uploads; configure it only when needed, "
            f"then pass --allow-remote-ocr (apply at {ocr['apply_url']}; run `{ocr['configure_command']}`)."
        )
    print(f"next: {status['next']}")
    return 0 if status["ok"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="image2ppt", description="Manage Image2PPT configuration and runtime diagnostics")
    sub = parser.add_subparsers(required=True)
    doc = sub.add_parser("doctor", help="Check local runtime, rendering, OCR, image, font, and resource readiness")
    doc.add_argument("--check-api", action="store_true", help="Require credentials for the explicitly selected remote backend.")
    doc.add_argument(
        "--image-backend",
        choices=sorted(ALLOWED_IMAGE_BACKENDS),
        help="Inspect this backend; auto resolves to local-only and never checks OAuth.",
    )
    doc.add_argument(
        "--check-codex",
        action="store_true",
        help="Explicitly inspect CODEX_AUTH_FILE; never implied by auto/local-only.",
    )
    doc.add_argument(
        "--allow-remote-ocr",
        action="store_true",
        help="Explicitly select PaddleOCR-VL when a configured token exists; no network probe is performed by doctor.",
    )
    doc.add_argument("--check-ocr", action="store_true", help="Require a configured PaddleOCR token; no network request is made.")
    doc.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    doc.add_argument("--timeout", type=int, default=30, help="Reserved for opt-in network probes.")
    doc.set_defaults(func=doctor)
    cfg = sub.add_parser("config", help="Write or update the active project/user config.yaml")
    cfg.add_argument("--api-key", help="OpenAI or OpenAI-compatible image API key to store.")
    cfg.add_argument("--base-url", help="OpenAI-compatible base URL.")
    cfg.add_argument("--clear-base-url", action="store_true", help="Remove OPENAI_BASE_URL from the config file.")
    cfg.add_argument("--model", help="Default provider image model id.")
    cfg.add_argument(
        "--image-backend",
        choices=sorted(ALLOWED_IMAGE_BACKENDS),
        help="Default transport backend for image generate/edit calls.",
    )
    cfg.add_argument("--image-user-agent", help="Optional User-Agent for the OpenAI-compatible API only.")
    cfg.add_argument(
        "--clear-image-user-agent",
        action="store_true",
        help="Remove IMAGE2PPT_IMAGE_USER_AGENT from the config file.",
    )
    cfg.add_argument("--paddle-ocr-token", help=f"Baidu AI Studio PaddleOCR token. Apply at {PADDLE_TOKEN_APPLY_URL}.")
    cfg.set_defaults(func=config)
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
