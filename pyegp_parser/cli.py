"""Command-line interface for the EGP Parser.

Provides three subcommands:
- parse: Parse a single .egp file to JSON
- bulk: Parse all .egp files in a directory
- print: Pretty-print a parsed project.json file

Requirements: 15.6, 15.16, 15.17, 19.7
"""

import argparse
import sys
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="pyegp-parser",
        description="Parse SAS Enterprise Guide .egp project files into structured JSON.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # parse subcommand: single file mode
    parse_cmd = subparsers.add_parser(
        "parse",
        help="Parse a single .egp file to JSON",
        description="Parse a single .egp file and produce structured JSON output.",
    )
    parse_cmd.add_argument(
        "file",
        type=str,
        help="Path to the .egp file to parse",
    )
    parse_cmd.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for project.json and schema.json (default: same directory as input file)",
    )

    # bulk subcommand: directory mode
    bulk_cmd = subparsers.add_parser(
        "bulk",
        help="Parse all .egp files in a directory",
        description="Recursively discover and parse all .egp files in a directory.",
    )
    bulk_cmd.add_argument(
        "directory",
        type=str,
        help="Root directory to scan for .egp files",
    )
    bulk_cmd.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for JSON results (preserves subdirectory structure)",
    )

    # print subcommand: pretty-print mode
    print_cmd = subparsers.add_parser(
        "print",
        help="Pretty-print a parsed project.json file",
        description="Display a human-readable summary of a parsed project.json file.",
    )
    print_cmd.add_argument(
        "file",
        type=str,
        help="Path to the project.json file to pretty-print",
    )

    return parser


def cmd_parse(args: argparse.Namespace) -> int:
    """Execute the 'parse' subcommand.

    Args:
        args: Parsed arguments with 'file' and optional 'output_dir'.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    from . import parse_file

    egp_path = Path(args.file)
    output_dir = Path(args.output_dir) if args.output_dir else None

    try:
        result = parse_file(egp_path, output_dir=output_dir)
        if output_dir:
            print(f"Parsed successfully: {egp_path}")
            print(f"Output written to: {output_dir}")
        else:
            print(f"Parsed successfully: {egp_path}")
            if result.source is not None:
                print(f"Source: {result.source.file_name}")
                print(f"ZIP entries: {result.source.total_zip_entries}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_bulk(args: argparse.Namespace) -> int:
    """Execute the 'bulk' subcommand.

    Args:
        args: Parsed arguments with 'directory' and optional 'output_dir'.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    from . import parse_directory

    directory = Path(args.directory)
    output_dir = Path(args.output_dir) if args.output_dir else None

    try:
        result = parse_directory(directory, output_dir=output_dir)
        print("Bulk processing complete:")
        print(f"  Total files: {result.summary.total_files}")
        print(f"  Successful:  {result.summary.success_count}")
        print(f"  Failed:      {result.summary.failure_count}")
        if result.failures:
            print("\nFailed files:")
            for failure in result.failures:
                print(f"  {failure.file_path}: {failure.error_message}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_print(args: argparse.Namespace) -> int:
    """Execute the 'print' subcommand.

    Args:
        args: Parsed arguments with 'file' (path to project.json).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    from .pretty_printer import pretty_print

    json_path = Path(args.file)

    if not json_path.exists():
        print(f"Error: File not found: {json_path}", file=sys.stderr)
        return 1

    try:
        json_content = json_path.read_text(encoding="utf-8")
        output = pretty_print(json_content)
        print(output)
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> None:
    """Entry point for the pyegp-parser CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Dispatch to the appropriate subcommand handler
    handlers = {
        "parse": cmd_parse,
        "bulk": cmd_bulk,
        "print": cmd_print,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    exit_code = handler(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
