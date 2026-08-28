"""Property-based tests for DNA round-trip serialization.

**Validates: Requirements 3.4, 4.3**

Uses Hypothesis to generate random DNADescriptor trees with arbitrary nesting
depth (0 to ~3 levels). Serializes each to DNA XML format, then decodes back
using decode_dna() and verifies structural equivalence.
"""

import xml.etree.ElementTree as ET
from html import escape

from hypothesis import given, settings
from hypothesis import strategies as st

from pyegp_parser.parsers.dna_parser import DNADescriptor, decode_dna

# ---------------------------------------------------------------------------
# Strategies for generating DNADescriptor instances
# ---------------------------------------------------------------------------

# Safe XML text: printable characters that won't break XML parsing
# Excludes <, >, &, ", ', null bytes, and whitespace-only strings
_safe_xml_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Pd", "Pc"),
        blacklist_characters="<>&\"'\x00\r\n\t",
    ),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() != "")

# Optional safe XML text (None or a value)
_optional_text = st.one_of(st.none(), _safe_xml_text)

# Optional boolean
_optional_bool = st.one_of(st.none(), st.booleans())


@st.composite
def _dna_descriptor_strategy(draw, max_depth: int = 3) -> DNADescriptor:
    """Generate a random DNADescriptor with nesting up to max_depth levels.

    Required fields (type, name, version) always have non-empty string values.
    Optional fields may be None or valid string/bool values.
    parent_dna may be None or a recursively generated DNADescriptor.
    """
    # Required fields
    type_val = draw(_safe_xml_text)
    name_val = draw(_safe_xml_text)
    version_val = draw(_safe_xml_text)

    # Optional string fields
    assembly = draw(_optional_text)
    factory = draw(_optional_text)
    parent_name = draw(_optional_text)
    display_name = draw(_optional_text)
    display_path = draw(_optional_text)
    server = draw(_optional_text)
    library = draw(_optional_text)
    full_path = draw(_optional_text)

    # Optional boolean fields
    read_only = draw(_optional_bool)
    temp = draw(_optional_bool)

    # Recursive parent_dna (with decreasing depth)
    parent_dna = None
    if max_depth > 0:
        include_parent = draw(st.booleans())
        if include_parent:
            parent_dna = draw(_dna_descriptor_strategy(max_depth=max_depth - 1))

    return DNADescriptor(
        type=type_val,
        name=name_val,
        version=version_val,
        assembly=assembly,
        factory=factory,
        parent_name=parent_name,
        display_name=display_name,
        display_path=display_path,
        server=server,
        library=library,
        full_path=full_path,
        read_only=read_only,
        temp=temp,
        parent_dna=parent_dna,
    )


# ---------------------------------------------------------------------------
# Test-only serializer: DNADescriptor -> DNA XML string
# ---------------------------------------------------------------------------


def serialize_dna(descriptor: DNADescriptor) -> str:
    """Serialize a DNADescriptor to a valid DNA XML string.

    This is a test-only utility for round-trip verification.
    The ParentDNA field is serialized as HTML-escaped child DNA XML,
    matching the format used in real EGP files.
    """
    root = ET.Element("DNA")

    # Required fields
    _add_element(root, "Type", descriptor.type)
    _add_element(root, "Name", descriptor.name)
    _add_element(root, "Version", descriptor.version)

    # Optional string fields
    if descriptor.assembly is not None:
        _add_element(root, "Assembly", descriptor.assembly)
    if descriptor.factory is not None:
        _add_element(root, "Factory", descriptor.factory)
    if descriptor.parent_name is not None:
        _add_element(root, "ParentName", descriptor.parent_name)
    if descriptor.display_name is not None:
        _add_element(root, "DisplayName", descriptor.display_name)
    if descriptor.display_path is not None:
        _add_element(root, "DisplayPath", descriptor.display_path)
    if descriptor.server is not None:
        _add_element(root, "Server", descriptor.server)
    if descriptor.library is not None:
        _add_element(root, "Library", descriptor.library)
    if descriptor.full_path is not None:
        _add_element(root, "FullPath", descriptor.full_path)

    # Optional boolean fields
    if descriptor.read_only is not None:
        _add_element(root, "ReadOnly", str(descriptor.read_only))
    if descriptor.temp is not None:
        _add_element(root, "Temp", str(descriptor.temp))

    # Recursive ParentDNA: serialize child as HTML-escaped XML text
    if descriptor.parent_dna is not None:
        parent_xml = serialize_dna(descriptor.parent_dna)
        parent_elem = ET.SubElement(root, "ParentDNA")
        parent_elem.text = escape(parent_xml)

    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def _add_element(parent: ET.Element, tag: str, text: str) -> None:
    """Add a child element with text content."""
    child = ET.SubElement(parent, tag)
    child.text = text


