"""Unit tests for the DNA parser module.

Covers:
1. Simple DNA XML with all fields populated
2. Double-encoded HTML entities (e.g., &amp;lt; -> <)
3. Recursive ParentDNA (nested 2+ levels deep)
4. Missing/absent optional fields -> None
5. Malformed XML -> ValueError
"""

from html import escape

import pytest

from pyegp_parser.parsers.dna_parser import DNADescriptor, decode_dna

# --- Test fixtures ---

SIMPLE_DNA_XML = """\
<DNA>
    <Type>SAS.Servers.ServerDef</Type>
    <Name>MyServer</Name>
    <Version>9.4</Version>
    <Assembly>SAS.Tasks.DataSources</Assembly>
    <Factory>SAS.Tasks.DataSources.DataSourceFactory</Factory>
    <ParentName>SASMain</ParentName>
    <DisplayName>WORK.MYTABLE</DisplayName>
    <DisplayPath>/servers/SASMain</DisplayPath>
    <Server>SASMain</Server>
    <Library>WORK</Library>
    <FullPath>C:\\Data\\myfile.sas7bdat</FullPath>
    <ReadOnly>True</ReadOnly>
    <Temp>False</Temp>
</DNA>"""

MINIMAL_DNA_XML = """\
<DNA>
    <Type>SAS.Servers.ServerDef</Type>
    <Name>TestServer</Name>
    <Version>1.0</Version>
</DNA>"""

NESTED_PARENT_DNA_XML = """\
<DNA>
    <Type>SAS.DataSources.DataSource</Type>
    <Name>Child</Name>
    <Version>1.0</Version>
    <Assembly>SAS.Tasks.DataSources</Assembly>
    <Factory>SAS.Tasks.DataSources.Factory</Factory>
    <Server>ChildServer</Server>
    <ParentDNA>&lt;DNA&gt;&lt;Type&gt;SAS.Servers.ServerDef&lt;/Type&gt;&lt;Name&gt;Parent&lt;/Name&gt;&lt;Version&gt;2.0&lt;/Version&gt;&lt;Server&gt;ParentServer&lt;/Server&gt;&lt;ParentDNA&gt;&amp;lt;DNA&amp;gt;&amp;lt;Type&amp;gt;SAS.Root&amp;lt;/Type&amp;gt;&amp;lt;Name&amp;gt;GrandParent&amp;lt;/Name&amp;gt;&amp;lt;Version&amp;gt;3.0&amp;lt;/Version&amp;gt;&amp;lt;/DNA&amp;gt;&lt;/ParentDNA&gt;&lt;/DNA&gt;</ParentDNA>
</DNA>"""


class TestDecodeDnaSimple:
    """Test decoding of well-formed DNA XML with all fields."""

    def test_all_fields_populated(self):
        result = decode_dna(SIMPLE_DNA_XML)

        assert result.type == "SAS.Servers.ServerDef"
        assert result.name == "MyServer"
        assert result.version == "9.4"
        assert result.assembly == "SAS.Tasks.DataSources"
        assert result.factory == "SAS.Tasks.DataSources.DataSourceFactory"
        assert result.parent_name == "SASMain"
        assert result.display_name == "WORK.MYTABLE"
        assert result.display_path == "/servers/SASMain"
        assert result.server == "SASMain"
        assert result.library == "WORK"
        assert result.full_path == "C:\\Data\\myfile.sas7bdat"
        assert result.read_only is True
        assert result.temp is False
        assert result.parent_dna is None

    def test_returns_dna_descriptor_type(self):
        result = decode_dna(SIMPLE_DNA_XML)
        assert isinstance(result, DNADescriptor)


class TestDecodeDnaDoubleEncoded:
    """Test handling of double-encoded HTML entities."""

    def test_single_html_encoding(self):
        """DNA that is HTML-escaped once (e.g., < becomes &lt;)."""
        encoded = escape(SIMPLE_DNA_XML)
        result = decode_dna(encoded)

        assert result.type == "SAS.Servers.ServerDef"
        assert result.name == "MyServer"
        assert result.version == "9.4"

    def test_double_html_encoding(self):
        """DNA that is HTML-escaped twice (e.g., &lt; becomes &amp;lt;)."""
        double_encoded = escape(escape(SIMPLE_DNA_XML))
        result = decode_dna(double_encoded)

        assert result.type == "SAS.Servers.ServerDef"
        assert result.name == "MyServer"
        assert result.version == "9.4"
        assert result.server == "SASMain"

    def test_already_decoded_xml(self):
        """DNA that is already valid XML (no encoding)."""
        result = decode_dna(SIMPLE_DNA_XML)
        assert result.type == "SAS.Servers.ServerDef"


