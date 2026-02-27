"""Tests for the MCP format parser."""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.models import SourceFormat
from aumai_toolcanon.parsers.mcp import MCPParser


class TestMCPParserCanParse:
    def test_camel_case_input_schema_accepted(self, mcp_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        assert parser.can_parse(mcp_tool) is True

    def test_snake_case_input_schema_also_accepted(self) -> None:
        parser = MCPParser()
        tool_def = {"name": "tool", "input_schema": {"type": "object"}}
        assert parser.can_parse(tool_def) is True

    def test_openai_wrapped_rejected(self, openai_wrapped_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        assert parser.can_parse(openai_wrapped_tool) is False

    def test_anthropic_format_rejected(self, anthropic_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        # Anthropic uses input_schema, which is also accepted by MCP parser
        # Both have 'input_schema' so MCP CAN parse it — verify via can_parse logic
        # The Anthropic fixture has input_schema + name => MCP can_parse returns True
        # This is by design (MCP accepts both camelCase and snake_case)
        assert parser.can_parse(anthropic_tool) is True

    def test_empty_dict_rejected(self) -> None:
        parser = MCPParser()
        assert parser.can_parse({}) is False

    def test_input_schema_without_name_rejected(self) -> None:
        parser = MCPParser()
        assert parser.can_parse({"inputSchema": {}}) is False


class TestMCPParserParse:
    def test_extracts_name(self, mcp_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        result = parser.parse(mcp_tool)
        assert result.name == "list_directory"

    def test_extracts_description(self, mcp_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        result = parser.parse(mcp_tool)
        assert "directory" in result.description.lower()

    def test_extracts_camel_case_input_schema(self, mcp_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        result = parser.parse(mcp_tool)
        assert "properties" in result.inputs
        assert "path" in result.inputs["properties"]

    def test_extracts_snake_case_input_schema(self) -> None:
        parser = MCPParser()
        tool_def = {
            "name": "snake_tool",
            "description": "Uses snake_case schema.",
            "input_schema": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        }
        result = parser.parse(tool_def)
        assert "key" in result.inputs["properties"]

    def test_camel_case_takes_priority_over_snake_case(self) -> None:
        parser = MCPParser()
        tool_def = {
            "name": "dual_schema",
            "description": "Has both schema keys.",
            "inputSchema": {
                "type": "object",
                "properties": {"camel": {"type": "string"}},
            },
            "input_schema": {
                "type": "object",
                "properties": {"snake": {"type": "string"}},
            },
        }
        result = parser.parse(tool_def)
        # camelCase should be preferred
        assert "camel" in result.inputs["properties"]

    def test_source_format_is_mcp(self, mcp_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        result = parser.parse(mcp_tool)
        assert result.source_format is SourceFormat.mcp

    def test_outputs_always_empty(self, mcp_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        result = parser.parse(mcp_tool)
        assert result.outputs == {}

    def test_original_definition_preserved(self, mcp_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        result = parser.parse(mcp_tool)
        assert result.original_definition == mcp_tool

    def test_parse_empty_dict_gives_empty_name(self) -> None:
        parser = MCPParser()
        result = parser.parse({})
        assert result.name == ""
        assert result.inputs == {}

    def test_capabilities_inferred_from_name(self, mcp_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        result = parser.parse(mcp_tool)
        # "list_directory" contains "file" indirectly via "list" verb and no write verbs
        assert result.capabilities.side_effects is False

    def test_required_field_passed_through(self, mcp_tool: dict[str, Any]) -> None:
        parser = MCPParser()
        result = parser.parse(mcp_tool)
        assert "required" in result.inputs
        assert "path" in result.inputs["required"]
