"""Tests for Pydantic models in aumai_toolcanon.models."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from aumai_toolcanon.models import (
    CanonicalizationResult,
    CanonicalTool,
    SourceFormat,
    ToolCapability,
    ToolSecurity,
)

# ---------------------------------------------------------------------------
# SourceFormat enum
# ---------------------------------------------------------------------------


class TestSourceFormat:
    def test_all_expected_members_exist(self) -> None:
        members = {f.value for f in SourceFormat}
        assert members == {"openai", "anthropic", "mcp", "langchain", "raw"}

    def test_string_coercion(self) -> None:
        assert SourceFormat("openai") is SourceFormat.openai
        assert SourceFormat("mcp") is SourceFormat.mcp

    def test_invalid_member_raises(self) -> None:
        with pytest.raises(ValueError):
            SourceFormat("unknown_format")

    def test_is_str_subclass(self) -> None:
        # SourceFormat extends str, so format values are directly comparable
        assert SourceFormat.openai == "openai"


# ---------------------------------------------------------------------------
# ToolCapability model
# ---------------------------------------------------------------------------


class TestToolCapability:
    def test_defaults(self) -> None:
        cap = ToolCapability()
        assert cap.action == ""
        assert cap.domain == ""
        assert cap.side_effects is False
        assert cap.idempotent is True
        assert cap.cost_estimate == "unknown"

    def test_explicit_values(self) -> None:
        cap = ToolCapability(
            action="write",
            domain="filesystem",
            side_effects=True,
            idempotent=False,
            cost_estimate="free",
        )
        assert cap.action == "write"
        assert cap.domain == "filesystem"
        assert cap.side_effects is True
        assert cap.idempotent is False
        assert cap.cost_estimate == "free"

    def test_model_dump_roundtrip(self) -> None:
        cap = ToolCapability(action="read", domain="web")
        dumped = cap.model_dump()
        restored = ToolCapability(**dumped)
        assert restored == cap


# ---------------------------------------------------------------------------
# ToolSecurity model
# ---------------------------------------------------------------------------


class TestToolSecurity:
    def test_defaults(self) -> None:
        sec = ToolSecurity()
        assert sec.required_permissions == []
        assert sec.data_classification == "public"
        assert sec.pii_handling == "none"

    def test_explicit_values(self) -> None:
        sec = ToolSecurity(
            required_permissions=["read:files", "network"],
            data_classification="confidential",
            pii_handling="processes",
        )
        assert "read:files" in sec.required_permissions
        assert sec.data_classification == "confidential"
        assert sec.pii_handling == "processes"

    def test_permissions_list_is_independent_per_instance(self) -> None:
        sec_a = ToolSecurity()
        sec_b = ToolSecurity()
        sec_a.required_permissions.append("admin")
        assert sec_b.required_permissions == []


# ---------------------------------------------------------------------------
# CanonicalTool model
# ---------------------------------------------------------------------------


class TestCanonicalTool:
    def test_requires_name(self) -> None:
        with pytest.raises(ValidationError):
            CanonicalTool()  # type: ignore[call-arg]

    def test_minimal_construction(self) -> None:
        tool = CanonicalTool(name="my_tool")
        assert tool.name == "my_tool"
        assert tool.version == "1.0.0"
        assert tool.description == ""
        assert tool.security is None
        assert tool.source_format is SourceFormat.raw
        assert tool.inputs == {}
        assert tool.outputs == {}

    def test_full_construction(self) -> None:
        cap = ToolCapability(action="search", domain="web")
        sec = ToolSecurity(required_permissions=["internet"])
        tool = CanonicalTool(
            name="search_web",
            version="2.0.0",
            description="Web search tool.",
            capabilities=cap,
            inputs={"type": "object", "properties": {}},
            outputs={"type": "object"},
            security=sec,
            source_format=SourceFormat.openai,
            original_definition={"type": "function"},
        )
        assert tool.name == "search_web"
        assert tool.version == "2.0.0"
        assert tool.capabilities.action == "search"
        assert tool.security is not None
        assert "internet" in tool.security.required_permissions
        assert tool.source_format is SourceFormat.openai

    def test_model_dump_json_mode(self) -> None:
        tool = CanonicalTool(name="test_tool", source_format=SourceFormat.mcp)
        dumped: dict[str, Any] = tool.model_dump(mode="json")
        assert dumped["name"] == "test_tool"
        assert dumped["source_format"] == "mcp"

    def test_model_validate_roundtrip(self) -> None:
        tool = CanonicalTool(
            name="roundtrip_tool",
            description="Testing roundtrip.",
            source_format=SourceFormat.anthropic,
        )
        data = tool.model_dump(mode="json")
        restored = CanonicalTool.model_validate(data)
        assert restored.name == tool.name
        assert restored.description == tool.description
        assert restored.source_format is SourceFormat.anthropic

    def test_capabilities_defaults_applied(self) -> None:
        tool = CanonicalTool(name="t")
        assert isinstance(tool.capabilities, ToolCapability)

    def test_inputs_and_outputs_are_independent(self) -> None:
        tool_a = CanonicalTool(name="a")
        tool_b = CanonicalTool(name="b")
        tool_a.inputs["x"] = 1
        assert "x" not in tool_b.inputs

    def test_original_definition_stores_arbitrary_data(self) -> None:
        orig: dict[str, Any] = {"custom": True, "nested": {"a": 1}}
        tool = CanonicalTool(name="t", original_definition=orig)
        assert tool.original_definition["custom"] is True


# ---------------------------------------------------------------------------
# CanonicalizationResult model
# ---------------------------------------------------------------------------


class TestCanonicalizationResult:
    def test_construction(self) -> None:
        tool = CanonicalTool(name="result_tool")
        result = CanonicalizationResult(
            tool=tool,
            warnings=["Missing description."],
            source_format_detected=SourceFormat.openai,
        )
        assert result.tool.name == "result_tool"
        assert len(result.warnings) == 1
        assert result.source_format_detected is SourceFormat.openai

    def test_warnings_default_empty(self) -> None:
        tool = CanonicalTool(name="clean_tool")
        result = CanonicalizationResult(
            tool=tool,
            source_format_detected=SourceFormat.mcp,
        )
        assert result.warnings == []

    def test_warnings_list_is_independent(self) -> None:
        tool = CanonicalTool(name="t")
        res_a = CanonicalizationResult(
            tool=tool, source_format_detected=SourceFormat.raw
        )
        res_b = CanonicalizationResult(
            tool=tool, source_format_detected=SourceFormat.raw
        )
        res_a.warnings.append("warn")
        assert res_b.warnings == []
