"""Smoke tests for the optional MCP server.

The MCP server ships behind the ``mcp`` extra (``pip install
"pyegp-parser[mcp]"``); the whole module is skipped when the extra is not
installed. Tools are MCPServer-decorated plain functions, so they are called
directly and their JSON string results asserted.

Skipping is a convenience for contributors who install without the extra. CI
installs it and sets ``REQUIRE_MCP_EXTRA=1``, which turns a missing extra into
an error — otherwise a broken install would silently leave this module untested
while the run stayed green.
"""

import asyncio
import importlib
import json
import os
import zipfile
from pathlib import Path

import pytest

if os.environ.get("REQUIRE_MCP_EXTRA") == "1":
    importlib.import_module("mcp")
else:
    pytest.importorskip("mcp", reason="the 'mcp' optional extra is not installed")

from pyegp_parser import mcp_server

from .fixtures_real_world import EG81_PROJECT

EXPECTED_TOOLS = {
    "parse_egp",
    "parse_egp_directory",
    "get_project_summary",
    "get_sas_code",
    "get_data_lineage",
    "get_queries",
}

_PROJECT_XML = """<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="EGProject">
  <Project>
    <Element Label="Test" Type="SAS.EG.ProjectElements.Project" ID="abc123">
    </Element>
    <Elements />
  </Project>
</ProjectCollection>"""


@pytest.fixture
def egp_path(tmp_path: Path) -> str:
    """A minimal valid .egp archive on disk."""
    path = tmp_path / "test.egp"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("project.xml", _PROJECT_XML)
    return str(path)


@pytest.fixture
def corrupt_egp_path(tmp_path: Path) -> str:
    """A valid ZIP with the right extension but no project.xml — parse_file
    raises ValueError, exercising every tool's exception branch."""
    path = tmp_path / "corrupt.egp"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("not_project.xml", "irrelevant")
    return str(path)


@pytest.fixture
def mixed_directory(tmp_path: Path, egp_path: str) -> str:
    """A directory with one parseable .egp and one that fails to parse."""
    directory = tmp_path / "mixed"
    directory.mkdir()
    (directory / "good.egp").write_bytes(Path(egp_path).read_bytes())
    with zipfile.ZipFile(directory / "bad.egp", "w") as zf:
        zf.writestr("not_project.xml", "irrelevant")
    return str(directory)


class TestToolRegistration:
    def test_all_tools_registered(self):
        """Every documented tool is registered on the FastMCP server."""
        tools = asyncio.run(mcp_server.mcp.list_tools())
        names = {tool.name for tool in tools}
        assert names >= EXPECTED_TOOLS


class TestParseEgp:
    def test_returns_project_json(self, egp_path):
        data = json.loads(mcp_server.parse_egp(egp_path))
        assert data["_type"] == "ParsedProject"
        assert data["source"]["file_name"] == "test.egp"

    def test_output_dir_writes_json(self, egp_path, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        data = json.loads(mcp_server.parse_egp(egp_path, output_dir=str(out_dir)))
        assert data["status"] == "success"
        assert list(out_dir.rglob("*.json"))

    def test_missing_file_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.parse_egp(str(tmp_path / "missing.egp")))
        assert "error" in data

    def test_wrong_extension_returns_error_json(self, tmp_path):
        not_egp = tmp_path / "file.txt"
        not_egp.write_text("not an egp")
        data = json.loads(mcp_server.parse_egp(str(not_egp)))
        assert "error" in data

    def test_corrupt_archive_returns_error_json(self, corrupt_egp_path):
        """A .egp that exists and has the right extension but fails to parse
        (missing project.xml) hits the try/except ValueError branch, not the
        upfront existence/extension checks."""
        data = json.loads(mcp_server.parse_egp(corrupt_egp_path))
        assert "error" in data


class TestParseEgpDirectory:
    def test_parses_directory(self, egp_path):
        directory = str(Path(egp_path).parent)
        data = json.loads(mcp_server.parse_egp_directory(directory))
        assert data["status"] == "success"
        assert data["total_files"] == 1
        assert data["success_count"] == 1

    def test_missing_directory_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.parse_egp_directory(str(tmp_path / "nope")))
        assert "error" in data

    def test_partial_failure_lists_failures(self, mixed_directory):
        data = json.loads(mcp_server.parse_egp_directory(mixed_directory))
        assert data["status"] == "success"
        assert data["total_files"] == 2
        assert data["success_count"] == 1
        assert data["failure_count"] == 1
        assert len(data["failures"]) == 1
        assert "bad.egp" in data["failures"][0]["file"]


class TestGetProjectSummary:
    def test_summarizes_project(self, egp_path):
        data = json.loads(mcp_server.get_project_summary(egp_path))
        assert "project_name" in data
        assert "counts" in data
        assert data["counts"]["queries"] == 0

    def test_missing_file_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.get_project_summary(str(tmp_path / "no.egp")))
        assert "error" in data

    def test_corrupt_archive_returns_error_json(self, corrupt_egp_path):
        data = json.loads(mcp_server.get_project_summary(corrupt_egp_path))
        assert "error" in data

    def test_summarizes_real_project(self):
        """A project with process flows, tasks, and data items exercises the
        execution_order, data_sources, and completeness branches that an
        empty synthetic project never reaches."""
        data = json.loads(mcp_server.get_project_summary(str(EG81_PROJECT)))
        assert data["counts"]["elements"] > 0
        assert data["counts"]["code_tasks"] > 0
        assert len(data["execution_order"]) == 2
        for flow in data["execution_order"]:
            assert flow["nodes"]
        assert data["data_sources"]
        assert data["data_sources"][0]["server"] is not None
        assert data["completeness"] == {
            "total_entries": 40,
            "processed": 30,
            "unprocessed": 10,
        }


