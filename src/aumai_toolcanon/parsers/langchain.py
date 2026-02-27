"""Parser for LangChain tool format.

LangChain tool schema formats:
1. BaseTool subclass representation:
   {"name": ..., "description": ..., "args_schema": {"properties": {...}}}

2. StructuredTool representation:
   {"name": ..., "description": ..., "schema": {"properties": {...}}}

3. JSON schema from tool.schema():
   {"title": ..., "description": ..., "properties": {...}, "type": "object"}
"""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.models import CanonicalTool, SourceFormat
from aumai_toolcanon.parsers.openai import _infer_capabilities


class LangChainParser:
    """Parse LangChain tool definitions into CanonicalTool."""

    def parse(self, tool_def: dict[str, Any]) -> CanonicalTool:
        """Parse a LangChain tool definition dict."""
        name: str = tool_def.get("name", tool_def.get("title", ""))
        description: str = tool_def.get("description", "")

        # Try to extract parameter schema from various LangChain representations
        inputs: dict[str, Any] = {}

        if "args_schema" in tool_def:
            # Pydantic model schema dumped as dict
            schema = tool_def["args_schema"]
            inputs = self._extract_schema(schema)
        elif "schema" in tool_def:
            inputs = self._extract_schema(tool_def["schema"])
        elif "parameters" in tool_def:
            inputs = tool_def["parameters"]
        elif "properties" in tool_def:
            # Direct JSON Schema object
            inputs = {
                "type": "object",
                "properties": tool_def["properties"],
                "required": tool_def.get("required", []),
            }

        capabilities = _infer_capabilities(name, description)

        return CanonicalTool(
            name=name,
            description=description,
            capabilities=capabilities,
            inputs=inputs,
            outputs={},
            source_format=SourceFormat.langchain,
            original_definition=tool_def,
        )

    def _extract_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Normalize a Pydantic/JSON schema to a JSON Schema object."""
        if schema.get("type") == "object" or "properties" in schema:
            return {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            }
        # Pydantic v2 model_json_schema format
        if "model_fields" in schema:
            properties: dict[str, Any] = {}
            required: list[str] = []
            for field_name, field_info in schema["model_fields"].items():
                properties[field_name] = {"type": "string"}  # conservative default
                if field_info.get("is_required", True):
                    required.append(field_name)
            return {"type": "object", "properties": properties, "required": required}

        return schema

    def can_parse(self, tool_def: dict[str, Any]) -> bool:
        """Return True if this dict looks like a LangChain tool definition."""
        return (
            "args_schema" in tool_def
            or "schema" in tool_def
            or (
                "name" in tool_def
                and "description" in tool_def
                and "properties" in tool_def
            )
        )


__all__ = ["LangChainParser"]