# ---------------------------------------------------------------------------
# Structural equivalence comparison
# ---------------------------------------------------------------------------


def descriptors_equivalent(a: DNADescriptor, b: DNADescriptor) -> bool:
    """Check if two DNADescriptors are structurally equivalent.

    Compares all fields including recursive parent_dna.
    """
    if a.type != b.type:
        return False
    if a.name != b.name:
        return False
    if a.version != b.version:
        return False
    if a.assembly != b.assembly:
        return False
    if a.factory != b.factory:
        return False
    if a.parent_name != b.parent_name:
        return False
    if a.display_name != b.display_name:
        return False
    if a.display_path != b.display_path:
        return False
    if a.server != b.server:
        return False
    if a.library != b.library:
        return False
    if a.full_path != b.full_path:
        return False
    if a.read_only != b.read_only:
        return False
    if a.temp != b.temp:
        return False

    # Recursive parent check
    if a.parent_dna is None and b.parent_dna is None:
        return True
    if a.parent_dna is None or b.parent_dna is None:
        return False
    return descriptors_equivalent(a.parent_dna, b.parent_dna)


# ---------------------------------------------------------------------------
# Property 3: DNA Round-Trip
# ---------------------------------------------------------------------------


class TestDNARoundTrip:
    """**Validates: Requirements 3.4, 4.3**"""

    @given(descriptor=_dna_descriptor_strategy())
    @settings(max_examples=500)
    def test_serialize_then_decode_preserves_structure(self, descriptor: DNADescriptor):
        """Generate a random DNADescriptor, serialize to XML, decode back,
        and verify the decoded result is structurally equivalent to the original.

        This validates that decode_dna correctly handles:
        - All optional fields (present or absent)
        - Recursive ParentDNA nesting
        - HTML-escaped parent DNA content
        """
        # Serialize to XML
        xml_text = serialize_dna(descriptor)

        # Decode back
        decoded = decode_dna(xml_text)

        # Verify structural equivalence
        assert descriptors_equivalent(descriptor, decoded), (
            f"Round-trip failed.\n"
            f"Original: {descriptor}\n"
            f"Decoded:  {decoded}\n"
            f"XML:      {xml_text}"
        )

    @given(descriptor=_dna_descriptor_strategy(max_depth=0))
    @settings(max_examples=300)
    def test_flat_descriptor_round_trip(self, descriptor: DNADescriptor):
        """Flat descriptors (no parent_dna) round-trip correctly.

        This isolates the basic field serialization/deserialization from
        recursive nesting concerns.
        """
        xml_text = serialize_dna(descriptor)
        decoded = decode_dna(xml_text)

        assert decoded.type == descriptor.type
        assert decoded.name == descriptor.name
        assert decoded.version == descriptor.version
        assert decoded.assembly == descriptor.assembly
        assert decoded.factory == descriptor.factory
        assert decoded.parent_name == descriptor.parent_name
        assert decoded.display_name == descriptor.display_name
        assert decoded.display_path == descriptor.display_path
        assert decoded.server == descriptor.server
        assert decoded.library == descriptor.library
        assert decoded.full_path == descriptor.full_path
        assert decoded.read_only == descriptor.read_only
        assert decoded.temp == descriptor.temp
        assert decoded.parent_dna is None

    @given(descriptor=_dna_descriptor_strategy(max_depth=3))
    @settings(max_examples=300)
    def test_nesting_depth_preserved(self, descriptor: DNADescriptor):
        """The nesting depth of parent_dna is preserved through round-trip."""
        xml_text = serialize_dna(descriptor)
        decoded = decode_dna(xml_text)

        # Count nesting depth of original
        original_depth = _nesting_depth(descriptor)
        decoded_depth = _nesting_depth(decoded)

        assert original_depth == decoded_depth, (
            f"Nesting depth mismatch: original={original_depth}, "
            f"decoded={decoded_depth}"
        )


def _nesting_depth(descriptor: DNADescriptor) -> int:
    """Count the nesting depth of parent_dna chain (0 = no parent)."""
    depth = 0
    current = descriptor.parent_dna
    while current is not None:
        depth += 1
        current = current.parent_dna
    return depth
