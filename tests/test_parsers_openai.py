"""Tests for the OpenAI format parser."""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.models import SourceFormat
from aumai_toolcanon.parsers.openai import OpenAIParser, _infer_capabilities


class TestOpenAIParserCanParse:
    def test_wrapped_format_accepted(self, openai_wrapped_tool: dict[str, Any]) -> None:
        parser = OpenAIParser()
        assert parser.can_parse(openai_wrapped_tool) is True

    def test_legacy_format_accepted(self, openai_legacy_tool: dict[str, Any]) -> None:
        parser = OpenAIParser()
        assert parser.can_parse(openai_legacy_tool) is True

    def test_anthropic_format_rejected(self, anthropic_tool: dict[str, Any]) -> None:
        parser = OpenAIParser()
        assert parser.can_parse(anthropic_tool) is False

    def test_mcp_format_rejected(self, mcp_tool: dict[str, Any]) -> None:
        parser = OpenAIParser()
        assert parser.can_parse(mcp_tool) is False

    def test_empty_dict_rejected(self) -> None:
        parser = OpenAIParser()
        assert parser.can_parse({}) is False

    def test_type_function_without_function_key_rejected(self) -> None:
        parser = OpenAIParser()
        assert parser.can_parse({"type": "function"}) is False

    def test_name_without_parameters_rejected(self) -> None:
        parser = OpenAIParser()
        # name alone is not enough for legacy format detection
        assert parser.can_parse({"name": "tool_only"}) is False


class TestOpenAIParserParse:
    def test_parse_wrapped_format_extracts_name(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        parser = OpenAIParser()
        result = parser.parse(openai_wrapped_tool)
        assert result.name == "search_web"

    def test_parse_wrapped_format_extracts_description(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        parser = OpenAIParser()
        result = parser.parse(openai_wrapped_tool)
        assert "Search" in result.description

    def test_parse_wrapped_format_extracts_parameters(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        parser = OpenAIParser()
        result = parser.parse(openai_wrapped_tool)
        assert "properties" in result.inputs
        assert "query" in result.inputs["properties"]

    def test_parse_wrapped_format_source_format(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        parser = OpenAIParser()
        result = parser.parse(openai_wrapped_tool)
        assert result.source_format is SourceFormat.openai

    def test_parse_wrapped_stores_original_definition(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        parser = OpenAIParser()
        result = parser.parse(openai_wrapped_tool)
        assert result.original_definition == openai_wrapped_tool

    def test_parse_legacy_format(self, openai_legacy_tool: dict[str, Any]) -> None:
        parser = OpenAIParser()
        result = parser.parse(openai_legacy_tool)
        assert result.name == "get_weather"
        assert "location" in result.inputs.get("properties", {})

    def test_parse_empty_function_dict(self) -> None:
        parser = OpenAIParser()
        tool_def = {"type": "function", "function": {}}
        result = parser.parse(tool_def)
        assert result.name == ""
        assert result.description == ""
        assert result.inputs == {}

    def test_parse_missing_parameters_key_gives_empty_inputs(self) -> None:
        parser = OpenAIParser()
        tool_def = {"name": "no_params", "parameters": {}}
        result = parser.parse(tool_def)
        assert result.inputs == {}

    def test_parse_outputs_always_empty(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        parser = OpenAIParser()
        result = parser.parse(openai_wrapped_tool)
        assert result.outputs == {}


class TestInferCapabilities:
    def test_search_verb_gives_search_action(self) -> None:
        cap = _infer_capabilities("search_web", "Search the internet")
        assert cap.action == "search"
        assert cap.side_effects is False
        assert cap.idempotent is True

    def test_write_verb_gives_side_effects(self) -> None:
        cap = _infer_capabilities("write_file", "Write content to disk")
        assert cap.side_effects is True
        assert cap.idempotent is False

    def test_delete_verb_gives_side_effects(self) -> None:
        cap = _infer_capabilities("delete_record", "Delete a record")
        assert cap.side_effects is True

    def test_read_verb_no_side_effects(self) -> None:
        cap = _infer_capabilities("read_document", "Read file contents")
        assert cap.action == "read"
        assert cap.side_effects is False

    def test_file_keyword_gives_filesystem_domain(self) -> None:
        cap = _infer_capabilities("read_file", "Read a file")
        assert cap.domain == "filesystem"

    def test_web_keyword_gives_web_domain(self) -> None:
        cap = _infer_capabilities("fetch_web_page", "Fetch page from web")
        assert cap.domain == "web"

    def test_sql_keyword_gives_database_domain(self) -> None:
        cap = _infer_capabilities("run_sql", "Execute SQL query")
        assert cap.domain == "database"

    def test_http_keyword_gives_web_domain(self) -> None:
        cap = _infer_capabilities("make_http_call", "Make an HTTP request")
        assert cap.domain == "web"

    def test_unknown_text_gives_general_domain(self) -> None:
        cap = _infer_capabilities("mystery_tool", "Does something mysterious")
        assert cap.domain == "general"

    def test_cost_estimate_always_unknown(self) -> None:
        cap = _infer_capabilities("any_tool", "Any description")
        assert cap.cost_estimate == "unknown"

    def test_create_verb_gives_side_effects(self) -> None:
        cap = _infer_capabilities("create_record", "Creates a new record")
        assert cap.side_effects is True

    def test_get_verb_no_side_effects(self) -> None:
        cap = _infer_capabilities("get_user", "Gets a user object")
        assert cap.side_effects is False
        assert cap.action == "get"
