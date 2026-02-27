"""Tests for the emitter module."""

from __future__ import annotations

from typing import Any

import pytest

from aumai_toolcanon.emitter import (
    emit_anthropic,
    emit_json_schema,
    emit_mcp,
    emit_openai,
)
from aumai_toolcanon.models import (
    CanonicalTool,
)

# ---------------------------------------------------------------------------
# emit_openai
# ---------------------------------------------------------------------------


class TestEmitOpenAI:
    def test_top_level_structure(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_openai(canonical_search_tool)
        assert result["type"] == "function"
        assert "function" in result

    def test_function_has_name(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_openai(canonical_search_tool)
        assert result["function"]["name"] == "search_web"

    def test_function_has_description(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_openai(canonical_search_tool)
        assert "Search" in result["function"]["description"]

    def test_function_has_parameters(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_openai(canonical_search_tool)
        params = result["function"]["parameters"]
        assert "properties" in params

    def test_parameters_has_type_object(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_openai(canonical_search_tool)
        assert result["function"]["parameters"]["type"] == "object"

    def test_empty_inputs_produces_empty_object_schema(self) -> None:
        tool = CanonicalTool(name="no_params", inputs={})
        result = emit_openai(tool)
        params = result["function"]["parameters"]
        assert params["type"] == "object"
        assert params["properties"] == {}

    def test_inputs_without_type_gets_type_object_prepended(self) -> None:
        tool = CanonicalTool(
            name="implicit_type",
            inputs={"properties": {"x": {"type": "string"}}},
        )
        result = emit_openai(tool)
        assert result["function"]["parameters"]["type"] == "object"

    def test_inputs_with_existing_type_preserved(self) -> None:
        tool = CanonicalTool(
            name="explicit_type",
            inputs={"type": "object", "properties": {}},
        )
        result = emit_openai(tool)
        assert result["function"]["parameters"]["type"] == "object"

    def test_output_is_valid_dict(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_openai(canonical_search_tool)
        assert isinstance(result, dict)

    def test_required_field_preserved(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_openai(canonical_search_tool)
        assert "required" in result["function"]["parameters"]
        assert "query" in result["function"]["parameters"]["required"]


# ---------------------------------------------------------------------------
# emit_anthropic
# ---------------------------------------------------------------------------


class TestEmitAnthropic:
    def test_top_level_structure(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_anthropic(canonical_search_tool)
        assert "name" in result
        assert "description" in result
        assert "input_schema" in result

    def test_name_correct(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_anthropic(canonical_search_tool)
        assert result["name"] == "search_web"

    def test_description_correct(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_anthropic(canonical_search_tool)
        assert "Search" in result["description"]

    def test_input_schema_has_properties(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_anthropic(canonical_search_tool)
        assert "properties" in result["input_schema"]

    def test_input_schema_type_object(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_anthropic(canonical_search_tool)
        assert result["input_schema"]["type"] == "object"

    def test_empty_inputs_gives_empty_object_schema(self) -> None:
        tool = CanonicalTool(name="empty_inputs", inputs={})
        result = emit_anthropic(tool)
        assert result["input_schema"]["type"] == "object"
        assert result["input_schema"]["properties"] == {}

    def test_inputs_without_type_gets_type_object(self) -> None:
        tool = CanonicalTool(
            name="no_type",
            inputs={"properties": {"param": {"type": "string"}}},
        )
        result = emit_anthropic(tool)
        assert result["input_schema"]["type"] == "object"

    def test_no_type_key_in_top_level(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_anthropic(canonical_search_tool)
        assert "type" not in result

    def test_required_field_preserved(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_anthropic(canonical_search_tool)
        assert "required" in result["input_schema"]


# ---------------------------------------------------------------------------
# emit_mcp
# ---------------------------------------------------------------------------


class TestEmitMCP:
    def test_top_level_structure(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_mcp(canonical_search_tool)
        assert "name" in result
        assert "description" in result
        assert "inputSchema" in result

    def test_uses_camel_case_input_schema_key(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_mcp(canonical_search_tool)
        assert "inputSchema" in result
        assert "input_schema" not in result

    def test_name_correct(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_mcp(canonical_search_tool)
        assert result["name"] == "search_web"

    def test_input_schema_type_object(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_mcp(canonical_search_tool)
        assert result["inputSchema"]["type"] == "object"

    def test_empty_inputs_gives_empty_object_schema(self) -> None:
        tool = CanonicalTool(name="empty", inputs={})
        result = emit_mcp(tool)
        assert result["inputSchema"]["type"] == "object"
        assert result["inputSchema"]["properties"] == {}

    def test_inputs_without_type_gets_type_object(self) -> None:
        tool = CanonicalTool(
            name="notype",
            inputs={"properties": {"val": {"type": "boolean"}}},
        )
        result = emit_mcp(tool)
        assert result["inputSchema"]["type"] == "object"

    def test_no_type_key_in_top_level(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_mcp(canonical_search_tool)
        assert "type" not in result


# ---------------------------------------------------------------------------
# emit_json_schema
# ---------------------------------------------------------------------------


class TestEmitJSONSchema:
    def test_has_dollar_schema_key(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_json_schema(canonical_search_tool)
        assert "$schema" in result
        assert "json-schema.org" in result["$schema"]

    def test_title_set_to_tool_name(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_json_schema(canonical_search_tool)
        assert result["title"] == "search_web"

    def test_description_included(self, canonical_search_tool: CanonicalTool) -> None:
        result = emit_json_schema(canonical_search_tool)
        assert "Search" in result["description"]

    def test_properties_merged_from_inputs(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_json_schema(canonical_search_tool)
        assert "properties" in result

    def test_capabilities_extension_present(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_json_schema(canonical_search_tool)
        assert "x-capabilities" in result

    def test_capabilities_extension_has_expected_keys(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_json_schema(canonical_search_tool)
        cap = result["x-capabilities"]
        assert "action" in cap
        assert "domain" in cap
        assert "side_effects" in cap
        assert "idempotent" in cap
        assert "cost_estimate" in cap

    def test_capabilities_values_match_tool(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_json_schema(canonical_search_tool)
        cap = result["x-capabilities"]
        assert cap["action"] == canonical_search_tool.capabilities.action
        assert cap["domain"] == canonical_search_tool.capabilities.domain
        assert cap["side_effects"] == canonical_search_tool.capabilities.side_effects

    def test_security_extension_present_when_security_set(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_json_schema(canonical_search_tool)
        assert "x-security" in result

    def test_security_extension_absent_when_security_none(self) -> None:
        tool = CanonicalTool(name="no_security", security=None)
        result = emit_json_schema(tool)
        assert "x-security" not in result

    def test_security_extension_has_expected_keys(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_json_schema(canonical_search_tool)
        sec = result["x-security"]
        assert "required_permissions" in sec
        assert "data_classification" in sec
        assert "pii_handling" in sec

    def test_outputs_included_as_x_outputs(
        self, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emit_json_schema(canonical_search_tool)
        assert "x-outputs" in result
        assert "properties" in result["x-outputs"]

    def test_x_outputs_absent_when_outputs_empty(self) -> None:
        tool = CanonicalTool(name="no_output", outputs={})
        result = emit_json_schema(tool)
        assert "x-outputs" not in result

    def test_empty_inputs_still_produces_valid_schema(self) -> None:
        tool = CanonicalTool(name="empty_tool")
        result = emit_json_schema(tool)
        assert result["title"] == "empty_tool"
        assert "x-capabilities" in result


# ---------------------------------------------------------------------------
# Cross-format property tests
# ---------------------------------------------------------------------------


class TestEmitterSharedProperties:
    """Verify properties are consistent across all emitters."""

    @pytest.mark.parametrize(
        "emitter_fn,schema_key",
        [
            (emit_openai, "parameters"),
            (emit_anthropic, "input_schema"),
            (emit_mcp, "inputSchema"),
        ],
    )
    def test_name_consistent_across_formats(
        self,
        emitter_fn: Any,
        schema_key: str,
        canonical_write_tool: CanonicalTool,
    ) -> None:
        result = emitter_fn(canonical_write_tool)
        if schema_key == "parameters":
            assert result["function"]["name"] == "write_file"
        else:
            assert result["name"] == "write_file"

    @pytest.mark.parametrize(
        "emitter_fn",
        [emit_openai, emit_anthropic, emit_mcp, emit_json_schema],
    )
    def test_all_emitters_return_dict(
        self, emitter_fn: Any, canonical_search_tool: CanonicalTool
    ) -> None:
        result = emitter_fn(canonical_search_tool)
        assert isinstance(result, dict)

    def test_minimal_tool_can_be_emitted_to_all_formats(self) -> None:
        tool = CanonicalTool(name="minimal")
        assert isinstance(emit_openai(tool), dict)
        assert isinstance(emit_anthropic(tool), dict)
        assert isinstance(emit_mcp(tool), dict)
        assert isinstance(emit_json_schema(tool), dict)
