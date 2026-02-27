"""Tests for the Anthropic format parser."""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.models import SourceFormat
from aumai_toolcanon.parsers.anthropic import AnthropicParser


class TestAnthropicParserCanParse:
    def test_standard_format_accepted(self, anthropic_tool: dict[str, Any]) -> None:
        parser = AnthropicParser()
        assert parser.can_parse(anthropic_tool) is True

    def test_openai_wrapped_rejected(self, openai_wrapped_tool: dict[str, Any]) -> None:
        parser = AnthropicParser()
        assert parser.can_parse(openai_wrapped_tool) is False

    def test_mcp_format_rejected(self, mcp_tool: dict[str, Any]) -> None:
        parser = AnthropicParser()
        # MCP uses inputSchema (camelCase), not input_schema
        assert parser.can_parse(mcp_tool) is False

    def test_empty_dict_rejected(self) -> None:
        parser = AnthropicParser()
        assert parser.can_parse({}) is False

    def test_input_schema_without_name_rejected(self) -> None:
        parser = AnthropicParser()
        assert parser.can_parse({"input_schema": {}}) is False

    def test_name_without_input_schema_rejected(self) -> None:
        parser = AnthropicParser()
        assert parser.can_parse({"name": "tool"}) is False


class TestAnthropicParserParse:
    def test_extracts_name(self, anthropic_tool: dict[str, Any]) -> None:
        parser = AnthropicParser()
        result = parser.parse(anthropic_tool)
        assert result.name == "read_file"

    def test_extracts_description(self, anthropic_tool: dict[str, Any]) -> None:
        parser = AnthropicParser()
        result = parser.parse(anthropic_tool)
        assert (
            "filesystem" in result.description.lower()
            or "file" in result.description.lower()
        )

    def test_extracts_input_schema(self, anthropic_tool: dict[str, Any]) -> None:
        parser = AnthropicParser()
        result = parser.parse(anthropic_tool)
        assert "properties" in result.inputs
        assert "path" in result.inputs["properties"]

    def test_source_format_is_anthropic(self, anthropic_tool: dict[str, Any]) -> None:
        parser = AnthropicParser()
        result = parser.parse(anthropic_tool)
        assert result.source_format is SourceFormat.anthropic

    def test_outputs_always_empty(self, anthropic_tool: dict[str, Any]) -> None:
        parser = AnthropicParser()
        result = parser.parse(anthropic_tool)
        assert result.outputs == {}

    def test_original_definition_preserved(
        self, anthropic_tool: dict[str, Any]
    ) -> None:
        parser = AnthropicParser()
        result = parser.parse(anthropic_tool)
        assert result.original_definition == anthropic_tool

    def test_parse_empty_dict_gives_empty_name_and_inputs(self) -> None:
        parser = AnthropicParser()
        result = parser.parse({})
        assert result.name == ""
        assert result.inputs == {}

    def test_capabilities_inferred_for_read_tool(
        self, anthropic_tool: dict[str, Any]
    ) -> None:
        parser = AnthropicParser()
        result = parser.parse(anthropic_tool)
        # "read_file" should produce filesystem domain and no side effects
        assert result.capabilities.domain == "filesystem"
        assert result.capabilities.side_effects is False

    def test_parse_tool_with_write_in_name(self) -> None:
        parser = AnthropicParser()
        tool_def = {
            "name": "write_data",
            "description": "Write data to storage.",
            "input_schema": {"type": "object", "properties": {}},
        }
        result = parser.parse(tool_def)
        assert result.capabilities.side_effects is True

    def test_parse_tool_missing_input_schema(self) -> None:
        parser = AnthropicParser()
        tool_def = {"name": "no_schema_tool", "description": "A tool."}
        result = parser.parse(tool_def)
        assert result.inputs == {}

    def test_required_field_passed_through(
        self, anthropic_tool: dict[str, Any]
    ) -> None:
        parser = AnthropicParser()
        result = parser.parse(anthropic_tool)
        assert "required" in result.inputs
        assert "path" in result.inputs["required"]
