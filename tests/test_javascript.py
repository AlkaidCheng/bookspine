"""Run the JavaScript tests of the static scripts."""

import shutil
import subprocess
from pathlib import Path

import pytest

TEST_PATHS = sorted(Path(__file__).parent.glob("*.test.js"))


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
@pytest.mark.parametrize("test_path", TEST_PATHS, ids=lambda path: path.name)
def test_javascript(test_path: Path) -> None:
    completed = subprocess.run(
        ["node", "--test", str(test_path)], capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
