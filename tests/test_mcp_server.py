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


class TestGetProjectSummary:
    def test_summarizes_project(self, egp_path):
        data = json.loads(mcp_server.get_project_summary(egp_path))
        assert "project_name" in data
        assert "counts" in data
        assert data["counts"]["queries"] == 0

    def test_missing_file_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.get_project_summary(str(tmp_path / "no.egp")))
        assert "error" in data


class TestGetSasCode:
    def test_empty_project_has_no_code(self, egp_path):
        data = json.loads(mcp_server.get_sas_code(egp_path))
        assert data["code_blocks"] == []

    def test_unknown_element_returns_error_json(self, egp_path):
        data = json.loads(mcp_server.get_sas_code(egp_path, element_id="nope-123"))
        assert "error" in data


class TestGetDataLineage:
    def test_empty_project_has_no_lineage(self, egp_path):
        data = json.loads(mcp_server.get_data_lineage(egp_path))
        assert data["lineage"] == []

    def test_unknown_element_returns_error_json(self, egp_path):
        data = json.loads(mcp_server.get_data_lineage(egp_path, element_id="nope-123"))
        assert "error" in data


class TestGetQueries:
    def test_empty_project_has_no_queries(self, egp_path):
        data = json.loads(mcp_server.get_queries(egp_path))
        assert data["queries"] == []
