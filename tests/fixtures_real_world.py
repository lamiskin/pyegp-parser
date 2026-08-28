"""Paths to the real-world SAS Enterprise Guide fixtures used by the test suite."""

from pathlib import Path

REAL_WORLD_DIR = Path(__file__).resolve().parent / "fixtures" / "real_world"

EG81_PROJECT = REAL_WORLD_DIR / "eg81_process_flows.egp"
EG71_PROJECT = REAL_WORLD_DIR / "eg71_code_tasks.egp"
