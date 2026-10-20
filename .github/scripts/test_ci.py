import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("ci", Path(__file__).with_name("ci.py"))
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class PolicyTests(unittest.TestCase):
    def test_application_and_server_scopes(self):
        self.assertEqual(ci.scopes(["public/app/features/dashboard/Dashboard.ts"]), (True, False))
        self.assertEqual(ci.scopes(["pkg/api/dashboard.go"]), (False, True))
        self.assertEqual(ci.scopes(["README.md"]), (False, False))
        for path in ["plugins/slack/index.ts", "shared/utils/test.ts", "yarn.lock", ".jestconfig.json", "unknown"]:
            self.assertEqual(ci.scopes([path]), (True, True), path)
        self.assertEqual(ci.scopes([]), (True, True))

    def test_unknown_and_runtime_paths_run(self):
        self.assertFalse(ci.code_required(["README.md", "CI.md"]))
        for path in ["docs/query.json", "design/check.go", "go.mod", ".github/workflows/pr-ci.yml", "src/main.go", "new-file", "README.md\nmain.go"]:
            self.assertTrue(ci.code_required([path]), path)
        self.assertTrue(ci.code_required([]))

    def test_gate_rejects_failure_cancellation_and_unexpected_skips(self):
        self.assertTrue(ci.gate("success", "true", "success"))
        self.assertTrue(ci.gate("success", "false", "skipped"))
        for state in ["failure", "cancelled", "skipped", ""]:
            self.assertFalse(ci.gate(state, "true", "success"))
            self.assertFalse(ci.gate("success", "true", state))
        self.assertFalse(ci.gate("success", "false", "failure"))
        self.assertFalse(ci.gate("success", "", "skipped"))

    def test_real_diff_includes_both_sides_of_rename_and_invalid_base_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            try:
                os.chdir(directory)
                def git(*args):
                    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL).decode().strip()
                git("init")
                git("config", "user.name", "CI fixture")
                git("config", "user.email", "ci@example.invalid")
                Path("code with space.go").write_text("package example\n")
                git("add", ".")
                git("commit", "-m", "fixture")
                base = git("rev-parse", "HEAD")
                git("mv", "code with space.go", "README.md")
                git("commit", "-m", "move")
                with patch.dict(os.environ, {"CI_BASE_SHA": base}):
                    self.assertEqual(set(ci.changed()), {"code with space.go", "README.md"})
                    self.assertTrue(ci.code_required(ci.changed()))
                with patch.dict(os.environ, {"CI_BASE_SHA": "missing-ref"}):
                    with self.assertRaises(subprocess.CalledProcessError):
                        ci.changed()
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
