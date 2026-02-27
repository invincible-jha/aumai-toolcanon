"""Round-trip tests: parse -> canonical -> emit correctness.

Each test verifies that tool definitions survive a full parse-emit cycle
with the critical fields (name, description, parameters) preserved.
"""

from __future__ import annotations

from typing import Any

import pytest

from aumai_toolcanon.core import Canonicalizer
from aumai_toolcanon.emitter import emit_anthropic, emit_mcp, emit_openai


class TestOpenAIRoundTrip:
    def test_wrapped_roundtrip_name(self, openai_wrapped_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_wrapped_tool)
        emitted = emit_openai(result.tool)
        assert emitted["function"]["name"] == openai_wrapped_tool["function"]["name"]

    def test_wrapped_roundtrip_description(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_wrapped_tool)
        emitted = emit_openai(result.tool)
        assert (
            emitted["function"]["description"]
            == openai_wrapped_tool["function"]["description"]
        )

    def test_wrapped_roundtrip_parameters_properties(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_wrapped_tool)
        emitted = emit_openai(result.tool)
        original_props = openai_wrapped_tool["function"]["parameters"]["properties"]
        emitted_props = emitted["function"]["parameters"]["properties"]
        assert set(original_props.keys()) == set(emitted_props.keys())

    def test_wrapped_roundtrip_type_preserved(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_wrapped_tool)
        emitted = emit_openai(result.tool)
        assert emitted["type"] == "function"

    def test_legacy_roundtrip_name(self, openai_legacy_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_legacy_tool)
        emitted = emit_openai(result.tool)
        assert emitted["function"]["name"] == openai_legacy_tool["name"]

    def test_legacy_roundtrip_required_preserved(
        self, openai_legacy_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_legacy_tool)
        emitted = emit_openai(result.tool)
        original_required = set(
            openai_legacy_tool["parameters"].get("required", [])
        )
        emitted_required = set(
            emitted["function"]["parameters"].get("required", [])
        )
        assert original_required == emitted_required


class TestAnthropicRoundTrip:
    def test_name_preserved(self, anthropic_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(anthropic_tool)
        emitted = emit_anthropic(result.tool)
        assert emitted["name"] == anthropic_tool["name"]

    def test_description_preserved(self, anthropic_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(anthropic_tool)
        emitted = emit_anthropic(result.tool)
        assert emitted["description"] == anthropic_tool["description"]

    def test_input_schema_properties_preserved(
        self, anthropic_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(anthropic_tool)
        emitted = emit_anthropic(result.tool)
        original_props = anthropic_tool["input_schema"]["properties"]
        emitted_props = emitted["input_schema"]["properties"]
        assert set(original_props.keys()) == set(emitted_props.keys())

    def test_required_preserved(self, anthropic_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(anthropic_tool)
        emitted = emit_anthropic(result.tool)
        assert set(emitted["input_schema"].get("required", [])) == set(
            anthropic_tool["input_schema"].get("required", [])
        )

    def test_openai_to_anthropic_cross_format(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_wrapped_tool)
        # Cross-format emit: OpenAI -> canonical -> Anthropic
        emitted = emit_anthropic(result.tool)
        assert emitted["name"] == openai_wrapped_tool["function"]["name"]
        assert "input_schema" in emitted


class TestMCPRoundTrip:
    def test_name_preserved(self, mcp_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(mcp_tool)
        emitted = emit_mcp(result.tool)
        assert emitted["name"] == mcp_tool["name"]

    def test_description_preserved(self, mcp_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(mcp_tool)
        emitted = emit_mcp(result.tool)
        assert emitted["description"] == mcp_tool["description"]

    def test_input_schema_properties_preserved(self, mcp_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(mcp_tool)
        emitted = emit_mcp(result.tool)
        original_props = mcp_tool["inputSchema"]["properties"]
        emitted_props = emitted["inputSchema"]["properties"]
        assert set(original_props.keys()) == set(emitted_props.keys())

    def test_camel_case_key_in_output(self, mcp_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(mcp_tool)
        emitted = emit_mcp(result.tool)
        assert "inputSchema" in emitted
        assert "input_schema" not in emitted

    def test_anthropic_to_mcp_cross_format(
        self, anthropic_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(anthropic_tool)
        emitted = emit_mcp(result.tool)
        assert emitted["name"] == anthropic_tool["name"]
        assert "inputSchema" in emitted


class TestLangChainRoundTrip:
    def test_name_preserved_args_schema(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(langchain_args_schema_tool)
        emitted = emit_openai(result.tool)
        assert emitted["function"]["name"] == langchain_args_schema_tool["name"]

    def test_properties_preserved_args_schema(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(langchain_args_schema_tool)
        emitted = emit_openai(result.tool)
        original_props = langchain_args_schema_tool["args_schema"]["properties"]
        emitted_props = emitted["function"]["parameters"]["properties"]
        assert set(original_props.keys()) == set(emitted_props.keys())

    def test_langchain_to_anthropic_cross_format(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(langchain_args_schema_tool)
        emitted = emit_anthropic(result.tool)
        assert emitted["name"] == langchain_args_schema_tool["name"]
        assert "input_schema" in emitted


class TestMultiFormatCrossEmission:
    """Verify that any input format can be emitted to any output format."""

    @pytest.mark.parametrize(
        "input_fixture_name",
        [
            "openai_wrapped_tool",
            "openai_legacy_tool",
            "anthropic_tool",
            "mcp_tool",
            "langchain_args_schema_tool",
        ],
    )
    def test_any_input_emits_openai(
        self, request: pytest.FixtureRequest, input_fixture_name: str
    ) -> None:
        tool_def = request.getfixturevalue(input_fixture_name)
        canon = Canonicalizer()
        result = canon.canonicalize(tool_def)
        emitted = emit_openai(result.tool)
        assert emitted["type"] == "function"
        assert "function" in emitted

    @pytest.mark.parametrize(
        "input_fixture_name",
        [
            "openai_wrapped_tool",
            "anthropic_tool",
            "mcp_tool",
            "langchain_args_schema_tool",
        ],
    )
    def test_any_input_emits_anthropic(
        self, request: pytest.FixtureRequest, input_fixture_name: str
    ) -> None:
        tool_def = request.getfixturevalue(input_fixture_name)
        canon = Canonicalizer()
        result = canon.canonicalize(tool_def)
        emitted = emit_anthropic(result.tool)
        assert "input_schema" in emitted

    @pytest.mark.parametrize(
        "input_fixture_name",
        [
            "openai_wrapped_tool",
            "anthropic_tool",
            "mcp_tool",
            "langchain_schema_tool",
        ],
    )
    def test_any_input_emits_mcp(
        self, request: pytest.FixtureRequest, input_fixture_name: str
    ) -> None:
        tool_def = request.getfixturevalue(input_fixture_name)
        canon = Canonicalizer()
        result = canon.canonicalize(tool_def)
        emitted = emit_mcp(result.tool)
        assert "inputSchema" in emitted
