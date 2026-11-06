"""The notices that travel with the compiled module."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_DIR = Path(__file__).parent.parent
MANIFEST_PATH = REPOSITORY_DIR / "rust" / "Cargo.toml"
NOTICE_PATH = REPOSITORY_DIR / "LICENSES" / "rust-crates.txt"

# Everything linked into the module, on any platform. Proc-macro crates run only at
# build time. https://doc.rust-lang.org/cargo/commands/cargo-tree.html
LINKED_CRATES_COMMAND = [
    "cargo",
    "tree",
    "--manifest-path",
    str(MANIFEST_PATH),
    "--edges",
    "normal,no-proc-macro",
    "--target",
    "all",
    "--prefix",
    "none",
]


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo is not installed")
def test_every_linked_crate_has_a_notice() -> None:
    listing = subprocess.run(
        LINKED_CRATES_COMMAND, capture_output=True, check=True, text=True
    ).stdout
    crates = {line.split()[0] for line in listing.splitlines()} - {"bookspine"}
    noticed = {
        line.split()[0]
        for line in NOTICE_PATH.read_text(encoding="utf-8").splitlines()
        if line.endswith(">")
    }
    assert crates <= noticed
