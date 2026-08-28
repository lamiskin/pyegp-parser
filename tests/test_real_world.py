"""Tests against real SAS Enterprise Guide projects.

The rest of the suite builds ``project.xml`` by hand. Real ``.egp`` files differ
from those fixtures in ways that matter: element IDs carry their own type prefix
(``<ID>CodeTask-xjq1AoRtuimaEV8v</ID>``) rather than being bare, and
``project.xml`` is UTF-16.

That prefix difference hid a bug these tests now guard: the archive path was
built as ``CodeTask-{id}/code.sas``, so real IDs resolved to
``CodeTask-CodeTask-.../code.sas`` and every embedded SAS code body was silently
dropped. See ``tests/fixtures/real_world/README.md`` for the full account.
"""

import re
import zipfile

import pytest

from pyegp_parser import parse_file
from pyegp_parser.serializer import to_dict

from .fixtures_real_world import EG71_PROJECT, EG81_PROJECT, REAL_WORLD_DIR
from .scrubbed_guard import find_scrubbed

# Shapes that identify a *person, host, or organisation* regardless of whether
# anyone thought to add the literal string above. An exact-string list can only
# catch what a previous maintainer already knew about; every identifier missed
# so far — an expanded org name, a second hostname, a UNC server — was invisible
# to the list but obvious to these.
_IDENTIFIER_SHAPES = (
    # A OneDrive for Business path carries the tenant's organisation name.
    re.compile(r"OneDrive - (?!Example Org\b)[A-Za-z0-9][A-Za-z0-9 ._-]{2,}"),
    # UNC server names.
    re.compile(r"\\\\(?!eghost\b)[A-Za-z0-9_-]{2,}\\", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # Private-range addresses only. A bare dotted quad is too broad here: SAS
    # writes component versions like `7.100.5.0` that are indistinguishable
    # from an IP, and internal addresses that leak are RFC 1918 in practice.
    re.compile(r"\b(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)\d{1,3}\.\d{1,3}\b"),
)


def _decode_entry(raw: bytes) -> str:
    """Decode an archive entry, handling UTF-16 with *and without* a BOM.

    EG writes ``project.xml`` as UTF-16LE, and not always with a BOM. Treating a
    BOM-less UTF-16 entry as UTF-8 yields mojibake in which no identifier can be
    found, so a guard that only checks for a BOM silently passes over exactly
    the file most likely to carry them.
    """
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    if raw[:400].count(0) > len(raw[:400]) // 4:
        return raw.decode("utf-16-le", "replace")
    return raw.decode("utf-8", "replace")


@pytest.fixture(scope="module")
def eg81():
    """The EG 8.1 project, parsed once."""
    return to_dict(parse_file(str(EG81_PROJECT)))


class TestEG81Project:
    """A genuine EG 8.1 project with two process flows."""

    def test_reports_eg_version(self, eg81):
        assert eg81["metadata"]["eg_version"] == "8.1"

    def test_extracts_full_element_inventory(self, eg81):
        assert len(eg81["elements"]) == 29
        assert len(eg81["containers"]) == 2
        assert len(eg81["tasks"]) == 8
        assert len(eg81["code_elements"]) == 4
        assert len(eg81["log_elements"]) == 4
        assert len(eg81["shortcuts"]) == 4

    def test_extracts_data_and_external_references(self, eg81):
        assert len(eg81["data_list"]) == 3
        assert len(eg81["external_files"]) == 1

    def test_source_info_reflects_the_archive(self, eg81):
        source = eg81["source"]
        assert source["file_name"] == "eg81_process_flows.egp"
        assert source["total_zip_entries"] == 40
        assert source["file_size_bytes"] > 0

    def test_completeness_accounts_for_every_entry(self, eg81):
        summary = eg81["completeness_summary"]
        assert summary["total_entries"] == 40
        assert (
            summary["processed_entries"] + summary["unprocessed_entries"]
            == summary["total_entries"]
        )

    def test_element_ids_carry_their_type_prefix(self, eg81):
        """Real EG IDs embed the element type; synthetic fixtures use bare IDs."""
        ids = [element["id"] for element in eg81["elements"] if element.get("id")]
        assert any(element_id.startswith("CodeTask-") for element_id in ids)
        assert any(element_id.startswith("PFD-") for element_id in ids)


def _code_task_dirs(path):
    """IDs of the code tasks that actually ship a ``code.sas`` in the archive."""
    with zipfile.ZipFile(path) as archive:
        return {
            name.split("/")[-2]
            for name in archive.namelist()
            if name.endswith("/code.sas")
        }


class TestEmbeddedSasCode:
    """Extraction of embedded SAS code from a real project.

    Regression cover for the archive-path bug: real EG element IDs already
    carry their type prefix, so building ``CodeTask-{id}/code.sas`` produced
    ``CodeTask-CodeTask-.../code.sas`` and dropped every code body.
    """

    def test_code_content_is_populated(self, eg81):
        """Code tasks with a ``code.sas`` entry expose its contents."""
        available = _code_task_dirs(EG81_PROJECT)
        code_tasks = [
            task for task in eg81["tasks"] if task["_type"] == "CodeTaskElement"
        ]
        assert code_tasks

        populated = [task for task in code_tasks if task["metadata"]["id"] in available]
        assert populated, "no code task lined up with a code.sas archive entry"
        for task in populated:
            assert task["code_content"], (
                f"{task['metadata']['id']} has a code.sas entry but no code_content"
            )

    def test_code_content_round_trips_the_archive_bytes(self, eg81):
        """The extracted text matches what the ZIP entry actually holds."""
        with zipfile.ZipFile(EG81_PROJECT) as archive:
            for task in eg81["tasks"]:
                if task["_type"] != "CodeTaskElement" or not task["code_content"]:
                    continue
                entry = f"{task['metadata']['id']}/code.sas"
                expected = archive.read(entry).decode("utf-8")
                assert task["code_content"] == expected

    def test_code_task_without_an_archive_entry_stays_none(self, eg81):
        """A code task with no ``code.sas`` is reported as absent, not invented."""
        available = _code_task_dirs(EG81_PROJECT)
        missing = [
            task
            for task in eg81["tasks"]
            if task["_type"] == "CodeTaskElement"
            and task["metadata"]["id"] not in available
        ]
        assert missing, "fixture no longer covers the absent-code.sas case"
        assert all(task["code_content"] is None for task in missing)

    def test_eg_task_configs_are_loaded(self, eg81):
        """The same prefix bug also blanked EGTask configs."""
        eg_tasks = [task for task in eg81["tasks"] if task["_type"] == "EGTaskElement"]
        assert eg_tasks
        assert all(task["task_config"] for task in eg_tasks)


class TestEG71Project:
    """An EG 7.1 project — an older schema revision than any synthetic fixture."""

    def test_archive_is_a_readable_eg_project(self):
        with zipfile.ZipFile(EG71_PROJECT) as archive:
            names = archive.namelist()
        assert "project.xml" in names
        assert any(name.endswith("code.sas") for name in names)

    def test_parses(self):
        """A Log element with no <Log> section no longer aborts the parse.

        This project contains one such element; it used to raise
        ``ValueError`` and take the whole file down with it.
        """
        parsed = to_dict(parse_file(str(EG71_PROJECT)))
        assert parsed["metadata"]["eg_version"] == "7.1"
        assert parsed["elements"]

    def test_incomplete_log_element_is_still_recorded(self):
        """The unparseable log element is retained, with empty display settings."""
        parsed = to_dict(parse_file(str(EG71_PROJECT)))
        logs = parsed["log_elements"]
        assert logs, "log elements were dropped entirely"
        incomplete = [log for log in logs if log["line_size"] is None]
        assert incomplete, "fixture no longer covers the malformed-Log case"
        assert all(log["metadata"]["id"] for log in incomplete)


@pytest.mark.parametrize(
    "path",
    sorted(REAL_WORLD_DIR.glob("*.egp")),
    ids=lambda p: p.name,
)
def test_fixtures_contain_no_unscrubbed_identifiers(path):
    """Guard: the committed fixtures must stay free of upstream identifiers.

    The identifiers are matched by hash rather than by literal, so that this
    repository does not itself publish the values the fixtures were sanitised to
    remove. See ``tests/scrubbed_guard.py``.
    """
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            text = _decode_entry(archive.read(name))
            hit = find_scrubbed(text + " " + name)
            assert hit is None, (
                f"{path.name}:{name} contains a known upstream identifier at "
                f"offset {hit[0]} (sha256 {hit[1][:12]}…). Re-run the "
                "sanitisation step; the procedure is in "
                "tests/fixtures/real_world/README.md."
            )


@pytest.mark.parametrize(
    "path",
    sorted(REAL_WORLD_DIR.glob("*.egp")),
    ids=lambda p: p.name,
)
def test_fixtures_contain_no_identifier_shaped_strings(path):
    """Guard: catch identifiers nobody thought to add to ``_SCRUBBED``.

    The named-identifier list above is necessarily retrospective. This asserts
    on the *shape* of a leak instead, so an unfamiliar host, tenant, mailbox or
    routable address fails the build the first time it appears.
    """
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            text = _decode_entry(archive.read(name))
            for pattern in _IDENTIFIER_SHAPES:
                found = pattern.search(text)
                assert found is None, (
                    f"{path.name}:{name} contains {found.group(0)!r}, which looks "
                    "like a real identifier. Sanitise it, then extend the "
                    "substitution table in tests/fixtures/real_world/README.md."
                )
