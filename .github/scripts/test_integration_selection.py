"""Exercise the upstream selector and shard scripts with isolated package data."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts/ci/backend-tests"


class IntegrationSelectionTests(unittest.TestCase):
    def test_only_integration_packages_are_partitioned_without_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "go.mod").write_text("module fixture\n")
            packages = []
            for i in range(5):
                package = root / ("package" + str(i))
                package.mkdir()
                name = "TestIntegrationExample" if i < 4 else "TestUnitExample"
                (package / "example_test.go").write_text(
                    "package fixture\nfunc " + name + "(t *testing.T) {}\n"
                )
                packages.append(str(package))
            # Only package discovery is stubbed; run the real upstream scripts.
            go = root / "go"
            go.write_text(
                '#!/usr/bin/env bash\n'
                'for arg in "$@"; do\n'
                '  if [[ "$arg" == */... ]]; then printf "%s\\n" "$FIXTURE_PACKAGES"; exit; fi\n'
                'done\n'
                'for arg in "$@"; do [[ "$arg" == /* ]] && printf "%s\\n" "$arg"; done\n'
            )
            go.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                       FIXTURE_PACKAGES="\n".join(packages))
            selected = subprocess.check_output(
                ["bash", str(SCRIPTS / "pkgs-with-tests-named.sh"), "-b", "TestIntegration"],
                cwd=root, env=env, text=True,
            )
            self.assertEqual(set(selected.splitlines()), set(packages[:4]))
            shards = []
            for i in range(1, 5):
                shard = subprocess.check_output(
                    ["bash", str(SCRIPTS / "shard.sh"), "-N" + str(i) + "/4", "-d-"],
                    input=selected, cwd=root, env=env, text=True,
                ).splitlines()
                self.assertEqual(len(shard), 1)
                shards.extend(shard)
            self.assertEqual(len(shards), len(set(shards)))
            self.assertEqual(set(shards), set(packages[:4]))


if __name__ == "__main__":
    unittest.main()
