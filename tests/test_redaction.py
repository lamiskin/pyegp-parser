"""Tests for best-effort credential redaction of SAS code and logs."""

import pytest

from pyegp_parser.redaction import (
    REDACTION_PLACEHOLDER,
    is_sensitive_field,
    redact,
    redact_text,
)


@pytest.mark.parametrize(
    "source",
    [
        "libname db oracle user=etluser password=hunter2 path=orcl;",
        "libname db oracle user=etluser password='hunter2' path=orcl;",
        'libname db oracle user=etluser password="hunter2" path=orcl;',
        "proc sql; connect to oracle (user=etluser pwd=hunter2 path=orcl);",
        "libname x sqlsvr user=etluser PW=hunter2;",
        "%let db_pwd = hunter2;",
    ],
)
def test_credentials_are_removed_from_sas_code(source):
    """The secret disappears and the placeholder takes its place."""
    redacted, count = redact_text(source)

    assert "hunter2" not in redacted
    assert REDACTION_PLACEHOLDER in redacted
    assert count >= 1


def test_encoded_passwords_are_redacted():
    """PWENCODE output is reversible, so it is treated as plaintext."""
    redacted, count = redact_text("libname db oracle password={SAS002}A1B2C3D4;")

    assert "{SAS002}" not in redacted
    assert "A1B2C3D4" not in redacted
    assert count == 1


def test_surrounding_code_is_preserved():
    """Only the credential is replaced; the statement stays readable."""
    redacted, _ = redact_text(
        "libname dw oracle user=etluser password=hunter2 path=prod;"
    )

    assert redacted == (
        f"libname dw oracle user=etluser password={REDACTION_PLACEHOLDER} path=prod;"
    )


@pytest.mark.parametrize(
    "source",
    [
        "select PASSWORD_HASH from users;",
        "data out; set in(keep=password_hash); run;",
        "/* the password policy is documented elsewhere */",
    ],
)
def test_schema_metadata_is_not_redacted(source):
    """A column *named* password is structure, not a secret."""
    redacted, count = redact_text(source)

    assert redacted == source
    assert count == 0


def test_redact_walks_nested_output():
    """Redaction reaches code buried in the serialized project structure."""
    data = {
        "tasks": [
            {
                "label": "Load",
                "code_content": "libname db oracle password=hunter2;",
                "log_content": "NOTE: libname db oracle password=hunter2;",
            }
        ]
    }

    redacted, count = redact(data)

    assert count == 2
    assert "hunter2" not in str(redacted)
    # The original is untouched — redact() deep-copies.
    assert "hunter2" in data["tasks"][0]["code_content"]


def test_password_named_keys_are_replaced_outright():
    """A value under a password-like key is removed regardless of its shape."""
    redacted, count = redact({"connection": {"password": "hunter2"}})

    assert redacted["connection"]["password"] == REDACTION_PLACEHOLDER
    assert count == 1


def test_is_sensitive_field():
    assert is_sensitive_field("password")
    assert is_sensitive_field("db_pwd")
    assert not is_sensitive_field("label")


def test_written_project_json_is_redacted(tmp_path, monkeypatch):
    """The wiring matters as much as the patterns: written output must be clean."""
    from pyegp_parser import serializer

    monkeypatch.setattr(
        serializer,
        "to_dict",
        lambda _project: {"code_content": "libname db oracle password=hunter2;"},
    )

    written = serializer.serialize_project(object(), tmp_path)

    assert "hunter2" not in written
    assert "hunter2" not in (tmp_path / "project.json").read_text(encoding="utf-8")
    assert REDACTION_PLACEHOLDER in written


def test_redaction_can_be_disabled_explicitly(tmp_path, monkeypatch):
    """Opting out is possible for callers who need byte-faithful code."""
    from pyegp_parser import serializer

    monkeypatch.setattr(
        serializer,
        "to_dict",
        lambda _project: {"code_content": "libname db oracle password=hunter2;"},
    )

    written = serializer.serialize_project(object(), tmp_path, redact=False)

    assert "hunter2" in written


def test_clean_code_is_returned_unchanged():
    """No credentials means no edits and no count."""
    source = "proc means data=sashelp.class; run;"

    redacted, count = redact_text(source)

    assert redacted == source
    assert count == 0
