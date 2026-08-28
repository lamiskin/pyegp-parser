# Security Policy

## Supported versions

The latest released version on PyPI receives security fixes.

## Reporting a vulnerability

Please report security issues privately via GitHub's
[private vulnerability reporting](https://github.com/lamiskin/pyegp-parser/security/advisories/new)
rather than opening a public issue.

Please do **not** include real or confidential `.egp` data or parsed output in
your report — a minimal synthetic reproduction is preferred.

You can expect an initial response within a reasonable timeframe. Thanks for
helping keep the project and its users safe.

## Security model, and what this tool does not guarantee

`pyegp-parser` reads ZIP archives and XML and produces JSON. It executes no SAS
code, opens no database connections, and resolves no external XML entities.

The important thing to understand about `.egp` files is that they carry
**embedded SAS programs and execution logs**, reproduced verbatim in parser
output. SAS code routinely contains live credentials:

```sas
libname dw oracle user=etluser password=hunter2 path=prod;
```

So the parser performs **best-effort credential redaction** when it writes
output. Detected credentials are replaced with `[SENSITIVE - REDACTED]`:

- `password=` / `passwd=` / `pwd=` / `pw=` / `pass=` assignments, quoted or bare
- SAS-encoded passwords (`{SAS002}...`) — `PROC PWENCODE` output is reversible,
  so it is treated as plaintext
- `%LET` macro assignments whose variable name looks password-like
- Values under a password-like key

Redaction is applied when a `project.json` is written and to output returned by
the MCP server. `to_dict()` is a pure serializer and does **not** redact — call
`pyegp_parser.redaction.redact()` yourself if you route output elsewhere, or
pass `redact=False` to `serialize_project()` if you deliberately need
byte-faithful code.

Treat that as a convenience, not a security boundary:

- Redaction targets credentials. It does **not** remove server names, library
  paths, database or schema names, file paths, or usernames — all of which SAS
  code and EG logs contain freely.
- A credential in an unusual form (a custom macro, a value assembled at runtime,
  an authentication-domain reference) will not match the patterns.
- Column and macro-variable *names* containing "password" are deliberately left
  intact, because they are schema metadata rather than secrets.

**Review parser output before sharing it** outside your organisation, attaching
it to an issue, or feeding it to an external service. If you find a credential
that survives redaction, please report it privately as a vulnerability.
