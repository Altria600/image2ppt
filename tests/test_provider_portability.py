"""Offline coverage for provider-neutral, local-first image backends."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CLI_DIR = ROOT / "cli"
RUNTIME_DIR = CLI_DIR / "image2ppt" / "runtime"
sys.path.insert(0, str(CLI_DIR))

from image2ppt.runtime import configure_image_backend, image_gen, runtime_env  # noqa: E402


def run_image(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    child_env.pop("OPENAI_API_KEY", None)
    child_env.pop("IMAGE2PPT_IMAGE_BACKEND", None)
    child_env.pop("CODEX_AUTH_FILE", None)
    if env:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, str(RUNTIME_DIR / "image_gen.py"), *args],
        cwd=ROOT,
        env=child_env,
        text=True,
        capture_output=True,
    )


class ProviderPortabilityTest(unittest.TestCase):
    def test_auto_does_not_probe_codex_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth = Path(tmp) / "auth.json"
            auth.write_text('{"tokens":{"access_token":"must-not-be-read"}}', encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    "IMAGE2PPT_CONFIG_HOME": tmp,
                    "IMAGE2PPT_IMAGE_BACKEND": "auto",
                    "CODEX_AUTH_FILE": str(auth),
                },
                clear=False,
            ), mock.patch.object(runtime_env, "codex_oauth_ready", side_effect=AssertionError("OAuth probe")):
                selected, ready = runtime_env.select_image_backend(
                    {"IMAGE2PPT_IMAGE_BACKEND": "auto"}, codex_ready=True, api_ready=True
                )
                self.assertEqual("local-only", selected)
                self.assertTrue(ready)
                status = runtime_env.collect_status()
                self.assertFalse(status["image_backend"]["codex_oauth"]["checked"])
                self.assertEqual("local-only", status["image_backend"]["selection"])

    def test_configured_ocr_token_does_not_switch_from_offline_by_itself(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ,
            {"IMAGE2PPT_CONFIG_HOME": tmp, "PADDLE_OCR_TOKEN": "configured-token"},
            clear=False,
        ):
            status = runtime_env.collect_status()
            self.assertEqual("builtin-ink", status["ocr"]["selection"])
            self.assertFalse(status["ocr"]["remote_authorized"])
            authorized = runtime_env.collect_status(allow_remote_ocr=True)
            self.assertEqual("paddleocr-vl", authorized["ocr"]["selection"])
            self.assertTrue(authorized["ocr"]["remote_authorized"])

    def test_local_only_contract_has_no_remote_requirement(self):
        args = argparse.Namespace(
            backend_id="local-only",
            tool_name=None,
            tool_call=None,
            fallback_command=None,
            input_context_policy=None,
            model=None,
            runtime_home="/tmp/image2ppt",
        )
        contract = configure_image_backend.backend_contract(args)
        self.assertEqual("local-only", contract["backend_id"])
        self.assertEqual(["native", "svg", "source-extracted"], contract["capabilities"])
        self.assertFalse(contract["remote_credentials_required"])
        self.assertFalse(contract["requires_remote_authorization"])
        self.assertEqual([], contract["fallback_order"])

        auto_values = vars(args).copy()
        auto_values["backend_id"] = "auto"
        auto = argparse.Namespace(**auto_values)
        auto_contract = configure_image_backend.backend_contract(auto)
        self.assertEqual("local-only", auto_contract["backend_id"])
        self.assertEqual("auto", auto_contract["requested_backend"])

    def test_host_image_tool_contract_requires_explicit_workbuddy_declaration(self):
        args = argparse.Namespace(
            backend_id="host-image-tool",
            tool_name="WorkBuddy",
            tool_call="workbuddy.image.generate",
            fallback_command=None,
            input_context_policy=None,
            model="workbuddy-image-v1",
            runtime_home="/tmp/image2ppt",
        )
        contract = configure_image_backend.backend_contract(args)
        self.assertEqual("WorkBuddy", contract["tool_name"])
        self.assertEqual("workbuddy.image.generate", contract["tool_call"])
        self.assertTrue(contract["agent_only"])
        self.assertFalse(contract["subprocess_invocation"])
        self.assertFalse(contract["automatic_fallback"])
        self.assertNotIn("required_parameters", contract)
        self.assertIn("actual schema", contract["parameter_policy"])

        result = run_image(
            "generate",
            "--backend",
            "host-image-tool",
            "--tool-name",
            "WorkBuddy",
            "--tool-call",
            "workbuddy.image.generate",
            "--prompt",
            "test",
            "--out",
            "/tmp/provider-portability-host.png",
            "--dry-run",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["subprocess_invocation"])
        self.assertEqual("WorkBuddy", payload["tool_name"])

    def test_builtin_alias_never_declares_remote_fallback(self):
        args = argparse.Namespace(
            backend_id="builtin-imagegen",
            tool_name=None,
            tool_call=None,
            fallback_command=None,
            input_context_policy=None,
            model=None,
            runtime_home="/tmp/image2ppt",
        )
        contract = configure_image_backend.backend_contract(args)
        self.assertEqual("host-image-tool", contract["compatibility_alias_for"])
        self.assertEqual([], contract["fallback_order"])
        self.assertFalse(contract["automatic_fallback"])

    def test_external_import_is_import_only_and_remote_gate_is_explicit(self):
        args = argparse.Namespace(
            backend_id="external-import",
            tool_name=None,
            tool_call=None,
            fallback_command=None,
            input_context_policy=None,
            model=None,
            runtime_home="/tmp/image2ppt",
        )
        contract = configure_image_backend.backend_contract(args)
        self.assertTrue(contract["import_required"])
        self.assertEqual(["source_image", "dest"], contract["required_parameters"]["import"])

        blocked = run_image(
            "generate",
            "--backend",
            "openai-compatible-api",
            "--model",
            "provider/image-v1",
            "--prompt",
            "test",
            "--out",
            "/tmp/provider-portability-api.png",
        )
        self.assertNotEqual(0, blocked.returncode)
        self.assertIn("--allow-remote", blocked.stderr)

        configured_but_not_authorized = run_image(
            "generate",
            "--backend",
            "openai-compatible-api",
            "--model",
            "provider/image-v1",
            "--prompt",
            "test",
            "--out",
            "/tmp/provider-portability-api.png",
            env={"OPENAI_API_KEY": "configured-but-not-authorized"},
        )
        self.assertNotEqual(0, configured_but_not_authorized.returncode)
        self.assertIn("--allow-remote", configured_but_not_authorized.stderr)

        dry = run_image(
            "generate",
            "--backend",
            "openai-compatible-api",
            "--model",
            "provider/image-v1",
            "--prompt",
            "test",
            "--out",
            "/tmp/provider-portability-api.png",
            "--dry-run",
        )
        self.assertEqual(0, dry.returncode, dry.stderr)
        payload = json.loads(dry.stdout)
        self.assertEqual("openai-compatible-api", payload["backend"])
        self.assertTrue(payload["requires_allow_remote"])
        self.assertFalse(payload["remote_authorized"])

    def test_explicit_codex_is_the_only_path_that_reads_oauth(self):
        with mock.patch.object(image_gen, "_codex_available", return_value=False) as probe:
            self.assertEqual("local-only", image_gen._select_backend("auto", "gpt-image-2"))
            probe.assert_not_called()

    def test_codex_contract_import_preserves_explicit_producer(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page_001"
            page.mkdir()
            source = Path(tmp) / "generated.png"
            Image.new("RGB", (8, 8), "red").save(source)
            (page / "imagegen-jobs.json").write_text('{"schema_version":1,"jobs":[]}', encoding="utf-8")
            (page / "page_request.json").write_text(
                json.dumps({"image_backend": {"backend_id": "codex-oauth"}}), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME_DIR / "record_imagegen_result.py"),
                    str(page),
                    "--job-id",
                    "legacy-codex",
                    "--source-image",
                    str(source),
                    "--dest",
                    "assets/generated.png",
                    "--backend",
                    "codex-oauth",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            jobs = json.loads((page / "imagegen-jobs.json").read_text(encoding="utf-8"))
            self.assertEqual("codex-oauth", jobs["jobs"][0]["backend"])

    def test_external_import_contract_accepts_only_explicit_local_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page_001"
            page.mkdir()
            source = Path(tmp) / "prepared.png"
            Image.new("RGB", (8, 8), "blue").save(source)
            (page / "imagegen-jobs.json").write_text('{"schema_version":1,"jobs":[]}', encoding="utf-8")
            (page / "page_request.json").write_text(
                json.dumps({"image_backend": {"backend_id": "external-import"}}), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME_DIR / "record_imagegen_result.py"),
                    str(page),
                    "--job-id",
                    "external-local",
                    "--source-image",
                    str(source),
                    "--dest",
                    "assets/prepared.png",
                    "--backend",
                    "external-import",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((page / "assets/prepared.png").is_file())


if __name__ == "__main__":
    unittest.main()
