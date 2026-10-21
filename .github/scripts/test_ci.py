import copy
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
        for path in ["plugins/slack/index.ts", "shared/utils/test.ts", ".jestconfig.json", "unknown"]:
            self.assertEqual(ci.scopes([path]), (True, True), path)
        self.assertEqual(ci.scopes([]), (True, True))

    def test_docs_dependencies_and_shared_contracts(self):
        cases = {
            "docs/sources/panels/index.md": (False, False),
            "docs/sources/panels/example.png": (False, False),
            "docs/sources/example.go": (True, True),
            "docs/config.yaml": (True, True),
            "public/img/logo.svg": (True, False),
            "yarn.lock": (True, False),
            "package.json": (True, False),
            ".yarn/releases/yarn.cjs": (True, False),
            "go.mod": (False, True),
            "apps/dashboard/go.sum": (False, True),
            "go.work": (False, True),
            "apps/dashboard/pkg/migration/schema.ts": (True, True),
            "packages/grafana-schema/src/dashboard.ts": (True, True),
            "packages/grafana-api-clients/src/query.ts": (True, True),
            "pkg/codegen/main.go": (True, True),
            "pkg/kinds/dashboard.go": (True, True),
            "pkg/api/schema.cue": (True, True),
            "kindsv2/dashboard-ts.yaml": (True, True),
            "proto/query.proto": (True, True),
            "public/openapi3.json": (True, True),
            ".github/scripts/ci.py": (True, True),
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(ci.scopes([path]), expected)
        self.assertEqual(ci.scopes(["pkg/api/api.go", "public/app/app.ts"]), (True, True))

    def test_actual_workflow_gate(self):
        jobs = {"plan": {"result": "success", "outputs": {"app": "false", "server": "true"}}}
        for name in ["backend", "backend-build", "integration"]:
            jobs[name] = {"result": "success"}
        for name in ["frontend", "frontend-checks"]:
            jobs[name] = {"result": "skipped"}
        for app, server in [("false", "false"), ("true", "false"),
                            ("false", "true"), ("true", "true")]:
            planned = copy.deepcopy(jobs)
            planned["plan"]["outputs"] = {"app": app, "server": server}
            for name in ["backend", "backend-build", "integration"]:
                planned[name]["result"] = "success" if server == "true" else "skipped"
            for name in ["frontend", "frontend-checks"]:
                planned[name]["result"] = "success" if app == "true" else "skipped"
            ci.check_jobs(planned)
        for name in jobs:
            for state in ["failure", "cancelled"]:
                changed = copy.deepcopy(jobs)
                changed[name]["result"] = state
                with self.subTest(job=name, state=state), self.assertRaises(ValueError):
                    ci.check_jobs(changed)
        for name, state in [("integration", "skipped"), ("frontend", "success")]:
            changed = copy.deepcopy(jobs)
            changed[name]["result"] = state
            with self.assertRaises(ValueError):
                ci.check_jobs(changed)
        jobs["plan"]["outputs"]["app"] = ""
        with self.assertRaises(ValueError):
            ci.check_jobs(jobs)

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
                Path("pkg").mkdir()
                Path("pkg/code with space.go").write_text("package example\n")
                git("add", ".")
                git("commit", "-m", "fixture")
                base = git("rev-parse", "HEAD")
                git("mv", "pkg/code with space.go", "README.md")
                git("commit", "-m", "move")
                with patch.dict(os.environ, {"CI_BASE_SHA": base}):
                    self.assertEqual(set(ci.changed()), {"pkg/code with space.go", "README.md"})
                    self.assertEqual(ci.scopes(ci.changed()), (False, True))
                git("rm", "README.md")
                git("commit", "-m", "delete")
                with patch.dict(os.environ, {"CI_BASE_SHA": base}):
                    self.assertEqual(ci.changed(), ["pkg/code with space.go"])
                    self.assertEqual(ci.scopes(ci.changed()), (False, True))
                with patch.dict(os.environ, {"CI_BASE_SHA": "missing-ref"}):
                    with self.assertRaises(subprocess.CalledProcessError):
                        ci.changed()
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
