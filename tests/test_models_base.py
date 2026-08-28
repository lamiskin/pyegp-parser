"""Tests for pyegp_parser.models.base module."""

from dataclasses import fields

from pyegp_parser.models.base import ElementMetadata


class TestElementMetadataDefaults:
    """Verify all fields default to None or empty list per requirements 2.7, 5.3."""

    def test_all_optional_fields_default_to_none(self):
        """Creating ElementMetadata with no args produces all-None optional fields."""
        meta = ElementMetadata()
        assert meta.label is None
        assert meta.type is None
        assert meta.container is None
        assert meta.id is None
        assert meta.created_on is None
        assert meta.modified_on is None
        assert meta.modified_by is None
        assert meta.modified_by_eg_id is None
        assert meta.modified_by_eg_ver is None
        assert meta.has_serialization_error is None

    def test_input_ids_defaults_to_empty_list(self):
        """input_ids defaults to an empty list, not None."""
        meta = ElementMetadata()
        assert meta.input_ids == []
        assert isinstance(meta.input_ids, list)

    def test_input_ids_not_shared_across_instances(self):
        """Each instance gets its own input_ids list (no mutable default sharing)."""
        m1 = ElementMetadata()
        m2 = ElementMetadata()
        m1.input_ids.append("id-1")
        assert m2.input_ids == []


class TestElementMetadataConstruction:
    """Verify fields can be set via constructor."""

    def test_set_all_fields(self):
        meta = ElementMetadata(
            label="My Task",
            type="SAS.EG.ProjectElements.Query",
            container="container-123",
            id="element-456",
            created_on="2024-01-15T10:30:00",
            modified_on="2024-06-20T14:00:00",
            modified_by="John Doe",
            modified_by_eg_id="eg-user-789",
            modified_by_eg_ver="8.1",
            has_serialization_error=False,
            input_ids=["input-1", "input-2"],
        )
        assert meta.label == "My Task"
        assert meta.type == "SAS.EG.ProjectElements.Query"
        assert meta.container == "container-123"
        assert meta.id == "element-456"
        assert meta.created_on == "2024-01-15T10:30:00"
        assert meta.modified_on == "2024-06-20T14:00:00"
        assert meta.modified_by == "John Doe"
        assert meta.modified_by_eg_id == "eg-user-789"
        assert meta.modified_by_eg_ver == "8.1"
        assert meta.has_serialization_error is False
        assert meta.input_ids == ["input-1", "input-2"]

    def test_partial_construction(self):
        """Only set some fields; others remain None."""
        meta = ElementMetadata(label="Partial", id="abc-123")
        assert meta.label == "Partial"
        assert meta.id == "abc-123"
        assert meta.type is None
        assert meta.modified_by is None
        assert meta.input_ids == []


class TestElementMetadataFieldCount:
    """Verify the dataclass has exactly the expected fields per requirement 5.2."""

    def test_has_eleven_fields(self):
        """ElementMetadata must have 11 fields matching the standard metadata spec."""
        expected_names = {
            "label",
            "type",
            "container",
            "id",
            "created_on",
            "modified_on",
            "modified_by",
            "modified_by_eg_id",
            "modified_by_eg_ver",
            "has_serialization_error",
            "input_ids",
        }
        actual_names = {f.name for f in fields(ElementMetadata)}
        assert actual_names == expected_names
