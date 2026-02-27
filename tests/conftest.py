"""Shared test fixtures for aumai-toolcanon."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aumai_toolcanon.models import (
    CanonicalTool,
    SourceFormat,
    ToolCapability,
    ToolSecurity,
)

# ---------------------------------------------------------------------------
# Raw format fixtures — one dict per format
# ---------------------------------------------------------------------------


@pytest.fixture()
def openai_wrapped_tool() -> dict[str, Any]:
    """OpenAI tool definition in the modern wrapped format."""
    return {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    }


@pytest.fixture()
def openai_legacy_tool() -> dict[str, Any]:
    """OpenAI tool in the legacy function-call format (no outer wrapper)."""
    return {
        "name": "get_weather",
        "description": "Get current weather for a location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["location"],
        },
    }


@pytest.fixture()
def anthropic_tool() -> dict[str, Any]:
    """Anthropic tool-use definition."""
    return {
        "name": "read_file",
        "description": "Read the contents of a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file."},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["path"],
        },
    }


@pytest.fixture()
def mcp_tool() -> dict[str, Any]:
    """MCP (Model Context Protocol) tool definition."""
    return {
        "name": "list_directory",
        "description": "List files in a directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
    }


@pytest.fixture()
def langchain_args_schema_tool() -> dict[str, Any]:
    """LangChain tool using args_schema (Pydantic model schema)."""
    return {
        "name": "send_email",
        "description": "Send an email to a recipient.",
        "args_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    }


@pytest.fixture()
def langchain_schema_tool() -> dict[str, Any]:
    """LangChain StructuredTool using schema key."""
    return {
        "name": "query_database",
        "description": "Execute a SQL query against the database.",
        "schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
                "params": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["sql"],
        },
    }


@pytest.fixture()
def langchain_direct_properties_tool() -> dict[str, Any]:
    """LangChain JSON schema format with properties at top level."""
    return {
        "name": "fetch_url",
        "description": "Fetch content from a URL.",
        "properties": {
            "url": {"type": "string"},
            "timeout": {"type": "integer", "default": 30},
        },
        "required": ["url"],
    }


@pytest.fixture()
def langchain_model_fields_tool() -> dict[str, Any]:
    """LangChain Pydantic v2 model_json_schema style with model_fields."""
    return {
        "name": "parse_document",
        "description": "Parse a document into structured data.",
        "args_schema": {
            "model_fields": {
                "content": {"is_required": True},
                "format": {"is_required": False},
            }
        },
    }


@pytest.fixture()
def raw_tool_with_name() -> dict[str, Any]:
    """Raw/unknown format with a name field."""
    return {
        "name": "mysterious_tool",
        "description": "A tool with no recognized format.",
        "some_custom_key": {"data": "value"},
    }


@pytest.fixture()
def raw_tool_no_name() -> dict[str, Any]:
    """Raw/unknown format with no name or description."""
    return {"some_custom_key": {"data": "value"}}


# ---------------------------------------------------------------------------
# CanonicalTool fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def canonical_search_tool() -> CanonicalTool:
    """A fully-specified CanonicalTool for a search operation."""
    return CanonicalTool(
        name="search_web",
        description="Search the web for current information.",
        capabilities=ToolCapability(
            action="search",
            domain="web",
            side_effects=False,
            idempotent=True,
            cost_estimate="low",
        ),
        inputs={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
        outputs={"type": "object", "properties": {"results": {"type": "array"}}},
        security=ToolSecurity(
            required_permissions=["internet"],
            data_classification="public",
            pii_handling="none",
        ),
        source_format=SourceFormat.openai,
    )


@pytest.fixture()
def canonical_write_tool() -> CanonicalTool:
    """A CanonicalTool for a write operation (has side effects)."""
    return CanonicalTool(
        name="write_file",
        description="Write content to a file.",
        capabilities=ToolCapability(
            action="write",
            domain="filesystem",
            side_effects=True,
            idempotent=False,
            cost_estimate="free",
        ),
        inputs={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        outputs={},
        source_format=SourceFormat.anthropic,
    )


@pytest.fixture()
def canonical_minimal_tool() -> CanonicalTool:
    """A CanonicalTool with only the required name field."""
    return CanonicalTool(name="bare_tool")


# ---------------------------------------------------------------------------
# File-based fixtures (write temp JSON files for CLI tests)
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_openai_json(tmp_path: Path, openai_wrapped_tool: dict[str, Any]) -> Path:
    """Write the OpenAI tool definition to a temp JSON file."""
    file_path = tmp_path / "openai_tool.json"
    file_path.write_text(json.dumps(openai_wrapped_tool), encoding="utf-8")
    return file_path


@pytest.fixture()
def tmp_anthropic_json(tmp_path: Path, anthropic_tool: dict[str, Any]) -> Path:
    """Write the Anthropic tool definition to a temp JSON file."""
    file_path = tmp_path / "anthropic_tool.json"
    file_path.write_text(json.dumps(anthropic_tool), encoding="utf-8")
    return file_path


@pytest.fixture()
def tmp_canonical_json(tmp_path: Path, canonical_search_tool: CanonicalTool) -> Path:
    """Write a CanonicalTool to a temp JSON file."""
    file_path = tmp_path / "canonical_tool.json"
    file_path.write_text(
        json.dumps(canonical_search_tool.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture()
def tmp_mcp_json(tmp_path: Path, mcp_tool: dict[str, Any]) -> Path:
    """Write the MCP tool definition to a temp JSON file."""
    file_path = tmp_path / "mcp_tool.json"
    file_path.write_text(json.dumps(mcp_tool), encoding="utf-8")
    return file_path
