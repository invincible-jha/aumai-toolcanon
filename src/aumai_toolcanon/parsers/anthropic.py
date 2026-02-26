"""Parser for Anthropic tool use format."""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.models import CanonicalTool, SourceFormat
from aumai_toolcanon.parsers.openai import _infer_capabilities


class AnthropicParser:
    """Parse Anthropic tool definitions into CanonicalTool."""

    def parse(self, tool_def: dict[str, Any]) -> CanonicalTool:
        """Parse Anthropic tool definition.

        Expected format:
        ``{"name": ..., "description": ..., "input_schema": {...}}``
        """
        name: str = tool_def.get("name", "")
        description: str = tool_def.get("description", "")
        input_schema: dict[str, Any] = tool_def.get("input_schema", {})

        capabilities = _infer_capabilities(name, description)

        return CanonicalTool(
            name=name,
            description=description,
            capabilities=capabilities,
            inputs=input_schema,
            outputs={},
            source_format=SourceFormat.anthropic,
            original_definition=tool_def,
        )

    def can_parse(self, tool_def: dict[str, Any]) -> bool:
        """Return True if this dict looks like an Anthropic tool definition."""
        return "input_schema" in tool_def and "name" in tool_def


__all__ = ["AnthropicParser"]
