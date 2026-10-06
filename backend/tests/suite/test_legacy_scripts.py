"""
Runs the project's original end-to-end scripts (tests/test_accounts.py and
tests/test_cases.py) inside the pytest run, each against its own freshly
seeded database, so they are part of one regression command.
"""

import os
import subprocess
import sys

import pytest

from conftest import BACKEND


@pytest.mark.parametrize("script", ["test_accounts.py", "test_cases.py"])
def test_original_end_to_end_script(script, tmp_path):
    env = {**os.environ, "NIVARA_DB_PATH": str(tmp_path / "legacy.db")}
    seed = subprocess.run([sys.executable, "seed_demo.py"], cwd=BACKEND, env=env,
                          capture_output=True, text=True, timeout=300)
    assert seed.returncode == 0, seed.stderr[-2000:]
    run = subprocess.run([sys.executable, os.path.join("tests", script)], cwd=BACKEND, env=env,
                         capture_output=True, text=True, timeout=300)
    failures = [line for line in run.stdout.splitlines() if line.startswith("FAIL")]
    assert run.returncode == 0 and "ALL PASSED" in run.stdout, "\n".join(failures) or run.stderr[-2000:]
