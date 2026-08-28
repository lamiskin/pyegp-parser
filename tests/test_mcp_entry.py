"""Tests for the MCP console-script entry point.

These do not need the ``mcp`` extra: the missing-extra path is simulated by
blocking the import, so the guard is covered on every CI job.
"""

import builtins
import sys

import pytest

from pyegp_parser import mcp_entry


def _block_mcp_import(monkeypatch, missing="mcp"):
    """Make ``import mcp...`` raise ModuleNotFoundError(name=missing)."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.split(".")[0] == "mcp" or name == "pyegp_parser.mcp_server":
            raise ModuleNotFoundError(f"No module named {missing!r}", name=missing)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "pyegp_parser.mcp_server", raising=False)


def test_missing_extra_exits_with_install_hint(monkeypatch, capsys):
    """Without the extra, the script exits cleanly naming the install command."""
    _block_mcp_import(monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        mcp_entry.main()

    message = str(excinfo.value)
    assert 'pip install "pyegp-parser[mcp]"' in message
    # A bare traceback is exactly what this entry point exists to avoid.
    assert "Traceback" not in message


def test_unrelated_import_error_is_not_swallowed(monkeypatch):
    """A genuine missing dependency must still surface as an error, not a hint."""
    _block_mcp_import(monkeypatch, missing="something_else")

    with pytest.raises(ModuleNotFoundError):
        mcp_entry.main()


def test_runs_server_when_extra_is_present(monkeypatch):
    """With the extra importable, the entry point delegates to the server."""
    pytest.importorskip("mcp", reason="the 'mcp' optional extra is not installed")

    called = []
    monkeypatch.setattr(
        "pyegp_parser.mcp_server.main", lambda: called.append(True), raising=True
    )

    mcp_entry.main()

    assert called == [True]
