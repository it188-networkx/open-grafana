"""Conservative PR scope and fail-closed aggregate gate."""
import os
import subprocess
import sys


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
    # Only known non-runtime documentation may skip expensive checks.
    return not files or any(p not in {"README.md", "AGENTS.md", "CI.md"} for p in files)


def scopes(files):
    app = server = not files
    for path in files:
        if path in {"README.md", "AGENTS.md", "CI.md"}:
            continue
        if path.startswith(("packages/", "public/")):
            app = True
        elif path.startswith(("pkg/", "apps/")):
            server = True
        else:
            # Shared code, plugins, dependencies and unknown paths affect both.
            app = server = True
    return app, server


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
    elif command == "gate":
        if not gate(os.environ["PLAN_RESULT"], os.environ["PLAN_RUN"], os.environ["VALIDATION_RESULT"]):
            raise SystemExit("Required PR checks failed or did not complete")
    else:
        raise SystemExit("Unknown command: " + command)
