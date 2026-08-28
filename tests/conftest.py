"""Shared test fixtures and configuration for EGP parser tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_egp_dir() -> Path:
    """Return the path to the directory containing sample .egp files."""
    # Locate sample EGP files relative to the workspace
    workspace_root = Path(__file__).resolve().parent.parent
    return workspace_root


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test outputs."""
    output = tmp_path / "output"
    output.mkdir()
    return output
