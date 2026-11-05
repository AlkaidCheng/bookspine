"""Run the JavaScript tests of the export formats."""

import shutil
import subprocess
from pathlib import Path

import pytest

TEST_PATH = Path(__file__).parent / "export_formats.test.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_export_formats() -> None:
    completed = subprocess.run(
        ["node", "--test", str(TEST_PATH)], capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
