"""Tests for the pyegp_parser CLI module."""

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pyegp_parser.cli import cmd_bulk, cmd_parse, cmd_print, create_parser, main


@pytest.fixture
def valid_egp_file(tmp_path: Path) -> Path:
    """Create a minimal valid .egp file for testing."""
    egp_path = tmp_path / "test.egp"
    project_xml = """<?xml version="1.0" encoding="utf-8"?>
<ProjectCollection EGVersion="8.1" Type="EGProject">
  <Project>
    <Element Label="Test" Type="SAS.EG.ProjectElements.Project" ID="abc123">
    </Element>
    <Elements />
  </Project>
</ProjectCollection>"""
    with zipfile.ZipFile(egp_path, "w") as zf:
        zf.writestr("project.xml", project_xml)
    return egp_path


@pytest.fixture
def valid_project_json(tmp_path: Path) -> Path:
    """Create a minimal valid project.json for pretty-print testing."""
    json_path = tmp_path / "project.json"
    data = {
        "_type": "ParsedProject",
        "_schema_version": "1.0.0",
        "source": {
            "_type": "SourceInfo",
            "file_path": "/tmp/test.egp",
            "file_name": "test.egp",
            "file_size_bytes": 1024,
            "parsed_at": "2024-01-01T00:00:00",
            "total_zip_entries": 1,
        },
        "metadata": None,
        "settings": None,
        "data_list": [],
        "external_files": [],
        "elements": [],
        "containers": [],
        "parameters": [],
        "project_log": None,
        "visual_layout": None,
        "completeness_summary": None,
        "unprocessed_entries": [],
        "completeness_warning": False,
        "binary_entries": [],
    }
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return json_path


class TestCreateParser:
    """Tests for the argument parser creation."""

    def test_parser_has_parse_subcommand(self):
        parser = create_parser()
        args = parser.parse_args(["parse", "test.egp"])
        assert args.command == "parse"
        assert args.file == "test.egp"

    def test_parser_parse_with_output_dir(self):
        parser = create_parser()
        args = parser.parse_args(["parse", "test.egp", "--output-dir", "/tmp/out"])
        assert args.command == "parse"
        assert args.file == "test.egp"
        assert args.output_dir == "/tmp/out"

    def test_parser_has_bulk_subcommand(self):
        parser = create_parser()
        args = parser.parse_args(["bulk", "/path/to/dir"])
        assert args.command == "bulk"
        assert args.directory == "/path/to/dir"

    def test_parser_bulk_with_output_dir(self):
        parser = create_parser()
        args = parser.parse_args(["bulk", "/path/to/dir", "--output-dir", "/tmp/out"])
        assert args.command == "bulk"
        assert args.directory == "/path/to/dir"
        assert args.output_dir == "/tmp/out"

    def test_parser_has_print_subcommand(self):
        parser = create_parser()
        args = parser.parse_args(["print", "project.json"])
        assert args.command == "print"
        assert args.file == "project.json"

    def test_parser_no_command(self):
        parser = create_parser()
        args = parser.parse_args([])
        assert args.command is None


class TestCmdParse:
    """Tests for the parse subcommand handler."""

    def test_parse_valid_file(self, valid_egp_file: Path, tmp_path: Path):
        parser = create_parser()
        output_dir = tmp_path / "output"
        args = parser.parse_args(
            ["parse", str(valid_egp_file), "--output-dir", str(output_dir)]
        )
        exit_code = cmd_parse(args)
        assert exit_code == 0
        assert (output_dir / "project.json").exists()

    def test_parse_nonexistent_file(self, tmp_path: Path):
        parser = create_parser()
        args = parser.parse_args(["parse", str(tmp_path / "nonexistent.egp")])
        exit_code = cmd_parse(args)
        assert exit_code == 1

    def test_parse_invalid_zip(self, tmp_path: Path):
        invalid_file = tmp_path / "invalid.egp"
        invalid_file.write_text("not a zip file")
        parser = create_parser()
        args = parser.parse_args(["parse", str(invalid_file)])
        exit_code = cmd_parse(args)
        assert exit_code == 1

    def test_parse_no_output_dir(self, valid_egp_file: Path):
        parser = create_parser()
        args = parser.parse_args(["parse", str(valid_egp_file)])
        exit_code = cmd_parse(args)
        assert exit_code == 0


class TestCmdBulk:
    """Tests for the bulk subcommand handler."""

    def test_bulk_valid_directory(self, valid_egp_file: Path, tmp_path: Path):
        parser = create_parser()
        output_dir = tmp_path / "bulk_output"
        args = parser.parse_args(
            ["bulk", str(valid_egp_file.parent), "--output-dir", str(output_dir)]
        )
        exit_code = cmd_bulk(args)
        assert exit_code == 0

    def test_bulk_nonexistent_directory(self, tmp_path: Path):
        parser = create_parser()
        args = parser.parse_args(["bulk", str(tmp_path / "nonexistent")])
        exit_code = cmd_bulk(args)
        assert exit_code == 1

    def test_bulk_empty_directory(self, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        parser = create_parser()
        args = parser.parse_args(["bulk", str(empty_dir)])
        exit_code = cmd_bulk(args)
        assert exit_code == 0


class TestCmdPrint:
    """Tests for the print subcommand handler."""

    def test_print_nonexistent_file(self, tmp_path: Path):
        parser = create_parser()
        args = parser.parse_args(["print", str(tmp_path / "nonexistent.json")])
        exit_code = cmd_print(args)
        assert exit_code == 1

    def test_print_invalid_json(self, tmp_path: Path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not valid json at all", encoding="utf-8")
        parser = create_parser()
        args = parser.parse_args(["print", str(bad_json)])
        exit_code = cmd_print(args)
        assert exit_code == 1


class TestMain:
    """Tests for the main entry point."""

    def test_main_no_args(self):
        with patch("sys.argv", ["pyegp-parser"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_parse_command(self, valid_egp_file: Path):
        with patch("sys.argv", ["pyegp-parser", "parse", str(valid_egp_file)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_parse_nonexistent(self, tmp_path: Path):
        with patch(
            "sys.argv", ["pyegp-parser", "parse", str(tmp_path / "missing.egp")]
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
