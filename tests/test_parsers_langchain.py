"""Tests for the LangChain format parser."""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.models import SourceFormat
from aumai_toolcanon.parsers.langchain import LangChainParser


class TestLangChainParserCanParse:
    def test_args_schema_format_accepted(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        assert parser.can_parse(langchain_args_schema_tool) is True

    def test_schema_format_accepted(
        self, langchain_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        assert parser.can_parse(langchain_schema_tool) is True

    def test_direct_properties_format_accepted(
        self, langchain_direct_properties_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        assert parser.can_parse(langchain_direct_properties_tool) is True

    def test_openai_wrapped_rejected(self, openai_wrapped_tool: dict[str, Any]) -> None:
        parser = LangChainParser()
        assert parser.can_parse(openai_wrapped_tool) is False

    def test_empty_dict_rejected(self) -> None:
        parser = LangChainParser()
        assert parser.can_parse({}) is False

    def test_name_and_description_only_rejected(self) -> None:
        parser = LangChainParser()
        # No args_schema, schema, or properties key
        assert parser.can_parse({"name": "tool", "description": "A tool."}) is False


class TestLangChainParserParseArgsSchema:
    def test_extracts_name(self, langchain_args_schema_tool: dict[str, Any]) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_args_schema_tool)
        assert result.name == "send_email"

    def test_extracts_description(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_args_schema_tool)
        assert "email" in result.description.lower()

    def test_extracts_properties_from_args_schema(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_args_schema_tool)
        props = result.inputs.get("properties", {})
        assert "to" in props
        assert "subject" in props
        assert "body" in props

    def test_required_preserved_from_args_schema(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_args_schema_tool)
        assert "required" in result.inputs
        assert set(result.inputs["required"]) == {"to", "subject", "body"}

    def test_source_format_is_langchain(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_args_schema_tool)
        assert result.source_format is SourceFormat.langchain

    def test_inputs_type_is_object(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_args_schema_tool)
        assert result.inputs.get("type") == "object"

    def test_side_effects_inferred_for_send_email(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_args_schema_tool)
        assert result.capabilities.side_effects is True


class TestLangChainParserParseSchemaKey:
    def test_extracts_name_from_schema_tool(
        self, langchain_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_schema_tool)
        assert result.name == "query_database"

    def test_extracts_properties_from_schema_key(
        self, langchain_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_schema_tool)
        props = result.inputs.get("properties", {})
        assert "sql" in props

    def test_required_preserved_from_schema_key(
        self, langchain_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_schema_tool)
        assert "sql" in result.inputs.get("required", [])


class TestLangChainParserParseDirectProperties:
    def test_extracts_name_from_title_fallback(self) -> None:
        parser = LangChainParser()
        tool_def = {
            "title": "titled_tool",
            "description": "Uses title as name.",
            "args_schema": {"type": "object", "properties": {}},
        }
        result = parser.parse(tool_def)
        # name key takes priority; title is fallback
        assert result.name == "titled_tool"

    def test_extracts_properties_from_direct_properties(
        self, langchain_direct_properties_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_direct_properties_tool)
        assert "url" in result.inputs.get("properties", {})

    def test_required_preserved_from_direct_properties(
        self, langchain_direct_properties_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_direct_properties_tool)
        assert "url" in result.inputs.get("required", [])

    def test_inputs_type_object_set_for_direct_properties(
        self, langchain_direct_properties_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_direct_properties_tool)
        assert result.inputs.get("type") == "object"


class TestLangChainParserParseModelFields:
    def test_model_fields_format_produces_properties(
        self, langchain_model_fields_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_model_fields_tool)
        props = result.inputs.get("properties", {})
        assert "content" in props
        assert "format" in props

    def test_model_fields_required_respected(
        self, langchain_model_fields_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_model_fields_tool)
        required = result.inputs.get("required", [])
        # content has is_required=True, format has is_required=False
        assert "content" in required
        assert "format" not in required


class TestLangChainParserMiscellaneous:
    def test_parse_empty_dict(self) -> None:
        parser = LangChainParser()
        result = parser.parse({})
        assert result.name == ""
        assert result.inputs == {}
        assert result.source_format is SourceFormat.langchain

    def test_original_definition_preserved(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_args_schema_tool)
        assert result.original_definition == langchain_args_schema_tool

    def test_outputs_always_empty(self, langchain_schema_tool: dict[str, Any]) -> None:
        parser = LangChainParser()
        result = parser.parse(langchain_schema_tool)
        assert result.outputs == {}

    def test_extract_schema_with_no_type_or_properties(self) -> None:
        parser = LangChainParser()
        # A schema that has neither 'type': 'object' nor 'properties'
        tool_def = {
            "name": "passthrough_tool",
            "description": "Raw schema passthrough.",
            "args_schema": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
        }
        result = parser.parse(tool_def)
        # Should passthrough the schema as-is
        assert "anyOf" in result.inputs

    def test_parameters_key_used_when_present(self) -> None:
        parser = LangChainParser()
        tool_def = {
            "name": "param_tool",
            "description": "Tool with parameters key.",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "integer"}},
            },
        }
        result = parser.parse(tool_def)
        assert "x" in result.inputs.get("properties", {})