class TestGetSasCode:
    def test_empty_project_has_no_code(self, egp_path):
        data = json.loads(mcp_server.get_sas_code(egp_path))
        assert data["code_blocks"] == []

    def test_unknown_element_returns_error_json(self, egp_path):
        data = json.loads(mcp_server.get_sas_code(egp_path, element_id="nope-123"))
        assert "error" in data

    def test_missing_file_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.get_sas_code(str(tmp_path / "no.egp")))
        assert "error" in data

    def test_corrupt_archive_returns_error_json(self, corrupt_egp_path):
        data = json.loads(mcp_server.get_sas_code(corrupt_egp_path))
        assert "error" in data

    def test_all_code_from_real_project(self):
        """No element_id: collects code from both CodeTask elements and
        Code elements."""
        data = json.loads(mcp_server.get_sas_code(str(EG81_PROJECT)))
        types = {block["type"] for block in data["code_blocks"]}
        assert types == {"CodeTask", "CodeElement"}

    def test_task_element_id_matches_task_and_its_code_child(self):
        """A CodeTask's own ID matches it directly, and also matches its
        child Code element via parent_id — both branches fire for one ID."""
        data = json.loads(
            mcp_server.get_sas_code(
                str(EG81_PROJECT), element_id="CodeTask-eFeFyI2IrkNJmU7j"
            )
        )
        # One block from the task match (its own element_id, has "code"),
        # one from the ce.parent_id match (the Code element's own
        # element_id, tagged with parent_id back to the task).
        assert len(data["code_blocks"]) == 2
        task_block = next(b for b in data["code_blocks"] if "code" in b)
        child_block = next(b for b in data["code_blocks"] if "full_code" in b)
        assert task_block["element_id"] == "CodeTask-eFeFyI2IrkNJmU7j"
        assert child_block["parent_id"] == "CodeTask-eFeFyI2IrkNJmU7j"

    def test_code_element_id_matches_directly(self):
        """A Code element's own ID matches it via ce.metadata.id, not via
        parent_id."""
        data = json.loads(
            mcp_server.get_sas_code(
                str(EG81_PROJECT), element_id="Code-KtgYEOok4RfPaxkg"
            )
        )
        assert len(data["code_blocks"]) >= 1
        assert all(
            block["element_id"] == "Code-KtgYEOok4RfPaxkg"
            for block in data["code_blocks"]
        )


class TestGetDataLineage:
    def test_empty_project_has_no_lineage(self, egp_path):
        data = json.loads(mcp_server.get_data_lineage(egp_path))
        assert data["lineage"] == []

    def test_unknown_element_returns_error_json(self, egp_path):
        data = json.loads(mcp_server.get_data_lineage(egp_path, element_id="nope-123"))
        assert "error" in data

    def test_missing_file_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.get_data_lineage(str(tmp_path / "no.egp")))
        assert "error" in data

    def test_corrupt_archive_returns_error_json(self, corrupt_egp_path):
        data = json.loads(mcp_server.get_data_lineage(corrupt_egp_path))
        assert "error" in data

    def test_full_lineage_from_real_project(self):
        data = json.loads(mcp_server.get_data_lineage(str(EG81_PROJECT)))
        assert data["lineage"]
        entry = data["lineage"][0]
        assert "element" in entry
        assert entry["reads_from"]

    def test_specific_element_dependents(self):
        """A task referenced as an input by several other elements exercises
        the dependents branch."""
        data = json.loads(
            mcp_server.get_data_lineage(
                str(EG81_PROJECT), element_id="CodeTask-cRIArx6TeBFFoe9Z"
            )
        )
        assert data["element"]["id"] == "CodeTask-cRIArx6TeBFFoe9Z"
        assert data["dependents"]

    def test_specific_element_inputs_resolve_via_element_map(self):
        """A shortcut whose input_id points at a task (not a data item or
        another shortcut) exercises the element-type inputs branch."""
        data = json.loads(
            mcp_server.get_data_lineage(
                str(EG81_PROJECT), element_id="ShortCutToData-dGoyvIraA6lVr3jS"
            )
        )
        assert len(data["inputs"]) == 1
        assert data["inputs"][0]["id"] == "CodeTask-cRIArx6TeBFFoe9Z"


class TestGetQueries:
    def test_empty_project_has_no_queries(self, egp_path):
        data = json.loads(mcp_server.get_queries(egp_path))
        assert data["queries"] == []

    def test_missing_file_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.get_queries(str(tmp_path / "no.egp")))
        assert "error" in data

    def test_corrupt_archive_returns_error_json(self, corrupt_egp_path):
        data = json.loads(mcp_server.get_queries(corrupt_egp_path))
        assert "error" in data


class TestMain:
    def test_main_runs_the_server(self, monkeypatch):
        """main() is the pyegp-parser-mcp console-script entry point; stub
        out mcp.run() so the test doesn't actually start a stdio server."""
        calls = []
        monkeypatch.setattr(mcp_server.mcp, "run", lambda: calls.append(True))
        mcp_server.main()
        assert calls == [True]
