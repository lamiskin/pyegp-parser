# Real-world SAS Enterprise Guide fixtures

Genuine `.egp` projects, used because hand-written `project.xml` cannot
reproduce how real Enterprise Guide serialises a project.

## Provenance

Both files come from
[ShenzhenYAO/sas_egp_v8tov7](https://github.com/ShenzhenYAO/sas_egp_v8tov7),
retrieved 2026-07-27.

| Fixture | Upstream path | EG version | Notes |
|---|---|---|---|
| `eg81_process_flows.egp` | `data/in/sample_a_v8.egp` | 8.1 | Authored by Enterprise Guide; two process flows, 29 elements |
| `eg71_code_tasks.egp` | `data/out/history/05_test_jsconverted_v7.egp` | 7.1 | Produced by the upstream v8→v7 converter; its logs and SAS code are EG-authored |

> **Licence caveat.** The upstream repository publishes no licence. It is the
> only public source of genuine `.egp` files found — a survey of 54 SAS-related
> repositories turned up no other candidates, and because `.egp` files are ZIP
> archives GitHub's code search never indexes them. These fixtures are included
> as test data on that basis; if the absence of an upstream licence is a concern,
> remove this directory and `test_real_world.py` will skip.

`eg81_process_flows.egp` contains a `.git/` directory captured inside the
archive by its author. It was checked and holds only default `git init` scaffolding
— no remotes, no user identity — and is kept because it exercises the parser's
handling of unexpected archive entries.

## Sanitisation

The upstream project embedded its author's identifiers. Every occurrence was
rewritten before committing, so these files are **not** byte-for-byte identical
to upstream:

| What it was | Replacement |
|---|---|
| The author's name, in two forms, one carrying an employer initialism | `Example User` |
| Their workstation host name, bare and in `c:\users\…\` paths | `EGHOST` / `eghost` |
| A second host name in `_CLIENTPROJECTPATHHOST` | `EGHOST` |
| A UNC file-redirect server in `\\…\FOLDERREDIR$\…` | `eghost` |
| Their user name | `eguser` |
| The employer's full name, in a OneDrive for Business path | `OneDrive - Example Org` |

The upstream values are deliberately **not** listed here. This fixture set is
the work of one identifiable person, and naming the values would reassemble in a
single table what the substitution took apart: a full name, an employer, a user
name, two workstations and a file server. They are held as hashes in
`tests/scrubbed_guard.py` instead; that module documents what the hashing does
and does not achieve.

Rewriting happened inside the ZIP with entry names, order, and timestamps
preserved; `project.xml` was re-encoded to match the original byte-for-byte,
including whether it carries a UTF-16 BOM. Parse results are unchanged — both
files yield the same element counts, completeness summary, and ZIP entry totals
as the originals, and every archive entry other than `project.xml` is byte-identical.

> **Why the last four rows exist.** The first sanitisation pass missed them, and
> the guard did not notice. `eg71_code_tasks.egp/project.xml` is UTF-16LE
> **without a BOM**, and the guard decoded any BOM-less entry as UTF-8 — turning
> that file into mojibake in which no identifier could ever match. It was the
> file carrying the author's name, user name, and UNC server. Separately, the
> employer's full name is the expansion of an initialism the guard already
> watched for: it looked for the short form while the spelled-out organisation
> name sat in a OneDrive path. An abbreviation and its expansion are two
> identifiers, not one.

Two guards now run over the fixtures. `test_fixtures_contain_no_unscrubbed_identifiers`
hashes candidate windows out of each archive entry and compares them against the
stored digests, decoding UTF-16 with or without a BOM.
`test_fixtures_contain_no_identifier_shaped_strings` asserts on the *shape* of a
leak — OneDrive tenants, UNC servers, e-mail addresses, RFC 1918 addresses — so
an identifier nobody has thought of yet fails the build the first time it
appears, rather than waiting to be added to a list.

## Defects these files exposed (both now fixed)

Neither was reachable from the hand-written fixtures; both were found by adding
these files and are now covered by regression tests.

1. **Embedded SAS code was silently dropped.** `parsers/task_parser.py` built the
   archive path as `CodeTask-{id}/code.sas`, but real EG element IDs already
   begin with `CodeTask-`, producing `CodeTask-CodeTask-.../code.sas`. The lookup
   missed, a warning was logged, and `code_content` became `None` for *every*
   code task. The same double-prefixing blanked `EGTask` and `ImportTask`
   configs. Fixed by `_element_dir()`, which only adds the prefix when the ID
   does not already carry it. Covered by
   `test_task_parser.py::TestPrefixedElementIds` and
   `test_real_world.py::TestEmbeddedSasCode`.
2. **A malformed Log element aborted the whole parse.** `eg71_code_tasks.egp`
   raised `ValueError: Log element 'Log-C2VOTFC7LgPEnUsG' is missing required Log
   section`, taking the entire file down. `parse_file` now catches it, logs a
   warning, and records the element without its display settings — matching how
   unparseable process-flow containers were already handled. `parse_log_element`
   itself still raises, so its contract is unchanged. Covered by
   `test_real_world.py::TestEG71Project`.

Note that two code tasks (`CodeTask-zuxheXrmOhkcqb2t` in the 8.1 project,
`CodeTask-MxlwbePYM8xnyu6B` in the 7.1 one) have no `code.sas` entry at all, so
their `code_content` is legitimately `None`; a test pins that distinction so a
future regression cannot pass by inventing content.

The `9JWEnME6zVrlt3Rn/PFD-…/CodeTask-…/code.sas` entries in the 8.1 archive are
duplicates from a git working tree its author captured inside the project. The
canonical task folders sit at the archive root, which is what the parser reads.

## Refreshing

Re-download from the upstream paths above, re-apply the substitution table, and
re-run `pytest tests/test_real_world.py`. Do not commit upstream files directly.
Remember that `project.xml` may be UTF-16LE without a BOM — decode accordingly,
or the pass will appear to succeed on a file it never actually read.

Because the upstream values are not written down here, recovering them means
opening the upstream files and reading the identifiers out — which is the
sanitisation step anyway. If that pass turns up an identifier the guard does not
yet know about, add it by hashing its lowercased form and extending both
`_DIGESTS` and `_WINDOW_LENGTHS` in `tests/scrubbed_guard.py`:

```bash
python3 -c 'import hashlib,sys; v=sys.argv[1].lower(); print(hashlib.sha256(v.encode()).hexdigest(), len(v))' 'VALUE'
```
