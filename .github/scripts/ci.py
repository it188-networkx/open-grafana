"""Conservative PR scope and fail-closed aggregate gate."""
import json
import os
import subprocess
import sys
from pathlib import PurePosixPath


def git(*args):
    return subprocess.check_output(["git", *args])


def changed():
    base = os.environ.get("CI_BASE_SHA")
    if not base and os.environ.get("ACT") == "true":
        base = "origin/main"
    if not base:
        raise ValueError("CI_BASE_SHA is required")
    base = git("merge-base", base, "HEAD").decode().strip()
    # No renames exposes both sides of moves; NUL handles spaces and newlines.
    return [p.decode() for p in git("diff", "--name-only", "--no-renames", "-z", base, "HEAD").split(b"\0") if p]


def code_required(files):
    return any(scopes(files))


def scopes(files):
    app = server = not files
    for path in files:
        name = PurePosixPath(path).name
        suffix = PurePosixPath(path).suffix
        # Generated documentation and mixed-language packages are contracts too.
        if path in {
            "docs/sources/setup-grafana/configure-grafana/feature-toggles/index.md",
            "docs/sources/visualizations/panels-visualizations/query-transform-data/transform-data/index.md",
        } or path.startswith("pkg/services/featuremgmt/") or (
            path.startswith(("apps/", "pkg/"))
            and suffix in {".ts", ".tsx", ".js", ".jsx", ".css"}
        ):
            app = server = True
            continue
        if path in {"README.md", "AGENTS.md", "CI.md"} or (
            path.startswith("docs/sources/")
            and suffix in {".md", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
        ):
            continue
        # Shared contracts/generators must be classified before language roots.
        if path.startswith(("kinds/", "kindsv2/", "pkg/kinds/", "pkg/codegen/",
                            "proto/", "packages/grafana-schema/",
                            "packages/grafana-api-clients/",
                            "apps/dashboard/pkg/migration/")) or suffix in {".cue", ".proto"} or path == "public/openapi3.json":
            app = server = True
        elif name in {"go.mod", "go.sum", "go.work", "go.work.sum"}:
            server = True
        elif path.startswith(("packages/", "public/", ".yarn/")) or path in {
            "package.json", "yarn.lock", ".yarnrc.yml", "jest.config.js",
            "eslint.config.js", "nx.json", "tsconfig.json",
        }:
            app = True
        elif path.startswith(("pkg/", "apps/")):
            server = True
        else:
            # CI policy, scripts, configuration and unknown paths require both.
            app = server = True
    return app, server


def check_jobs(jobs):
    if jobs["plan"]["result"] != "success":
        raise ValueError("Planning failed")
    for name, scope in [("backend", "server"), ("backend-build", "server"),
                        ("integration", "server"), ("frontend", "app"),
                        ("frontend-checks", "app")]:
        planned = jobs["plan"]["outputs"][scope]
        expected = {"true": "success", "false": "skipped"}.get(planned)
        if expected is None or jobs[name]["result"] != expected:
            raise ValueError("Required check did not complete: " + name)


def gate(plan, run, validation):
    return plan == "success" and ((run == "true" and validation == "success") or
                                  (run == "false" and validation == "skipped"))


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "plan":
        files = [] if os.environ.get("ACT") == "true" else changed()
        app, server = scopes(files)
        run = app or server
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            for name, value in [("run", run), ("app", app), ("server", server)]:
                output.write(name + "=" + str(value).lower() + "\n")
        print("Run code checks:", run)
    elif command == "check-jobs":
        check_jobs(json.loads(os.environ["RESULTS"]))
    elif command == "gate":
        if not gate(os.environ["PLAN_RESULT"], os.environ["PLAN_RUN"], os.environ["VALIDATION_RESULT"]):
            raise SystemExit("Required PR checks failed or did not complete")
    else:
        raise SystemExit("Unknown command: " + command)