class TestDecodeDnaRecursive:
    """Test recursive ParentDNA decoding."""

    def test_two_levels_deep(self):
        """ParentDNA contains another DNA with its own ParentDNA."""
        result = decode_dna(NESTED_PARENT_DNA_XML)

        # Top level
        assert result.type == "SAS.DataSources.DataSource"
        assert result.name == "Child"
        assert result.server == "ChildServer"

        # First parent
        assert result.parent_dna is not None
        parent = result.parent_dna
        assert parent.type == "SAS.Servers.ServerDef"
        assert parent.name == "Parent"
        assert parent.version == "2.0"
        assert parent.server == "ParentServer"

        # Grandparent
        assert parent.parent_dna is not None
        grandparent = parent.parent_dna
        assert grandparent.type == "SAS.Root"
        assert grandparent.name == "GrandParent"
        assert grandparent.version == "3.0"
        assert grandparent.parent_dna is None

    def test_single_parent_dna(self):
        """DNA with a single level of ParentDNA."""
        xml = """\
<DNA>
    <Type>SAS.DataSources.DataSource</Type>
    <Name>ChildDS</Name>
    <Version>1.0</Version>
    <ParentDNA>&lt;DNA&gt;&lt;Type&gt;SAS.Servers.ServerDef&lt;/Type&gt;&lt;Name&gt;ParentSrv&lt;/Name&gt;&lt;Version&gt;2.0&lt;/Version&gt;&lt;/DNA&gt;</ParentDNA>
</DNA>"""
        result = decode_dna(xml)

        assert result.name == "ChildDS"
        assert result.parent_dna is not None
        assert result.parent_dna.type == "SAS.Servers.ServerDef"
        assert result.parent_dna.name == "ParentSrv"
        assert result.parent_dna.version == "2.0"
        assert result.parent_dna.parent_dna is None


class TestDecodeDnaOptionalFields:
    """Test that missing/absent optional fields return None."""

    def test_minimal_dna(self):
        """Only required fields (Type, Name, Version) present."""
        result = decode_dna(MINIMAL_DNA_XML)

        assert result.type == "SAS.Servers.ServerDef"
        assert result.name == "TestServer"
        assert result.version == "1.0"
        assert result.assembly is None
        assert result.factory is None
        assert result.parent_name is None
        assert result.display_name is None
        assert result.display_path is None
        assert result.server is None
        assert result.library is None
        assert result.full_path is None
        assert result.read_only is None
        assert result.temp is None
        assert result.parent_dna is None

    def test_empty_element_text_treated_as_none(self):
        """Elements with empty text content are treated as absent."""
        xml = """\
<DNA>
    <Type>SAS.Test</Type>
    <Name>Test</Name>
    <Version>1.0</Version>
    <Server>  </Server>
    <Library></Library>
</DNA>"""
        result = decode_dna(xml)
        assert result.server is None
        assert result.library is None

    def test_empty_parent_dna_element(self):
        """ParentDNA element present but with no text content."""
        xml = """\
<DNA>
    <Type>SAS.Test</Type>
    <Name>Test</Name>
    <Version>1.0</Version>
    <ParentDNA></ParentDNA>
</DNA>"""
        result = decode_dna(xml)
        assert result.parent_dna is None


class TestDecodeDnaMalformed:
    """Test that malformed XML raises ValueError."""

    def test_completely_invalid_xml(self):
        with pytest.raises(ValueError, match="DNA XML cannot be parsed"):
            decode_dna("not xml at all { } < >")

    def test_unclosed_tags(self):
        with pytest.raises(ValueError, match="DNA XML cannot be parsed"):
            decode_dna("<DNA><Type>Unclosed")

    def test_empty_string(self):
        with pytest.raises((ValueError, Exception)):
            decode_dna("")

    def test_malformed_parent_dna(self):
        """ParentDNA text that cannot be parsed as XML raises ValueError."""
        xml = """\
<DNA>
    <Type>SAS.Test</Type>
    <Name>Test</Name>
    <Version>1.0</Version>
    <ParentDNA>not valid xml at all</ParentDNA>
</DNA>"""
        with pytest.raises(ValueError, match="DNA XML cannot be parsed"):
            decode_dna(xml)


class TestDecodeDnaBooleanParsing:
    """Test boolean field parsing edge cases."""

    def test_true_case_insensitive(self):
        xml = """\
<DNA>
    <Type>T</Type>
    <Name>N</Name>
    <Version>V</Version>
    <ReadOnly>TRUE</ReadOnly>
    <Temp>True</Temp>
</DNA>"""
        result = decode_dna(xml)
        assert result.read_only is True
        assert result.temp is True

    def test_false_values(self):
        xml = """\
<DNA>
    <Type>T</Type>
    <Name>N</Name>
    <Version>V</Version>
    <ReadOnly>False</ReadOnly>
    <Temp>false</Temp>
</DNA>"""
        result = decode_dna(xml)
        assert result.read_only is False
        assert result.temp is False

    def test_non_boolean_text_treated_as_false(self):
        """Non-'true' text in boolean fields is treated as False."""
        xml = """\
<DNA>
    <Type>T</Type>
    <Name>N</Name>
    <Version>V</Version>
    <ReadOnly>yes</ReadOnly>
</DNA>"""
        result = decode_dna(xml)
        assert result.read_only is False
