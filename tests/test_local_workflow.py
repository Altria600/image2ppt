from __future__ import annotations

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
RUNTIME = ROOT / "cli/image2ppt/runtime"
sys.path.insert(0, str(RUNTIME))
import deck_text_hints


class LocalWorkflowTests(unittest.TestCase):
    def make_run(self, root: Path) -> Path:
        run = root / "中文 多页"
        pages = []
        for index in (1, 2):
            page_id = f"page_{index:03d}"
            page = run / "pages" / page_id
            page.mkdir(parents=True)
            Image.new("RGB", (100, 60), "white").save(page / "source.png")
            (page / "page_request.json").write_text("{}", encoding="utf-8")
            (page / "worker-prompt.md").write_text("Reconstruct this page.", encoding="utf-8")
            pages.append({"page_id": page_id, "page_dir": f"pages/{page_id}",
                          "page_request": f"pages/{page_id}/page_request.json", "status": "pending"})
        for name, data in {
            "deck_manifest.json": {"schema_version": 1, "pages": pages, "image_backend": {"backend_id": "local-only"}},
            "page_jobs.json": {"schema_version": 1, "pages": pages},
            "run_state.json": {"status": "inputs_prepared", "history": []},
        }.items():
            (run / name).write_text(json.dumps(data), encoding="utf-8")
        return run

    def test_default_hints_never_read_token_or_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(Path(tmp))
            with mock.patch.object(sys, "argv", ["hints", str(run)]), \
                 mock.patch.object(deck_text_hints, "paddle_token") as token, \
                 mock.patch.object(deck_text_hints, "paddle_pages") as remote:
                self.assertEqual(0, deck_text_hints.main())
            token.assert_not_called()
            remote.assert_not_called()
            for page in (run / "pages").iterdir():
                hints = json.loads((page / "text_hints.json").read_text())
                self.assertEqual("builtin-ink", hints["backend"])

    def test_remote_hints_require_explicit_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(Path(tmp))
            with mock.patch.object(sys, "argv", ["hints", str(run), "--allow-remote-ocr"]), \
                 mock.patch.object(deck_text_hints, "paddle_token", return_value="test-token"), \
                 mock.patch.object(deck_text_hints, "paddle_pages", return_value={}) as remote:
                self.assertEqual(0, deck_text_hints.main())
            remote.assert_called_once()

    def test_multi_page_local_claim_is_sequential_and_rejects_reclaim(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(Path(tmp))

            def claim(page_id):
                return subprocess.run(
                    [sys.executable, str(RUNTIME / "record_page_dispatch.py"), str(run),
                     "--page", page_id, "--agent-id", "main", "--local", "--prompt-file", "worker-prompt.md"],
                    capture_output=True, text=True,
                )

            self.assertEqual(0, claim("page_001").returncode)
            self.assertNotEqual(0, claim("page_001").returncode)
            blocked = claim("page_002")
            self.assertNotEqual(0, blocked.returncode)
            self.assertIn("active page", blocked.stderr)
            jobs_path = run / "page_jobs.json"
            jobs = json.loads(jobs_path.read_text())
            jobs["pages"][0]["status"] = "completed"
            jobs_path.write_text(json.dumps(jobs), encoding="utf-8")
            self.assertEqual(0, claim("page_002").returncode)

    def test_next_argv_handles_space_paths_and_resumes_active_local_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(Path(tmp))
            command = [sys.executable, str(ROOT / "cli/image2ppt/cli.py"), "run", "next", str(run), "--local", "--json"]
            env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
            first = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
            payload = json.loads(first.stdout)
            self.assertEqual(["page_001"], payload["suggested_pages"])
            self.assertIn(str(run.resolve()), payload["next_argv"])
            dispatched = subprocess.run(payload["next_argv"], capture_output=True, text=True)
            self.assertEqual(0, dispatched.returncode, dispatched.stderr)
            active = json.loads(subprocess.run(command, capture_output=True, text=True, check=True, env=env).stdout)
            self.assertEqual("resume_page_locally", active["stage"])
            self.assertEqual("page_001", active["page_id"])
