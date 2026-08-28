"""Best-effort credential redaction for parsed EGP output.

Unlike SSIS packages, where credentials sit in structured connection-string
fields, an `.egp` project hides them in **free text**: embedded SAS programs,
execution logs, and task configuration. A single `LIBNAME` or `CONNECT TO`
statement routinely carries a live database password, and those statements are
reproduced verbatim in parser output.

This module therefore redacts by *pattern* rather than by field name:

1. ``password=`` / ``pwd=`` / ``pw=`` / ``pass=`` assignments, with the value
   quoted or bare, as used by ``LIBNAME``, ``CONNECT TO`` and ``PROC`` options.
2. SAS-encoded passwords (``{SAS002}...``), which are trivially reversible with
   ``PROC PWENCODE`` and must be treated as plaintext.
3. ``%LET`` macro assignments whose variable name looks password-like.
4. Dictionary keys that are themselves password-like.

Treat this as a convenience, not a security boundary — see ``SECURITY.md``. It
does not remove server names, library paths, schema names, or usernames, all of
which SAS code contains freely.
"""

import copy
import re
from typing import Any

#: Replacement written in place of a detected credential.
REDACTION_PLACEHOLDER = "[SENSITIVE - REDACTED]"

# Option keywords that introduce a credential in SAS syntax.
_CREDENTIAL_KEYWORD = r"(?:password|passwd|pwd|pw|pass)"

# `password='secret'`, `pwd = secret`, `PW="secret"`. The `\b` before the
# keyword and the required `=` keep column names such as PASSWORD_HASH intact.
_ASSIGNMENT = re.compile(
    rf"(?i)\b({_CREDENTIAL_KEYWORD})(\s*=\s*)('[^']*'|\"[^\"]*\"|[^\s;,)]+)"
)

# `{SAS002}A1B2C3...` — PWENCODE output, reversible, so still a secret.
_ENCODED = re.compile(r"(?i)\{sas\d{3}\}[A-Za-z0-9+/=]*")

# `%let db_pwd = secret;`
_MACRO_ASSIGN = re.compile(
    r"(?i)(%let\s+[A-Za-z_][A-Za-z0-9_]*(?:pass|pwd|pw)[A-Za-z0-9_]*\s*=\s*)([^;\n]+)"
)

#: Substring patterns marking a *dict key* as holding a credential.
SENSITIVE_FIELD_PATTERNS = ("password", "passwd", "pwd")


def redact_text(text: str) -> tuple[str, int]:
    """Redact credential patterns in a block of free text.

    Args:
        text: SAS code, a log, or any other free-text value.

    Returns:
        Tuple of (redacted text, number of redactions performed).
    """
    if not text:
        return text, 0

    count = 0

    def _assignment(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}{match.group(2)}{REDACTION_PLACEHOLDER}"

    def _macro(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}{REDACTION_PLACEHOLDER}"

    def _encoded(_match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return REDACTION_PLACEHOLDER

    redacted = _ASSIGNMENT.sub(_assignment, text)
    redacted = _MACRO_ASSIGN.sub(_macro, redacted)
    redacted = _ENCODED.sub(_encoded, redacted)
    return redacted, count


def is_sensitive_field(field_name: str) -> bool:
    """Return True if a dictionary key looks like it holds a credential."""
    lowered = field_name.lower()
    return any(pattern in lowered for pattern in SENSITIVE_FIELD_PATTERNS)


def redact(data: Any) -> tuple[Any, int]:
    """Deep-copy a parsed-output structure and redact credentials within it.

    Every string is scanned for the credential patterns above, and any value
    whose key is itself password-like is replaced outright.

    Args:
        data: Serialized parser output (dict, list, or scalar).

    Returns:
        Tuple of (redacted deep copy, total number of redactions).
    """
    redacted = copy.deepcopy(data)
    return redacted, _walk(redacted)


def _walk(obj: Any) -> int:
    if isinstance(obj, dict):
        return _walk_dict(obj)
    if isinstance(obj, list):
        return sum(_walk_item(obj, index) for index in range(len(obj)))
    return 0


def _walk_item(container: list[Any], index: int) -> int:
    value = container[index]
    if isinstance(value, str):
        container[index], count = redact_text(value)
        return count
    return _walk(value)


def _walk_dict(mapping: dict[str, Any]) -> int:
    count = 0
    for key, value in mapping.items():
        if isinstance(value, str):
            if is_sensitive_field(str(key)):
                if value != REDACTION_PLACEHOLDER:
                    mapping[key] = REDACTION_PLACEHOLDER
                    count += 1
            else:
                mapping[key], found = redact_text(value)
                count += found
        else:
            count += _walk(value)
    return count
