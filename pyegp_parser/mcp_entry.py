"""Console-script entry point for the optional MCP server.

Kept separate from :mod:`pyegp_parser.mcp_server` so that running
``pyegp-parser-mcp`` without the ``mcp`` extra installed prints a one-line
install hint instead of an import traceback. The server module itself imports
``mcp`` at module scope, which is why the guard cannot live there.
"""

import sys

_MISSING_EXTRA_HINT = (
    'pyegp-parser: the MCP server requires the optional "mcp" extra.\n'
    'Install it with:  pip install "pyegp-parser[mcp]"'
)


def main() -> None:
    """Run the MCP server, or exit with an install hint if the extra is absent."""
    try:
        from pyegp_parser.mcp_server import main as run_server
    except ModuleNotFoundError as exc:
        # Only translate a missing `mcp` package; anything else is a real bug.
        if (exc.name or "").split(".")[0] != "mcp":
            raise
        sys.exit(_MISSING_EXTRA_HINT)

    run_server()


if __name__ == "__main__":
    main()
